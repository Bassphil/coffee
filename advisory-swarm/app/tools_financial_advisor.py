"""Financial-advisor mock tools over the seeded portfolio.json fixture.

Pure, deterministic functions over local JSON — no network, no state. Intended to merge into
the shared app/tools.py tool list once that file exists; TOOL_SCHEMAS/TOOL_IMPLS are kept in the
Anthropic tool-use shape so the merge is a dict/list concatenation, not a rewrite.
"""

import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


@lru_cache(maxsize=1)
def _portfolio() -> dict:
    return json.loads((DATA_DIR / "portfolio.json").read_text())


def get_client_portfolio() -> dict:
    """Return the client's holdings, target allocation, and concentration metrics."""
    data = _portfolio()
    return {
        "holdings": data["holdings"],
        "target_allocation": data["target_allocation"],
        "liquid_net_worth": data["liquid_net_worth"],
        "concentration_pct_of_liquid_net_worth": data["concentration_pct_of_liquid_net_worth"],
    }


def get_market_assumptions(asset_class: str) -> dict:
    """Return expected-return/volatility assumptions for one asset class."""
    assumptions = _portfolio()["market_assumptions"]
    if asset_class not in assumptions:
        return {
            "asset_class": asset_class,
            "error": f"no assumptions for '{asset_class}'",
            "known_asset_classes": sorted(assumptions),
        }
    return {"asset_class": asset_class, **assumptions[asset_class]}


TOOL_SCHEMAS = [
    {
        "name": "get_client_portfolio",
        "description": (
            "Get the client's current holdings, target allocation, and concentration risk "
            "metrics."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_market_assumptions",
        "description": (
            "Get expected return and volatility assumptions for one asset class "
            "(equities, concentrated_equity, diversifiers, cash)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "asset_class": {
                    "type": "string",
                    "description": "One of: equities, concentrated_equity, diversifiers, cash",
                }
            },
            "required": ["asset_class"],
        },
    },
]

TOOL_IMPLS = {
    "get_client_portfolio": lambda **kwargs: get_client_portfolio(),
    "get_market_assumptions": lambda **kwargs: get_market_assumptions(kwargs["asset_class"]),
}
