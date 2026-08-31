"""W1 agent service — the real brain behind the game.

A thin FastAPI over the SAME agent code the repo ships (`tools.cast_candidates`,
the callbacks, the emit/trace plugin). The Next site's /api/w1/* proxies here, so a
"Summon" click really runs the ADK agent tool on real Nano Banana and returns the
real TraceEvent stream. This is the honest "site = face, agent = brain" wiring.

Run:  bash valley.sh        (boots this on 8100, and the app on 3200)
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root → `shared`


import forge  # noqa: F401  — settles Vertex-vs-key config for every surface

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

import base64 as _b64
from collections import namedtuple

from .backends import get_backend
from . import tools
from .callbacks import before_agent, before_tool, after_tool
from .emit import set_run_id, set_sink
from shared.contracts.trace_event import TraceEvent

Tool = namedtuple("Tool", "name")


def _shrink(png: bytes, size: int = 512, quality: int = 82) -> str:
    """Downscale + JPEG-compress a generated image → a small data URL, so the browser
    isn't asked to hold multiple 2 MB base64 blobs (that froze the tab). ~60 KB each."""
    from io import BytesIO
    from PIL import Image
    im = Image.open(BytesIO(png)).convert("RGB")
    im.thumbnail((size, size))
    buf = BytesIO()
    im.save(buf, format="JPEG", quality=quality)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

app = FastAPI(title="Agent 101 · W1 character_forge")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class ListSink:
    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    def emit(self, e: TraceEvent) -> None:
        self.events.append(e)


class CaptureCtx:
    """The slice of ToolContext the real tools need, capturing artifact bytes so
    the service can return them."""

    def __init__(self) -> None:
        self.state: dict = {}
        self.arts: dict[str, bytes] = {}

    async def save_artifact(self, filename: str, artifact) -> int:
        self.arts[filename] = artifact.inline_data.data
        return 0


@app.get("/health")
def health() -> dict:
    return {"ok": True, "agent": "character_forge", "tool": "cast_candidates"}


@app.post("/cast")
async def cast(req: Request) -> dict:
    body = await req.json()
    description = body.get("description", "") or "a cute mystical familiar"
    # get_backend() already knows the mode (Vertex project, or a key).
    tools.set_backend(get_backend())

    sink = ListSink()
    set_sink(sink)
    set_run_id("w1-cast-live")
    ctx = CaptureCtx()

    await before_agent(ctx)                        # the REAL callback
    result = await tools.cast_candidates(description, ctx)   # the REAL agent tool

    candidates = [
        {"id": name, "src": _shrink(ctx.arts[name])}
        for name in result.get("candidates", []) if name in ctx.arts
    ]
    return {
        "mode": "live-agent",
        "candidates": candidates,
        "events": [e.model_dump() for e in sink.events],
    }


def _decode(data_url_or_b64: str) -> bytes | None:
    if not data_url_or_b64:
        return None
    raw = data_url_or_b64.split(",", 1)[-1]  # strip data:image/png;base64,
    return _b64.b64decode(raw)


@app.post("/adorn")
async def adorn(req: Request) -> dict:
    """One multiturn dress-up turn. Runs the REAL generate_look with the REAL
    before_tool pin. `reference` is the claimed familiar (canon); `prev` is the last
    rendered look (for latest-anchor drift). `op`/`item`/`outfit` carry the equip state:
    the outfit is accumulated session state, this turn adds or removes one item."""
    body = await req.json()
    op = body.get("op", "equip")                  # "equip" | "unequip"
    item = body.get("item") or body.get("form", "Crown")
    outfit = body.get("outfit", [])               # the FULL equipped set AFTER this op
    anchor = body.get("anchor", "canon")          # "canon" | "latest"
    tools.set_backend(get_backend())

    sink = ListSink()
    set_sink(sink)
    set_run_id(f"w1-adorn-{anchor}")
    ctx = CaptureCtx()
    ctx.state.update({
        "character_ref": "canon", "anchor_mode": anchor,
        "character_sheet": {"description": ""}, "look_history": [],
        "equipped": list(outfit),
        "op": f"{op} {item}",
        "character_ref_png": _decode(body.get("reference", "")),
        # the id + bytes of the previous look — set only when there IS one, so latest-anchor
        # can pin to it (drift). Without this the pin silently falls back to canon.
        "_last_output": "prev_look" if body.get("prev") else None,
        "_last_output_png": _decode(body.get("prev", "")),
        "app:style_rules": {"banned_terms": ["bootleg", "logo"], "must_show_face": True},
    })

    tool = Tool("generate_look")
    await before_tool(tool, {"form": item}, ctx)          # the REAL pin (canon vs latest)
    result = await tools.generate_look(item, ctx)          # the REAL tool → real Nano Banana
    await after_tool(tool, {"form": item}, ctx, result)

    art = result.get("artifact")
    img = _shrink(ctx.arts[art]) if art in ctx.arts else None
    return {"mode": "live-agent", "image": img, "form": item, "op": op, "item": item,
            "outfit": outfit, "anchor": anchor,
            "events": [e.model_dump() for e in sink.events]}
