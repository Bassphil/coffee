"""Every structured-output JSON schema, in one place.

Anthropic's structured outputs require additionalProperties: false on every object node,
including nested ones — easy to miss, so every schema below sets it explicitly. (Found this the
hard way debugging the financial_advisor draft call — a bare nested object 400s.)
"""

SPECIALIST_DRAFT_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "domain_findings": {"type": "string"},
            "recommendation": {"type": "string"},
            "cross_domain_implications": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "domain": {"type": "string"},
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
                    "properties": {"domain": {"type": "string"}, "concern": {"type": "string"}},
                    "required": ["domain", "concern"],
                    "additionalProperties": False,
                },
            },
            "assumptions": {"type": "array", "items": {"type": "string"}},
            "open_questions": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "domain_findings",
            "recommendation",
            "cross_domain_implications",
            "what_id_push_back_on",
            "assumptions",
            "open_questions",
        ],
        "additionalProperties": False,
    },
}

REBUTTAL_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "position": {"type": "string", "enum": ["hold", "concede", "qualify"]},
            "reasoning": {"type": "string"},
            "condition_under_which_other_is_right": {"type": "string"},
            "revised_recommendation": {"type": "string"},
        },
        "required": [
            "position",
            "reasoning",
            "condition_under_which_other_is_right",
            "revised_recommendation",
        ],
        "additionalProperties": False,
    },
}

CONFLICT_LIST_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "conflicts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "topic": {"type": "string"},
                        "type": {
                            "type": "string",
                            "enum": [
                                "recommendation",
                                "factual",
                                "sequencing",
                                "assumption",
                                "emphasis",
                            ],
                        },
                        "positions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "agent": {"type": "string"},
                                    "quote": {"type": "string"},
                                },
                                "required": ["agent", "quote"],
                                "additionalProperties": False,
                            },
                        },
                        "question": {"type": "string"},
                        "materiality": {
                            "type": "string",
                            "enum": ["changes_action", "changes_number", "framing_only"],
                        },
                    },
                    "required": ["id", "topic", "type", "positions", "question", "materiality"],
                    "additionalProperties": False,
                },
            },
            "rationale": {
                "type": "string",
                "description": "Why this list is complete, including if it's empty — never leave this bare.",
            },
        },
        "required": ["conflicts", "rationale"],
        "additionalProperties": False,
    },
}

MEMO_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "headline": {"type": "string"},
            "recommendation": {"type": "string"},
            "domain_findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"domain": {"type": "string"}, "summary": {"type": "string"}},
                    "required": ["domain", "summary"],
                    "additionalProperties": False,
                },
            },
            "conflicts_resolved": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string"},
                        "tension": {"type": "string"},
                        "resolution": {"type": "string"},
                        "tradeoff": {"type": "string"},
                    },
                    "required": ["topic", "tension", "resolution", "tradeoff"],
                    "additionalProperties": False,
                },
            },
            "action_plan": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "step": {"type": "integer"},
                        "action": {"type": "string"},
                        "owner": {"type": "string"},
                        "timing": {"type": "string"},
                    },
                    "required": ["step", "action", "owner", "timing"],
                    "additionalProperties": False,
                },
            },
            "open_questions": {"type": "array", "items": {"type": "string"}},
            "assumptions": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "headline",
            "recommendation",
            "domain_findings",
            "conflicts_resolved",
            "action_plan",
            "open_questions",
            "assumptions",
        ],
        "additionalProperties": False,
    },
}
