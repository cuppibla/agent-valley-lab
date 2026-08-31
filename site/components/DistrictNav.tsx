"use client";
import Link from "next/link";

const REPO = "https://github.com/cuppibla/agent-valley-lab";

export default function DistrictNav() {
  const btn: React.CSSProperties = {
    display: "inline-flex", alignItems: "center", gap: 5, textDecoration: "none",
    fontSize: 11.5, padding: "6px 11px", borderRadius: 999, color: "var(--sub)",
    border: "1px solid var(--line)", background: "rgba(255,255,255,.55)",
  };

  return (
    <div className="mono" style={{ display: "flex", gap: 6, alignItems: "center" }}>
      <Link href="/" style={{ ...btn, color: "var(--violet)", borderColor: "var(--line-strong)" }}>map</Link>
      <a href={`${REPO}/tree/main/forge/agent`} target="_blank" rel="noreferrer"
        style={{ ...btn, color: "var(--gold-deep)" }} title="the agent behind this district">
        {"</>"} code
      </a>
    </div>
  );
}
