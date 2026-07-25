"""
The analysis pipeline: pitch deck PDF -> four Claude API calls -> report data.

Each call uses structured outputs, so the model returns validated JSON matching
one slice of the `report_template` contract instead of prose we would have to
parse. The deck rides along as a cached document block in every call, so only
the first request pays full price for it.

Public entry point: `analyze_deck(pdf_path, company_name, progress=...)` returns
the populated report data; `run_analysis(...)` also writes the .docx.
"""

from __future__ import annotations

import base64
import json
from datetime import date
from pathlib import Path
from typing import Any, Callable

import anthropic

from report_template import (
    CONVICTION_STAGES,
    DECK_SECTIONS,
    DESIGN_DIMENSIONS,
    MAX_STAGE_SCORE,
    MAX_TOTAL_SCORE,
    MAX_VALIDATION_SCORE,
    PLACEHOLDER,
    blank_report_data,
    build_report,
    validate_report_data,
)
from schemas import (
    CONVICTION_SCHEMA,
    DECK_SCHEMA,
    READINESS_SCHEMA,
    VALIDATION_SCHEMA,
)

MODEL = "claude-opus-5"
MAX_TOKENS = 32000  # streamed, so no HTTP-timeout concern
EFFORT = "high"
MAX_PDF_BYTES = 32 * 1024 * 1024  # API limit on a base64 document block

# The one business rule that is not a document-structure concern: how the total
# score maps to the band printed on the title-page banner. Edit thresholds here.
CONVICTION_BANDS: list[tuple[int, str]] = [
    (45, "High Conviction | Ready for Partner Meeting"),
    (38, "Qualified | Standard Diligence"),
    (30, "Developing | Targeted Diligence Required"),
    (22, "Early-Stage | Additional Diligence Required"),
    (0, "Pre-Qualified | Material Gaps Outstanding"),
]

PROGRESS_STEPS = [
    "Reading the deck",
    "Section 1 — Data readiness",
    "Section 2 — Conviction ladder",
    "Section 2B — Deck analysis",
    "Section 3 — Validation check",
    "Building the document",
]


class AnalysisError(RuntimeError):
    """Raised when the pipeline cannot produce a usable report."""


# --- Prompt fragments ---------------------------------------------------------


def _stage_catalogue() -> str:
    lines = []
    for stage in CONVICTION_STAGES:
        lines.append(f"Stage {stage['number']} — {stage['name']}")
        for point in stage["data_points"]:
            lines.append(f"  - {point}")
    return "\n".join(lines)


READINESS_PROMPT = f"""\
You are a pre-analysis data readiness reviewer for the TEN Capital Investor Conviction Ladder framework.

The attached pitch deck is the only source. Produce a DATA READINESS REPORT identifying what
information is present, partial, or missing for each of the ten conviction stages.

CONVICTION LADDER STAGES AND REQUIRED DATA POINTS:

{_stage_catalogue()}

RULES:
- Return one `stage_breakdown` entry per stage, in the order above, with one item per required
  data point. Copy each `data_point` string verbatim from the list above — do not reword, merge,
  split, or add data points.
- Status is PRESENT (clearly addressed), PARTIAL (touched on but incomplete or unsourced), or
  MISSING (not found anywhere in the deck). A data point that is present but unsourced is PARTIAL.
- Every `note` must be one line and must cite the slide, section, or claim that justifies the
  status — or state plainly that the item does not appear anywhere in the deck.
- `readiness` per stage: GREEN = all data points present; AMBER = gaps exist but the core is
  present; RED = critical gaps that materially impair scoring accuracy.
- `critical_gaps` (P1) are only the missing items that would prevent accurate scoring of that
  stage. `high_priority_gaps` (P2) materially reduce scoring accuracy without fully blocking it.
  In both, `stage` is a short label like "Stage 5" and `item` is one line.
- `readiness_recommendation`: state whether the deck is ready for full conviction analysis now,
  or what minimum additions are needed first.
- Base every assessment solely on the deck. Do not infer or assume data that is not shown.
"""


