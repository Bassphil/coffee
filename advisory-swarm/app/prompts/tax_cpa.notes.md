# tax_cpa persona — build notes

Owner: tax track. This file is the contract between the tax persona and the
shared skeleton (Phase 0) + the other two personas. It is not sent to any model.

## What this persona is

One of the three fixed panel members (`financial_advisor`, `tax_cpa`,
`estate_attorney`). Loaded from `prompts/tax_cpa.txt` into `system[2]`, short and
unmarked for caching per the design doc. Model/effort come from the config dict
(`claude-sonnet-5`, adaptive thinking, `effort: medium` is the starting
hypothesis).

Standing bias: minimize **lifetime** tax, not the current-year bill. It diverges
from the advisor (who optimizes portfolio risk/return) and the attorney (who
optimizes transfer-tax exposure and control), which is what produces the
demo's conflicts.

## Files owned by the tax track

| File | Status | Notes |
|---|---|---|
| `prompts/tax_cpa.txt` | done | persona; emits `cross_domain_implications`, `what_id_push_back_on`, `open_questions` |
| `prompts/tax_cpa.notes.md` | this file | not sent to any model |
| `data/tax_brackets_2026.json` | done | all of `get_tax_brackets()`. Synthetic, internally consistent, not IRS-exact |
| `data/state_rules.json` | done (tax sub-objects) | **shared file** — `estate` / `trust_law` / `finance` sub-objects are `null`, owned by other tracks |
| `data/scenarios.json` | done (tax entry) | **shared file** — one entry, `tax_liquidity_event`; other tracks append |
| `tools_tax.py` | done | `get_tax_brackets` + `get_state_rules` impls & schemas; `TAX_TOOLS` / `TAX_TOOL_IMPLS` for the Phase 0 aggregator |
| `evals/tax_cases.py` | done | `ROUTER_LABELS` (L1), `PLANTED_CONFLICTS` (L2), `GOLD_MEMO_POINTS` (L3) |

## Planted conflicts (Layer 2 ground truth)

All three are structurally guaranteed by the `tax_liquidity_event` scenario in
`data/scenarios.json` (Jordan/Sam Reyes: CA domicile, ~$39M net worth, $22M
founder stock at $600K basis acquired 2022-03, acquisition closing 2026-Q1).
Full records — agents, positions, questions, materiality, required tool
grounding — live in `evals/tax_cases.py::PLANTED_CONFLICTS`.

- **C1 — trust funding before close** (tax_cpa ↔ estate_attorney), `sequencing`,
  `changes_action`. Push-back target `estate_attorney`: forfeited step-up + QSBS
  holding-period / per-issuer interaction; baseline is "hold to the 2027-03-10
  five-year mark and the federal gain may be fully excluded anyway."
- **C2 — diversify now vs. staged** (tax_cpa ↔ financial_advisor),
  `recommendation`, `changes_number`. Push-back target `financial_advisor`: a
  2026 sale is ~$8M of tax (23.8% federal + 13.3% CA on ~$21.4M gain); wait for
  QSBS, consider a pre-sale domicile change, hedge rather than sell early.
- **C3 — lifetime gift vs. hold-to-death** (tax_cpa ↔ estate_attorney),
  `recommendation`, `changes_action`. Carryover basis vs. step-up in dollar
  terms; gift cash / post-sale proceeds instead of the low-basis shares.

## Dependencies on Phase 0 / other tracks

1. **Shared `SpecialistDraft` schema** (`schemas.py`) must include, at minimum:
   `recommendation`, `reasoning`, `key_numbers[]` (with a `source_tool` field so
   grounding is checkable), `cross_domain_implications[]`,
   `what_id_push_back_on[]` (with `target` + `claim` + `why`), `assumptions[]`,
   `open_questions[]` (with a `refer_to` professional), `confidence`.
2. **`tools.py` aggregator** merges `tools_tax.TAX_TOOLS` into the single
   name-sorted tool list every specialist sees, and `TAX_TOOL_IMPLS` into the
   dispatch table. Also expected in that shared list (other tracks / Phase 0):
   `get_client_profile`, `get_portfolio`, `get_prior_finding`. The persona
   scopes which it calls; it must not 400 if the others are present.
3. **`data/profile.json` / `data/portfolio.json`** — the canned scenario carries
   its own `profile` / `portfolio` inline, so these shared defaults are not
   blocking. When they land, reconcile field names (the scenario uses
   `state_of_domicile`, `filing_status`, `net_worth`, `cost_basis`,
   `current_value`, `qsbs_candidate`).
4. **`specialists.py`** entry:
   `{"id": "tax_cpa", "display_name": "Tax CPA", "persona_file": "prompts/tax_cpa.txt"}`
5. **`evals/tasks.py` aggregator** imports the three lists from
   `evals/tax_cases.py` and merges them with the legal / finance tracks'
   equivalents. Router set target is ~30 labeled turns total; tax contributes 10.

## Not done yet

- Rebuttal-context check (Phase 3): confirm the persona behaves when it sees
  only a counterpart's quoted span + its own draft, not the full draft.
- Second/third canned scenarios (legal- and finance-led) — not tax's to write,
  but C1/C3 need the estate_attorney persona to actually take the trust-first
  position for the conflict to fire.
- `get_prior_finding` multi-turn behavior once the tool exists.
- Persona length is ~300 tokens; trim if the shared prefix budget gets tight.
