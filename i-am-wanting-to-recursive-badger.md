# Multi-Agent Financial Advisory Swarm — Development Plan

## Context

Real financial decisions cross domains that no single professional owns. A client gets a
recommendation from a financial advisor, then has to independently consult a CPA and an estate
attorney — and the three answers rarely compose cleanly. The client is left reconciling
contradictory expert advice with no expertise of their own. That reconciliation is the actual
work, and today nobody does it.

We are building a demo that does it: the user describes a scenario in a chat box, a supervisor
dispatches all three domain specialists — financial advisor, CPA, estate attorney — who draft in
parallel, the supervisor surfaces where they **actually disagree**, the conflicting specialists
respond to each other, and the supervisor returns one integrated memo with the tradeoffs made
explicit.

**Intended outcome:** a self-contained prototype, runnable from one command, that a stakeholder
can drive live in a browser. The demo-able moment is not "three agents answered" — it is *"here
is where your CPA and your attorney disagree, and here is how we resolved it."* Everything here
is subordinate to making that moment land.

**Second, equally load-bearing goal:** the system must be *measurable*. Five routes each have a
model and effort choice, and the plan's assignments are currently guesses. An eval harness that
scores quality per layer and gates cost optimization behind it is what turns those guesses into
decisions — and an admin screen makes that visible rather than terminal-only.

**Not in scope:** real advice, real client data, authentication, persistence beyond process
memory, production deployment.

---

## Confirmed decisions

| Decision | Choice |
|---|---|
| Deliverable | Standalone demo prototype, new top-level `advisory-swarm/` |
| Backend | FastAPI + `AsyncAnthropic`, SSE streaming |
| Frontend | Two hand-written pages, no build step: `web/index.html`, `web/admin.html` |
| Routing | **Two tiers** — `direct` (Haiku, no specialists) or `swarm` (fixed panel of 3) |
| Cross-talk | Parallel drafts → conflict extraction → targeted rebuttal → synthesis |
| Grounding | Mock tools over seeded JSON fixtures; no web search |
| Intake | Free-text scenario + editable synthetic client-profile panel |
| Output | Live agent activity, then a structured memo |
| Session | Multi-turn, in-memory, cost-aware |
| Evaluation | **Full: 4 graded layers + gated composite score + config sweep** |
| Admin | **Second screen — live agent monitoring, evals, usage/cost** |
| Demo safety | Record every run to JSONL; `--replay` plays it back through the same endpoint |
| Team | **Solo** — phasing is sequential, not parallel tracks |

### Why two tiers, not three — and why a fixed panel, not dynamic routing

An earlier draft had `direct` / `single` / `swarm` with a valve letting a single specialist
escalate itself, plus a 5-specialist registry the supervisor picked a subset from per turn. Both
are cut. Reasoning:

**No escalation tier.** The middle `single` tier and its promotion valve created an orphaned-draft
problem (work discarded on promotion) and a re-promotion loop risk, for a cost saving the `direct`
tier already captures. Deleting it removes a module and a failure mode for free.

**No dynamic roster.** With only three domains in play, subset selection buys little — skipping
one of three agents is a small cost win — while it actively works against the demo's thesis. The
whole point is showing where a financial advisor, a CPA, and an estate attorney disagree; a
partial roster risks landing on a pairing that surfaces no conflict at all, undermining the
centerpiece for the sake of a marginal saving. **Every swarm turn dispatches all three specialists
together**, every time. The router's only job is `direct` vs. `swarm` — it no longer picks who's in
the room.

**Mis-tiering is asymmetric.** A false `swarm` costs ~30¢. A false `direct` silently skips the
entire value proposition on the highest-liability content. So `direct` is not a peer of `swarm`:
it requires a **positive match against an enumerated allowlist** (greeting, definition of a term,
restate/reformat request, question answerable verbatim from the standing memo). Everything else
defaults up. The router eval weights this asymmetry explicitly.

---

## Architecture

### Turn lifecycle

```
user turn
  └─ ROUTE (Haiku 4.5, structured output, single call)
       ├─ tier=direct → answer already in the routing response → stream → done
       └─ tier=swarm  → panel: [financial_advisor, tax_cpa, estate_attorney]  (fixed, every time)
            ├─ PHASE 1  drafts, all 3 specialists in parallel (asyncio.gather)
            ├─ PHASE 2  conflict extraction (supervisor sees all full drafts)
            │            └─ zero conflicts → skip Phase 3
            ├─ PHASE 3  rebuttal — only conflicting agents, in parallel, one round
            └─ PHASE 4  synthesis → memo (turn 1) or memo patch (turn 2+)
```

