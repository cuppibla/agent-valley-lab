"""The Character Forge tools. Three player actions, three shapes of control.

  cast_candidates — describe a character → its portrait, plus a PROVISIONAL pin
                    (provisional_ref) so a look can never render from nothing.
  lock_candidate  — pick one as canon. A tool that spends NO model: a pure state write.
  generate_look   — transmog: same face, new form. The reference is pinned by the
                    before_tool callback (see callbacks.py) into temp:active_reference.

Two pins, not one. `cast` pins the reference — provisional, unnamed, just enough
that there is always a face to hold. `lock_candidate` is what makes it canon: it
names the character and dissolves the candidates. The provisional pin is a floor,
not a replacement — see callbacks._resolve_reference for the order they resolve in.

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


async def artifact_png(tool_context, filename: str | None) -> bytes | None:
    """Best-effort: the PNG bytes behind an artifact name, or None.

    The bytes are the anchor — `backends.py` only sends an image to the model
    when it is handed `reference_png`. State can only ever hold the NAME:
    session state is persisted as JSON and PNG bytes are not JSON. So the name
    lives in state and the bytes are fetched back from the artifact store.
    """
    if not filename:
        return None
    try:
        part = await tool_context.load_artifact(filename)
    except Exception:                     # no artifact service, or no such name
        return None
    inline = getattr(part, "inline_data", None) if part is not None else None
    return getattr(inline, "data", None)


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
    # PROVISIONAL PIN. Nothing is canon yet — nobody has picked, nobody has named
    # it — but a face now exists, so `generate_look` must never render from nothing
    # again. The name is session-tier because the look comes a TURN later and temp:
    # dies with the turn; the bytes ride along in temp: for this turn, and after that
    # before_tool reloads them from the artifact by name. lock_candidate overrides
    # both (see _resolve_reference): this is a floor, not a decision.
    tool_context.state["provisional_ref"] = filenames[0]
    tool_context.state["temp:provisional_ref_png"] = pngs[0][0]
    emit(type=TraceEventType.STATE_DELTA, hook="after_tool",
         label=(f"+ temp:candidates ({len(filenames)})  "
                f"+ provisional_ref {filenames[0]}"),
         payload={"count": len(filenames), "provisional_ref": filenames[0]})
    return {"status": "ok", "candidates": filenames, "count": len(filenames)}


async def lock_candidate(index: int, name: str, tool_context: ToolContext) -> dict:
    """Lock one candidate as the canonical character. Spends no model — a pure state write.

    `cast_candidates` left a provisional pin behind so a look could never render
    from nothing. This is the step that makes it CANON: it names the character,
    writes `character_ref`, and dissolves the candidates. Provisional → decided.

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
    # The name is the receipt; the BYTES are the anchor. Pin them now, while the
    # chosen candidate is unambiguous, in the temp tier — they are not JSON, so
    # they must never reach the persisted state (before_tool reloads them from
    # the artifact on later turns, when this temp key is long gone).
    png = await artifact_png(tool_context, ref)
    if png is not None:
        tool_context.state["temp:character_ref_png"] = png
    sheet = tool_context.state.get("character_sheet", {})
    sheet["name"] = name
    tool_context.state["character_sheet"] = sheet
    tool_context.state["temp:candidates"] = []  # candidates dissolve
    # the provisional pin has been promoted — blank it so the State tab shows one
    # anchor, not two. (ADK's State has no delete; "" is the falsy form, the same
    # way temp:candidates dissolves to [].)
    tool_context.state["provisional_ref"] = ""
    tool_context.state["look_history"] = []
    emit(type=TraceEventType.STATE_DELTA, hook="after_tool",
         label=(f"+ character_ref {'+ temp:character_ref_png ' if png else ''}"
                f" − temp:candidates  − provisional_ref  (0 tok, $0.00)"),
         payload={"character_ref": ref, "name": name,
                  "reference_bytes": len(png) if png else 0})
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
