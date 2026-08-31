"""TraceEvent — the normalized event every week's agent emits.

One stream, three consumers: the Runtime Inspector visualizes it, shared/eval
reduces it into gate metrics, and the JSONL sink persists it as a REPLAY
fixture. LIVE and REPLAY render identically because both are just this stream.

Emitted by the TraceEmitterPlugin (M1) from ADK plugin/callback hooks — which
is itself the W1 lesson: the machine that renders weeks 2–5 is built out of
week 1's own concepts.

`stream_sample` exists from day one so W5's continuous tracks (audio, frames,
$/min) fit the same Inspector instead of forking it.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from enum import Enum
from pathlib import Path
from typing import Optional, Protocol

from pydantic import BaseModel, Field


class TraceEventType(str, Enum):
    MODEL_CALL = "model_call"
    TOOL_CALL = "tool_call"
    STATE_DELTA = "state_delta"
    MEMORY_READ = "memory_read"
    MEMORY_WRITE = "memory_write"
    HUMAN_PAUSE = "human_pause"
    RESUME = "resume"
    STREAM_SAMPLE = "stream_sample"  # W5 continuous tracks; payload: {track, value, ...}


class Cost(BaseModel):
    tokens: int = 0
    usd: float = 0.0


class TraceEvent(BaseModel):
    ts: float = Field(default_factory=time.time)  # epoch seconds
    run_id: str
    span_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    parent_span_id: Optional[str] = None
    week: Optional[int] = None      # which zone produced it (site routing)
    hook: Optional[str] = None      # lifecycle door, e.g. "before_tool" — the Inspector badge
    type: TraceEventType
    label: str                      # short human line, e.g. "ref_pin → character_ref"
    payload: dict = Field(default_factory=dict)
    cost: Cost = Field(default_factory=Cost)


# ── sinks ───────────────────────────────────────────────────────────────────

class TraceSink(Protocol):
    def emit(self, event: TraceEvent) -> None: ...


class JsonlSink:
    """Append-only JSONL file — the REPLAY fixture format."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: TraceEvent) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(event.model_dump_json() + "\n")


class QueueSink:
    """In-process asyncio queue — the LIVE feed the site streams over SSE."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[TraceEvent] = asyncio.Queue()

    def emit(self, event: TraceEvent) -> None:
        self.queue.put_nowait(event)


class MultiSink:
    """Fan out to several sinks (LIVE + fixture capture at once)."""

    def __init__(self, *sinks: TraceSink):
        self.sinks = sinks

    def emit(self, event: TraceEvent) -> None:
        for sink in self.sinks:
            sink.emit(event)


def read_jsonl(path: str | Path) -> list[TraceEvent]:
    """Load a REPLAY fixture back into events."""
    events = []
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(TraceEvent.model_validate_json(line))
    return events


if __name__ == "__main__":
    import tempfile

    run_id = "smoke-" + uuid.uuid4().hex[:6]
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "trace.jsonl"
        sink = JsonlSink(path)
        sink.emit(TraceEvent(run_id=run_id, week=1, hook="before_tool",
                             type=TraceEventType.TOOL_CALL,
                             label="ref_pin → character_ref",
                             payload={"anchored_to": "canon"}))
        sink.emit(TraceEvent(run_id=run_id, week=1, hook="after_tool",
                             type=TraceEventType.STATE_DELTA,
                             label="+ current_look",
                             cost=Cost(tokens=2140, usd=0.03)))
        sink.emit(TraceEvent(run_id=run_id, week=5,
                             type=TraceEventType.STREAM_SAMPLE,
                             label="audio_out",
                             payload={"track": "audio_out", "value": 0.42}))
        back = read_jsonl(path)
        assert len(back) == 3 and back[0].label == "ref_pin → character_ref"
        assert back[1].cost.usd == 0.03 and back[2].type == TraceEventType.STREAM_SAMPLE
        print(f"roundtrip OK — 3 events → {path.name} → parsed back intact")
