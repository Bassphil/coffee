"""
The domain tool the tax_cpa specialist needs: get_tax_brackets.

Per the Design Document, every specialist gets an IDENTICAL, name-sorted tool
list (prompt-cache stability) and is scoped to its own tools by prompt, not by
availability. So `get_tax_brackets` goes into the shared list in tools.py
alongside get_state_trust_rules (estate_attorney_tools.py) and the financial
advisor's tools. It's defined here separately only because tools.py doesn't
exist yet.

State / trust / gift-tax facts: the tax_cpa persona calls the estate track's
`get_state_trust_rules` (estate_attorney_tools.py) -- there is one shared state
fixture (data/state_rules.json) and one tool for it. This module deliberately
does not define a second state tool.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=None)
def _load(name: str) -> dict:
    return json.loads((_DATA_DIR / name).read_text())


GET_TAX_BRACKETS_SPEC = {
    "name": "get_tax_brackets",
    "description": (
        "Look up synthetic U.S. federal tax parameters for a tax year and filing "
        "status: ordinary-income and long-term capital-gains brackets, standard "
        "deduction, net investment income tax, additional Medicare tax, AMT, the "
        "estate/gift exclusion and rate, section 1202 (QSBS) rules, and "
        "retirement-account limits. Use this to ground any federal tax number -- "
        "never assert one from memory. For state income tax, trust taxation, and "
        "gift-completion timing, use get_state_trust_rules instead."
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


# exports for the Phase 0 tools.py aggregator
TAX_TOOLS = [GET_TAX_BRACKETS_SPEC]
TAX_TOOL_IMPLS = {"get_tax_brackets": get_tax_brackets}


if __name__ == "__main__":
    import pprint

    pprint.pp(get_tax_brackets(2026, "married_filing_jointly"))
    print()
    pprint.pp(get_tax_brackets(2030, "single"))
