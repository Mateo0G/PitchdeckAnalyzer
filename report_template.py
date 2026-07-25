"""
TEN Capital — Conviction Analysis Report Template
=================================================

The document skeleton every generated analysis follows. This module owns the
*structure and formatting only*; all content is supplied by the caller through
the `ReportData` mapping described below. No company-specific text lives here.

Usage
-----
    from report_template import build_report, blank_report_data

    data = blank_report_data()          # fully-formed skeleton with placeholders
    data["company_name"] = "..."        # populate from the model output
    ...
    build_report(Path("out.docx"), data)

Document map (page breaks marked ⏎)
-----------------------------------
    Title page      Company / Document title / Source / Date / Conviction banner   ⏎
    SECTION 1 — DATA READINESS REPORT
        1.1  Summary Table                  10-row readiness matrix + verdict
        1.2  Stage-by-Stage Breakdown       one Status/Data Point/Notes table per stage
        1.3  Critical Gaps (P1)             Stage | Missing Item
        1.4  High-Priority Gaps (P2)        Stage | Partial/Missing Item
        1.5  Recommendation                 prose                                  ⏎
    SECTION 2 — INVESTOR CONVICTION LADDER ANALYSIS
        2.1  Score Summary                  Stage | Name | Score (/5) + TOTAL row
        2.2  Stage-by-Stage Narrative       one heading + prose block per stage     ⏎
    SECTION 2B — PITCH DECK ANALYSIS: STRENGTHS, WEAKNESSES & RECOMMENDATIONS
        2B.1 Section-by-Section Assessment  Section | Strengths | Weaknesses | Recs
        2B.2 Formatting, Storytelling & Design Recommendations
        2B.3 Proposed Revised Slide Outline Slide | Content                        ⏎
    SECTION 3 — VALIDATION CHECK
        (banner)                            Validation score + verdict
        3.1  Hallucination Inventory        Claim | Type | Verdict | Source Check
        3.2  Clean Claims                   prose
        3.3  Flags for Manual Review        numbered list
        3.4  Summary                        prose
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Sequence

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

# --- Brand palette -----------------------------------------------------------

NAVY = "1F3864"        # section headings, table header fill, primary brand
BLUE = "2E75B6"        # sub-headings, document subtitle, score figure
GREY = "555555"        # metadata lines, footer
GOLD = "FFC000"        # total-score and validation-score emphasis
BANNER_FILL = "D5E8F0"  # conviction banner background
ZEBRA_FILL = "F2F2F2"  # alternating body-row fill
WHITE = "FFFFFF"

# Status / readiness colour coding — (cell fill, text colour)
STATUS_COLORS: dict[str, tuple[str, str]] = {
    "PRESENT": ("E2EFDA", "375623"),
    "PARTIAL": ("FFF2CC", "7F6000"),
    "MISSING": ("FFCCCC", "C00000"),
    "GREEN": ("E2EFDA", "375623"),
    "AMBER": ("FFF2CC", "7F6000"),
    "RED": ("FFCCCC", "C00000"),
    "SUPPORTED": ("E2EFDA", "375623"),
    "CLEAN": ("E2EFDA", "375623"),
    "FLAG": ("FFF2CC", "7F6000"),
    "DISTORTED": ("FFF2CC", "7F6000"),
    "UNSUPPORTED": ("FFCCCC", "C00000"),
    "FABRICATED": ("FFCCCC", "C00000"),
}

# Stage score 4–5 reads green, 3 amber, 1–2 red.
SCORE_COLORS: dict[int, tuple[str, str]] = {
    5: STATUS_COLORS["GREEN"],
    4: STATUS_COLORS["GREEN"],
    3: STATUS_COLORS["AMBER"],
    2: STATUS_COLORS["RED"],
    1: STATUS_COLORS["RED"],
}

# --- Typography --------------------------------------------------------------

BODY_FONT = "Arial"
FOOTER_FONT = "Open Sans"

SIZE_TITLE = Pt(22)
SIZE_SUBTITLE = Pt(13)
SIZE_META = Pt(10)
SIZE_SECTION = Pt(15)
SIZE_SUBSECTION = Pt(11)
SIZE_STAGE_HEADING = Pt(10)
SIZE_BODY = Pt(10)
SIZE_TABLE = Pt(9)
SIZE_FOOTER = Pt(7)
SIZE_BANNER_LABEL = Pt(13)
SIZE_BANNER_FIGURE = Pt(28)

PAGE_MARGIN = Inches(0.75)
FOOTER_LOGO = "TEN_Capital_logo_footer.png"  # resolved relative to this file

# --- The framework being scored ----------------------------------------------
# Stage names and required data points drive both the readiness matrix (Section 1)
# and the score summary (Section 2). Edit here to change the framework everywhere.

CONVICTION_STAGES: list[dict[str, Any]] = [
    {
        "number": 1,
        "name": "Pattern Interrupt",
        "data_points": [
            "Compelling opening hook (first 1–2 slides)",
            "Clear company positioning statement (why us, why now)",
            "Legal/forward-looking slide placed at back (not front)",
            "Problem teaser visible within first 2 slides",
        ],
    },
    {
        "number": 2,
        "name": "Problem Belief",
        "data_points": [
            "Quantified problem size",
            "Timeliness or urgency signal",
            "Proof that incumbent solutions have failed",
            "Payor perspective (who pays today and at what cost)",
            "Buyer segmentation (distinct decision-makers identified)",
            "Source citations for key claims",
        ],
    },
    {
        "number": 3,
        "name": "Solution Credibility",
        "data_points": [
            "Mechanism of action or core technology clearly explained",
            "Preclinical or technical validation data",
            "Human or customer validation data",
            "Product/formulation specification",
            "Regulatory or approval pathway identified",
            "CMC, manufacturing, or production readiness",
        ],
    },
    {
        "number": 4,
        "name": "Founder Credibility",
        "data_points": [
            "Founding scientist or domain expert with verifiable authority",
            "CEO with relevant stage-appropriate leadership experience",
            "Full-time operational lead for the next milestone",
            "Key execution partner named",
            "Functional leadership gaps acknowledged or filled",
            "Key opinion leader or customer endorsements",
        ],
    },
    {
        "number": 5,
        "name": "Market Upside",
        "data_points": [
            "TAM with methodology and source",
            "Bottoms-up SAM or serviceable market logic",
            "Revenue model or partnership transaction structure",
            "Near-term value creation event",
            "Comparable company exits with multiples",
        ],
    },
    {
        "number": 6,
        "name": "Differentiation & Defensibility",
        "data_points": [
            "IP summary (patent type, jurisdiction, expiry)",
            "Competitive positioning matrix or differentiation statement",
            "Composition-of-matter vs. method/use distinction addressed",
            "Regulatory exclusivity or other structural moat",
            "Design-around or imitation risk acknowledged",
        ],
    },
    {
        "number": 7,
        "name": "Traction Validation",
        "data_points": [
            "Non-dilutive funding, grants, or awards secured",
            "Product or clinical validation data from target population",
            "Customer, partner, or strategic engagement",
            "Key opinion leader or customer endorsement",
            "Current round status and named lead investor",
        ],
    },
    {
        "number": 8,
        "name": "Risk Framing",
        "data_points": [
            "Dedicated risk or risk/mitigation slide",
            "Primary technical or execution risk identified",
            "Regulatory risk addressed",
            "Commercial or go-to-market risk addressed",
            "Financial risk (runway, note maturity, funding gap)",
            "Mitigation strategy for each key risk",
        ],
    },
    {
        "number": 9,
        "name": "Deal Logic",
        "data_points": [
            "Valuation with methodology and comparable transactions",
            "Use of proceeds with line-item breakdown",
            "Instrument terms (rate, discount, maturity, conversion trigger)",
            "Milestone timeline vs. funding runway reconciled",
            "Current round status and remaining gap addressed",
        ],
    },
    {
        "number": 10,
        "name": "Personal Commitment",
        "data_points": [
            "Founder personal or financial commitment signal",
            '"Why now" narrative',
            "Specific acquirer or exit path with rationale",
            "Mission or personal connection to the problem",
        ],
    },
]

# Deck sections assessed in Section 2B — fixed rows of the strengths/weaknesses table.
DECK_SECTIONS: list[str] = [
    "Executive Summary / Cover",
    "Problem Statement",
    "Solution / Technology",
    "Market Opportunity",
    "Business Model",
    "Team",
    "Traction & Milestones",
    "Competitive Landscape",
    "Risk & Mitigation",
    "Deal Terms / Investment Ask",
    "Call-to-Action / Closing",
]

# Design dimensions covered in 2B.2 — one labelled paragraph each.
DESIGN_DIMENSIONS: list[str] = [
    "TYPOGRAPHY",
    "NARRATIVE FLOW",
    "DATA VISUALIZATION",
    "SLIDE DENSITY",
    "COLOR CONSISTENCY",
]

# Hallucination taxonomy used in the Section 3 inventory.
HALLUCINATION_TYPES: list[str] = [
    "CLEAN",
    "Fabricated Facts",
    "False Citations",
    "Unsupported Inferences",
    "Misquoted or Distorted Data",
    "Invented Gaps",
    "Scope Creep",
    "Tone/Framing Distortion",
]

MAX_STAGE_SCORE = 5
MAX_TOTAL_SCORE = MAX_STAGE_SCORE * len(CONVICTION_STAGES)
MAX_VALIDATION_SCORE = 10


# --- Low-level formatting helpers --------------------------------------------


def _shade(cell, fill: str) -> None:
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), fill)
    cell._tc.get_or_add_tcPr().append(shd)


def _set_borders(table) -> None:
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "4")
        element.set(qn("w:color"), "auto")
        borders.append(element)
    table._tbl.tblPr.append(borders)


def _write_cell(
    cell,
    text: str,
    *,
    fill: str = WHITE,
    color: str = "000000",
    bold: bool = False,
    size: Pt = SIZE_TABLE,
    align: WD_ALIGN_PARAGRAPH | None = None,
) -> None:
    _shade(cell, fill)
    para = cell.paragraphs[0]
    para.text = ""
    if align is not None:
        para.alignment = align
    para.paragraph_format.space_after = Pt(2)
    run = para.add_run(str(text))
    run.font.name = BODY_FONT
    run.font.size = size
    run.font.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)


def _add_table(doc: Document, headers: Sequence[str], widths: Sequence[float] | None = None):
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    _set_borders(table)
    for i, header in enumerate(headers):
        _write_cell(table.rows[0].cells[i], header, fill=NAVY, color=WHITE, bold=True)
    if widths:
        for row in table.rows:
            for i, width in enumerate(widths):
                row.cells[i].width = Inches(width)
    return table


def _add_body_row(table, values: Sequence[str], index: int, coded_column: int | None = None):
    """Append a zebra-striped body row; `coded_column` gets status colour coding."""
    fill = WHITE if index % 2 == 0 else ZEBRA_FILL
    cells = table.add_row().cells
    for i, value in enumerate(values):
        key = str(value).strip().upper()
        if i == coded_column and key in STATUS_COLORS:
            cell_fill, cell_color = STATUS_COLORS[key]
            _write_cell(cells[i], value, fill=cell_fill, color=cell_color, bold=True)
        else:
            _write_cell(cells[i], value, fill=fill)
    return cells


def _heading(doc: Document, text: str, *, size: Pt, color: str, before: int, after: int):
    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(before)
    para.paragraph_format.space_after = Pt(after)
    run = para.add_run(text)
    run.font.name = BODY_FONT
    run.font.size = size
    run.font.bold = True
    run.font.color.rgb = RGBColor.from_string(color)
    return para


def section_heading(doc: Document, text: str):
    """SECTION N — TITLE"""
    return _heading(doc, text, size=SIZE_SECTION, color=NAVY, before=18, after=9)


def subsection_heading(doc: Document, text: str):
    """N.N  Sub-section title"""
    return _heading(doc, text, size=SIZE_SUBSECTION, color=BLUE, before=12, after=6)


def stage_heading(doc: Document, text: str):
    """Stage N — Name (optionally with score suffix)"""
    return _heading(doc, text, size=SIZE_STAGE_HEADING, color=NAVY, before=10, after=4)


def body_paragraph(doc: Document, text: str, *, bold_prefix: str | None = None):
    para = doc.add_paragraph()
    para.paragraph_format.space_after = Pt(5)
    if bold_prefix:
        run = para.add_run(f"{bold_prefix} ")
        run.font.name = BODY_FONT
        run.font.size = SIZE_BODY
        run.font.bold = True
        run.font.color.rgb = RGBColor.from_string(NAVY)
    run = para.add_run(text)
    run.font.name = BODY_FONT
    run.font.size = SIZE_BODY
    return para


def page_break(doc: Document) -> None:
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


# --- Fixed document furniture ------------------------------------------------


def _add_footer(doc: Document, document_title: str, compiled_on: str) -> None:
    """Single-line centred TEN Capital footer: title · page · compiled-on · logo."""
    logo = _find_logo()
    for section in doc.sections:
        section.footer.is_linked_to_previous = False
        para = section.footer.paragraphs[0]
        para.text = ""
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        def _run(text: str):
            run = para.add_run(text)
            run.font.name = FOOTER_FONT
            run.font.size = SIZE_FOOTER
            run.font.color.rgb = RGBColor.from_string(GREY)
            return run

        _run(f"{document_title}          ")
        _add_page_number(_run(""))
        _run(f"     Compiled on {compiled_on} by TEN Capital Network    ")
        if logo is not None:
            para.add_run().add_picture(str(logo), width=Inches(0.67), height=Inches(0.25))


def _find_logo() -> Path | None:
    """Locate the footer logo beside this module, or in the parent folder."""
    here = Path(__file__).parent
    for candidate in (here / FOOTER_LOGO, here.parent / FOOTER_LOGO):
        if candidate.exists():
            return candidate
    return None


def _add_page_number(run) -> None:
    begin, field, end = OxmlElement("w:fldChar"), OxmlElement("w:instrText"), OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    field.set(qn("xml:space"), "preserve")
    field.text = "PAGE"
    end.set(qn("w:fldCharType"), "end")
    for element in (begin, field, end):
        run._r.append(element)


def title_page(doc: Document, data: dict) -> None:
    def centred(text: str, size: Pt, color: str, bold: bool, after: int):
        para = doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.paragraph_format.space_after = Pt(after)
        run = para.add_run(text)
        run.font.name = BODY_FONT
        run.font.size = size
        run.font.bold = bold
        run.font.color.rgb = RGBColor.from_string(color)

    doc.add_paragraph()
    centred(data["company_name"].upper(), SIZE_TITLE, NAVY, True, 10)
    centred(data["document_title"], SIZE_SUBTITLE, BLUE, False, 8)
    centred(f"Source: {data['source']}", SIZE_META, GREY, False, 15)
    centred(f"{data['date']}  |  Prepared by TEN Capital Network", SIZE_META, GREY, False, 20)
    conviction_banner(doc, data["conviction_score"])


def conviction_banner(doc: Document, score: dict) -> None:
    """Centred single-cell banner: label / figure / band."""
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    _set_borders(table)
    cell = table.rows[0].cells[0]
    cell.width = Inches(4.0)
    _shade(cell, BANNER_FILL)
    cell.paragraphs[0].text = ""

    lines = [
        ("CONVICTION SCORE", SIZE_BANNER_LABEL, NAVY, True),
        (f"{score['total']} / {score.get('max', MAX_TOTAL_SCORE)}", SIZE_BANNER_FIGURE, BLUE, True),
        (score["band"], SIZE_BODY, GREY, False),
    ]
    for i, (text, size, color, bold) in enumerate(lines):
        para = cell.paragraphs[0] if i == 0 else cell.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = para.add_run(text)
        run.font.name = BODY_FONT
        run.font.size = size
        run.font.bold = bold
        run.font.color.rgb = RGBColor.from_string(color)


def validation_banner(doc: Document, validation: dict) -> None:
    """Navy full-width banner carrying the validation score and one-line verdict."""
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    _set_borders(table)
    cell = table.rows[0].cells[0]
    _shade(cell, NAVY)
    cell.paragraphs[0].text = ""

    head = cell.paragraphs[0]
    head.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = head.add_run(
        f"VALIDATION SCORE: {validation['score']} / {validation.get('max', MAX_VALIDATION_SCORE)}"
    )
    run.font.name = BODY_FONT
    run.font.size = Pt(18)
    run.font.bold = True
    run.font.color.rgb = RGBColor.from_string(GOLD)

    verdict = cell.add_paragraph()
    verdict.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = verdict.add_run(validation["verdict"])
    run.font.name = BODY_FONT
    run.font.size = SIZE_BODY
    run.font.color.rgb = RGBColor.from_string(WHITE)


# --- Section builders ---------------------------------------------------------


def section_1_data_readiness(doc: Document, data: dict) -> None:
    section_heading(doc, "SECTION 1 — DATA READINESS REPORT")

    subsection_heading(doc, "1.1  Summary Table")
    body_paragraph(
        doc,
        "The following table summarizes data readiness across all 10 Conviction Ladder "
        "stages. GREEN = all key data points present; AMBER = gaps exist but core is "
        "present; RED = critical gaps that materially impair scoring accuracy.",
    )
    table = _add_table(doc, ["Stage", "Present", "Partial", "Missing", "Readiness"],
                       widths=[3.15, 0.85, 0.85, 0.85, 1.30])
    for i, row in enumerate(data["readiness_summary"]):
        _add_body_row(
            table,
            [row["stage"], row["present"], row["partial"], row["missing"], row["readiness"]],
            i,
            coded_column=4,
        )
    doc.add_paragraph()
    body_paragraph(doc, data["overall_verdict"], bold_prefix="OVERALL VERDICT:")

    subsection_heading(doc, "1.2  Stage-by-Stage Breakdown")
    for stage in data["stage_breakdown"]:
        stage_heading(doc, stage["stage"])
        table = _add_table(doc, ["Status", "Data Point", "Notes"], widths=[1.0, 2.2, 3.8])
        for i, item in enumerate(stage["items"]):
            _add_body_row(table, [item["status"], item["data_point"], item["note"]], i, coded_column=0)
        doc.add_paragraph()

    subsection_heading(doc, "1.3  Critical Gaps (P1) — Must Resolve Before Full Conviction Analysis")
    table = _add_table(doc, ["Stage", "Missing Item"], widths=[1.2, 5.8])
    for i, gap in enumerate(data["critical_gaps"]):
        _add_body_row(table, [gap["stage"], gap["item"]], i)
    doc.add_paragraph()

    subsection_heading(doc, "1.4  High-Priority Gaps (P2) — Materially Reduce Scoring Accuracy")
    table = _add_table(doc, ["Stage", "Partial/Missing Item"], widths=[1.2, 5.8])
    for i, gap in enumerate(data["high_priority_gaps"]):
        _add_body_row(table, [gap["stage"], gap["item"]], i)
    doc.add_paragraph()

    subsection_heading(doc, "1.5  Recommendation")
    body_paragraph(doc, data["readiness_recommendation"])


def section_2_conviction_ladder(doc: Document, data: dict) -> None:
    section_heading(doc, "SECTION 2 — INVESTOR CONVICTION LADDER ANALYSIS")

    subsection_heading(doc, "2.1  Score Summary")
    table = _add_table(doc, ["Stage", "Name", f"Score (/ {MAX_STAGE_SCORE})"], widths=[0.8, 4.9, 1.3])
    for i, row in enumerate(data["score_summary"]):
        cells = table.add_row().cells
        fill = WHITE if i % 2 == 0 else ZEBRA_FILL
        _write_cell(cells[0], row["stage"], fill=fill)
        _write_cell(cells[1], row["name"], fill=fill)
        score_fill, score_color = SCORE_COLORS.get(row["score"], (fill, "000000"))
        _write_cell(
            cells[2],
            f"{row['score']} / {MAX_STAGE_SCORE}",
            fill=score_fill,
            color=score_color,
            bold=True,
            align=WD_ALIGN_PARAGRAPH.CENTER,
        )

    total = data["conviction_score"]
    cells = table.add_row().cells
    _write_cell(cells[0], "", fill=NAVY)
    _write_cell(cells[1], "TOTAL CONVICTION SCORE", fill=NAVY, color=WHITE, bold=True)
    _write_cell(
        cells[2],
        f"{total['total']} / {total.get('max', MAX_TOTAL_SCORE)}",
        fill=GOLD,
        color=NAVY,
        bold=True,
        align=WD_ALIGN_PARAGRAPH.CENTER,
    )
    doc.add_paragraph()
    body_paragraph(doc, data["score_commentary"])

    subsection_heading(doc, "2.2  Stage-by-Stage Narrative")
    for entry in data["stage_narratives"]:
        stage_heading(doc, f"{entry['stage']}   •   Score: {entry['score']} / {MAX_STAGE_SCORE}")
        body_paragraph(doc, entry["narrative"])


def section_2b_deck_analysis(doc: Document, data: dict) -> None:
    section_heading(doc, "SECTION 2B — PITCH DECK ANALYSIS: STRENGTHS, WEAKNESSES & RECOMMENDATIONS")
    body_paragraph(
        doc,
        "The following analysis applies the deck review framework: a section-by-section "
        "assessment of what is working, what is hurting investor perception, and specific "
        "actionable improvements.",
    )

    subsection_heading(doc, "2B.1  Section-by-Section Assessment")
    table = _add_table(doc, ["Section", "Strengths", "Weaknesses / Gaps", "Recommendations"],
                       widths=[1.3, 1.9, 1.9, 1.9])
    for i, row in enumerate(data["section_assessment"]):
        cells = _add_body_row(
            table,
            [row["section"], row["strengths"], row["weaknesses"], row["recommendations"]],
            i,
        )
        for run in cells[0].paragraphs[0].runs:
            run.font.bold = True
    doc.add_paragraph()

    subsection_heading(doc, "2B.2  Formatting, Storytelling & Design Recommendations")
    for item in data["design_recommendations"]:
        body_paragraph(doc, item["text"], bold_prefix=f"{item['label']}:")

    subsection_heading(doc, "2B.3  Proposed Revised Slide Outline")
    table = _add_table(doc, ["Slide", "Content"], widths=[0.8, 6.2])
    for i, row in enumerate(data["revised_outline"]):
        _add_body_row(table, [row["slide"], row["content"]], i)


def section_3_validation(doc: Document, data: dict) -> None:
    section_heading(doc, "SECTION 3 — VALIDATION CHECK")
    validation = data["validation"]
    validation_banner(doc, validation)
    doc.add_paragraph()

    subsection_heading(doc, "3.1  Hallucination Inventory")
    table = _add_table(doc, ["Claim in Analysis", "Hallucination Type", "Verdict", "Source Check"],
                       widths=[2.5, 1.4, 1.1, 2.0])
    for i, row in enumerate(validation["inventory"]):
        _add_body_row(
            table,
            [row["claim"], row["type"], row["verdict"], row["source_check"]],
            i,
            coded_column=2,
        )
    doc.add_paragraph()

    subsection_heading(doc, "3.2  Clean Claims")
    body_paragraph(doc, validation["clean_claims"])

    subsection_heading(doc, "3.3  Flags for Manual Review")
    for i, flag in enumerate(validation["flags"], start=1):
        body_paragraph(doc, f"{i}. {flag}")

    subsection_heading(doc, "3.4  Summary")
    body_paragraph(doc, validation["summary"])


# --- Entry point --------------------------------------------------------------


def build_report(output_path: Path | str, data: dict) -> Path:
    """Render `data` into the branded TEN Capital conviction analysis document."""
    doc = Document()

    normal = doc.styles["Normal"]
    normal.font.name = BODY_FONT
    normal.font.size = SIZE_BODY
    for section in doc.sections:
        section.left_margin = section.right_margin = PAGE_MARGIN
        section.top_margin = section.bottom_margin = PAGE_MARGIN

    title_page(doc, data)
    page_break(doc)

    section_1_data_readiness(doc, data)
    page_break(doc)

    section_2_conviction_ladder(doc, data)
    page_break(doc)

    section_2b_deck_analysis(doc, data)
    page_break(doc)

    section_3_validation(doc, data)

    _add_footer(doc, data["document_title"], data["date"])

    output_path = Path(output_path)
    doc.save(str(output_path))
    return output_path


# --- Skeleton data ------------------------------------------------------------

PLACEHOLDER = "[TO BE COMPLETED]"


def blank_report_data() -> dict:
    """
    A fully-formed, content-free instance of the data contract.

    Every key the template reads is present, pre-expanded to the fixed rows of
    the framework (10 stages, 11 deck sections, 5 design dimensions) so callers
    can fill values in place rather than reconstructing the shape.
    """
    return {
        # Header block
        "company_name": PLACEHOLDER,
        "document_title": "TEN Capital Investor Conviction Analysis",
        "source": PLACEHOLDER,                      # source deck filename
        "date": PLACEHOLDER,                        # e.g. "January 1, 2026"
        # Default stage score is the 1/5 floor, so the skeleton is self-consistent.
        "conviction_score": {
            "total": len(CONVICTION_STAGES),
            "max": MAX_TOTAL_SCORE,
            "band": PLACEHOLDER,
        },

        # 1.1 — one row per stage; counts must sum to that stage's data points
        "readiness_summary": [
            {
                "stage": f"{s['number']} — {s['name']}",
                "present": 0,
                "partial": 0,
                "missing": len(s["data_points"]),
                "readiness": "RED",                 # GREEN | AMBER | RED
            }
            for s in CONVICTION_STAGES
        ],
        "overall_verdict": PLACEHOLDER,

        # 1.2 — one table per stage; one row per required data point
        "stage_breakdown": [
            {
                "stage": f"Stage {s['number']} — {s['name']}",
                "items": [
                    {"status": "MISSING", "data_point": dp, "note": PLACEHOLDER}
                    for dp in s["data_points"]
                ],
            }
            for s in CONVICTION_STAGES
        ],

        # 1.3 / 1.4 — variable length
        "critical_gaps": [{"stage": PLACEHOLDER, "item": PLACEHOLDER}],
        "high_priority_gaps": [{"stage": PLACEHOLDER, "item": PLACEHOLDER}],
        "readiness_recommendation": PLACEHOLDER,

        # 2.1 / 2.2 — one row and one narrative per stage
        "score_summary": [
            {"stage": s["number"], "name": s["name"], "score": 1} for s in CONVICTION_STAGES
        ],
        "score_commentary": PLACEHOLDER,
        "stage_narratives": [
            {"stage": f"Stage {s['number']} — {s['name']}", "score": 1, "narrative": PLACEHOLDER}
            for s in CONVICTION_STAGES
        ],

        # 2B.1 / 2B.2 / 2B.3
        "section_assessment": [
            {
                "section": name,
                "strengths": PLACEHOLDER,
                "weaknesses": PLACEHOLDER,
                "recommendations": PLACEHOLDER,
            }
            for name in DECK_SECTIONS
        ],
        "design_recommendations": [
            {"label": label, "text": PLACEHOLDER} for label in DESIGN_DIMENSIONS
        ],
        "revised_outline": [{"slide": n, "content": PLACEHOLDER} for n in range(1, 17)],

        # Section 3
        "validation": {
            "score": 0,
            "max": MAX_VALIDATION_SCORE,
            "verdict": PLACEHOLDER,
            "inventory": [
                {
                    "claim": PLACEHOLDER,
                    "type": "CLEAN",
                    "verdict": "SUPPORTED",
                    "source_check": PLACEHOLDER,
                }
            ],
            "clean_claims": PLACEHOLDER,
            "flags": [PLACEHOLDER],
            "summary": PLACEHOLDER,
        },
    }


def validate_report_data(data: dict) -> list[str]:
    """Return a list of structural problems; empty list means the data fits the template."""
    problems: list[str] = []

    def require(container: dict, keys: Iterable[str], where: str) -> None:
        for key in keys:
            if key not in container:
                problems.append(f"missing key '{key}' in {where}")

    require(data, blank_report_data().keys(), "report data")
    if not problems:
        for name, expected in (
            ("readiness_summary", len(CONVICTION_STAGES)),
            ("stage_breakdown", len(CONVICTION_STAGES)),
            ("score_summary", len(CONVICTION_STAGES)),
            ("stage_narratives", len(CONVICTION_STAGES)),
        ):
            if len(data[name]) != expected:
                problems.append(f"'{name}' has {len(data[name])} rows, expected {expected}")
        total = sum(row["score"] for row in data["score_summary"])
        if total != data["conviction_score"]["total"]:
            problems.append(
                f"conviction_score.total ({data['conviction_score']['total']}) "
                f"does not match the sum of stage scores ({total})"
            )
    return problems


if __name__ == "__main__":
    # Emit the empty skeleton so the layout can be inspected without an API call.
    out = build_report(Path(__file__).with_name("_template_preview.docx"), blank_report_data())
    print(f"Wrote template preview -> {out}")
