"""TraceEmitterPlugin — the global emitter that powers the Runtime Inspector.

This is Week 1's own Plugin lesson turned load-bearing: a BasePlugin (global,
cross-cutting) sets the run id and emits the coarse model/tool/cost events, while
the agent callbacks add the semantic detail. Both funnel through emit() into one
sink — so the machine that renders weeks 2-5 is built out of week 1's concepts.
"""

from __future__ import annotations

from typing import Any, Optional

from google.adk.plugins.base_plugin import BasePlugin

from .emit import emit, set_run_id, set_sink
from shared.contracts.trace_event import TraceEventType


class TraceEmitterPlugin(BasePlugin):
    def __init__(self, sink) -> None:
        super().__init__(name="trace_emitter")
        set_sink(sink)

    async def before_run_callback(self, *, invocation_context) -> None:
        set_run_id(invocation_context.invocation_id)
        return None

    async def before_tool_callback(self, *, tool, tool_args, tool_context) -> Optional[dict]:
        emit(type=TraceEventType.TOOL_CALL, hook="before_tool",
             label=f"tool_call {tool.name}({', '.join(f'{k}=…' for k in tool_args)})")
        return None

    async def after_model_callback(self, *, callback_context, llm_response) -> None:
        usage = getattr(llm_response, "usage_metadata", None)
        tokens = getattr(usage, "total_token_count", 0) or 0 if usage else 0
        emit(type=TraceEventType.MODEL_CALL, hook="after_model",
             label="model response", tokens=tokens,
             usd=round(tokens * 3e-6, 4))  # placeholder rate; real pricing at M2
        return None
