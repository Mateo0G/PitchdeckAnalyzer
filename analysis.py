"""
The analysis pipeline: pitch deck PDF -> one Claude API call -> report data.

The call uses structured outputs, so the model returns validated JSON matching
the `report_template` contract instead of prose we would have to parse. The deck
rides along as a document block.

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
    DECK_SECTIONS,
    DESIGN_DIMENSIONS,
    PLACEHOLDER,
    blank_report_data,
    build_report,
    validate_report_data,
)
from schemas import DECK_SCHEMA

MODEL = "claude-opus-5"
MAX_TOKENS = 32000  # streamed, so no HTTP-timeout concern
EFFORT = "high"
MAX_PDF_BYTES = 32 * 1024 * 1024  # API limit on a base64 document block

PROGRESS_STEPS = [
    "Reading the deck",
    "Analyzing the deck",
    "Building the document",
]


class AnalysisError(RuntimeError):
    """Raised when the pipeline cannot produce a usable report."""


# --- Prompt -------------------------------------------------------------------


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


# --- API plumbing -------------------------------------------------------------


def _pdf_block(pdf_bytes: bytes) -> dict:
    """The deck as a document block."""
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


def _apply_deck(data: dict, result: dict) -> None:
    """Fill Section 1, forcing the template's fixed sections and design labels."""
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


# --- Public entry points ------------------------------------------------------


def analyze_deck(
    pdf_path: Path | str,
    company_name: str | None = None,
    progress: Callable[[int, str], None] | None = None,
    client: anthropic.Anthropic | None = None,
) -> dict:
    """Run the analysis call and return populated report data."""
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
    _apply_deck(data, _call(client, pdf_block, DECK_PROMPT, DECK_SCHEMA, "Section 1"))

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
        progress(2, PROGRESS_STEPS[2])
    return build_report(output_path, data)


if __name__ == "__main__":  # CLI: python analysis.py deck.pdf [output.docx]
    import sys

    if len(sys.argv) < 2:
        raise SystemExit("usage: python analysis.py <deck.pdf> [output.docx]")
    deck = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else deck.with_name(
        f"{deck.stem} - TEN Capital Deck Analysis.docx"
    )
    written = run_analysis(
        deck, out, progress=lambda i, label: print(f"[{i + 1}/{len(PROGRESS_STEPS)}] {label}", flush=True)
    )
    print(f"Saved {written}")
