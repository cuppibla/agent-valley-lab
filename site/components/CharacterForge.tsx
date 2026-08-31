"use client";

export type Turn = {
  lookId?: string; op: "equip" | "unequip"; item: string; src: string };

export default function CharacterForge({
  heroSrc, heroName = "Mochi", anchor = "canon", equipped, history, busy = false, onRemove,
}: {
  heroSrc?: string; heroName?: string; anchor?: "canon" | "latest";
  equipped: string[]; history: Turn[]; busy?: boolean;
  // Taking something off is a BUTTON, not a sentence — there is nothing to interpret,
  // so nothing needs a model. The request box and this ✕ sit on the same screen on purpose.
  onRemove?: (item: string) => void;
}) {
  const off = anchor === "latest";
  const ring = off ? "var(--rose)" : "var(--gold)";
  const glow = off ? "rgba(229,138,168,.45)" : "rgba(230,192,105,.5)";

  return (
    <div className="glass" style={{ padding: 18, height: "100%",
      borderColor: off ? "rgba(229,138,168,.5)" : "rgba(230,192,105,.5)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <span className="serif" style={{ fontSize: 17, color: "var(--ink)" }}>🐾 {heroName}</span>
        <span className={`pill ${off ? "warn" : "gold"}`}>{off ? "◈ drifting" : "◆ same face"}</span>
      </div>

      {/* the live hero — the current full outfit, re-rendered every turn */}
      <div style={{ display: "flex", justifyContent: "center", marginBottom: 12 }}>
        <div style={{ position: "relative", width: 184, height: 184, borderRadius: 26, overflow: "hidden",
          border: `3px solid ${ring}`, boxShadow: `0 0 26px ${glow}`,
          animation: "floaty 4.5s ease-in-out infinite" }}>
          {heroSrc
            ? <img src={heroSrc} alt={heroName} width={184} height={184} style={{ objectFit: "cover", display: "block" }} />
            : <div style={{ width: "100%", height: "100%", background: "#f0ecf8" }} />}
          {busy && (
            <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center",
              background: "rgba(40,32,60,.34)", backdropFilter: "blur(1px)" }}>
              <span style={{ fontSize: 30, animation: "floaty 1.2s ease-in-out infinite" }}>✦</span>
            </div>
          )}
        </div>
      </div>

      {/* the outfit = accumulated session state */}
      <div className="mono" style={{ fontSize: 10.5, letterSpacing: ".14em", color: "var(--faint)", marginBottom: 6 }}>
        OUTFIT · {equipped.length}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, minHeight: 26, marginBottom: 12 }}>
        {equipped.length === 0
          ? <span style={{ fontSize: 12.5, color: "var(--faint)" }}>ask for something ↑</span>
          : equipped.map((it) => (
            <span key={it} style={{ display: "inline-flex", alignItems: "center", gap: 5,
              fontSize: 12, fontWeight: 600, padding: "3px 6px 3px 10px", borderRadius: 999,
              background: "rgba(111,199,173,.16)", color: "var(--mint)", border: "1px solid rgba(111,199,173,.4)" }}>
              {it}
              {onRemove && (
                <button disabled={busy} onClick={() => onRemove(it)} title={`take off ${it}`}
                  style={{ border: "none", background: "transparent", color: "var(--mint)",
                    cursor: busy ? "default" : "pointer", fontSize: 13, lineHeight: 1,
                    padding: "0 2px", opacity: busy ? .4 : .75 }}>✕</button>
              )}
            </span>
          ))}
      </div>

      {/* the multiturn history — every add/remove, in order */}
      <div className="mono" style={{ fontSize: 10.5, letterSpacing: ".14em", color: "var(--faint)", marginBottom: 6 }}>
        SESSION · {history.length}
      </div>
      <div style={{ display: "flex", gap: 8, overflowX: "auto", paddingBottom: 4, minHeight: history.length ? undefined : 8 }}>
        {history.map((t, i) => (
          <div key={i} style={{ flexShrink: 0, width: 74, animation: "riseIn .35s ease both" }}>
            <img src={t.src} alt={t.item} width={74} height={74}
              style={{ borderRadius: 10, objectFit: "cover", display: "block",
                border: "1px solid var(--line)", boxShadow: "0 3px 9px rgba(150,130,200,.12)" }} />
            <div style={{ fontSize: 9.5, textAlign: "center", marginTop: 3, whiteSpace: "nowrap",
              overflow: "hidden", textOverflow: "ellipsis",
              color: t.op === "unequip" ? "var(--rose)" : "var(--mint)" }}>
              {t.op === "unequip" ? "−" : "+"} {t.item}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
