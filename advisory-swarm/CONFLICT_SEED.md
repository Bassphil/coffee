# Seeded conflict — concentrated position vs. QSBS holding period

For whoever owns `evals/tasks.py` (conflict-extraction ground truth) and the `tax_cpa` specialist.

## The fixture

`app/data/portfolio.json` gives the demo client a $2.4M pre-IPO employer-stock grant, acquired
2022-03-01, QSBS-eligible once held 5 years (2027-03-01). It's 61.5% of liquid net worth against
a 60/30/10 target allocation — well outside target.

## The conflict this is designed to produce

- **Topic:** diversification timing vs. QSBS eligibility
- **Type:** `recommendation`
- **Materiality:** `changes_action` (sell now vs. wait ~6 months) — not a framing difference, a
  genuine different-next-action disagreement, so it should survive the materiality gate.
- **financial_advisor position:** 61.5% concentration is a real risk against the stated target;
  recommends starting a staged diversification sale now rather than waiting on a single date.
- **tax_cpa position (teammate-owned):** selling before 2027-03-01 forfeits the QSBS exclusion on
  a $2.22M gain; recommends holding until the date passes, or structuring around it (10b5-1,
  installment sale, etc.).

## Why this one, specifically

Both positions are individually defensible and grounded in fixture data (concentration metric
from `get_client_portfolio()`, QSBS date from the same tool) — no fabrication needed on either
side, and the conflict is forced by the fixture's numbers rather than by prompt-level instruction
to disagree. This is what the Design Document calls "structurally guaranteed" conflicts, and it
doubles as this conflict's ground truth for the conflict-recall eval.

## Dependency

The 2027-03-01 QSBS date needs to line up with whatever QSBS/holding-period rule the tax_cpa
fixtures encode — flagging for that owner to confirm before this is wired into `evals/tasks.py`.
