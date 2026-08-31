"use client";
import type { TraceEvent } from "@/lib/contracts";

const HOOK_COLOR: Record<string, string> = {
  before_agent: "#b6a9d8", before_model: "#f2cf86", after_model: "#f2cf86",
  before_tool: "#9fe6c4", after_tool: "#9fe6c4",
};

export default function RuntimeInspector({ events }: { events: TraceEvent[] }) {
  const tokens = events.reduce((s, e) => s + (e.cost?.tokens || 0), 0);
  const usd = events.reduce((s, e) => s + (e.cost?.usd || 0), 0);
  const live = events.length > 0;

  return (
    <div style={{ height: "100%", borderRadius: 18, overflow: "hidden", padding: "13px 15px",
      display: "flex", flexDirection: "column",
      background: "linear-gradient(180deg,#2a2540,#231f36)",
      border: "1px solid rgba(150,120,220,.35)", boxShadow: "0 16px 40px rgba(80,60,130,.28)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <span className="mono" style={{ fontSize: 12, fontWeight: 700, letterSpacing: ".16em", color: "#cdbcf5" }}>
          ▸ RUNTIME INSPECTOR
        </span>
        <span className="mono" style={{ fontSize: 10, padding: "3px 9px", borderRadius: 999, letterSpacing: ".08em",
          color: live ? "#9fe6c4" : "#a89cc8",
          border: `1px solid ${live ? "rgba(159,230,196,.5)" : "rgba(168,156,200,.4)"}` }}>
          {live ? "● LIVE" : "idle"}
        </span>
      </div>

      <div className="mono" style={{ fontSize: 11.5, lineHeight: 1.85, flex: 1, overflowY: "auto",
        minHeight: 250, color: "#d9d0f0" }}>
        {events.length === 0 && <div style={{ color: "#8a7fb0" }}>tap an adornment ↑</div>}
        {events.map((e) => (
          <div key={e.span_id} style={{ display: "flex", gap: 8, padding: "1px 0", animation: "riseIn .25s ease both" }}>
            <span style={{ color: "#8a7fb0", minWidth: 84 }}>{e.hook || e.type}</span>
            <span style={{ color: HOOK_COLOR[e.hook || ""] || "#d9d0f0", flex: 1 }}>{e.label}</span>
            {e.cost?.usd > 0 && <span style={{ color: "#8a7fb0" }}>${e.cost.usd.toFixed(2)}</span>}
          </div>
        ))}
      </div>

      <div className="mono" style={{ marginTop: 8, paddingTop: 8, borderTop: "1px solid rgba(150,120,220,.22)",
        display: "flex", justifyContent: "space-between", fontSize: 11, color: "#8a7fb0" }}>
        <span>{events.length} events</span>
        <span>{tokens.toLocaleString()} tok · ${usd.toFixed(2)}</span>
      </div>
    </div>
  );
}