CONVICTION_PROMPT = f"""\
You are a venture investor at TEN Capital scoring the attached pitch deck against the Investor
Conviction Ladder. Each of the ten stages scores 1–5, for a maximum of {MAX_TOTAL_SCORE}.

CONVICTION LADDER STAGES AND THE DATA POINTS THAT DRIVE EACH SCORE:

{_stage_catalogue()}

SCORING GUIDE:
5 — every data point present, sourced, and compelling.
4 — strong, with one minor gap or unsourced claim.
3 — credible but with meaningful gaps; an investor could not fully validate the stage.
2 — substantially incomplete; several required data points absent.
1 — the stage is effectively unaddressed in the deck.

A DATA READINESS REVIEW of the same deck is provided below. Use it as evidence — a stage whose
required data points are largely MISSING cannot score above 2.

{{readiness_digest}}

RULES:
- Return exactly one `score_summary` row and one `stage_narratives` entry per stage, numbered 1–10.
- `name` must be the stage name exactly as listed above.
- Each narrative is one paragraph of 100–200 words that cites specific slides, figures, names, and
  claims from the deck, states plainly what earned the score, and states what held it back.
- Do not invent data. If something is absent from the deck, say it is absent.
- `score_commentary`: two to four sentences on the total, the strongest stages, and the weakest.
"""


DECK_PROMPT = f"""\
You are reviewing the attached investor pitch deck for structure, narrative, and design — a
section-by-section assessment of what is working, what is hurting investor perception, and what
specifically to change.

RULES:
- Return exactly one `section_assessment` row for each of these deck sections, in this order:
  {", ".join(DECK_SECTIONS)}.
  If a section is absent from the deck, say so in `strengths` (e.g. "N/A — not present in the
  deck") and treat its absence as the weakness.
- `strengths`, `weaknesses`, and `recommendations` are each two to four sentences. Recommendations
  must be concrete and actionable — name the slide to add, the data to cite, or the language to
  use, including example wording where it helps.
- Return exactly one `design_recommendations` entry for each of these labels, in this order:
  {", ".join(DESIGN_DIMENSIONS)}. Each `text` is two to four sentences on that dimension as it
  applies to this deck specifically.
- `revised_outline`: a proposed slide-by-slide running order optimizing the investor narrative,
  numbered from 1. One line of content per slide. Aim for 14–18 slides.
- Cite what is actually in the deck. Where you draw on outside market knowledge (for example
  naming competitors that do not appear in the deck), make that explicit in the text.
"""


VALIDATION_PROMPT = f"""\
You are a hallucination auditor. Validate the AI-generated analysis below against its only source —
the attached pitch deck — and score it from 1 to {MAX_VALIDATION_SCORE}, where {MAX_VALIDATION_SCORE}
means fully grounded in the source with no hallucinated content and 1 means predominantly fabricated.

HALLUCINATION TYPES: Fabricated Facts; False Citations; Unsupported Inferences; Misquoted or
Distorted Data; Invented Gaps; Scope Creep; Tone/Framing Distortion. Use CLEAN when a claim is
fully supported.

SCORING RUBRIC (abbreviated):
10 — every claim directly traceable to the deck. 9 — one or two minor unsupported inferences.
8 — a few unsupported inferences, figures accurate. 7 — several inferences or one scope-creep item.
6 — inference-as-fact pattern, one or two distorted figures. 5 — multiple unsupported claims.
4 — significant fabricated detail. 3 — core conclusions unsupportable. 2 — mostly fabricated.
1 — bears little relationship to the source.

RULES:
- Check every factual claim, figure, name, and citation in the analysis against the deck.
- `inventory`: one row per checked claim, quoting or closely paraphrasing it, with the hallucination
  type, a verdict of SUPPORTED / DISTORTED / UNSUPPORTED / FABRICATED / FLAG, and a `source_check`
  citing the slide that supports or refutes it. Cover the quantitative claims, named people and
  organizations, and the notable MISSING calls. Aim for 20–30 rows.
- Do not credit claims that are generally true but not traceable to this deck.
- Hedged language that accurately signals an inference is not a fabrication — flag it as an
  inference, not a fabrication.
- Score conservatively: when in doubt whether a claim is supported, treat it as unsupported.
- `clean_claims`: state the count and percentage of fully supported claims.
- `flags`: claims a human reviewer should verify manually, one per entry.
- `summary`: two to three sentences on reliability and whether the analysis can be used as-is,
  used with caveats, or should be regenerated.
- Judge only whether the analysis is grounded in the deck — not whether its conclusions are correct.

--- ANALYSIS UNDER REVIEW ---
{{analysis_digest}}
"""


