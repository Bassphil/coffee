"""Live sanity check for the financial_advisor persona — no orchestrator/client.py needed.

Runs the persona directly against Sonnet 5 with its two tools, on the seeded concentrated-
position scenario, then in rebuttal mode against only a quoted CPA span. Reads
ANTHROPIC_API_KEY from advisory-swarm/.env or the environment. Manual/CI-optional check, not
part of the offline test suite.

Usage: python scripts/smoke_financial_advisor.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from specialist_runner import run_draft, run_rebuttal  # noqa: E402

SCENARIO = (
    "Client scenario: significant concentration in a single pre-IPO employer-stock grant. "
    "Pull the portfolio and market assumptions, then give your recommendation."
)

REBUTTAL_QUESTION = (
    "Should the client begin selling the concentrated position now, or wait for the QSBS date?"
)
CPA_QUOTE = (
    "Selling any portion of the position before 2027-03-01 forfeits the QSBS exclusion on "
    "approximately $2.22M of gain, so the client should hold until the date passes."
)


def main():
    print("=== Draft mode ===")
    tool_log = []
    draft = run_draft(SCENARIO, tool_log=tool_log)
    for call in tool_log:
        print(f"  [tool_call] {call['tool']}({call['input']})")
    print(json.dumps(draft, indent=2))
    assert draft["cross_domain_implications"], "expected non-empty cross_domain_implications"
    assert draft["what_id_push_back_on"], "expected non-empty what_id_push_back_on"
    print("OK: cross-domain fields populated.\n")

    print("=== Rebuttal mode (quoted span only, no full draft) ===")
    rebuttal = run_rebuttal(REBUTTAL_QUESTION, CPA_QUOTE)
    print(json.dumps(rebuttal, indent=2))
    assert rebuttal["position"] in ("hold", "concede", "qualify")
    print(f"OK: structured rebuttal with position={rebuttal['position']!r}.")


if __name__ == "__main__":
    main()
