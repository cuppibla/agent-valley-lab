// Mirrors shared/contracts/trace_event.ts — the shape the Inspector reduces.
// (Copied across the monorepo boundary for the slice; codegen unifies at M3-final.)

export type TraceEventType =
  | "model_call" | "tool_call" | "state_delta" | "memory_read"
  | "memory_write" | "human_pause" | "resume" | "stream_sample";

export type Hook =
  | "before_agent" | "after_agent" | "before_model"
  | "after_model" | "before_tool" | "after_tool" | null;

export interface TraceEvent {
  ts: number;
  run_id: string;
  span_id: string;
  parent_span_id: string | null;
  week: number | null;
  hook: Hook;
  type: TraceEventType;
  label: string;
  payload: Record<string, any>;
  cost: { tokens: number; usd: number };
}

