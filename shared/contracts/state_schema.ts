/**
 * The growing state schema — TS mirror of state_schema.py.
 * Hand-kept in sync at M0; codegen from the Python source lands at M3.
 * The site renders SCHEMA week-by-week as the navigation rail.
 */

export type Tier = "temp" | "session" | "user" | "app";
export type Mutability = "free" | "confirm" | "write_protected";
export type KeyStatus = "active" | "stub";

export interface ArtifactRef {
  filename: string;
  version: number;
}

export interface CharacterSheet {
  name: string;
  description: string;
  style_notes: string;
}

export interface LookEntry {
  form: string;
  artifact: ArtifactRef;
  anchored_to: "canon" | "latest";
  similarity: number | null;
}

export interface StateKeyDef {
  key: string;
  tier: Tier;
  week: 1 | 2 | 3 | 4 | 5;
  value_type: string;
  description: string;
  mutability: Mutability;
  promoted_from?: string;
  status: KeyStatus;
}

export const SCHEMA: StateKeyDef[] = [
  // ── W1 · Control — Character Forge ────────────────────────────────────
  { key: "temp:candidates", tier: "temp", week: 1, value_type: "ArtifactRef[]", mutability: "free", status: "active",
    description: "The cast candidates. Not locked in — gone when the turn ends." },
  { key: "provisional_ref", tier: "session", week: 1, value_type: "ArtifactRef", mutability: "free", status: "active",
    description: "What cast pinned before anyone locked: unnamed, overridable, and the reason a look can never render from nothing." },
  { key: "character_ref", tier: "session", week: 1, value_type: "ArtifactRef", mutability: "free", status: "active",
    description: "The canonical reference art. The anchor every generation is pinned to." },
  { key: "character_sheet", tier: "session", week: 1, value_type: "CharacterSheet", mutability: "free", status: "active",
    description: "The character card: name, cast prompt, style constraints." },
  { key: "current_look", tier: "session", week: 1, value_type: "LookEntry", mutability: "free", status: "active",
    description: "The look on stage right now. A ref — the image lives in Artifacts." },
  { key: "look_history", tier: "session", week: 1, value_type: "LookEntry[]", mutability: "free", status: "active",
    description: "The codex: every transmog this session, in order. Feeds the drift gate." },
  { key: "app:style_rules", tier: "app", week: 1, value_type: "dict", mutability: "free", status: "active",
    description: "World style + content rules every character obeys (the after_model guard reads this)." },

  // ── W2 · Decompose — review board + region builder ────────────────────
  { key: "content_verdict", tier: "session", week: 2, value_type: "dict", mutability: "free", status: "stub",
    description: "Reviewer merge: approve / revise / reject, with rule_id citations." },
  { key: "art_notes", tier: "session", week: 2, value_type: "dict", mutability: "free", status: "stub",
    description: "art_checker findings (vision). Own key — parallel branches never share one." },
  { key: "lore_notes", tier: "session", week: 2, value_type: "dict", mutability: "free", status: "stub",
    description: "lore_checker findings (rules + classifier)." },
  { key: "balance_notes", tier: "session", week: 2, value_type: "dict", mutability: "free", status: "stub",
    description: "balance_checker findings (pure SQL — no LLM)." },
  { key: "data_notes", tier: "session", week: 2, value_type: "dict", mutability: "free", status: "stub",
    description: "data_checker findings (pure SQL — no LLM)." },
  { key: "region_zones", tier: "session", week: 2, value_type: "dict[]", mutability: "free", status: "stub",
    description: "Parsed zones of the region under construction." },
  { key: "asset_matches", tier: "session", week: 2, value_type: "dict", mutability: "free", status: "stub",
    description: "Catalog matches per zone (via the asset-catalog MCP)." },
  { key: "placement_tiers", tier: "session", week: 2, value_type: "dict", mutability: "free", status: "stub",
    description: "Router output per need: exact / similar / procedural fallback." },

  // ── W3 · Coordinate — game economy ────────────────────────────────────
  { key: "order_state", tier: "session", week: 3, value_type: "dict", mutability: "free", status: "stub",
    description: "Purchase graph position. State doubles as the audit log." },
  { key: "idempotency_key", tier: "session", week: 3, value_type: "string", mutability: "free", status: "stub",
    description: "Replay the same request → charge exactly once. No double-spend." },
  { key: "execution_trace", tier: "session", week: 3, value_type: "dict[]", mutability: "free", status: "stub",
    description: "Node-by-node record; the graph replay renders from this." },
  { key: "pending_trade", tier: "session", week: 3, value_type: "dict", mutability: "free", status: "stub",
    description: "Suspended trade/return awaiting its wake condition or a human." },

  // ── W4 · Remember — remember the player ───────────────────────────────
  { key: "user:character_ref", tier: "user", week: 4, value_type: "ArtifactRef", mutability: "free", status: "stub",
    promoted_from: "character_ref",
    description: "W1's anchor, promoted. Same mechanism, wider blast radius." },
  { key: "user:skills", tier: "user", week: 4, value_type: "dict[]", mutability: "free", status: "stub",
    description: "Unlocked skills. Relational store — JOIN-able facts." },
  { key: "user:inventory", tier: "user", week: 4, value_type: "dict[]", mutability: "free", status: "stub",
    promoted_from: "asset_matches",
    description: "W2's asset catalog as the player's persistent inventory." },
  { key: "user:playstyle", tier: "user", week: 4, value_type: "dict", mutability: "write_protected", status: "stub",
    description: "Playstyle profile. Hardcore flag is write-protected — explicit confirmation only." },

  // ── W5 · Live — the live companion ────────────────────────────────────
  { key: "temp:frame_ref", tier: "temp", week: 5, value_type: "ArtifactRef", mutability: "free", status: "stub",
    description: "Latest look_now() frame. Momentary by design — never stored." },
  { key: "live_turn_state", tier: "session", week: 5, value_type: "dict", mutability: "free", status: "stub",
    description: "Bidi turn bookkeeping: interruptions, in-flight tool calls." },
];

export const keysForWeek = (week: number): StateKeyDef[] =>
  SCHEMA.filter((k) => k.week === week);
