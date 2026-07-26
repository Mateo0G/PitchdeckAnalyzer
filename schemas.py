"""
JSON schema for the structured-output call in the analysis pipeline.

The schema mirrors the `report_template` data contract, so the model's validated
output drops straight into the document builder. It is built from the canonical
framework lists in `report_template`, so changing a deck section or design
dimension there changes what the model is asked to produce.

Schema constraints (structured outputs): every object needs `required` listing
all properties and `additionalProperties: false`. Numeric/length constraints
(`minimum`, `minItems`, ...) are not supported — use `enum` where a value must
be bounded.
"""

from __future__ import annotations

from typing import Any

from report_template import DECK_SECTIONS, DESIGN_DIMENSIONS


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


# --- Section 1 — Pitch Deck Analysis ------------------------------------------

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
