"""EventSink: the orchestrator emits events through this, and never knows who's listening.

A sink is just `async def sink(event: dict) -> None`. server.py passes a QueueSink (SSE),
tests/scripts pass a CollectorSink. Every event gets a monotonic `seq` and `ts` stamped on here
so callers don't have to.
"""

import time
from dataclasses import dataclass, field


@dataclass
class CollectorSink:
    events: list = field(default_factory=list)
    _seq: int = 0

    async def __call__(self, event: dict) -> None:
        self._seq += 1
        self.events.append({**event, "seq": self._seq, "ts": time.time()})


class QueueSink:
    def __init__(self, queue):
        self.queue = queue
        self._seq = 0

    async def __call__(self, event: dict) -> None:
        self._seq += 1
        await self.queue.put({**event, "seq": self._seq, "ts": time.time()})
