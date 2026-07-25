"""
JSON schemas for the four structured-output calls in the analysis pipeline.

Each schema mirrors one slice of the `report_template` data contract, so the
model's validated output drops straight into the document builder. Schemas are
built from the canonical framework lists in `report_template`, so changing a
stage or deck section there changes what the model is asked to produce.

Schema constraints (structured outputs): every object needs `required` listing
all properties and `additionalProperties: false`. Numeric/length constraints
(`minimum`, `minItems`, ...) are not supported — use `enum` where a value must
be bounded.
"""

from __future__ import annotations

from typing import Any

from report_template import (
    CONVICTION_STAGES,
    DECK_SECTIONS,
    DESIGN_DIMENSIONS,
    HALLUCINATION_TYPES,
    MAX_STAGE_SCORE,
    MAX_VALIDATION_SCORE,
)

STATUS_VALUES = ["PRESENT", "PARTIAL", "MISSING"]
READINESS_VALUES = ["GREEN", "AMBER", "RED"]
VERDICT_VALUES = ["SUPPORTED", "DISTORTED", "UNSUPPORTED", "FABRICATED", "FLAG"]


def _obj(properties: dict[str, Any]) -> dict[str, Any]:
    """An object schema requiring every property, with no extras allowed."""
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _arr(items: dict[str, Any]) -> dict[str, Any]:
    return {"type": "array", "items": items}


_STR = {"type": "string"}
_INT = {"type": "integer"}


# --- Section 1 — Data Readiness Report ---------------------------------------

READINESS_SCHEMA = _obj(
    {
        "readiness_summary": _arr(
            _obj(
                {
                    "stage": {
                        "type": "string",
                        "description": "Stage label, e.g. '1 — Pattern Interrupt'",
                    },
                    "readiness": {"type": "string", "enum": READINESS_VALUES},
                }
            )
        ),
        "overall_verdict": {
            **_STR,
            "description": "One or two sentences summarizing overall data readiness.",
        },
        "stage_breakdown": _arr(
            _obj(
                {
                    "stage": {
                        "type": "string",
                        "description": "Stage label, e.g. 'Stage 1 — Pattern Interrupt'",
                    },
                    "items": _arr(
                        _obj(
                            {
                                "data_point": {
                                    "type": "string",
                                    "description": "The required data point, copied verbatim from the list given.",
                                },
                                "status": {"type": "string", "enum": STATUS_VALUES},
                                "note": {
                                    "type": "string",
                                    "description": "One line citing the slide or absence that justifies the status.",
                                },
                            }
                        )
                    ),
                }
            )
        ),
        "critical_gaps": _arr(
            _obj({"stage": _STR, "item": _STR}),
        ),
        "high_priority_gaps": _arr(
            _obj({"stage": _STR, "item": _STR}),
        ),
        "readiness_recommendation": _STR,
    }
)


# --- Section 2 — Investor Conviction Ladder Analysis --------------------------

CONVICTION_SCHEMA = _obj(
    {
        "score_summary": _arr(
            _obj(
                {
                    "stage": {
                        "type": "integer",
                        "enum": [s["number"] for s in CONVICTION_STAGES],
                    },
                    "name": _STR,
                    "score": {
                        "type": "integer",
                        "enum": list(range(1, MAX_STAGE_SCORE + 1)),
                    },
                }
            )
        ),
        "score_commentary": {
            **_STR,
            "description": "Two to four sentences on the total score, strongest and weakest stages.",
        },
        "stage_narratives": _arr(
            _obj(
                {
                    "stage": {
                        "type": "integer",
                        "enum": [s["number"] for s in CONVICTION_STAGES],
                    },
                    "narrative": {
                        "type": "string",
                        "description": "One evidence-based paragraph citing specific slides and figures.",
                    },
                }
            )
        ),
    }
)


# --- Section 2B — Pitch Deck Analysis -----------------------------------------

DECK_SCHEMA = _obj(
    {
        "section_assessment": _arr(
            _obj(
                {
                    "section": {"type": "string", "enum": DECK_SECTIONS},
                    "strengths": _STR,
                    "weaknesses": _STR,
                    "recommendations": _STR,
                }
            )
        ),
        "design_recommendations": _arr(
            _obj(
                {
                    "label": {"type": "string", "enum": DESIGN_DIMENSIONS},
                    "text": _STR,
                }
            )
        ),
        "revised_outline": _arr(
            _obj({"slide": _INT, "content": _STR}),
        ),
    }
)


# --- Section 3 — Validation Check ---------------------------------------------

VALIDATION_SCHEMA = _obj(
    {
        "score": {
            "type": "integer",
            "enum": list(range(1, MAX_VALIDATION_SCORE + 1)),
        },
        "verdict": {
            **_STR,
            "description": "One sentence stating the validation verdict.",
        },
        "inventory": _arr(
            _obj(
                {
                    "claim": _STR,
                    "type": {"type": "string", "enum": HALLUCINATION_TYPES},
                    "verdict": {"type": "string", "enum": VERDICT_VALUES},
                    "source_check": _STR,
                }
            )
        ),
        "clean_claims": {
            **_STR,
            "description": "Count and percentage of claims fully supported by the deck.",
        },
        "flags": _arr(_STR),
        "summary": _STR,
    }
)
