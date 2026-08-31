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
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root → `shared`


import forge  # noqa: F401  — settles Vertex-vs-key config for every surface

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

import base64 as _b64
from collections import namedtuple

from google.adk.artifacts import InMemoryArtifactService
from google.adk.events import Event, EventActions
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from .backends import get_backend
from . import tools
from .callbacks import before_agent, before_tool, after_tool
from .emit import set_run_id, set_sink
from .lanes import dresser, summoner
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


APP = "valley"
_sessions = InMemorySessionService()
_artifacts = InMemoryArtifactService()
_runners = {"summon": Runner(app_name=APP, agent=summoner, session_service=_sessions,
                             artifact_service=_artifacts),
            "dress": Runner(app_name=APP, agent=dresser, session_service=_sessions,
                            artifact_service=_artifacts)}


async def _run(lane: str, sid: str, text: str, seed: dict | None = None) -> tuple[list[dict], bool]:
    """Drive one lane. Returns (the tools' return values, did_call_tool).

    `seed` is written straight into session state before the run — that is how the
    browser's picked reference and the identity-lock toggle reach `before_tool`.
    """
    sess = await _sessions.get_session(app_name=APP, user_id="traveler", session_id=sid)
    if sess is None:
        sess = await _sessions.create_session(app_name=APP, user_id="traveler", session_id=sid)
    if seed:
        # get_session hands back a copy, so mutating sess.state is a no-op. A state
        # delta on an event is the supported way to write into a live session.
        await _sessions.append_event(sess, Event(
            author="valley", invocation_id=f"seed-{sid}",
            actions=EventActions(state_delta=seed)))

    # Read the tool's own return value rather than diffing artifact keys: a second
    # dress-up turn overwrites look_0.png, so the key set does not change.
    called, results = False, []
    msg = types.Content(role="user", parts=[types.Part(text=text)])
    async for ev in _runners[lane].run_async(user_id="traveler", session_id=sid, new_message=msg):
        for part in (ev.content.parts if ev.content else []) or []:
            if part.function_call:
                called = True
            if part.function_response and isinstance(part.function_response.response, dict):
                results.append(part.function_response.response)
    return results, called


async def _artifact_png(sid: str, name: str) -> bytes | None:
    part = await _artifacts.load_artifact(
        app_name=APP, user_id="traveler", session_id=sid, filename=name)
    return part.inline_data.data if part and part.inline_data else None


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
    """The TYPING lane. A real agent reads the traveler's sentence and picks the tool.

    Contrast this with /adorn's sibling below and with the button path: here nobody
    hardcoded `cast_candidates` — the model chose it from a docstring.
    """
    body = await req.json()
    description = body.get("description", "") or "a cute mystical familiar"
    sid = body.get("session_id") or f"s-{uuid.uuid4().hex[:10]}"
    tools.set_backend(get_backend())

    sink = ListSink()
    set_sink(sink)
    set_run_id("w1-cast-live")

    results, called = await _run("summon", sid, description)
    if not called:                      # rare: the model answered without summoning
        results, called = await _run("summon", sid,
                                     f"Call cast_candidates now for: {description}")

    candidates = []
    for r in results:
        for name in r.get("candidates", []):
            png = await _artifact_png(sid, name)
            if png:
                candidates.append({"id": name, "src": _shrink(png)})

    if not candidates:                  # last resort — never hand the UI an empty list
        ctx = CaptureCtx()
        await before_agent(ctx)
        result = await tools.cast_candidates(description, ctx)
        candidates = [{"id": n, "src": _shrink(ctx.arts[n])}
                      for n in result.get("candidates", []) if n in ctx.arts]

    return {"mode": "live-agent", "session_id": sid, "candidates": candidates,
            "events": [e.model_dump() for e in sink.events]}


def _decode(data_url_or_b64: str) -> bytes | None:
    if not data_url_or_b64:
        return None
    raw = data_url_or_b64.split(",", 1)[-1]  # strip data:image/png;base64,
    return _b64.b64decode(raw)


@app.post("/adorn")
async def adorn(req: Request) -> dict:
    """The REQUEST lane. The traveler types what they want and picks which render to
    work from; the agent calls generate_look; `before_tool` decides whether that pick
    is honoured or overruled by the identity lock.

    The pick is a request. The lock is a rule. That is chapter 5, in one endpoint.
    """
    body = await req.json()
    request_text = body.get("request") or f"give it {body.get('item', 'a crown')}"
    sid = body.get("session_id")
    outfit = body.get("outfit", [])
    op = body.get("op", "equip")
    item = body.get("item") or "an accessory"
    tools.set_backend(get_backend())

    sink = ListSink()
    set_sink(sink)
    set_run_id("w1-adorn-live")

    seed = {
        "character_ref": body.get("canon_id", "canon"),
        "character_ref_png": _decode(body.get("canon", "")),
        "requested_reference": body.get("reference_id", body.get("canon_id", "canon")),
        "requested_reference_png": _decode(body.get("reference", "")),
        "identity_lock": bool(body.get("identity_lock", True)),
        "equipped": list(outfit),
        "op": f"{op} {item}",
        # the ids so far — generate_look names the next render look_{len}.png
        "look_history": list(body.get("history_ids", [])),
        "app:style_rules": {"banned_terms": ["bootleg", "logo"], "must_show_face": True},
    }

    results, called = await _run("dress", sid, request_text, seed)
    if not called:
        results, called = await _run("dress", sid,
                                     f"Call generate_look now with: {item}", seed)

    img, look_id = None, None
    for r in results:
        name = r.get("artifact")
        png = await _artifact_png(sid, name) if name else None
        if png:
            img, look_id = _shrink(png), name
    return {"mode": "live-agent", "session_id": sid, "image": img, "look_id": look_id,
            "form": item,
            "op": op, "item": item, "outfit": outfit,
            "identity_lock": seed["identity_lock"],
            "reference_id": seed["requested_reference"],
            "events": [e.model_dump() for e in sink.events]}
