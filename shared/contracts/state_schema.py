"""The growing state schema — the spine of Agent 101 Live.

Single source of truth for every state key the five-week system uses.
The Python agents import it for tier/key validation; the site renders its
week-by-week growth as the navigation rail. `state_schema.ts` is the
hand-kept mirror until codegen lands (M3).

ADK state is a flat key-value store with tier prefixes (`temp:`, `user:`,
`app:`; no prefix = session). This module describes KEYS, not a nested
object: each `StateKeyDef` says where a key lives, which week introduces
it, what shape its value has, and how it may change.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── tiers & mutability ──────────────────────────────────────────────────────

class Tier(str, Enum):
    TEMP = "temp"        # dies with the invocation
    SESSION = "session"  # lives for the session (default, no prefix)
    USER = "user"        # persists across sessions for one user
    APP = "app"          # shared by all users


class Mutability(str, Enum):
    FREE = "free"                      # overwrite at will
    CONFIRM = "confirm"                # changes require explicit confirmation
    WRITE_PROTECTED = "write_protected"  # only an explicit, confirmed flow may change it


# ── value shapes (W1 concrete; W2+ arrive with their weeks) ─────────────────

class ArtifactRef(BaseModel):
    """Pointer into the Artifact service. Bytes never live in state."""
    filename: str
    version: int = 0


class CharacterSheet(BaseModel):
    """The character card. The state key and the RPG term are the same word."""
    name: str
    description: str          # the cast prompt, verbatim
    style_notes: str = ""     # constraints the reasoning model must honor


class LookEntry(BaseModel):
    """One transmog result in the codex."""
    form: str                            # e.g. "Paladin Plate"
    artifact: ArtifactRef
    anchored_to: Literal["canon", "latest"]
    similarity: Optional[float] = None   # filled by shared/eval/drift.py


# ── the registry ────────────────────────────────────────────────────────────

class StateKeyDef(BaseModel):
    key: str                       # full key incl. prefix, e.g. "temp:candidates"
    tier: Tier
    week: int                      # week that introduces the key (1–5)
    value_type: str                # model name above, or a primitive description
    description: str
    mutability: Mutability = Mutability.FREE
    promoted_from: Optional[str] = None  # key this one graduates from (wider scope, same mechanism)
    status: Literal["active", "stub"] = "stub"  # stub = designed, not yet built


SCHEMA: list[StateKeyDef] = [
    # ── W1 · Control — Character Forge ──────────────────────────────────────
    StateKeyDef(
        key="temp:candidates", tier=Tier.TEMP, week=1, status="active",
        value_type="list[ArtifactRef]",
        description="The cast candidates. Not locked in — gone when the turn ends.",
    ),
    StateKeyDef(
        key="provisional_ref", tier=Tier.SESSION, week=1, status="active",
        value_type="ArtifactRef",
        description=("What cast pinned before anyone locked: unnamed, overridable, "
                     "and the reason a look can never render from nothing."),
    ),
    StateKeyDef(
        key="character_ref", tier=Tier.SESSION, week=1, status="active",
        value_type="ArtifactRef",
        description="The canonical reference art. The anchor every generation is pinned to.",
    ),
    StateKeyDef(
        key="character_sheet", tier=Tier.SESSION, week=1, status="active",
        value_type="CharacterSheet",
        description="The character card: name, cast prompt, style constraints.",
    ),
    StateKeyDef(
        key="current_look", tier=Tier.SESSION, week=1, status="active",
        value_type="LookEntry",
        description="The look on stage right now. A ref — the image lives in Artifacts.",
    ),
    StateKeyDef(
        key="look_history", tier=Tier.SESSION, week=1, status="active",
        value_type="list[LookEntry]",
        description="The codex: every transmog this session, in order. Feeds the drift gate.",
    ),
    StateKeyDef(
        key="app:style_rules", tier=Tier.APP, week=1, status="active",
        value_type="dict",
        description="World style + content rules every character obeys (the after_model guard reads this).",
    ),

    # ── W2 · Decompose — review board + region builder ──────────────────────
    StateKeyDef(key="content_verdict", tier=Tier.SESSION, week=2,
                value_type="dict", description="Reviewer merge: approve / revise / reject, with rule_id citations."),
    StateKeyDef(key="art_notes", tier=Tier.SESSION, week=2,
                value_type="dict", description="art_checker findings (vision). Own key — parallel branches never share one."),
    StateKeyDef(key="lore_notes", tier=Tier.SESSION, week=2,
                value_type="dict", description="lore_checker findings (rules + classifier)."),
    StateKeyDef(key="balance_notes", tier=Tier.SESSION, week=2,
                value_type="dict", description="balance_checker findings (pure SQL — no LLM)."),
    StateKeyDef(key="data_notes", tier=Tier.SESSION, week=2,
                value_type="dict", description="data_checker findings (pure SQL — no LLM)."),
    StateKeyDef(key="region_zones", tier=Tier.SESSION, week=2,
                value_type="list[dict]", description="Parsed zones of the region under construction."),
    StateKeyDef(key="asset_matches", tier=Tier.SESSION, week=2,
                value_type="dict", description="Catalog matches per zone (via the asset-catalog MCP)."),
    StateKeyDef(key="placement_tiers", tier=Tier.SESSION, week=2,
                value_type="dict", description="Router output per need: exact / similar / procedural fallback."),

    # ── W3 · Coordinate — game economy ──────────────────────────────────────
    StateKeyDef(key="order_state", tier=Tier.SESSION, week=3,
                value_type="dict", description="Purchase graph position. State doubles as the audit log."),
    StateKeyDef(key="idempotency_key", tier=Tier.SESSION, week=3,
                value_type="str", description="Replay the same request → charge exactly once. No double-spend."),
    StateKeyDef(key="execution_trace", tier=Tier.SESSION, week=3,
                value_type="list[dict]", description="Node-by-node record; the graph replay renders from this."),
    StateKeyDef(key="pending_trade", tier=Tier.SESSION, week=3,
                value_type="dict", description="Suspended trade/return awaiting its wake condition or a human."),

    # ── W4 · Remember — remember the player ─────────────────────────────────
    StateKeyDef(key="user:character_ref", tier=Tier.USER, week=4,
                value_type="ArtifactRef", promoted_from="character_ref",
                description="W1's anchor, promoted. Same mechanism, wider blast radius."),
    StateKeyDef(key="user:skills", tier=Tier.USER, week=4,
                value_type="list[dict]", description="Unlocked skills. Relational store — JOIN-able facts."),
    StateKeyDef(key="user:inventory", tier=Tier.USER, week=4,
                value_type="list[dict]", promoted_from="asset_matches",
                description="W2's asset catalog as the player's persistent inventory."),
    StateKeyDef(key="user:playstyle", tier=Tier.USER, week=4,
                value_type="dict", mutability=Mutability.WRITE_PROTECTED,
                description="Playstyle profile. Hardcore flag is write-protected — explicit confirmation only."),

    # ── W5 · Live — the live companion ──────────────────────────────────────
    StateKeyDef(key="temp:frame_ref", tier=Tier.TEMP, week=5,
                value_type="ArtifactRef", description="Latest look_now() frame. Momentary by design — never stored."),
    StateKeyDef(key="live_turn_state", tier=Tier.SESSION, week=5,
                value_type="dict", description="Bidi turn bookkeeping: interruptions, in-flight tool calls."),
]


# ── helpers ─────────────────────────────────────────────────────────────────

def keys_for_week(week: int) -> list[StateKeyDef]:
    """Keys introduced in `week` — the rows the schema rail highlights."""
    return [k for k in SCHEMA if k.week == week]


def validate_key(key: str) -> StateKeyDef:
    """Look up a key or raise. Agents call this instead of trusting strings."""
    for k in SCHEMA:
        if k.key == key:
            return k
    raise KeyError(f"'{key}' is not in the state schema — add it to shared/contracts first.")


def check_invariants() -> None:
    keys = [k.key for k in SCHEMA]
    assert len(keys) == len(set(keys)), "duplicate state keys"
    for k in SCHEMA:
        if k.promoted_from:
            assert k.promoted_from in keys, f"{k.key}: promoted_from '{k.promoted_from}' not in schema"
        if k.week == 1:
            assert k.status == "active", f"W1 key {k.key} must be active"
        prefix = k.key.split(":", 1)[0] if ":" in k.key else None
        expected = {Tier.TEMP: "temp", Tier.USER: "user", Tier.APP: "app"}.get(k.tier)
        assert prefix == expected, f"{k.key}: prefix does not match tier {k.tier.value}"


if __name__ == "__main__":
    check_invariants()
    for week in range(1, 6):
        rows = keys_for_week(week)
        print(f"W{week}  " + " · ".join(
            f"{k.key}{'*' if k.status == 'stub' else ''}" for k in rows))
    print("\ninvariants OK — * = stub (designed, not built)")
