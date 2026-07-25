# TEN Capital — Conviction Analysis Document Template

Structure and field map for every analysis document the Python app generates.
Implemented in [report_template.py](report_template.py); run `python report_template.py`
to write `_template_preview.docx`, an empty copy of the layout.

---

## 1. Document map

| Order | Element | Content | Page break after |
|---|---|---|---|
| 1 | Title page | Company name, document title, source deck, date, conviction banner | Yes |
| 2 | Section 1 | Data Readiness Report (1.1–1.5) | Yes |
| 3 | Section 2 | Investor Conviction Ladder Analysis (2.1–2.2) | Yes |
| 4 | Section 2B | Pitch Deck Analysis: Strengths, Weaknesses & Recommendations (2B.1–2B.3) | Yes |
| 5 | Section 3 | Validation Check (3.1–3.4) | — |

Header: empty. Footer on every page: `[Document Title]   [PAGE#]   Compiled on [DATE] by TEN Capital Network   [logo]`,
centred, Open Sans 7pt, grey `#555555`, logo `TEN_Capital_logo_footer.png` at 0.67" × 0.25".

---

## 2. Formatting specification

| Element | Font | Size | Weight | Colour | Alignment |
|---|---|---|---|---|---|
| Company name (title page) | Arial | 22pt | Bold | `#1F3864` navy | Centre |
| Document title | Arial | 13pt | Regular | `#2E75B6` blue | Centre |
| Source / date lines | Arial | 10pt | Regular | `#555555` grey | Centre |
| Section heading (`SECTION N — …`) | Arial | 15pt | Bold | `#1F3864` | Left |
| Sub-section heading (`N.N  …`) | Arial | 11pt | Bold | `#2E75B6` | Left |
| Stage heading (`Stage N — …`) | Arial | 10pt | Bold | `#1F3864` | Left |
| Body paragraph | Arial | 10pt | Regular | Black | Left |
| Table header row | Arial | 9pt | Bold | White on `#1F3864` | Left |
| Table body row | Arial | 9pt | Regular | Black on white / `#F2F2F2` zebra | Left |

Page: US Letter, 0.75" margins on all sides. All tables use single 0.5pt borders on every edge.

### Colour coding (applied automatically by cell value)

| Value | Fill | Text |
|---|---|---|
| `PRESENT` / `GREEN` / `SUPPORTED` / `CLEAN` | `#E2EFDA` | `#375623` |
| `PARTIAL` / `AMBER` / `FLAG` / `DISTORTED` | `#FFF2CC` | `#7F6000` |
| `MISSING` / `RED` / `UNSUPPORTED` / `FABRICATED` | `#FFCCCC` | `#C00000` |
| Stage score 4–5 | green | green |
| Stage score 3 | amber | amber |
| Stage score 1–2 | red | red |
| Total conviction score | `#FFC000` gold | `#1F3864` |

### Banners

- **Conviction banner** (title page): centred single-cell table, 4" wide, fill `#D5E8F0`.
  Three centred lines — `CONVICTION SCORE` (13pt bold navy), `NN / 50` (28pt bold blue),
  band label (10pt grey).
- **Validation banner** (Section 3): full-width single-cell table, fill `#1F3864`.
  `VALIDATION SCORE: N / 10` (18pt bold gold) over a one-line verdict (10pt white).

---

## 3. Fields analyzed, by section

### Title block
| Field | Type | Notes |
|---|---|---|
| `company_name` | text | Rendered upper-case |
| `document_title` | text | Default `TEN Capital Investor Conviction Analysis`; also used in the footer |
| `source` | text | Source deck filename |
| `date` | text | `Month D, YYYY`; also used in the footer |
| `conviction_score.total` | int | Must equal the sum of the ten stage scores |
| `conviction_score.band` | text | Qualification band, e.g. stage/diligence descriptor |

### Section 1 — Data Readiness Report

| Sub-section | Element | Columns / fields |
|---|---|---|
| 1.1 Summary Table | Table, 10 rows (one per stage) | `Stage` · `Present` · `Partial` · `Missing` · `Readiness` (GREEN/AMBER/RED) |
| 1.1 | Verdict paragraph | `overall_verdict`, prefixed **OVERALL VERDICT:** |
| 1.2 Stage-by-Stage Breakdown | 10 tables, one per stage; one row per required data point | `Status` (PRESENT/PARTIAL/MISSING) · `Data Point` · `Notes` |
| 1.3 Critical Gaps (P1) | Table, variable rows | `Stage` · `Missing Item` |
| 1.4 High-Priority Gaps (P2) | Table, variable rows | `Stage` · `Partial/Missing Item` |
| 1.5 Recommendation | Paragraph | Ready now vs. minimum additions needed |

