"""One trace stream, shared by the plugin and the agent callbacks.

The plugin sets the run id and emits the coarse model/tool events; the agent
callbacks emit the semantic ones (ref_pin, state_delta, guard). Everything
funnels through `emit()` into one sink, so LIVE (queue→SSE) and REPLAY (JSONL)
see the identical stream. That single stream is what the Inspector renders and
what the Runtime Inspector draws.
"""

from __future__ import annotations

import contextvars

from shared.contracts.trace_event import Cost, TraceEvent, TraceEventType

_sink = None  # set once by the app; None = drop (e.g. a bare import)
_run_id: contextvars.ContextVar[str] = contextvars.ContextVar("run_id", default="unbound")


def set_sink(sink) -> None:
    global _sink
    _sink = sink


def set_run_id(run_id: str) -> None:
    _run_id.set(run_id)


def emit(
    *,
    type: TraceEventType,
    label: str,
    hook: str | None = None,
    week: int | None = 1,
    payload: dict | None = None,
    tokens: int = 0,
    usd: float = 0.0,
) -> None:
    if _sink is None:
        return
    _sink.emit(TraceEvent(
        run_id=_run_id.get(),
        week=week,
        hook=hook,
        type=type,
        label=label,
        payload=payload or {},
        cost=Cost(tokens=tokens, usd=usd),
    ))
