"""The Character Forge tools. Three player actions, three shapes of control.

  cast_candidates — describe a character → its portrait (temp:, thrown away on lock)
  lock_candidate  — pick one as canon. A tool that spends NO model: a pure state write.
  generate_look   — transmog: same face, new form. The reference is pinned by the
                    before_tool callback (see callbacks.py) into temp:active_reference.

The render step is factored into `render_look` so the offline fixture generator
runs the exact same backend/artifact path the ADK tool runs.
"""

from __future__ import annotations

import asyncio

from google.adk.tools import ToolContext
from google.genai import types

from .backends import ImageBackend, get_backend
from .emit import emit
from shared.contracts.trace_event import TraceEventType

_backend: ImageBackend = get_backend()


#: How many portraits one summon draws. They render concurrently, so more
#: candidates cost tokens but almost no extra wall clock.
CANDIDATES = 1


def set_backend(b: ImageBackend) -> None:
    """Inject a backend (e.g. NanoBananaBackend with a per-request BYOK key)."""
    global _backend
    _backend = b


def render_look(*, sheet: str, form: str, reference_seed: str,
                reference_png: bytes | None = None,
                instruction: str | None = None) -> tuple[bytes, dict]:
    """Backend call + return (png_bytes, meta). Shared by the tool and the fixture."""
    result = _backend.render(sheet=sheet, form=form, reference_seed=reference_seed,
                             reference_png=reference_png, instruction=instruction)
    meta = {"form": form, "identity_hue": result.identity_hue}
    return result.png, meta


def _outfit_instruction(state) -> str | None:
    """Build the per-turn edit prompt for the multiturn dress-up.

    canon (holds): re-render the familiar wearing the FULL current outfit, always
      grounded in the pinned canon image → identity survives a long session.
    latest (drifts): edit the PREVIOUS output by just this turn's delta (+/- one
      item) → edits compound on edits → the face slowly drifts away.
    """
    equipped = state.get("equipped")
    if equipped is None:
        return None  # not a multiturn call — fall back to the single-form prompt
    op = state.get("op", "")           # "equip Crown" | "unequip Crown"
    item = op.split(" ", 1)[1] if " " in op else "an accessory"
    wearing = ", ".join(equipped) if equipped else "no accessories — just its bare adorable self"
    if state.get("anchor_mode") == "latest":
        if op.startswith("unequip"):
            return (f"The same familiar as the reference image — keep its exact face and low-poly "
                    f"style — but take the {item} off it.")
        return (f"The same familiar as the reference image — keep its exact face and low-poly "
                f"style — now also wearing {item}.")
    return (f"The same familiar as the reference image — identical face, colours, markings and "
            f"low-poly style — now wearing {wearing}. Keep the identity unchanged.")


async def cast_candidates(description: str, tool_context: ToolContext) -> dict:
    """Draw the familiar a traveler described.

    Args:
        description: What the creature looks like — species, colours, mood, era.

    Returns:
        dict with the artifact filenames of the portraits that were drawn.
    """
    # One portrait by default: a summon is the slowest, most expensive thing in the
    # lab, and one is enough to claim. Raise it for a pick-from-several flow —
    # they are drawn at the same time, so N costs the wall clock of one.
    pngs = await asyncio.gather(*(
        asyncio.to_thread(render_look, sheet=description, form="base portrait",
                          reference_seed=f"cast-{i}")
        for i in range(CANDIDATES)
    ))
    filenames: list[str] = []
    for i, (png, _meta) in enumerate(pngs):
        name = f"candidate_{i}.png"
        await tool_context.save_artifact(
            name, types.Part(inline_data=types.Blob(mime_type="image/png", data=png)))
        filenames.append(name)
    # refs (not bytes) go in state, in the temp tier — gone on lock
    tool_context.state["temp:candidates"] = filenames
    tool_context.state["character_sheet"] = {"name": "", "description": description,
                                             "style_notes": ""}
    emit(type=TraceEventType.STATE_DELTA, hook="after_tool",
         label=f"+ temp:candidates ({len(filenames)})", payload={"count": len(filenames)})
    return {"status": "ok", "candidates": filenames, "count": len(filenames)}


async def lock_candidate(index: int, name: str, tool_context: ToolContext) -> dict:
    """Lock one candidate as the canonical character. Spends no model — a pure state write.

    Args:
        index: Which candidate to make canon (0 is the first).
        name: The character's name.

    Returns:
        dict confirming the locked reference.
    """
    candidates = tool_context.state.get("temp:candidates", [])
    if not 0 <= index < len(candidates):
        return {"status": "error", "message": f"index {index} out of range"}
    ref = candidates[index]
    tool_context.state["character_ref"] = ref
    sheet = tool_context.state.get("character_sheet", {})
    sheet["name"] = name
    tool_context.state["character_sheet"] = sheet
    tool_context.state["temp:candidates"] = []  # candidates dissolve
    tool_context.state["look_history"] = []
    emit(type=TraceEventType.STATE_DELTA, hook="after_tool",
         label=f"+ character_ref  − temp:candidates  (0 tok, $0.00)",
         payload={"character_ref": ref, "name": name})
    return {"status": "ok", "character_ref": ref, "name": name}


async def generate_look(form: str, tool_context: ToolContext) -> dict:
    """Transmog the locked character into a new form. Same face, new look.

    Args:
        form: The form to render (e.g. "Paladin Plate", "Archmage Robes").

    Returns:
        dict with the new look's artifact filename.
    """
    state = tool_context.state
    sheet = state.get("character_sheet", {}).get("description", "")
    # the before_tool callback pinned the resolved reference here (seed + real image bytes):
    reference_seed = state.get("temp:active_reference") or state.get("character_ref", "unpinned")
    reference_png = state.get("temp:active_reference_png")
    instruction = _outfit_instruction(state)  # multiturn outfit prompt, or None for single-form
    png, meta = render_look(sheet=sheet, form=form, reference_seed=reference_seed,
                            reference_png=reference_png, instruction=instruction)
    name = f"look_{len(state.get('look_history', []))}.png"
    await tool_context.save_artifact(
        name, types.Part(inline_data=types.Blob(mime_type="image/png", data=png)))
    return {"status": "ok", "artifact": name, "form": form,
            "identity_hue": meta["identity_hue"]}
