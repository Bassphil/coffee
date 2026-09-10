# estate_attorney specialist — handoff

Status: **built and verified standalone**, live against `claude-sonnet-5`. Not yet
wired into an orchestrator, because none exists yet — see [Design Document](../Design%20Document.md)
for the full system spec this was built against.

## What's here

```
advisory-swarm/
  app/
    prompts/estate_attorney.txt          persona (system[2] block)
    data/state_rules.json                synthetic state/federal trust+tax fixture
    data/client_profile_sample.json      sample client for the standalone harness
    schemas/estate_attorney.py           SPECIALIST_DRAFT_SCHEMA + REBUTTAL_SCHEMA
    tools/estate_attorney_tools.py       get_state_trust_rules tool + impl
  run_estate_attorney.py                 standalone harness (no orchestrator needed)
  ESTATE_ATTORNEY_HANDOFF.md             this file
```

Run it:
```bash
cd advisory-swarm
python3 -m venv .venv && ./.venv/bin/pip install -r ../requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."
./.venv/bin/python run_estate_attorney.py
```
(A local `.venv` is recommended — this machine's global Python had an
incompatible pydantic/pydantic-core pair that broke the `anthropic` import.
If a teammate hits `SystemError: installed pydantic-core version is
incompatible`, this is why.)

It prints a draft, then a rebuttal against a fabricated `tax_cpa` quote, and
warns if the rebuttal conceded outright.

## The guaranteed conflict this specialist is seeded for

Per the Design Doc, canned scenarios must **structurally guarantee** a
cross-domain conflict. This specialist's half of it:

- **Client:** selling a business for $4M, California resident, QSBS-eligible
  stock, no LOI signed yet (expected in 4–6 weeks). (`data/client_profile_sample.json`)
- **The tension:** a CPA optimizing for gift-tax valuation certainty will
  want to fund a trust *after* the LOI is signed and price is fixed. That's
  exactly backwards — `state_rules.json["federal"].step_transaction_risk_note`
  says the IRS can collapse a gift made after a binding-or-near-binding
  agreement, so the trust has to be funded *before* any LOI exists.
- **A second, independent angle:** `state_rules.json["California"]` notes
  that CA taxes DING/NING-style trust income back to a CA-resident grantor
  regardless of situs — so a Nevada/Delaware trust proposed to dodge state
  income tax likely doesn't work at all for this client.
- Verified live: the model actually reasons through this correctly (grounds
  every number in the tool, holds position on rebuttal instead of folding,
  and separately notices the $10M single-holder QSBS exclusion already
  covers the ~$3.95M gain, so stacking isn't even necessary — a legitimate
  third angle worth keeping if you're writing the conflict-extraction eval's
  ground truth).

**If you're building tax_cpa:** for this scenario to produce the planted
conflict, tax_cpa's draft needs to actually propose funding a trust
*after* the LOI/price is fixed (for valuation-certainty reasons) and/or
propose a Nevada/Delaware situs trust for CA income tax savings. Otherwise
there's nothing for estate_attorney to push back on and the "0 conflicts"
failure mode the Design Doc warns about will hit this scenario.

## What I'm assuming from your shared modules (please reconcile, don't silently diverge)

- **`schemas.py`** — I defined `SPECIALIST_DRAFT_SCHEMA` and `REBUTTAL_SCHEMA`
  in `app/schemas/estate_attorney.py`, meant to be identical across all three
  specialists per the Design Doc. Adopt these into the real `schemas.py`, or
  tell me if you've already picked a different shape so I can conform instead
  of shipping a third copy.
- **`tools.py`** — `get_state_trust_rules` needs to go into the shared,
  name-sorted tool list every specialist receives (per the Design Doc, tool
  *availability* is identical across specialists; only the persona/prompt
  scopes usage). Don't leave it estate_attorney-only or you'll invalidate the
  cache prefix when specialists' tool sets diverge.
- **`specialists.py`** — expects an entry like
  `{"id": "estate_attorney", "display_name": "Estate Planning Attorney", "persona_file": "prompts/estate_attorney.txt"}`.
- **System block ordering** — my persona file is *only* the system[2]
  content (short, no cache_control, per the Design Doc). system[0] (house
  method + memo contract + tool rules) and system[1] (profile + standing-memo
  digest) are stubbed inline in `run_estate_attorney.py`
  (`STUB_HOUSE_METHOD`, `STUB_SESSION_BLOCK`) — replace those call sites with
  the real orchestrator once it exists; don't merge the stubs themselves.
- **Rebuttal isolation** — my rebuttal call only ever receives the
  counterpart's quoted span + my own draft, never a full opposing draft.
  Keep it that way when this gets wired into the real conflict/rebuttal
  phase — the Design Doc calls this out as load-bearing against capitulation.

## API shapes verified live in this session (claude-sonnet-5)

Useful if you're writing `client.py`:
- `thinking={"type": "adaptive"}` + `output_config={"effort": "medium", "format": {"type": "json_schema", "schema": {...}}}` — confirmed working shape.
- `system` must be `[{"type": "text", "text": "..."}, ...]`, not raw strings — a bare string list 400s.
- Every `object` node inside an `output_config.format` schema needs `"additionalProperties": false` explicitly, including nested array-item objects, or the API 400s.
- `max_tokens=1200` was too low and silently truncated to a `thinking`-only response (`stop_reason: max_tokens`, no text block) — bumped to 4096 for draft/rebuttal calls. Budget accordingly once real per-phase token caps are set.

## Not done / not my scope

Orchestrator, real `schemas.py`/`tools.py`/`specialists.py`/`session.py`,
routing, SSE, admin screen, the other two specialists, conflict extraction,
quote validation, evals. This is one specialist's slice only.
