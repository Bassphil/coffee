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

## Fixtures owned here

- `data/tax_brackets_2026.json` — everything `get_tax_brackets(year,
  filing_status)` returns. Synthetic, labeled. Internally consistent, not
  IRS-exact, by design.
- `data/state_rules.json` — **shared file**. Tax owns the `tax` sub-object of
  each state; `estate` / `trust_law` / `finance` sub-objects are `null` and
  belong to the other tracks. Returned by `get_state_rules(state)`.

## Planted conflicts (Layer 2 ground truth)

Each is guaranteed by fixture construction. The shared `data/profile.json` and
`data/portfolio.json` (owned by Phase 0 / advisor track) must contain the noted
fields or the conflict will not fire — see "Dependencies" below.

### C1 — trust funding timing vs. basis step-up  (tax_cpa ↔ estate_attorney)

- Fixture trigger: client domiciled in `CA` (`state_rules.CA.tax`:
  `taxes_nongrantor_trust_income_when` is fiduciary/beneficiary-residence based;
  no preferential LTCG rate) + net worth above the `$15M` exclusion in
  `tax_brackets_2026.json` so an estate-tax motive is real + a pre-IPO/founder
  position in `portfolio.json`.
- Attorney position: move shares into an irrevocable trust **before** the
  liquidity event to freeze value out of the estate.
- **tax_cpa gold position:** funding the trust pre-sale forfeits the death-time
  basis step-up on those shares and risks the QSBS holding-period / per-issuer
  analysis; quantify the estate-tax saving against the extra capital-gains cost
  before sequencing. `materiality: changes_action`.
- Expected `what_id_push_back_on[].target = "estate_attorney"`.

### C2 — diversify now vs. tax drag  (tax_cpa ↔ financial_advisor)

- Fixture trigger: `portfolio.json` holds a concentrated low-basis position
  (target ≈ 50%+ of net worth, basis ≈ 5–10% of value).
- Advisor position: sell down to a target concentration (e.g. 15%) now.
- **tax_cpa gold position:** realizing that gain costs ≈ 23.8% federal + state
  (`top_combined_ltcg_rate_federal` + `state_rules.<domicile>.tax`); stage over
  multiple years, hedge (collar / exchange fund), or gift appreciated shares to
  a donor-advised fund / CRT instead of a lump-sum sale. `materiality:
  changes_number` and `changes_action`.
- Expected `what_id_push_back_on[].target = "financial_advisor"`.

### C3 — lifetime gifting vs. hold-to-death  (tax_cpa ↔ estate_attorney)

- Fixture trigger: same estate-tax-exposed profile as C1.
- Attorney position: gift appreciated assets during life to use exclusion and
  remove future appreciation.
- **tax_cpa gold position:** lifetime gifts carry over the donor's basis
  (`estate_and_gift.lifetime_gift_basis_rule = "carryover"`); assets held to
  death get a step-up. For assets with large unrealized gain and heirs likely to
  sell, the income-tax cost of carryover basis can exceed the transfer-tax
  saving. `materiality: changes_action`.

## Dependencies on Phase 0 / other tracks

1. **Shared `SpecialistDraft` schema** (`schemas.py`) must include, at minimum:
   `recommendation`, `reasoning`, `key_numbers[]` (with a `source_tool` field so
   grounding is checkable), `cross_domain_implications[]`,
   `what_id_push_back_on[]` (with `target` + `claim` + `why`), `assumptions[]`,
   `open_questions[]` (with a `refer_to` professional), `confidence`.
2. **Tools** (`tools.py`, identical sorted list for all three personas):
   `get_client_profile`, `get_portfolio`, `get_state_rules`, `get_tax_brackets`,
   `get_prior_finding`. The persona scopes which it uses; it must not 400 if the
   others are present.
3. **`data/profile.json`** needs: `filing_status`, `state_of_domicile` (set to
   `"CA"` for the canned scenario), `approx_agi`, `net_worth`, `marital_status`.
4. **`data/portfolio.json`** needs the concentrated low-basis holding described
   in C2, and a founder/QSBS-eligible lot for C1 (acquisition date, basis,
   current value, `qsbs_candidate: true`).
5. **`specialists.py`** entry:
   `{"id": "tax_cpa", "display_name": "Tax CPA", "persona_file": "prompts/tax_cpa.txt"}`

## Not done yet

- Rebuttal behavior verification (Phase 3) — persona already names the two
  push-back triggers; needs the rebuttal schema wired.
- Hand-written gold memo answers for the canned scenarios (Layer 3).
- `data/scenarios.json` tax-relevant canned scenario(s).
- Coordinate `profile.json` / `portfolio.json` field names with the advisor
  track once Phase 0 lands.
