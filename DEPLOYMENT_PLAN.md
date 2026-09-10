# Deployment Plan — Local-Only Demo

Deployment approach for the advisory-swarm demo described in `Design Document.md`.
The design already assumes no auth, in-memory session state, and a
"localhost only" admin screen (see its Compliance and Admin sections) — so
the right deployment is running it locally at demo time, not standing up
hosting infrastructure.

## Setup

- Single `venv` + `requirements.txt`, `ANTHROPIC_API_KEY` in `.env`.
- One entrypoint: `python run.py`.
- Two browser tabs open before presenting: `localhost:8000` (chat) and
  `/admin` (agent monitor, evals, cost) — mirrors the design's own
  two-monitor demo setup.

## Demo-day insurance

- Pre-record `--replay` traces for the 2–3 canned scenarios
  (`data/scenarios.json`) the night before. Rehearse switching to
  `--replay` if the live API is slow, rate-limited, or down — the design
  doc calls this the highest-ROI ~40 lines in the project.
- Use the "load scenario" button instead of typing free-text live, to
  avoid landing on an ad-libbed input the fixtures don't cover (no
  conflict found, a degraded specialist, etc.).
- Set a hard per-session cost ceiling so a live rate-limit retry storm or
  a runaway tool loop can't blow budget or stall mid-demo.

## Final check before presenting

Run the design doc's own smoke tests immediately before the room fills up:

1. `python run.py` → `localhost:8000` loads, banner visible, `/admin` loads.
2. `python run.py --replay runs/<id>.jsonl` with `ANTHROPIC_API_KEY` unset →
   full UI renders. This is the demo insurance policy; test it as one.

## Why not a hosted deployment

Going public (e.g. a container on Fly.io/Render) would require bolting on
auth and rate/cost limiting that the design doc explicitly scopes out
(see "Not in scope"). That tradeoff is worth revisiting only if
stakeholders need to explore the demo unattended, without a presenter
driving it live.