### The load-bearing architectural constraint

**`run_turn(query, profile, config, sink) → TurnResult` must be importable and runnable with no
FastAPI and no HTTP in the loop.** The eval harness drives this function directly; the server is
just one caller. This has to be true from the first commit — retrofitting it means untangling the
orchestrator from the event emitter.

The mechanism is an **injected event sink**, not an `eval_mode` flag:

```python
# server passes an SSE queue sink; eval passes a collector; replay passes a file writer
async def run_turn(query, profile, config, sink: EventSink) -> TurnResult
```

Same code path in every mode, no branching on caller. `TurnResult` carries the memo, all events,
per-phase `usage`, per-phase wall clock, and the resolved config — everything the graders and the
admin screen need. This single decision is what makes the eval framework, the admin screen, and
replay mode all fall out of one implementation.

### Routing and the direct-answer merge

Route and direct-answer are **one Haiku call**, not two. Splitting them puts a full round trip of
dead air in front of every turn, including "hi".

```jsonc
{
  "tier": "direct" | "swarm",
  "reason": "...",                                   // shown in the HUD
  "missing_facts": ["state of residence"],
  "direct_answer": "..."                             // populated only when tier=direct
}
```

No `roster` field — when `tier=swarm`, all three specialists always run. The router's only
decision is `direct` vs. `swarm`.

Two rules enforced **in code, not in the prompt**:

1. **Any profile-panel edit disqualifies `direct` for the next turn** and marks the standing memo
   stale. Otherwise you demo an edit to net worth and get a Haiku answer off the old number.
2. The router receives a compact state header — does a standing memo exist, what `open_questions`
   remain, **what changed in the profile since last turn**. Without it, "what about California?"
   routes `direct` every time.

Give the direct answerer an explicit **abstain** path so a bad route is recoverable one hop later
rather than at synthesis time. The UI carries an `Auto / Force swarm / Force direct` toggle — a
live mis-route is more embarrassing than an unused control.

### Conflict representation — the quality crux

Prose conflicts produce mush. Use anchored, typed records:

```jsonc
{
  "id": "c1",
  "topic": "trust funding timing vs. QSBS eligibility",
  "type": "recommendation" | "factual" | "sequencing" | "assumption" | "emphasis",
  "positions": [
    {"agent": "tax_cpa",        "quote": "<verbatim span from that agent's draft>"},
    {"agent": "estate_attorney","quote": "<verbatim span>"}
  ],
  "question": "<the single question both agents must answer>",
  "materiality": "changes_action" | "changes_number" | "framing_only"
}
```

- **`quote` is validated in Python.** Substring-check each quote against its source draft and
  **drop any conflict whose quotes don't match**. Cheapest reliable hallucination guard available,
  fully deterministic, and it feeds a real admin metric: *"3 candidates, 1 dropped — unverifiable
  quote."*
- **`materiality` gates the rebuttal.** A conflict is real only if the drafts imply **different
  next actions or different numbers**. `framing_only` never triggers a rebuttal. Cap at **top 3**.

**Specialists must NOT see each other's full drafts.** A rebutting specialist gets only: the
conflict `question`, the counterpart's **verbatim quoted span**, and its own full draft. This is
not primarily token economy — full drafts cause *capitulation*. Shown a confident adjacent
expert's complete argument, a specialist defers, the conflict evaporates, and the demo shows a
fake resolution where the tension used to be. The **supervisor** gets full drafts; specialists get
the contested span.

Rebuttal is structured, one round, both sides in parallel, neither seeing the other's:

```jsonc
{"position": "hold" | "concede" | "qualify", "reasoning": "...",
 "condition_under_which_other_is_right": "...", "revised_recommendation": "..."}
```

**Plan for the empty conflict list** — if specialists stay in their lane, nobody contradicts
anybody and the centerpiece reports "0 conflicts" in front of an audience. All three required:

1. **Seed fixtures so conflicts are structurally guaranteed** for the canned scenarios — a state
   rule making trust-first attractive for tax while creating estate exposure; a concentrated
   illiquid position. *This also gives the conflict eval its ground truth.*
2. Every draft emits structured `cross_domain_implications` and `what_id_push_back_on`.
3. The extractor reads **those structured sections**, not free prose.

"No conflicts" must be an explicit structured decision with a rationale — never a bare empty
array, which is indistinguishable from a parse failure.

