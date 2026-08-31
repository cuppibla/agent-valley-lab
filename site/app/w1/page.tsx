"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import type { TraceEvent } from "@/lib/contracts";
import SummonScreen from "@/components/SummonScreen";
import CharacterForge, { type Turn } from "@/components/CharacterForge";
import RuntimeInspector from "@/components/RuntimeInspector";
import FamiliarPassport, { downloadPassport } from "@/components/FamiliarPassport";
import DialogueBox from "@/components/DialogueBox";
import SaveChip from "@/components/SaveChip";
import DistrictNav from "@/components/DistrictNav";
import { getSave, updateSave } from "@/lib/save";

// Tap to put on, tap again to take off. The outfit accumulates — that IS the state.
const ADORNMENTS = [
  { form: "Crown", icon: "/world/icons/items/crown.jpg" },
  { form: "Starry Cape", icon: "/world/icons/items/cape.jpg" },
  { form: "Crystal Charm", icon: "/world/icons/items/charm.jpg" },
  { form: "Cloud Halo", icon: "/world/icons/items/halo.jpg" },
  { form: "Sparkle Aura", icon: "/world/icons/items/aura.jpg" },
  { form: "Flower Wreath", icon: "/world/icons/items/wreath.jpg" },
];

export default function Grove() {
  const [phase, setPhase] = useState<"summon" | "forge">("summon");
  const [claimed, setClaimed] = useState<{ name: string; src: string } | null>(null);
  const [equipped, setEquipped] = useState<string[]>([]);
  const [hero, setHero] = useState("");
  const [history, setHistory] = useState<Turn[]>([]);
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [finished, setFinished] = useState(false);
  const [stamps, setStamps] = useState<boolean[]>([true, false, false, false, false]);
  const [restored, setRestored] = useState(false);
  // ⚓ canon = before_tool pins every render to the claimed familiar.
  // ◈ latest = it pins to the PREVIOUS render instead — the drift A/B.
  const [anchor, setAnchor] = useState<"canon" | "latest">("canon");

  // Reload the page and your familiar is still here. Pixels die; state doesn't.
  useEffect(() => {
    const s = getSave();
    if (s?.origin && s.name) {
      setClaimed({ name: s.name, src: s.origin });
      setHero(s.portrait || s.origin);
      setEquipped(s.outfit || []);
      setStamps(s.stamps ?? stamps);
      setPhase("forge");
      setRestored(true);
    }
  }, []);

  const name = claimed?.name ?? "your familiar";
  const turns = history.length;

  function claim(n: string, src: string) {
    setClaimed({ name: n, src });
    setHero(src);
    setEquipped([]); setHistory([]); setEvents([]); setErr(null); setFinished(false);
    setRestored(false);
    updateSave({ name: n, origin: src, portrait: src, outfit: [] });
    setPhase("forge");
  }

  function startOver() {
    setEquipped([]); setHistory([]); setEvents([]); setErr(null); setFinished(false);
    setHero(claimed?.src ?? "");
    updateSave({ portrait: claimed?.src, outfit: [] });
  }

  async function toggle(form: string) {
    if (busy || !claimed) return;
    const isOn = equipped.includes(form);
    const op: Turn["op"] = isOn ? "unequip" : "equip";
    const outfit = isOn ? equipped.filter((f) => f !== form) : [...equipped, form];
    setBusy(true); setErr(null); setFinished(false);
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), 45000);  // never let a slow call wedge a button
    try {
      const r = await fetch("/api/w1/adorn", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ op, item: form, outfit, anchor, reference: claimed.src,
                               prev: turns > 0 ? hero : null }),
        signal: ctl.signal,
      });
      const res = await r.json();
      if (res.image) {
        setHero(res.image);
        setEquipped(outfit);
        setHistory((h) => [...h, { op, item: form, src: res.image }]);
        const t = turns;
        setEvents((e) => [...e, ...((res.events || []) as TraceEvent[])
          .map((ev, k) => ({ ...ev, span_id: `${ev.span_id}-${t}-${k}` }))]);
        updateSave({ portrait: res.image, outfit });
      } else {
        setErr(res.error === "agent service unreachable"
          ? "The agent isn't running — start it with  bash valley.sh"
          : `The forge failed: ${res.error || "unknown"}`);
      }
    } catch {
      setErr("That took too long — tap it again.");
    } finally { clearTimeout(timer); setBusy(false); }
  }

  function finish() {
    const prev = getSave();
    const first = !prev?.stamps?.[0];
    const next = [...(prev?.stamps ?? [false, false, false, false, false])];
    next[0] = true;
    const saved = updateSave({ name, portrait: hero, outfit: equipped, stamps: next,
      sparks: (prev?.sparks ?? 0) + (first ? 5 : 0) });
    setStamps(saved.stamps);
    setFinished(true);
  }

  // Maren speaks in single breaths. Never a paragraph.
  const line = busy ? "The forge is working…"
    : finished ? "License granted. The Buildyard opens with Week 2."
    : anchor === "latest" ? `Unpinned — each turn copies the last one, not ${name}.`
    : restored && turns === 0 ? `${name} was still here.`
    : equipped.length === 0 ? "Tap something. Let's dress it up."
    : "Again — it stays itself.";

  return (
    <div className="wrap">
      <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 16 }}>
        <div>
          <span className="mono" style={{ fontSize: 11, letterSpacing: ".24em", color: "var(--violet-soft)" }}>
            01 · CONTROL
          </span>
          <div className="serif" style={{ fontSize: 22, color: "var(--ink)", lineHeight: 1.1 }}>
            {phase === "summon" ? "The Summoning Grove" : name}
          </div>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", gap: 10, alignItems: "center" }}>
          <DistrictNav /><SaveChip />
        </div>
      </div>

      {phase === "summon" && <SummonScreen onClaim={claim} />}

      {phase === "forge" && (
        <>
          <DialogueBox portrait="/world/npc/maren.jpg" speaker="Maren" role="the Forgekeeper"
            text={err ?? line} tone={err ? "var(--rose)" : busy ? "var(--violet)" : "var(--gold-deep)"}>
            <div style={{ display: "flex", gap: 6 }}>
              <button className={`rune ${anchor === "canon" ? "on" : ""}`}
                onClick={() => setAnchor("canon")}>⚓ pinned</button>
              <button className={`rune hot ${anchor === "latest" ? "on" : ""}`}
                onClick={() => setAnchor("latest")}>◈ unpinned</button>
            </div>
          </DialogueBox>

          <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap", alignItems: "center" }}>
            {ADORNMENTS.map((a) => {
              const on = equipped.includes(a.form);
              return (
                <button key={a.form} disabled={busy} onClick={() => toggle(a.form)}
                  title={a.form}
                  style={{ display: "flex", alignItems: "center", gap: 7,
                    padding: "6px 12px 6px 7px", borderRadius: 13, fontSize: 13, fontWeight: 600,
                    cursor: busy ? "default" : "pointer",
                    border: on ? "2px solid var(--mint)" : "1.5px solid var(--gold)",
                    background: on ? "rgba(111,199,173,.16)" : "rgba(255,247,225,.9)",
                    color: on ? "var(--mint)" : "var(--gold-deep)",
                    boxShadow: on ? "none" : "0 0 12px rgba(230,192,105,.3)",
                    opacity: busy ? .55 : 1 }}>
                  <span style={{ position: "relative", display: "block", width: 30, height: 30 }}>
                    <img src={a.icon} alt="" width={30} height={30}
                      style={{ borderRadius: 9, display: "block", opacity: on ? .85 : 1 }} />
                    {on && <span style={{ position: "absolute", right: -4, bottom: -4, width: 15, height: 15,
                      borderRadius: "50%", background: "var(--mint)", color: "#fff", fontSize: 10,
                      display: "grid", placeItems: "center" }}>✓</span>}
                  </span>
                  {a.form}
                </button>
              );
            })}
            {turns >= 2 && !busy && !finished && (
              <button className="rune on" style={{ marginLeft: 4 }} onClick={finish}>✨ finish</button>
            )}
            {turns > 0 && !busy && <button className="rune" onClick={startOver}>↺ start over</button>}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, alignItems: "stretch" }}>
            <CharacterForge heroSrc={hero || claimed?.src} heroName={claimed?.name}
              anchor={anchor} equipped={equipped} history={history} busy={busy} />
            <RuntimeInspector events={events} />
          </div>

          {finished && (
            <div className="glass" style={{ marginTop: 14, padding: "20px 22px", display: "flex",
              gap: 22, alignItems: "center", flexWrap: "wrap",
              borderColor: "rgba(111,199,173,.55)", background: "rgba(111,199,173,.08)" }}>
              <FamiliarPassport name={name} src={hero || claimed?.src} turns={turns}
                outfitCount={equipped.length} stamps={stamps} />
              <div style={{ flex: 1, minWidth: 260 }}>
                <div className="serif" style={{ fontSize: 20, color: "var(--ink)" }}>🎉 Passport minted</div>
                <div className="serif" style={{ fontSize: 15.5, color: "var(--gold-deep)", marginTop: 6 }}>
                  A model talks. A tool acts. What it changed is state.
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 14, flexWrap: "wrap" }}>
                  <button className="rune on" onClick={() =>
                    downloadPassport({ name, src: hero || claimed?.src, turns,
                      outfitCount: equipped.length, stamps })}>⤓ save passport</button>
                  <Link href="/" className="rune" style={{ textDecoration: "none" }}>◂ map</Link>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