Present + Partial + Missing must sum to the number of required data points for that stage.

### Section 2 — Investor Conviction Ladder Analysis

| Sub-section | Element | Columns / fields |
|---|---|---|
| 2.1 Score Summary | Table, 10 rows + total row | `Stage` · `Name` · `Score (/ 5)`; final row `TOTAL CONVICTION SCORE` · `NN / 50` |
| 2.1 | Commentary paragraph | Score band, strongest and weakest stages |
| 2.2 Stage-by-Stage Narrative | 10 heading + paragraph blocks | Heading `Stage N — Name   •   Score: N / 5`, then the evidence-based narrative |

### Section 2B — Pitch Deck Analysis

| Sub-section | Element | Columns / fields |
|---|---|---|
| 2B.1 Section-by-Section Assessment | Table, 11 rows (one per deck section) | `Section` · `Strengths` · `Weaknesses / Gaps` · `Recommendations` |
| 2B.2 Design Recommendations | 5 labelled paragraphs | `TYPOGRAPHY`, `NARRATIVE FLOW`, `DATA VISUALIZATION`, `SLIDE DENSITY`, `COLOR CONSISTENCY` |
| 2B.3 Proposed Revised Slide Outline | Table, one row per slide | `Slide` · `Content` |

### Section 3 — Validation Check

| Sub-section | Element | Columns / fields |
|---|---|---|
| Banner | `validation.score` (of 10) · `validation.verdict` | |
| 3.1 Hallucination Inventory | Table, one row per checked claim | `Claim in Analysis` · `Hallucination Type` · `Verdict` · `Source Check` |
| 3.2 Clean Claims | Paragraph | Count and percentage of fully supported claims |
| 3.3 Flags for Manual Review | Numbered paragraphs | One per item needing human verification |
| 3.4 Summary | Paragraph | Use as-is / use with caveats / regenerate |

---

## 4. Fixed vocabularies

**Conviction ladder stages** (fixed order, 10 stages, 5 points each, 50 max) — with the required
data points that become the rows of each 1.2 table:

1. Pattern Interrupt — 4 data points
2. Problem Belief — 6
3. Solution Credibility — 6
4. Founder Credibility — 6
5. Market Upside — 5
6. Differentiation & Defensibility — 5
7. Traction Validation — 5
8. Risk Framing — 6
9. Deal Logic — 5
10. Personal Commitment — 4

**Deck sections assessed in 2B.1:** Executive Summary / Cover · Problem Statement ·
Solution / Technology · Market Opportunity · Business Model · Team · Traction & Milestones ·
Competitive Landscape · Risk & Mitigation · Deal Terms / Investment Ask · Call-to-Action / Closing

**Status values:** `PRESENT` · `PARTIAL` · `MISSING`
**Readiness values:** `GREEN` · `AMBER` · `RED`
**Hallucination types:** `CLEAN` · Fabricated Facts · False Citations · Unsupported Inferences ·
Misquoted or Distorted Data · Invented Gaps · Scope Creep · Tone/Framing Distortion
**Validation verdicts:** `SUPPORTED` · `DISTORTED` · `UNSUPPORTED` · `FABRICATED` · `FLAG`

The canonical lists live in `report_template.py` as `CONVICTION_STAGES`, `DECK_SECTIONS`,
`DESIGN_DIMENSIONS`, `HALLUCINATION_TYPES` and `STATUS_COLORS`. Change the framework there and
both the skeleton and the rendered document follow.

---

## 5. Using the template

```python
from pathlib import Path
from report_template import blank_report_data, build_report, validate_report_data

data = blank_report_data()        # every key present, pre-expanded to the fixed rows
# ... populate from the model output ...
problems = validate_report_data(data)   # [] means the data fits the template
build_report(Path("Company - TEN Capital Conviction Analysis.docx"), data)
```

`blank_report_data()` returns the full data contract with `[TO BE COMPLETED]` placeholders,
so the model output only has to fill values — never rebuild the shape.
`validate_report_data()` checks that all keys are present, that the four per-stage lists have
exactly ten rows, and that the total score matches the sum of the stage scores.