---

## Model and cost policy

**Treat this table as the starting hypothesis, not settled fact.** The sweep exists to test it.

| Route | Model | Config |
|---|---|---|
| Routing + direct answer | `claude-haiku-4-5` | `thinking: {type:"enabled", budget_tokens:N}` |
| Specialist drafts | `claude-sonnet-5` | `thinking: {type:"adaptive"}`, `effort: "medium"` |
| Conflict extraction | `claude-sonnet-5` | `effort: "high"` |
| Rebuttal | `claude-sonnet-5` | `effort: "medium"` |
| Synthesis | `claude-opus-5` | `effort: "high"` |

Every route's model and effort must be **overridable from a config dict** — that is the sweep's
input surface. Hardcoding any of them kills the eval framework.

Load-bearing API facts, verified against the current reference — do not re-derive from memory:

- **Haiku 4.5 rejects `output_config.effort` with a 400** and still takes
  `thinking: {type:"enabled", budget_tokens:N}`. Sonnet 5 / Opus 5 reject `budget_tokens` with a
  400 and take `{type:"adaptive"}` + `effort`. **A shared `_call()` helper passing `effort`
  uniformly will 400 on the routing call — branch in `client.py`.**
- **Pricing (first-party):** Sonnet 5 **$2/$10** per MTok, Opus 5 **$5/$25**, Haiku 4.5 **$1/$5**.
  The repo's `ui_runner.py` table prices Sonnet at $3/$15 — that is the **Sonnet 4.6 rate and is
  stale.** Copy the table, then fix it.
- **`PRICING` must be keyed by the unprefixed model name.** Under Bedrock,
  `_model("claude-sonnet-5")` → `"anthropic.claude-sonnet-5"`, which `KeyError`s against the repo's
  table. Strip the prefix on lookup.
- Label cost readouts "est., first-party API rates" — Bedrock is partner-priced separately.
- **Caches are model-scoped**, so the cascade forfeits cross-tier reuse. Acceptable (see below).

Hard per-turn budget with graceful degradation: the panel is fixed at 3 specialists (no cap logic
needed), max 6 tool-loop iterations per specialist, token ceiling, and a per-specialist timeout
whose expiry emits `degraded` and synthesizes from partial results rather than failing the turn.

Set `max_retries` explicitly and **surface retries as events** — three parallel Sonnet calls can
still trip org rate limits, and the SDK's default backoff silently adds 10–30s that looks like a hang.

### Prompt caching — a latency lever, not a cost lever

"The first specialist writes the cache, the rest read at 0.1×" is **false under parallel fan-out**,
and this is documented: *a cache entry becomes readable only after the first response begins
streaming.* N parallel requests with an identical prefix all pay the **1.25× write** and none read.
Implemented naively, caching here is a 25% surcharge that returns nothing.

Do the arithmetic before investing: 4K shared prefix × 3 specialists, ideal caching saves roughly a
**cent or two per swarm turn.** Under a dollar across a whole demo session.

- **Do not** implement the serialize-then-fan-out dance. Buys $0.02, costs seconds of wall clock.
- **Do** pre-warm once per session with `max_tokens: 0` against the same `system`/`tools`; re-warm
  when the profile is edited. **The pre-warm must not carry `output_config.format` or
  `stream: true`** — both are rejected with `max_tokens: 0`.
- **Give every specialist an identical tool list, sorted by name**, scoping usage by prompt
  instruction. Tools render at position 0, and a tool-set change is the one change forcing a full
  rebuild of every cache tier. Per-specialist tool sets destroy the prefix before the shared system
  block is reached.
- Serialize fixture JSON with `sort_keys=True`. Unsorted `json.dumps` is a classic silent invalidator.
- **Do not mark the Haiku routing prompt.** Cacheable minimums are **not monotonic**: Sonnet 5 and
  Opus 4.8 are 1024, Opus 5 is 512, **Haiku 4.5 is 4096**. The routing prompt is under that, so the
  marker is dead code — `cache_creation_input_tokens: 0` there is correct, not a bug.

Block ordering (uses 2 of 4 breakpoints):

```
tools:     identical across specialists, sorted by name          <- position 0
system[0]: static house method + memo contract + tool rules       [cache_control]
system[1]: session block — profile + standing-memo digest         [cache_control]
system[2]: persona — short, divergent, NO cache_control
messages:  the assignment / conflict question
```

