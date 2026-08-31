// POST /api/w1/cast — the app's proxy to the real agent.
//
// The button already knows which tool it wants, so no model routes here: this
// hands `cast_candidates` straight to the Python service, which runs the REAL
// ADK tool on real Nano Banana. That is the whole difference between this door
// and the adk web door, where the model picks the tool itself.
//
// If the service isn't running, fall back to a recording of a real run so the
// valley never breaks mid-demo.

import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const maxDuration = 90;

const AGENT_URL = process.env.VALLEY_AGENT_URL || "http://127.0.0.1:8100";

// A recording of a real summon, for when the agent isn't running.
const REPLAY = [{ id: "cast-0", src: "/proto/cats/cast-0.jpg" }];

function replayTrace() {
  const run = "cast-" + Math.round(Date.now() / 1000);
  return [
    { hook: "before_tool", type: "tool_call", label: "tool_call cast_candidates(description=…)" },
    { hook: "after_tool", type: "state_delta", label: "+ temp:candidates (1)  ·  replay" },
  ].map((e, i) => ({ ...e, run_id: run, span_id: `${run}-${i}`, week: 1, payload: {},
    cost: { tokens: 0, usd: 0 } }));
}

export async function POST(req: NextRequest) {
  const { description = "" } = await req.json().catch(() => ({}));
  try {
    const r = await fetch(`${AGENT_URL}/cast`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ description }),
      signal: AbortSignal.timeout(85000),
    });
    if (r.ok) {
      const data = await r.json();
      if (data.candidates?.length) return NextResponse.json(data);
    }
  } catch {
    /* service down → replay below */
  }
  return NextResponse.json({ mode: "replay", candidates: REPLAY, events: replayTrace(),
    note: "agent not running — start it with: bash valley.sh" });
}
