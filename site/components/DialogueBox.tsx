"use client";
import { useEffect, useRef, useState } from "react";

// Classic RPG dialogue chrome — portrait left, name plate, typed text. A purely
// VISUAL convention (vocabulary firewall: no game terms needed to parse it).

export default function DialogueBox({
  portrait, speaker, role, text, tone = "var(--violet)", children,
}: {
  portrait: string; speaker: string; role?: string; text: string;
  tone?: string; children?: React.ReactNode;   // right-side controls (badges, buttons)
}) {
  const [shown, setShown] = useState(text);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (timer.current) clearInterval(timer.current);
    let i = 0;
    setShown("");
    timer.current = setInterval(() => {
      i += 2;                                   // 2 chars/tick — brisk, game-feel
      setShown(text.slice(0, i));
      if (i >= text.length && timer.current) clearInterval(timer.current);
    }, 14);
    return () => { if (timer.current) clearInterval(timer.current); };
  }, [text]);

  return (
    <div className="glass" style={{ padding: "10px 14px", marginBottom: 12, display: "flex",
      gap: 12, alignItems: "center", flexWrap: "wrap" }}>
      <div style={{ width: 56, height: 56, borderRadius: 14, overflow: "hidden", flexShrink: 0,
        border: "2px solid var(--gold)", boxShadow: "0 0 14px rgba(230,192,105,.35)" }}>
        <img src={portrait} alt={speaker} width={56} height={56}
          style={{ objectFit: "cover", display: "block" }} />
      </div>
      <div style={{ flex: 1, minWidth: 220 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
          <span className="serif" style={{ fontSize: 14.5, color: "var(--ink)", fontWeight: 600 }}>{speaker}</span>
          {role && <span className="mono" style={{ fontSize: 9.5, letterSpacing: ".12em", color: "var(--faint)" }}>{role.toUpperCase()}</span>}
        </div>
        <div style={{ fontSize: 13.5, color: tone, fontWeight: 500, lineHeight: 1.45, minHeight: 20, maxWidth: "62ch" }}>
          {shown}
          {shown.length < text.length && <span style={{ opacity: .5 }}>▎</span>}
        </div>
      </div>
      {children && <div style={{ display: "flex", gap: 8, alignItems: "center" }}>{children}</div>}
    </div>
  );
}