Persona is deliberately unmarked: marking it writes four distinct entries for ~200 tokens each — a
surcharge, not a saving. Profile lives in `system[1]` because it is user-editable; ahead of the
static block, every panel edit would invalidate everything.

**Fixtures live behind tools, never in the system prompt.** Inlining them would contradict the
grounding design: the specialist already has the answer, stops calling tools, and the tool-call
activity feed goes silent. The prefix carries the **method**; the data stays behind tools.

---

## Evaluation framework

The system has a configuration space and, without this, no way to explore it. Verification tells
you the pipeline runs; evaluation tells you whether a change helped. Quality here is **not one
number** — a change can improve memo prose while destroying conflict recall (extraction gets
conservative, finds fewer conflicts, the memo reads *more* fluent because it has less tension to
reconcile, and the centerpiece quietly dies). A single aggregate would hide that. Score per layer.

### Four graded layers

| # | Layer | Method | Ground truth | Cost to run |
|---|---|---|---|---|
| 1 | **Router** | Classification | ~30 hand-labeled turns → gold `tier` | Near-free (Haiku) |
| 2 | **Conflict extraction** | Recall / precision | Planted conflicts in the seeded fixtures | Moderate |
| 3 | **Memo quality** | LLM judge, rubric | Hand-written gold answers for canned scenarios | Moderate |
| 4 | **Cost + latency** | Measurement | Baseline config | Free (rides along) |

**Layer 1 — Router.** Binary tier accuracy (`direct` vs. `swarm`) — no roster dimension, since the
panel is fixed. **Weight false-`direct` far heavier than false-`swarm`** — the asymmetry is stated
in the architecture but nothing enforces it until a grader does. Cheapest suite, highest
regression-guard ROI; run it on every change.

**Layer 2 — Conflict extraction.** Gradeable *precisely because* we seed fixtures deliberately —
ground truth is known by construction. Score **recall** against planted conflicts and **precision**
via quote-validation drop rate plus a judge on materiality of survivors. **If recall drops below
~0.80 the demo is broken regardless of how good the memo reads.**

**Layer 3 — Memo quality.** Judge rubric dimensions separately: every conflict gets an explicit
resolution; action plan sequences correctly; `open_questions` route to the right professional;
nothing asserted outside the fixtures.

**Layer 4 — Cost + latency.** Per-turn tokens, dollars, p50/p95 wall clock, **and a per-phase
breakdown** so you can see which phase eats the budget.

### The honest caveat on LLM judging

The judge shares a model family with the synthesizer and will tend to ratify its reasoning.
**Judge structure and grounding, not correctness:** did every number trace to a tool result? did
every flagged conflict get a resolution? is anything asserted that isn't in the fixtures? Those
are checkable. *"Is this good tax advice?"* is not, and a judge claiming to answer it gives false
confidence. For seeded scenarios, hand-write gold answers — you built the fixtures, so you know
the right answer. Use `FAST_MODEL` for the judge with a `PASS`/`FAIL` enum schema, matching the
existing pattern in day2/01.

### Composite score — gate, then optimize