# --- API plumbing -------------------------------------------------------------


def _pdf_block(pdf_bytes: bytes) -> dict:
    """The deck as a cached document block — identical prefix across all calls."""
    return {
        "type": "document",
        "source": {
            "type": "base64",
            "media_type": "application/pdf",
            "data": base64.standard_b64encode(pdf_bytes).decode("utf-8"),
        },
        "cache_control": {"type": "ephemeral"},
    }


def _call(
    client: anthropic.Anthropic,
    pdf_block: dict,
    prompt: str,
    schema: dict,
    label: str,
) -> dict[str, Any]:
    """One structured-output request; returns the parsed JSON object."""
    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": [pdf_block, {"type": "text", "text": prompt}]}],
    ) as stream:
        message = stream.get_final_message()

    if message.stop_reason == "refusal":
        raise AnalysisError(f"{label}: the request was declined by safety classifiers.")
    if message.stop_reason == "max_tokens":
        raise AnalysisError(
            f"{label}: the response hit the {MAX_TOKENS:,}-token limit before completing. "
            "Try a shorter deck or raise MAX_TOKENS."
        )

    text = next((b.text for b in message.content if b.type == "text"), "")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:  # structured outputs make this unlikely
        raise AnalysisError(f"{label}: model returned invalid JSON ({exc}).") from exc


# --- Reconciling model output with the template's fixed rows -------------------


def _match(rows: list[dict], key: str, wanted: Any, index: int) -> dict:
    """Find the row whose `key` equals `wanted`, else fall back to position."""
    for row in rows:
        if str(row.get(key, "")).strip().lower() == str(wanted).strip().lower():
            return row
    return rows[index] if index < len(rows) else {}


def _stage_label(stage: dict) -> str:
    return f"Stage {stage['number']} — {stage['name']}"


def _band_for(total: int) -> str:
    for threshold, label in CONVICTION_BANDS:
        if total >= threshold:
            return label
    return CONVICTION_BANDS[-1][1]


def _apply_readiness(data: dict, result: dict) -> None:
    """Fill Section 1, forcing the template's fixed stages and data points."""
    returned_stages = result.get("stage_breakdown", [])
    readiness_rows = result.get("readiness_summary", [])

    breakdown: list[dict] = []
    summary: list[dict] = []

    for i, stage in enumerate(CONVICTION_STAGES):
        source = _match(returned_stages, "stage", _stage_label(stage), i)
        returned_items = source.get("items", []) if isinstance(source, dict) else []

        items = []
        counts = {"PRESENT": 0, "PARTIAL": 0, "MISSING": 0}
        for j, point in enumerate(stage["data_points"]):
            item = _match(returned_items, "data_point", point, j)
            status = str(item.get("status", "MISSING")).upper()
            if status not in counts:
                status = "MISSING"
            counts[status] += 1
            items.append(
                {
                    "status": status,
                    "data_point": point,
                    "note": item.get("note") or "Not addressed in the deck.",
                }
            )

        breakdown.append({"stage": _stage_label(stage), "items": items})

        label = f"{stage['number']} — {stage['name']}"
        readiness = _match(readiness_rows, "stage", label, i).get("readiness")
        readiness = str(readiness or "").upper()
        if readiness not in ("GREEN", "AMBER", "RED"):
            # Derive it from the counts we just computed rather than guessing.
            readiness = "GREEN" if counts["PARTIAL"] + counts["MISSING"] == 0 else "AMBER"
        summary.append(
            {
                "stage": label,
                "present": counts["PRESENT"],
                "partial": counts["PARTIAL"],
                "missing": counts["MISSING"],
                "readiness": readiness,
            }
        )

    data["stage_breakdown"] = breakdown
    data["readiness_summary"] = summary
    data["overall_verdict"] = result.get("overall_verdict") or PLACEHOLDER
    data["readiness_recommendation"] = result.get("readiness_recommendation") or PLACEHOLDER
    for key in ("critical_gaps", "high_priority_gaps"):
        rows = [
            {"stage": row.get("stage", ""), "item": row.get("item", "")}
            for row in result.get(key, [])
            if row.get("item")
        ]
        data[key] = rows or [{"stage": "—", "item": "None identified."}]


