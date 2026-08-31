"""App wiring — root_agent + the TraceEmitter plugin + context caching.

`adk web` discovers `root_agent`; this module is for programmatic runs and for
choosing where the trace stream goes (LIVE queue vs JSONL fixture)."""

from __future__ import annotations

from pathlib import Path

from google.adk.apps.app import App
from google.adk.agents.context_cache_config import ContextCacheConfig

from .character_forge import root_agent
from .plugin_trace import TraceEmitterPlugin
from shared.contracts.trace_event import JsonlSink

_FIXTURE = Path(__file__).resolve().parents[2] / "domain" / "fixtures" / "w1_live.jsonl"


def build_app(sink=None) -> App:
    return App(
        name="character_forge",
        root_agent=root_agent,
        plugins=[TraceEmitterPlugin(sink or JsonlSink(_FIXTURE))],
        context_cache_config=ContextCacheConfig(min_tokens=2048, ttl_seconds=1800),
    )


app = build_app()
