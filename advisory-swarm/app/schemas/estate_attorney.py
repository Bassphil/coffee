"""
Proposed shared schemas for the advisory-swarm specialists.

SPECIALIST_DRAFT_SCHEMA and REBUTTAL_SCHEMA are meant to be IDENTICAL across
all three specialists (financial_advisor, tax_cpa, estate_attorney) and to
live in the shared `schemas.py` once it exists, per the Design Document's
"schemas.py — every structured-output schema in one place" note.

They are defined here only so the estate_attorney can be developed and run
standalone before that shared module exists. Whoever owns schemas.py should
adopt these (or reconcile them if a different shape was already chosen) so
the three specialists don't ship three divergent copies.

Every object schema sets `additionalProperties: false` — the live API
(verified against claude-sonnet-5 in this session) rejects
`output_config.format` object schemas without it.
"""

SPECIALIST_DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "domain_findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "finding": {"type": "string"},
                    "basis": {"type": "string", "description": "which tool result or fact this rests on"},
                },
                "required": ["finding", "basis"],
                "additionalProperties": False,
            },
        },
        "recommendation": {"type": "string"},
        "cross_domain_implications": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "enum": ["financial_advisor", "tax_cpa"]},
                    "implication": {"type": "string"},
                },
                "required": ["domain", "implication"],
                "additionalProperties": False,
            },
        },
        "what_id_push_back_on": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "enum": ["financial_advisor", "tax_cpa"]},
                    "concern": {"type": "string"},
                },
                "required": ["domain", "concern"],
                "additionalProperties": False,
            },
        },
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "open_questions": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "headline",
        "domain_findings",
        "recommendation",
        "cross_domain_implications",
        "what_id_push_back_on",
        "assumptions",
        "open_questions",
    ],
    "additionalProperties": False,
}

# Verbatim from the Design Document's "Conflict representation" section.
REBUTTAL_SCHEMA = {
    "type": "object",
    "properties": {
        "position": {"type": "string", "enum": ["hold", "concede", "qualify"]},
        "reasoning": {"type": "string"},
        "condition_under_which_other_is_right": {"type": "string"},
        "revised_recommendation": {"type": "string"},
    },
    "required": ["position", "reasoning", "condition_under_which_other_is_right", "revised_recommendation"],
    "additionalProperties": False,
}
