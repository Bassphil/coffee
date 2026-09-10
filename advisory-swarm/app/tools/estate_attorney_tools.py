"""
The one domain tool the estate_attorney specialist needs.

Per the Design Document, every specialist gets an IDENTICAL, name-sorted
tool list (for prompt-cache stability) and is scoped to its own tools by
prompt instruction, not by tool availability. So `get_state_trust_rules`
must be added to the shared tool list in tools.py alongside the other
specialists' tools, not kept private to estate_attorney. It's defined here,
separately, only because tools.py doesn't exist yet.
"""

import json
from pathlib import Path

_STATE_RULES_PATH = Path(__file__).resolve().parent.parent / "data" / "state_rules.json"

TOOL_SPEC = {
    "name": "get_state_trust_rules",
    "description": (
        "Look up synthetic trust, gift-tax, and estate-tax law facts for a given "
        "US state, or 'federal' for QSBS and gift-tax rules. Use this to ground any "
        "claim about state trust taxation, gift-completion timing, or QSBS stacking "
        "— never assert those facts from memory."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "state": {
                "type": "string",
                "description": "e.g. 'California', 'Nevada', or 'federal'",
            }
        },
        "required": ["state"],
    },
}


def get_state_trust_rules(state: str) -> dict:
    rules = json.loads(_STATE_RULES_PATH.read_text())
    entry = rules.get(state)
    if entry is None:
        return {"error": f"no synthetic data for '{state}'", "known_keys": [k for k in rules if not k.startswith("_")]}
    return entry
