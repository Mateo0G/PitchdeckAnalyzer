# TEN Capital — Pitch Deck Analysis Document Template

Structure and field map for every analysis document the Python app generates.
Implemented in [report_template.py](report_template.py); run `python report_template.py`
to write `_template_preview.docx`, an empty copy of the layout.

---

## 1. Document map

| Order | Element | Content | Page break after |
|---|---|---|---|
| 1 | Title page | Company name, document title, source deck, date | Yes |
| 2 | Section 1 | Pitch Deck Analysis: Strengths, Weaknesses & Recommendations (1.1–1.3) | — |

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
| Body paragraph | Arial | 10pt | Regular | Black | Left |
| Table header row | Arial | 9pt | Bold | White on `#1F3864` | Left |
| Table body row | Arial | 9pt | Regular | Black on white / `#F2F2F2` zebra | Left |

Page: US Letter, 0.75" margins on all sides. All tables use single 0.5pt borders on every edge.

---

## 3. Fields analyzed, by section

### Title block
| Field | Type | Notes |
|---|---|---|
| `company_name` | text | Rendered upper-case |
| `document_title` | text | Default `TEN Capital Pitch Deck Analysis`; also used in the footer |
| `source` | text | Source deck filename |
| `date` | text | `Month D, YYYY`; also used in the footer |

### Section 1 — Pitch Deck Analysis

| Sub-section | Element | Columns / fields |
|---|---|---|
| 1.1 Section-by-Section Assessment | Table, 11 rows (one per deck section) | `Section` · `Strengths` · `Weaknesses / Gaps` · `Recommendations` |
| 1.2 Design Recommendations | 5 labelled paragraphs | `TYPOGRAPHY`, `NARRATIVE FLOW`, `DATA VISUALIZATION`, `SLIDE DENSITY`, `COLOR CONSISTENCY` |
| 1.3 Proposed Revised Slide Outline | Table, one row per slide | `Slide` · `Content` |

---

## 4. Fixed vocabularies

**Deck sections assessed in 1.1:** Executive Summary / Cover · Problem Statement ·
Solution / Technology · Market Opportunity · Business Model · Team · Traction & Milestones ·
Competitive Landscape · Risk & Mitigation · Deal Terms / Investment Ask · Call-to-Action / Closing

**Design dimensions covered in 1.2:** TYPOGRAPHY · NARRATIVE FLOW · DATA VISUALIZATION ·
SLIDE DENSITY · COLOR CONSISTENCY

The canonical lists live in `report_template.py` as `DECK_SECTIONS` and `DESIGN_DIMENSIONS`.
Change the framework there and both the skeleton and the rendered document follow.

---

## 5. Using the template

```python
from pathlib import Path
from report_template import blank_report_data, build_report, validate_report_data

data = blank_report_data()        # every key present, pre-expanded to the fixed rows
# ... populate from the model output ...
problems = validate_report_data(data)   # [] means the data fits the template
build_report(Path("Company - TEN Capital Deck Analysis.docx"), data)
```

`blank_report_data()` returns the full data contract with `[TO BE COMPLETED]` placeholders,
so the model output only has to fill values — never rebuild the shape.
`validate_report_data()` checks that all keys are present, that the assessment table has exactly
eleven rows and the design recommendations five, and that the slide outline is not empty.
