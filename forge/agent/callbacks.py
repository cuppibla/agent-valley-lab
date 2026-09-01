"""The five callbacks — each a surface of control. Agent-level (positional sigs
in ADK 2.5). This is the heart of Week 1: callbacks are control flow, not logging.

  before_agent  seed state, load app:style_rules
  before_model  pin the character sheet into the reasoning model every turn
  before_tool   PIN the reference image for generate_look (canon vs latest = the A/B)
  after_tool    capture: write current_look / look_history (the state_delta)
  after_model   guard: reject an off-brand / bootleg look
"""

from __future__ import annotations

from typing import Any, Optional

from google.adk.models.llm_response import LlmResponse
from google.genai import types

from .emit import emit
from .tools import artifact_png
from shared.contracts.trace_event import TraceEventType

DEFAULT_STYLE_RULES = {
    "banned_terms": ["bootleg", "logo", "trademark", "©"],
    "must_show_face": True,
}


async def before_agent(callback_context) -> Optional[types.Content]:
    state = callback_context.state
    state.setdefault("temp:candidates", [])
    state.setdefault("character_sheet", {"name": "", "description": "", "style_notes": ""})
    state.setdefault("app:style_rules", DEFAULT_STYLE_RULES)
    state.setdefault("anchor_mode", "canon")  # the Stability Anchor: "canon" | "latest"
    return None


async def before_model(callback_context, llm_request) -> Optional[LlmResponse]:
    """Keep the reasoning model on-character every turn — inject the sheet."""
    sheet = callback_context.state.get("character_sheet") or {}
    if sheet.get("description"):
        llm_request.append_instructions(
            [f"Active character sheet — stay on it: {sheet['description']}"])
    emit(type=TraceEventType.MODEL_CALL, hook="before_model",
         label="inject character_sheet" if sheet.get("description") else "no sheet yet")
    return None


def _resolve_reference(state) -> tuple[str, str]:
    """Return (reference_seed, anchor_mode). This IS the drift A/B."""
    mode = state.get("anchor_mode", "canon")
    if mode == "latest" and state.get("_last_output"):
        return state["_last_output"], "latest"
    return state.get("character_ref", "unpinned"), "canon"


def _apply_identity_lock(state) -> tuple[str, Optional[bytes], str]:
    """The valley's request UI lets the traveler PICK which render to work from.
    Identity lock decides whether that pick is honoured or overruled.

    Returns (reference_seed, reference_png, trace_label).

    This is the whole of chapter 5: the pick is a request, the lock is a rule.
    """
    canon = state.get("character_ref", "unpinned")
    canon_png = state.get("character_ref_png")
    picked = state.get("requested_reference") or canon
    picked_png = state.get("requested_reference_png") or canon_png

    if state.get("identity_lock", True):
        state["anchor_mode"] = "canon"          # _outfit_instruction reads this
        label = (f"identity lock → overruled {picked}, anchored to {canon}"
                 if picked != canon else f"identity lock → {canon}")
        return canon, canon_png, label

    state["anchor_mode"] = "latest"
    return picked, picked_png, f"lock off → honoured {picked}"


async def before_tool(tool, args: dict[str, Any], tool_context) -> Optional[dict]:
    """Pin the reference for generate_look — the control action of the week."""
    if tool.name == "generate_look":
        state = tool_context.state
        if "requested_reference" in state:          # the valley's request UI
            seed, png, label = _apply_identity_lock(state)
            mode = state["anchor_mode"]
        else:                                        # adk web / character_forge
            seed, mode = _resolve_reference(state)
            png = (state.get("temp:_last_output_png") if mode == "latest"
                   else state.get("temp:character_ref_png"))
            if png is None:
                # A new turn: the temp tier is gone, the artifact is not. The
                # seed IS the artifact name, so read the bytes back off it.
                png = await artifact_png(tool_context, seed)
            label = f"ref_pin → {mode} ({seed})" + (" + bytes" if png else "  ·  no bytes")
        state["temp:active_reference"] = seed       # the tool reads this (seed)
        state["temp:active_reference_png"] = png    # the real image pin
        emit(type=TraceEventType.TOOL_CALL, hook="before_tool", label=label,
             payload={"anchored_to": mode, "reference_seed": seed,
                      "requested": state.get("requested_reference"),
                      "identity_lock": state.get("identity_lock", True)})
    return None


async def after_tool(tool, args: dict[str, Any], tool_context,
                     tool_response: dict) -> Optional[dict]:
    """Capture the look into state — ref, not bytes. The visible state_delta.

    ADK 2.5 passes the tool result as the `tool_response` kwarg at agent level."""
    if tool.name == "generate_look" and tool_response.get("status") == "ok":
        state = tool_context.state
        _, mode = _resolve_reference(state)
        entry = {"form": tool_response["form"], "artifact": tool_response["artifact"],
                 "anchored_to": mode, "identity_hue": tool_response.get("identity_hue")}
        history = state.get("look_history", [])
        history.append(entry)
        state["look_history"] = history
        state["current_look"] = entry
        state["_last_output"] = tool_response["artifact"]  # feeds "latest" anchoring next turn
        # ...and the bytes behind that name, so anchor_mode="latest" has something
        # real to anchor to this turn. temp: — PNG bytes are not JSON and the
        # session store is; before_tool reloads them from the artifact after that.
        last_png = await artifact_png(tool_context, tool_response["artifact"])
        if last_png is not None:
            state["temp:_last_output_png"] = last_png
        # multiturn: show the state delta as a +/- on the outfit set; else the single-look label
        equipped = state.get("equipped")
        if equipped is not None:
            op = state.get("op", "")
            sign = "−" if op.startswith("unequip") else "+"
            item = op.split(" ", 1)[1] if " " in op else tool_response["form"]
            outfit = ", ".join(equipped) if equipped else "—"
            label = f"{sign} {item}   ·   outfit: {outfit}"
        else:
            label = f"+ current_look ({tool_response['form']})"
        emit(type=TraceEventType.STATE_DELTA, hook="after_tool", label=label,
             payload={"look_count": len(history), "anchored_to": mode,
                      "form": tool_response["form"],
                      "identity_hue": tool_response.get("identity_hue")})
    return None


async def after_model(callback_context, llm_response) -> Optional[LlmResponse]:
    """Guard: block an off-brand / bootleg request before it becomes a look."""
    rules = callback_context.state.get("app:style_rules", DEFAULT_STYLE_RULES)
    text = ""
    if llm_response.content and llm_response.content.parts:
        text = " ".join(p.text or "" for p in llm_response.content.parts).lower()
    hit = next((t for t in rules.get("banned_terms", []) if t in text), None)
    if hit:
        emit(type=TraceEventType.MODEL_CALL, hook="after_model",
             label=f"guard: blocked ({hit})", payload={"term": hit})
        return LlmResponse(content=types.Content(role="model", parts=[types.Part(
            text=f"That form violates the world's style rules ({hit}). Pick another.")]))
    emit(type=TraceEventType.MODEL_CALL, hook="after_model", label="guard: pass")
    return None
