// POST /api/w1/adorn — one dress-up turn.
//
// Proxies to the service's /adorn, which runs the REAL generate_look against the
// claimed familiar. What comes back is a new image AND the trace events the
// Runtime Inspector draws — the state delta is the tool's real output.

import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const maxDuration = 60;

const AGENT_URL = process.env.VALLEY_AGENT_URL || "http://127.0.0.1:8100";

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  try {
    const r = await fetch(`${AGENT_URL}/adorn`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify(body), signal: AbortSignal.timeout(55000),
    });
    if (r.ok) return NextResponse.json(await r.json());
    return NextResponse.json({ error: "agent error" }, { status: 502 });
  } catch {
    return NextResponse.json({ error: "agent service unreachable" }, { status: 502 });
  }
}