Adapted directly from [`engagement_score()`](day2/02_inference-optimization/ui_runner.py#L606):

```
quality_gate = router_acc ≥ 0.90 AND conflict_recall ≥ 0.80 AND memo_judge ≥ 0.85
score        = 0 if not quality_gate
               else 50*(base_cost/cost) + 50*(base_p50/p50)
```

The gate-then-optimize structure is the important part: **it makes cost reduction inadmissible
unless quality holds**, which is what stops "make it cheaper" from silently becoming "make it
worse." Baseline is the first all-Sonnet config; every later config scores relative to it.

Report a **rate over `num_runs=3`, not a pass** — the swarm is nondeterministic, and a single run
is noise. This follows the `run_eval(..., num_runs=5)` precedent in
[Diagnose_Fix_Brief.py:666-960](day1/04_diagnosing-ai-problems/Diagnose_Fix_Brief.py#L666-L960).

### Config sweep

`sweep` runs a config matrix and prints/renders the Pareto frontier. This is what actually answers
the three open questions the model table only guesses at:

- Is Haiku good enough at routing, or does it under-call `direct` and cost 10× per turn?
- Does extraction need Sonnet at `high`, or does Haiku find the same planted conflicts for a fifth?
- Does Opus 5 synthesis measurably beat Sonnet 5, or is that 2.5× invisible to the room?

Hold a **held-out scenario set** back from tuning, following the existing `HOLDOUT_TASKS` /
`HOLDOUT_GOLD` convention — otherwise the sweep overfits to the demo scenarios.

**Print the projected cost before running.** A sweep is a few hundred swarm turns and real money.
Run the router suite on every change; run the full sweep only at decision points.

### Reuse

Nearly all the machinery exists in the repo:

- [Building_an_Eval.ipynb](day2/01_evals/Building_an_Eval.ipynb) — `GRADER_REGISTRY`, the
  `fn(result, check, context) → {score, reason}` grader signature, `run_eval(agent_fn, tasks,
  num_runs, max_workers)` with `ThreadPoolExecutor`, and the deliberate data-only return with
  separate `print_summary` / `save_results`. Results already land in `eval_results/`.
- [ui_runner.py:92-112, 606](day2/02_inference-optimization/ui_runner.py#L92-L112) —
  `engagement_score()`, `PRICING` / `calculate_cost`, and the baseline-state-on-disk pattern.
- [Diagnose_Fix_Brief.py:666-960](day1/04_diagnosing-ai-problems/Diagnose_Fix_Brief.py#L666-L960) —
  rate-not-pass reporting and `runs.jsonl` score history across sessions.

**`runs/*.jsonl` traces are also eval fixtures.** Every recorded run is a candidate regression
case — one artifact serving demo insurance, debugging, and eval corpus.

---

## Admin screen (`/admin` → `web/admin.html`)

A second page for monitoring the agents, the evals, and the spend. No auth — localhost demo only;
say so in the README.

**Design principle: the admin screen renders the same structures the eval harness and orchestrator
already produce.** No parallel data path. If a number isn't in `TurnResult`, `runs.jsonl`, or
`eval_results/`, it doesn't belong on the screen until it is.

### Panel 1 — Live agent monitor

- Active runs table: `run_id`, tier, current phase, elapsed, tokens so far.
- Per-specialist state chips: idle / drafting / tool-calling / rebutting / done / **degraded**.
- **Raw event tail** — the SSE stream scrolling live. Unglamorous and the single most useful thing
  on the page when something misbehaves mid-demo.
- Retry + rate-limit indicator, so a 20-second backoff reads as backoff and not as a hang.

### Panel 2 — Evaluation

- Run buttons per suite: `router` / `conflict` / `memo` / `full` / `sweep`.
- **Latest score per layer with gate status** — green/red against each threshold, so a failed gate
  is visible at a glance rather than inferred from numbers.
- Sweep table: config → gate pass/fail, cost, p50, `engagement_score`, sorted by score.
- **Pareto frontier chart** — cost vs. quality, latency vs. quality.
- Score history over time from `runs.jsonl`: did last night's prompt edit help?
- **Per-task drill-down** — click a failing task, get the transcript and the grader's `reason`
  string. Without this the scores tell you *that* something regressed but never *what*.

Eval runs take minutes, so they **reuse the existing `run_id` + SSE pattern** — progress streams as
events to the admin page exactly as a swarm turn streams to the chat page. Same plumbing, no new
transport.

### Panel 3 — Usage & cost

- Session cost meter, cumulative.
- **Per-route breakdown** (router / drafts / extraction / rebuttal / synthesis) — which phase eats
  the budget.
- Per-model breakdown: input, output, cache-read, cache-write tokens.
- Cost-per-turn distribution.
- **Tier mix** — the money chart for the cost story: *"62% of turns routed `direct` at $0.004;
  38% went to swarm at $0.31; blended $0.12/turn vs $0.31 if everything swarmed."* This single
  visual is the strongest argument the routing layer makes.
- Cache effectiveness: read vs. write tokens, with the expected-zero Haiku row annotated so it
  doesn't read as a bug.

> When building the charts, load the `dataviz` skill first — several of these (Pareto frontier,
> tier mix, cost distribution) are exactly the chart types where a default library palette and
> axis treatment will look amateurish next to the rest of the page.

### Endpoints

`GET /api/admin/runs` · `GET /api/admin/usage` · `POST /api/admin/eval` (returns `run_id`) ·
`GET /api/stream/{run_id}` (shared with chat) · `GET /api/admin/eval/results` · `GET /api/admin/sweep`

---

## SSE event contract — freeze first

Every event carries `seq` (monotonic), `phase`, and `agent_id` where applicable.

| Event | Payload |
|---|---|
| `turn_start` | `{turn_id, tier, reason}` |
| `route` | `{tier, reason, missing_facts}` |
| `agent_start` | `{agent_id, title, model}` |
| `tool_call` | `{agent_id, tool, input_summary}` |
| `progress` | `{agent_id, tokens_so_far}` |
| `draft_complete` | `{agent_id, draft, usage, cost_est}` |
| `conflicts` | `{found: [...], dropped: [{reason}]}` |
| `rebuttal` | `{agent_id, conflict_id, position, text}` |
| `memo` / `memo_patch` | `{...}` |
| `token` | `{text}` — synthesis and direct answers only |
| `degraded` | `{agent_id, reason}` |
| `retry` | `{agent_id, attempt, after_s}` |
| `usage` | `{turn: {...}, session: {...}, by_phase: {...}}` |
| `eval_progress` | `{suite, done, total, partial_scores}` |
| `error` / `done` | `{message}` / `{}` |

**Do not stream specialist tokens during fan-out.** Four interleaved token streams down one channel
are unreadable. Emit status events, let four cards fill in; stream tokens only for synthesis and
direct answers.

### Transport

- `POST /api/turn` → `run_id`; `GET /api/stream/{run_id}` is the `EventSource`. Native `EventSource`
  cannot POST, and the split lets a browser refresh **re-attach** to an in-flight swarm.
- Orchestration runs as a background task writing into a `run_id`-keyed queue. **Buffer the event
  log** so re-attach can replay from `Last-Event-ID`.
- Headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no`. Do not gzip the stream.
- Heartbeat `: ping` every 10–15s — keeps proxies alive *and* is how the generator learns the
  client disconnected.

### Concurrency

**Use `AsyncAnthropic` + `asyncio.gather`.** Every hard bug here — cross-thread queue safety,
cancellation, client sharing — is a consequence of blocking SDK calls in threads. Async removes all
three and gives real cancellation.

Extend the repo's factory with `_make_async_client()`. **Verify the async Bedrock Mantle class name
against the installed SDK before relying on it** — `AnthropicBedrockMantle` is the documented sync
class; the async counterpart is not documented in our reference. Thread fallback for the Bedrock
path only if absent. *(Attempted to verify during planning; the check was declined — it remains a
Phase 0 task: `python -c "import anthropic; print([n for n in dir(anthropic) if 'Bedrock' in n])"`.)*

If threads appear anywhere, the only correct shape is `loop.call_soon_threadsafe(queue.put_nowait,
event)`. **`asyncio.Queue` is not thread-safe** — calling `put_nowait` from a worker thread is the
bug that costs an evening. Capture the loop with `asyncio.get_running_loop()` before spawning. Note
also that a sync in-flight `messages.create` **cannot be interrupted and keeps billing** until it
returns; cancellation there is cooperative at best.

---

## Session memory

Four stores, not one blob:

| Store | Sent to model? | Bound |
|---|---|---|
| Chat transcript (verbatim) | Never wholesale | display only |
| `standing_memo` (structured) | Digest only | exactly 1, never concatenated |
| `facts` ledger (resolved facts + assumptions) | Always | ~40 items, deduped |
| Per-specialist draft archive, keyed by turn | On demand only | via tool |

The digest sent to the model is `headline`, current `recommendation`, `assumptions[]`,
`open_questions[]`, and `conflicts_resolved` reduced to `{topic, resolution}` one-liners. **Drop
`domain_findings` prose from context entirely**; expose it via a `get_prior_finding(domain, turn)`
tool — on-brand, since prior findings become a retrievable resource rather than context bloat.

**Reuse must be structural, not exhortative:**

- Follow-up synthesis emits a **patch**, not a fresh memo: `{unchanged: [ids], revised: [{id, was,
  now, why}], added: [...], retired: [...]}`. The UI renders a diff. Cheaper, forces reuse, and is a
  far better demo beat than a memo silently rewriting itself.
- The **redraft decision** on turn N is over **changed scope**, not the whole scenario. All three
  specialists are always in the panel, but if nothing in a given specialist's domain changed since
  the last turn, don't re-run it — carry its findings forward and label them "unchanged".
- Each re-run specialist gets its prior conclusions plus the delta: *"you already concluded X;
  address only what changed."*
- **Diff the profile panel between turns.** Highest-signal input to both the redraft decision and
  the specialist deltas, and rendering the diff makes the reuse legible.

The standing memo changes every swarm turn, so it belongs in `system[1]`, never `system[0]`.

---

## Repository layout

New top-level `advisory-swarm/` — a standalone prototype, not a Basecamp session, so it does not
belong under `day1/` or `day2/`.

```
advisory-swarm/
  README.md                 # setup + the frozen event contract
  requirements.txt          # fastapi, uvicorn + existing anthropic[bedrock]
  run.py                    # entrypoint; --replay; --eval <suite>; --sweep
  app/
    client.py               # PROVIDER/_model/_make_async_client + PRICING + cost calc
    config.py               # per-route model+effort (sweep's input surface), budgets, caps
    server.py               # FastAPI routes, SSE framing, run registry, admin endpoints
    orchestrator.py         # run_turn() + routing + the four phases  [NO fastapi import]
    events.py               # EventSink protocol: SSE / collector / file writer
    specialists.py          # fixed 3-specialist list
    schemas.py              # EVERY output_config JSON schema
    tools.py                # mock tool impls + one shared sorted schema list
    session.py              # locked store: profile, facts, standing memo, usage
    evals/
      graders.py            # router, conflict, memo, cost graders
      tasks.py              # labeled turns + scenarios + HOLDOUT set
      runner.py             # run_eval, engagement_score, sweep
    prompts/*.txt
    data/{profile,tax_brackets_2026,state_rules,portfolio,scenarios}.json
  web/index.html            # chat + profile panel + agent cards + memo
  web/admin.html            # monitor + evals + usage
  runs/                     # gitignored JSONL traces; replay source + eval corpus
  eval_results/             # gitignored; matches existing day2/01 convention
```

`orchestrator.py` importing `fastapi` is the canary for the architecture having broken — a lint
check worth adding.

Merged deliberately for a demo: routing folds into `orchestrator.py`; SSE framing into
`server.py`; cost into `client.py` — **pricing and model IDs must live together or they drift.**

Two modules that must exist as their own files:

- **`schemas.py`** — every structured-output schema in one place. These are what you'll tune at
  11pm the night before; scattered across four modules is the wrong ergonomics.
- **`specialists.py` as a declarative list** — `{id, display_name, persona_file}` for the fixed
  panel. There's no menu to keep in sync anymore (the router doesn't select a roster), but keeping
  this declarative rather than inlined still means adding a fourth domain later — should the demo
  ever call for one — touches one file, not five.

`session.py` needs a real store **with a lock** — background tasks mutate it concurrently.

**Fixed panel (all three run on every swarm turn):** `financial_advisor`, `tax_cpa`,
`estate_attorney`.

**Memo schema:** `headline`, `recommendation`, `domain_findings[]`, `conflicts_resolved[{topic,
tension, resolution, tradeoff}]`, `action_plan[{step, action, owner, timing}]`, `open_questions[]`,
`assumptions[]`.

---

## Demo safety: replay mode

Every run appends its full event stream to `runs/<run_id>.jsonl`. `run.py --replay <file>` plays it
back through the same `/api/stream` endpoint at original or 2× timing. The frontend cannot tell the
difference — same contract.

~40 lines, and the highest-ROI item in the project. If the API is slow, rate-limited, or down at
demo time, the demo still happens.

The live path stays at its natural 1.5–3 minutes (accepted). Two nearly-free latency measures still
ship: cap drafts at ~600 tokens via the structured schema (structure shortens output sharply), and
stream synthesis token-by-token so the final phase visibly produces text rather than spinning.

`data/scenarios.json` ships 3 canned scenarios behind a "load scenario" button — highest
value-per-line item for a live demo, and it doubles as the eval task set.

---

## Compliance

- Persistent UI banner: **"Synthetic data. Educational demonstration — not financial, tax, or legal
  advice."**
- Every memo's `open_questions[]` names **which licensed professional** to consult per item.
- Fixtures visibly labeled synthetic in the profile panel.

---

## Phasing — solo, sequential

Parallel tracks are dead; this is ordered for one person, with something demoable early and the
eval grader for each layer shipping **alongside** that layer rather than in a batch at the end.
That ordering is only possible because `run_turn()` is headless from Phase 0 — and it means you are
never tuning a layer you cannot measure.

**Phase 0 — Contract & skeleton.** Freeze the event contract into `README.md`. Write `schemas.py`,
`events.py` (the sink protocol), `client.py` with the Haiku-vs-Sonnet thinking branch and corrected
pricing. Verify the async Bedrock class name. Hand-author one replay fixture. **Exit criterion:
`run_turn()` runs end-to-end returning a stub `TurnResult`, with no FastAPI imported.**

**Phase 1 — Router + direct tier + router eval.** Specialist list, binary routing schema (no
roster field), direct answering. Ship `graders.py::router_grader` and ~30 labeled turns in the
same phase. **Exit: router eval passes ≥0.90 with false-`direct` weighted.**

**Phase 2 — Specialists + tools + fixtures.** Mock tools over seeded JSON, identical sorted tool
list, parallel drafts. Seed the fixtures so conflicts are structurally guaranteed — this is the
same work as authoring the conflict eval's ground truth, so do them together.

**Phase 3 — Conflict extraction + rebuttal + conflict eval.** The centerpiece. Quote validation in
Python. Ship recall/precision grading in the same phase; this is the layer most in need of tuning
and the one where flying blind is most expensive. **Exit: conflict recall ≥0.80 on canned scenarios.**

**Phase 4 — Synthesis + memo + memo judge.** Structured memo, gold answers for canned scenarios,
grounding-focused judge rubric.

**Phase 5 — Server + chat UI.** FastAPI, SSE, `web/index.html` built against the Phase 0 replay
fixture first, then switched to live. **Budget 600–900 lines** — four live panes, a memo renderer,
a diff view, and a HUD is routinely underestimated and may exceed the backend.

**Phase 6 — Admin screen + sweep.** `web/admin.html`, the three panels, `runner.py::sweep`, Pareto
rendering. Load the `dataviz` skill before the charts.

**Phase 7 — Multi-turn, memo patching, replay, polish.**

If time runs short, **Phases 6 and 7 are the compressible ones** — but do not cut the per-layer
graders from Phases 1, 3, and 4. Those are what keep the thing from silently degrading while you
tune it, and cutting them costs more than it saves.

---

## Verification

Beyond the eval suites, these are pass/fail smoke checks:

1. `python run.py` → `localhost:8000` loads, banner visible, profile populated; `/admin` loads.
2. **Architecture:** `orchestrator.py` imports no `fastapi`. `run_turn()` is callable from a bare
   Python REPL.
3. **Tier routing:** "what is a Roth conversion?" → `direct`, one Haiku call, sub-3s. "I'm selling
   my business for $4M, should I set up a trust first?" → `swarm`, all 3 specialists dispatched.
4. **Profile-edit rule:** edit net worth, ask a follow-up → asserts `direct` was disqualified.
5. **Quote validation:** inject a fabricated quote into extractor output → assert it is dropped and
   the drop surfaces in the admin panel.
6. **Rebuttal isolation:** assert the rebuttal prompt contains the counterpart's quoted span and
   **not** its full draft.
7. **Caching:** assert `cache_read_input_tokens > 0` on the second specialist call of a session;
   assert the Haiku routing call reports `cache_creation_input_tokens: 0` without raising.
8. **Cost:** `PRICING` lookup succeeds under both `PROVIDER=anthropic` and `PROVIDER=bedrock` (the
   prefix-stripping regression). Admin total matches summed `usage` within rounding.
9. **Degradation:** kill one specialist mid-flight → `degraded` event, synthesis still completes.
10. **Re-attach:** refresh mid-swarm → stream resumes from `Last-Event-ID`, run does not die.
11. **Replay:** `python run.py --replay runs/<id>.jsonl` with `ANTHROPIC_API_KEY` **unset** → full
    UI renders. This is the demo insurance policy; test it as one.
12. **Follow-up patching:** turn 2 emits `memo_patch` with a non-empty `unchanged[]`.
13. **Sweep:** `python run.py --sweep` prints projected cost, runs, and produces a frontier where at
    least one config beats baseline on score without failing the gate.

---

## Open risks

| Risk | Mitigation |
|---|---|
| Conflict extraction finds nothing → centerpiece empty | Fixtures seeded to guarantee conflicts; structured `cross_domain_implications`; extractor reads structure, not prose; **conflict recall gate catches it before the demo does** |
| Eval competes with demo polish for solo time | Graders ship with their layer, not as a phase; router suite is near-free; Phases 6–7 are the designated compressible ones |
| LLM judge ratifies its own family's reasoning | Judge grounding and structure, not advice correctness; hand-written gold answers for seeded scenarios |
| Sweep overfits to demo scenarios | Held-out scenario set, following existing `HOLDOUT_TASKS` convention |
| Async Bedrock Mantle class may not exist | Phase 0 verification task; thread fallback for the Bedrock path only |
| Frontend underestimated | Two pages budgeted explicitly; chat UI built against replay fixture before the backend exists |
| Sweep cost surprises | Print projected cost before running; router suite on every change, full sweep only at decision points |
