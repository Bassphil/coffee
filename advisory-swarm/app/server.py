"""FastAPI wrapper around orchestrator.run_turn(). Demo shortcuts: no re-attach/Last-Event-ID,
no heartbeat, no run persistence past process memory, CORS wide open. orchestrator.py itself
stays fastapi-free — this file is the only caller.
"""

import asyncio
import json
import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from events import QueueSink
from orchestrator import DEFAULT_CONFIG, run_turn

APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
WEB_DIR = APP_DIR.parent / "web"
DEFAULT_PROFILE = json.loads((DATA_DIR / "profile.json").read_text())

app = FastAPI()
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

RUNS: dict[str, dict] = {}  # run_id -> {"queue": asyncio.Queue, "result": TurnResult | None}


class TurnRequest(BaseModel):
    query: str
    profile: dict | None = None
    config: dict | None = None


@app.post("/api/turn")
async def post_turn(req: TurnRequest):
    run_id = uuid.uuid4().hex
    queue: asyncio.Queue = asyncio.Queue()
    RUNS[run_id] = {"queue": queue, "result": None}
    sink = QueueSink(queue)

    async def _go():
        try:
            result = await run_turn(
                req.query, req.profile or DEFAULT_PROFILE, req.config or DEFAULT_CONFIG, sink
            )
            RUNS[run_id]["result"] = result
        except Exception as exc:
            await sink({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
        finally:
            await queue.put(None)  # sentinel: stream ends

    asyncio.create_task(_go())
    return {"run_id": run_id}


@app.get("/api/stream/{run_id}")
async def get_stream(run_id: str):
    if run_id not in RUNS:
        return StreamingResponse(iter([""]), status_code=404)

    async def event_gen():
        queue = RUNS[run_id]["queue"]
        while True:
            event = await queue.get()
            if event is None:
                break
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/runs/{run_id}/result")
async def get_result(run_id: str):
    run = RUNS.get(run_id)
    if not run or run["result"] is None:
        return {"ready": False}
    result = run["result"]
    return {
        "ready": True,
        "memo": result.memo,
        "drafts": result.drafts,
        "conflicts": result.conflicts,
        "dropped_conflicts": result.dropped_conflicts,
        "rebuttals": result.rebuttals,
        "cost_by_phase": result.cost_by_phase,
        "total_cost": result.total_cost,
    }


if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
