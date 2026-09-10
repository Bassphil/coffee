"""
Tax-track tool implementations + schemas for advisory-swarm.

Phase 0 folds TAX_TOOLS into the single shared tool list in `tools.py` (sorted by
name, identical for every specialist -- cache-prefix requirement), and
TAX_TOOL_IMPLS into the shared dispatch table. This module is standalone: it
imports nothing from the app and reads only the JSON fixtures in ./data.

Design Document.md: "Fixtures live behind tools, never in the system prompt."
All data here is synthetic and labeled.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


@lru_cache(maxsize=None)
def _load(name: str) -> dict:
    return json.loads((DATA_DIR / name).read_text())


# --- get_tax_brackets --------------------------------------------------------

GET_TAX_BRACKETS_SCHEMA = {
    "name": "get_tax_brackets",
    "description": (
        "Return U.S. federal tax parameters for a tax year and filing status: "
        "ordinary-income and long-term capital-gains brackets, standard deduction, "
        "net investment income tax, additional Medicare tax, AMT, the estate/gift "
        "exclusion and rate, section 1202 (QSBS) rules, and retirement-account "
        "limits. Synthetic demonstration data."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "year": {"type": "integer", "description": "Tax year. Only 2026 is available."},
            "filing_status": {
                "type": "string",
                "enum": ["single", "married_filing_jointly"],
            },
        },
        "required": ["year", "filing_status"],
    },
}


def get_tax_brackets(year: int, filing_status: str) -> dict:
    data = _load("tax_brackets_2026.json")
    if year != data["year"]:
        return {"error": f"no fixture for tax year {year}; available: [{data['year']}]"}
    by_status = data["filing_status"].get(filing_status)
    if by_status is None:
        return {
            "error": f"unknown filing_status {filing_status!r}",
            "available": sorted(data["filing_status"]),
        }
    return {
        "year": data["year"],
        "filing_status": filing_status,
        **by_status,
        "top_combined_ltcg_rate_federal": data["top_combined_ltcg_rate_federal"],
        "estate_and_gift": data["estate_and_gift"],
        "qsbs_section_1202": data["qsbs_section_1202"],
        "retirement": data["retirement"],
        "_synthetic": True,
    }


# --- get_state_rules -------------------------------------------------------- --

GET_STATE_RULES_SCHEMA = {
    "name": "get_state_rules",
    "description": (
        "Return a U.S. state's rules relevant to this panel: the `tax` object "
        "(income tax, capital-gains treatment, section 1202 conformity, when the "
        "state taxes non-grantor trust income, pass-through-entity elective tax, "
        "residency posture) and, where populated, `estate` and `trust_law`. "
        "Synthetic demonstration data."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "state": {
                "type": "string",
                "description": "Two-letter state code, e.g. 'CA', 'NV', 'TX'.",
            }
        },
        "required": ["state"],
    },
}


def get_state_rules(state: str) -> dict:
    data = _load("state_rules.json")
    code = state.strip().upper()
    st = data["states"].get(code)
    if st is None:
        return {"error": f"no rules for state {state!r}", "available": sorted(data["states"])}
    return {
        "state": code,
        "name": st.get("name"),
        "tax": st.get("tax"),
        "estate": st.get("estate"),
        "trust_law": st.get("trust_law"),
        "_synthetic": True,
    }


# --- exports for the Phase 0 aggregator ------------------------------------- --

TAX_TOOLS = [GET_STATE_RULES_SCHEMA, GET_TAX_BRACKETS_SCHEMA]  # sorted by name
TAX_TOOL_IMPLS = {
    "get_tax_brackets": get_tax_brackets,
    "get_state_rules": get_state_rules,
}


if __name__ == "__main__":
    import pprint

    print("get_tax_brackets(2026, 'married_filing_jointly'):")
    pprint.pp(get_tax_brackets(2026, "married_filing_jointly"))
    print("\nget_state_rules('CA'):")
    pprint.pp(get_state_rules("CA"))
    print("\nget_state_rules('ZZ'):")
    pprint.pp(get_state_rules("ZZ"))
    print("\nget_tax_brackets(2030, 'single'):")
    pprint.pp(get_tax_brackets(2030, "single"))
