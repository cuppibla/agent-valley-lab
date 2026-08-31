/**
 * TraceEvent — TS mirror of trace_event.py.
 * One stream, three consumers: <RuntimeInspector> reduces it, shared/eval
 * scores it, JSONL fixtures replay it. LIVE (SSE) and REPLAY (JSONL) both
 * deliver exactly this shape, so the Inspector renders them identically.
 */

export type TraceEventType =
  | "model_call"
  | "tool_call"
  | "state_delta"
  | "memory_read"
  | "memory_write"
  | "human_pause"
  | "resume"
  | "stream_sample"; // W5 continuous tracks; payload: {track, value, ...}

export type Hook =
  | "before_agent"
  | "after_agent"
  | "before_model"
  | "after_model"
  | "before_tool"
  | "after_tool";

export interface Cost {
  tokens: number;
  usd: number;
}

export interface TraceEvent {
  ts: number; // epoch seconds
  run_id: string;
  span_id: string;
  parent_span_id: string | null;
  week: number | null; // which zone produced it
  hook: Hook | null;   // lifecycle door — the Inspector badge
  type: TraceEventType;
  label: string;       // short human line, e.g. "ref_pin → character_ref"
  payload: Record<string, unknown>;
  cost: Cost;
}

/** Parse one JSONL line into a TraceEvent (REPLAY loading). */
export const parseTraceLine = (line: string): TraceEvent =>
  JSON.parse(line) as TraceEvent;

/** Parse a whole JSONL fixture. */
export const parseTraceJsonl = (text: string): TraceEvent[] =>
  text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean)
    .map(parseTraceLine);
