# tax_cpa persona — build notes

Owner: tax track. The contract between the tax persona and the shared skeleton
(Phase 0) + the other two personas. Not sent to any model.

## What this persona is

One of the three fixed panel members (`financial_advisor`, `tax_cpa`,
`estate_attorney`). Loaded from `prompts/tax_cpa.txt` into `system[2]`, short and
unmarked for caching. Model/effort from the config dict (`claude-sonnet-5`,
adaptive thinking, `effort: medium` is the starting hypothesis).

Standing bias: minimize **lifetime** tax, not the current-year bill. It diverges
from the advisor (portfolio risk/return) and the attorney (transfer-tax exposure
and control), which is what produces the demo's conflicts.

## Reconciliation with the estate-attorney track (merged to main, PRs #1–2)

The estate track shipped structural choices first; the tax track conforms to
them. Decisions made in this branch:

| Concern | Resolution |
|---|---|
| `data/state_rules.json` shape | Adopted the estate track's flat top-level keys (`"California"`, `"Nevada"`, `"federal"`, read by `get_state_trust_rules`). Their entries are unchanged; the tax track adds a `tax_detail` object per state and the states `Florida` / `New York` / `Texas` / `Washington`. |
| federal lifetime gift exemption | Was $13.99M (estate) vs $15M (tax). Harmonized to **$15M** (OBBBA-2026) in both `state_rules.json` and `tax_brackets_2026.json`. |
| state tool | One tool: **`get_state_trust_rules`** (theirs). The tax track does **not** define a second state tool. Their impl takes full state names ('California'), so tax code uses full names too; Phase 0 can add two-letter-code normalization if desired. |
| tool location | `app/tools/tax_cpa_tools.py` (matches their `app/tools/estate_attorney_tools.py`). Provides only `get_tax_brackets`. |
| draft schema | Conformed persona + grader + samples to the estate track's `SPECIALIST_DRAFT_SCHEMA` (`app/schemas/estate_attorney.py`). |
| canned scenario | Their standalone fixture `client_profile_sample.json` folded into `data/scenarios.json` as `business_sale_pre_loi` with planted conflict **c4**. |
| `requirements.txt` | Restored at repo root (their `run_estate_attorney.py` depends on it). |

## Files owned / touched by the tax track

| File | Status | Notes |
|---|---|---|
| `prompts/tax_cpa.txt` | done | persona; fills `domain_findings.basis`, `cross_domain_implications`, `what_id_push_back_on`, `open_questions` (estate schema) |
| `prompts/tax_cpa.notes.md` | this file | — |
| `data/tax_brackets_2026.json` | done | all of `get_tax_brackets()`; synthetic, internally consistent |
| `data/state_rules.json` | done | **shared** — see reconciliation table; tax owns `tax_detail` + FL/NY/TX/WA |
| `data/scenarios.json` | done | **shared** — `tax_liquidity_event` (tax) + `business_sale_pre_loi` (estate, folded in) |
| `tools/tax_cpa_tools.py` | done | `get_tax_brackets` impl + spec; `TAX_TOOLS` / `TAX_TOOL_IMPLS` for the Phase 0 aggregator |
| `evals/tax_cases.py` | done | `ROUTER_LABELS` (L1, 11 turns), `PLANTED_CONFLICTS` (c1–c4, L2), `GOLD_MEMO_POINTS` (L3) |
| `evals/tax_grader.py` | done | Layer-3 grader on `completion` + `subject_integrity`; deterministic + batched PASS/FAIL judge; `SAMPLE_DRAFTS`, discrimination smoke test |

## Planted conflicts (Layer 2 ground truth)

Full records in `evals/tax_cases.py::PLANTED_CONFLICTS`.

**`tax_liquidity_event`** (Jordan/Sam Reyes: CA, ~$39M net worth, $22M founder
stock at $600K basis acquired 2022-03, acquisition closing 2026-Q1):

- **c1 — trust funding before close** (tax_cpa ↔ estate_attorney), `sequencing`,
  `changes_action`. Forfeited step-up + QSBS holding-period interaction; baseline
  is "hold to the 2027-03-10 five-year mark and the federal gain may be fully
  excluded anyway."
- **c2 — diversify now vs. staged** (tax_cpa ↔ financial_advisor),
  `changes_number`. A 2026 sale is ~$8M of tax (23.8% federal + 13.3% CA on a
  ~$21.4M gain); wait for QSBS, consider a pre-sale domicile change, hedge rather
  than sell early.
- **c3 — lifetime gift vs. hold-to-death** (tax_cpa ↔ estate_attorney),
  `changes_action`. Carryover basis vs. step-up in dollar terms.

**`business_sale_pre_loi`** (estate track's scenario — Dana Whitfield, CA,
single, $4M business, $50K basis, no LOI yet):

- **c4 — trust funding timing vs. the LOI** (tax_cpa ↔ estate_attorney),
  `sequencing`, `changes_action`. tax_cpa wants to wait for a fixed price
  (valuation certainty) and floats a Nevada situs; estate_attorney flags
  step-transaction risk (fund before any LOI) and the California DING/NING
  carve-out (Nevada situs doesn't help a CA resident). Resolution sides with the
  attorney. Fires off the persona's "don't rush appreciated property into a
  trust" + "a non-grantor trust has its own situs" reflexes.

## Dependencies on Phase 0 / other tracks

1. **Shared draft schema** — adopt the estate track's `SPECIALIST_DRAFT_SCHEMA`
   into `schemas.py`. One open item: the `domain` enum in
   `cross_domain_implications` / `what_id_push_back_on` is per-specialist (it
   lists the *other two* seats), so the three copies are not byte-identical —
   Phase 0 decides whether that's fine or the enum should be all three.
2. **`tools.py` aggregator** merges `tax_cpa_tools.TAX_TOOLS` and
   `estate_attorney_tools`' spec into one name-sorted list every specialist
   sees, plus `get_client_profile` / `get_portfolio` / `get_prior_finding`.
3. **`data/profile.json` / `data/portfolio.json`** — both canned scenarios carry
   their `profile` / `portfolio` inline, so shared defaults are not blocking.
   Field names in use: `state_of_domicile`, `filing_status`, `net_worth`,
   `cost_basis`, `current_value`, `qsbs_candidate`.
4. **`specialists.py`** entry:
   `{"id": "tax_cpa", "display_name": "Tax CPA", "persona_file": "prompts/tax_cpa.txt"}`
5. **`evals/tasks.py` aggregator** imports the three lists from `tax_cases.py`
   and merges with the legal / finance equivalents (~30 router turns total; tax
   contributes 11).
6. **`evals/tax_grader.py`** needs (a) a `judge(system, user, schema) -> dict`
   callable wrapping `client.py`'s FAST_MODEL, passed via `context["judge"]`;
   (b) an ordered-actions field on the draft schema (`recommended_actions[]` or
   `action_plan[]`) to make `completion.actions_sequenced` deterministic — it
   falls back to sequencing-language detection. `KNOWN_ANTIFACTS` is keyed per
   scenario; add a block per new tax scenario.

## Not done yet

- Rebuttal-context check (Phase 3): persona behavior when it sees only a
  counterpart's quoted span + its own draft.
- `get_prior_finding` multi-turn behavior once the tool exists.
- Once `session.py` exists: point `run_estate_attorney.py` at the
  `business_sale_pre_loi` scenario entry and delete `client_profile_sample.json`.
- Persona is ~300 tokens; trim if the shared prefix budget gets tight.