def _apply_conviction(data: dict, result: dict) -> None:
    """Fill Section 2 and the title-page banner; the total is computed, not trusted."""
    scores = result.get("score_summary", [])
    narratives = result.get("stage_narratives", [])

    summary: list[dict] = []
    stage_narratives: list[dict] = []
    for i, stage in enumerate(CONVICTION_STAGES):
        row = _match(scores, "stage", stage["number"], i)
        score = row.get("score", 1)
        score = score if isinstance(score, int) and 1 <= score <= MAX_STAGE_SCORE else 1
        summary.append({"stage": stage["number"], "name": stage["name"], "score": score})

        entry = _match(narratives, "stage", stage["number"], i)
        stage_narratives.append(
            {
                "stage": _stage_label(stage),
                "score": score,
                "narrative": entry.get("narrative") or PLACEHOLDER,
            }
        )

    total = sum(row["score"] for row in summary)
    data["score_summary"] = summary
    data["stage_narratives"] = stage_narratives
    data["score_commentary"] = result.get("score_commentary") or PLACEHOLDER
    data["conviction_score"] = {
        "total": total,
        "max": MAX_TOTAL_SCORE,
        "band": _band_for(total),
    }


def _apply_deck(data: dict, result: dict) -> None:
    """Fill Section 2B, forcing the template's fixed sections and design labels."""
    assessed = result.get("section_assessment", [])
    data["section_assessment"] = [
        {
            "section": name,
            "strengths": _match(assessed, "section", name, i).get("strengths") or PLACEHOLDER,
            "weaknesses": _match(assessed, "section", name, i).get("weaknesses") or PLACEHOLDER,
            "recommendations": _match(assessed, "section", name, i).get("recommendations")
            or PLACEHOLDER,
        }
        for i, name in enumerate(DECK_SECTIONS)
    ]

    design = result.get("design_recommendations", [])
    data["design_recommendations"] = [
        {"label": label, "text": _match(design, "label", label, i).get("text") or PLACEHOLDER}
        for i, label in enumerate(DESIGN_DIMENSIONS)
    ]

    outline = [
        {"slide": row.get("slide", i + 1), "content": row.get("content", "")}
        for i, row in enumerate(result.get("revised_outline", []))
        if row.get("content")
    ]
    data["revised_outline"] = outline or [{"slide": 1, "content": PLACEHOLDER}]


def _apply_validation(data: dict, result: dict) -> None:
    score = result.get("score", 0)
    inventory = [
        {
            "claim": row.get("claim", ""),
            "type": row.get("type", "CLEAN"),
            "verdict": row.get("verdict", "SUPPORTED"),
            "source_check": row.get("source_check", ""),
        }
        for row in result.get("inventory", [])
        if row.get("claim")
    ]
    data["validation"] = {
        "score": score if isinstance(score, int) else 0,
        "max": MAX_VALIDATION_SCORE,
        "verdict": result.get("verdict") or PLACEHOLDER,
        "inventory": inventory or [{"claim": PLACEHOLDER, "type": "CLEAN",
                                    "verdict": "SUPPORTED", "source_check": PLACEHOLDER}],
        "clean_claims": result.get("clean_claims") or PLACEHOLDER,
        "flags": result.get("flags") or ["None flagged for manual review."],
        "summary": result.get("summary") or PLACEHOLDER,
    }


# --- Digests passed between calls ---------------------------------------------


def _readiness_digest(data: dict) -> str:
    lines = ["DATA READINESS REVIEW (same deck):"]
    for stage, row in zip(data["stage_breakdown"], data["readiness_summary"]):
        lines.append(f"\n{stage['stage']} — readiness {row['readiness']}")
        for item in stage["items"]:
            lines.append(f"  [{item['status']}] {item['data_point']} — {item['note']}")
    lines.append(f"\nOverall verdict: {data['overall_verdict']}")
    return "\n".join(lines)


