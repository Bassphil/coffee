"""Offline tests for the financial_advisor slice — no API calls.

Covers: tool determinism against the fixture, and a hand-written sample draft's shape against
the schema proposed in SCHEMA_PROPOSAL.md (a local check, not the eventual shared schemas.py).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from tools_financial_advisor import get_client_portfolio, get_market_assumptions  # noqa: E402

# Rough token-per-word ratio for English text; used only as an approximate budget check since
# no tokenizer is available offline. Not a substitute for a real token count once client.py exists.
APPROX_TOKENS_PER_WORD = 1.3
DRAFT_TOKEN_BUDGET = 600


def validate_specialist_draft(draft: dict) -> list[str]:
    """Minimal structural check against the SpecialistDraft shape in SCHEMA_PROPOSAL.md."""
    errors = []
    required_str_fields = ["domain_findings", "recommendation"]
    required_list_fields = [
        "cross_domain_implications",
        "what_id_push_back_on",
        "assumptions",
        "open_questions",
    ]
    for field in required_str_fields:
        if not isinstance(draft.get(field), str) or not draft[field].strip():
            errors.append(f"{field} must be a non-empty string")
    for field in required_list_fields:
        if not isinstance(draft.get(field), list):
            errors.append(f"{field} must be a list")
    for item in draft.get("cross_domain_implications", []):
        if not isinstance(item, dict) or "domain" not in item or "implication" not in item:
            errors.append(f"cross_domain_implications item malformed: {item!r}")
    for item in draft.get("what_id_push_back_on", []):
        if not isinstance(item, dict) or "domain" not in item or "concern" not in item:
            errors.append(f"what_id_push_back_on item malformed: {item!r}")
    return errors


def approx_token_count(draft: dict) -> int:
    words = 0
    for field in ("domain_findings", "recommendation"):
        words += len(str(draft.get(field, "")).split())
    for field in ("cross_domain_implications", "what_id_push_back_on"):
        for item in draft.get(field, []):
            words += len(" ".join(str(v) for v in item.values()).split())
    for field in ("assumptions", "open_questions"):
        for item in draft.get(field, []):
            words += len(str(item).split())
    return int(words * APPROX_TOKENS_PER_WORD)


SAMPLE_DRAFT = {
    "domain_findings": (
        "The client holds 61.5% of liquid net worth in a single pre-IPO employer-stock grant, "
        "well above the 60/30/10 target allocation. The position is QSBS-eligible once held to "
        "2027-03-01."
    ),
    "recommendation": (
        "Begin a staged diversification sale now rather than waiting for the QSBS date; "
        "concentration risk outweighs the tax benefit at this position size."
    ),
    "cross_domain_implications": [
        {
            "domain": "tax_cpa",
            "implication": "Selling before 2027-03-01 forfeits QSBS exclusion on ~$2.22M of gain.",
        }
    ],
    "what_id_push_back_on": [
        {
            "domain": "tax_cpa",
            "concern": "A hold-until-QSBS-date recommendation ignores concentration risk in the interim.",
        }
    ],
    "assumptions": ["Client can tolerate near-term realized gains outside the QSBS position."],
    "open_questions": ["Client's after-tax cash-flow needs over the next 12 months."],
}


def test_get_client_portfolio_is_deterministic_and_shaped():
    result = get_client_portfolio()
    assert result == get_client_portfolio()
    assert "holdings" in result and isinstance(result["holdings"], list)
    assert result["target_allocation"] == {"equities": 0.60, "diversifiers": 0.30, "cash": 0.10}
    assert abs(result["concentration_pct_of_liquid_net_worth"] - 0.6154) < 1e-3


def test_get_market_assumptions_known_asset_class():
    result = get_market_assumptions("equities")
    assert result["asset_class"] == "equities"
    assert "expected_return" in result and "volatility" in result


def test_get_market_assumptions_unknown_asset_class():
    result = get_market_assumptions("crypto")
    assert "error" in result
    assert "equities" in result["known_asset_classes"]


def test_sample_draft_matches_proposed_schema():
    errors = validate_specialist_draft(SAMPLE_DRAFT)
    assert errors == []


def test_sample_draft_within_token_budget():
    assert approx_token_count(SAMPLE_DRAFT) < DRAFT_TOKEN_BUDGET


def test_malformed_draft_is_rejected():
    bad = dict(SAMPLE_DRAFT)
    bad["cross_domain_implications"] = [{"domain": "tax_cpa"}]  # missing "implication"
    errors = validate_specialist_draft(bad)
    assert errors