def _analysis_digest(data: dict) -> str:
    lines = [
        f"CONVICTION SCORE: {data['conviction_score']['total']} / {MAX_TOTAL_SCORE} "
        f"({data['conviction_score']['band']})",
        f"\nScore commentary: {data['score_commentary']}",
        "\nSTAGE SCORES AND NARRATIVES:",
    ]
    for entry in data["stage_narratives"]:
        lines.append(f"\n{entry['stage']} — {entry['score']}/{MAX_STAGE_SCORE}\n{entry['narrative']}")

    lines.append("\nDATA READINESS CALLS:")
    for stage in data["stage_breakdown"]:
        for item in stage["items"]:
            lines.append(f"  {stage['stage']} [{item['status']}] {item['data_point']} — {item['note']}")

    lines.append("\nDECK SECTION ASSESSMENT:")
    for row in data["section_assessment"]:
        lines.append(
            f"\n{row['section']}\n  Strengths: {row['strengths']}"
            f"\n  Weaknesses: {row['weaknesses']}\n  Recommendations: {row['recommendations']}"
        )

    lines.append("\nDESIGN RECOMMENDATIONS:")
    for row in data["design_recommendations"]:
        lines.append(f"  {row['label']}: {row['text']}")
    return "\n".join(lines)


# --- Public entry points ------------------------------------------------------


def analyze_deck(
    pdf_path: Path | str,
    company_name: str | None = None,
    progress: Callable[[int, str], None] | None = None,
    client: anthropic.Anthropic | None = None,
) -> dict:
    """Run the four-call pipeline and return populated report data."""
    pdf_path = Path(pdf_path)
    pdf_bytes = pdf_path.read_bytes()
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise AnalysisError(
            f"The deck is {len(pdf_bytes) / 1024 / 1024:.1f} MB; the API accepts up to "
            f"{MAX_PDF_BYTES // 1024 // 1024} MB. Compress or split the PDF and try again."
        )

    def step(index: int) -> None:
        if progress:
            progress(index, PROGRESS_STEPS[index])

    step(0)
    client = client or anthropic.Anthropic()
    pdf_block = _pdf_block(pdf_bytes)

    data = blank_report_data()
    data["company_name"] = (company_name or pdf_path.stem).strip() or pdf_path.stem
    data["source"] = pdf_path.name
    data["date"] = date.today().strftime("%B %d, %Y")

    step(1)
    _apply_readiness(data, _call(client, pdf_block, READINESS_PROMPT, READINESS_SCHEMA, "Section 1"))

    step(2)
    conviction_prompt = CONVICTION_PROMPT.format(readiness_digest=_readiness_digest(data))
    _apply_conviction(data, _call(client, pdf_block, conviction_prompt, CONVICTION_SCHEMA, "Section 2"))

    step(3)
    _apply_deck(data, _call(client, pdf_block, DECK_PROMPT, DECK_SCHEMA, "Section 2B"))

    step(4)
    validation_prompt = VALIDATION_PROMPT.format(analysis_digest=_analysis_digest(data))
    _apply_validation(data, _call(client, pdf_block, validation_prompt, VALIDATION_SCHEMA, "Section 3"))

    problems = validate_report_data(data)
    if problems:
        raise AnalysisError("Assembled report data does not fit the template: " + "; ".join(problems))

    return data


def run_analysis(
    pdf_path: Path | str,
    output_path: Path | str,
    company_name: str | None = None,
    progress: Callable[[int, str], None] | None = None,
) -> Path:
    """Analyze the deck and write the branded TEN Capital .docx."""
    data = analyze_deck(pdf_path, company_name=company_name, progress=progress)
    if progress:
        progress(5, PROGRESS_STEPS[5])
    return build_report(output_path, data)


if __name__ == "__main__":  # CLI: python analysis.py deck.pdf [output.docx]
    import sys

    if len(sys.argv) < 2:
        raise SystemExit("usage: python analysis.py <deck.pdf> [output.docx]")
    deck = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else deck.with_name(
        f"{deck.stem} - TEN Capital Conviction Analysis.docx"
    )
    written = run_analysis(deck, out, progress=lambda i, label: print(f"[{i + 1}/6] {label}", flush=True))
    print(f"Saved {written}")
