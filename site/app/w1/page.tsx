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

// Suggestions, not commands. Tapping one WRITES A SENTENCE into the request box —
// the traveler sees the words before they are sent, and can change them. That is the
// whole point: a button carries no intent; a sentence does, and an agent eats intent.
const SUGGESTIONS = [
  { label: "a golden crown", icon: "/world/icons/items/crown.jpg" },
  { label: "a starry cape", icon: "/world/icons/items/cape.jpg" },
  { label: "a crystal charm", icon: "/world/icons/items/charm.jpg" },
  { label: "a cloud halo", icon: "/world/icons/items/halo.jpg" },
  { label: "a sparkle aura", icon: "/world/icons/items/aura.jpg" },
  { label: "a flower wreath", icon: "/world/icons/items/wreath.jpg" },
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
  // Identity lock: when ON, before_tool OVERRULES whichever reference you picked and
  // anchors to canon anyway. Your pick is a request; the callback is the rule.
  const [identityLock, setIdentityLock] = useState(true);
  const [request, setRequest] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [canonId, setCanonId] = useState("canon");
  const [refId, setRefId] = useState("canon");        // which render to work from

  // Reload the page and your familiar is still here. Pixels die; state doesn't.
  useEffect(() => {
    const s = getSave();
    if (s?.origin && s.name) {
      // A restored familiar has no live agent session — mint one. The dresser works
      // from the reference image we send, so it does not need the old session's sheet.
      setSessionId(`s-restored-${Math.random().toString(36).slice(2, 10)}`);
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

  function claim(n: string, src: string, id: string, sid: string) {
    setClaimed({ name: n, src });
    setSessionId(sid); setCanonId(id); setRefId(id); setRequest("");
    setHero(src);
    setEquipped([]); setHistory([]); setEvents([]); setErr(null); setFinished(false);
    setRestored(false);
    updateSave({ name: n, origin: src, portrait: src, outfit: [] });
    setPhase("forge");
  }

  function startOver() {
    setEquipped([]); setHistory([]); setEvents([]); setErr(null); setFinished(false);
    setRefId(canonId); setRequest("");
    setHero(claimed?.src ?? "");
    updateSave({ portrait: claimed?.src, outfit: [] });
  }

  // The renders so far, newest last. This is what the reference strip shows.
  function gallery() {
    return [{ id: canonId, src: claimed?.src ?? "", label: "canon" },
            ...history.map((h, i) => ({ id: h.lookId ?? `look_${i}`, src: h.src,
                                        label: `turn ${i + 1}` }))];
  }

  async function send(text?: string, op: "equip" | "unequip" = "equip") {
    const msg = (text ?? request).trim();
    if (busy || !claimed || !msg) return;
    const outfit = op === "unequip" ? equipped.filter((x) => x !== msg) : [...equipped, msg];
    setBusy(true); setErr(null); setFinished(false);
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), 60000);
    try {
      const picked = gallery().find((g) => g.id === refId) ?? gallery()[0];
      const r = await fetch("/api/w1/adorn", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          // The agent reads this and picks the tool. Removing is phrased for it too —
          // the tool is the same one either way; only the sentence differs.
          request: op === "unequip" ? `take off ${msg}` : msg,
          item: msg, op, outfit,
          history_ids: history.map((h, i) => h.lookId ?? `look_${i}`),
          canon_id: canonId, canon: claimed.src,
          reference_id: picked.id, reference: picked.src,
          identity_lock: identityLock,        // ← before_tool honours or overrules the pick
        }),
        signal: ctl.signal,
      });
      const res = await r.json();
      if (res.image) {
        setHero(res.image);
        setEquipped(outfit);
        if (op === "equip") setRequest("");
        const nextId = res.look_id ?? `look_${history.length}`;
        setHistory((h) => [...h, { op, item: msg, src: res.image, lookId: nextId }]);
        setRefId(identityLock ? canonId : nextId);   // unlocked → the strip follows you forward
        const tn = history.length;
        setEvents((e) => [...e, ...((res.events || []) as TraceEvent[])
          .map((ev, k) => ({ ...ev, span_id: `${ev.span_id}-${tn}-${k}` }))]);
        updateSave({ portrait: res.image, outfit });
      } else {
        setErr(res.error === "agent service unreachable"
          ? "The agent isn't running — start it with  bash valley.sh"
          : `The forge failed: ${res.error || "unknown"}`);
      }
    } catch {
      setErr("That took too long — send it again.");
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
    : !identityLock ? `Lock off — each render copies the one you picked, not ${name}.`
    : restored && turns === 0 ? `${name} was still here.`
    : equipped.length === 0 ? "Tell me what to add. Or tap a suggestion."
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
              <button className={`rune ${identityLock ? "on" : "hot"}`}
                onClick={() => setIdentityLock(!identityLock)}
                title="When on, before_tool overrules whichever reference you picked.">
                {identityLock ? "🔒 identity lock · on" : "🔓 identity lock · off"}
              </button>
            </div>
          </DialogueBox>

          {/* ── the request: what you type is what the agent reads ─────────── */}
          <div className="glass" style={{ padding: "14px 16px", marginBottom: 12 }}>
            <div className="mono" style={{ fontSize: 10.5, letterSpacing: ".2em",
              color: "var(--violet-soft)", marginBottom: 8 }}>YOUR REQUEST → THE AGENT</div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input value={request} disabled={busy}
                onChange={(e) => setRequest(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") send(); }}
                placeholder="give it a tiny wizard hat…"
                style={{ flex: 1, padding: "10px 13px", borderRadius: 12, fontSize: 15,
                  border: "1.5px solid var(--gold)", background: "rgba(255,247,225,.9)",
                  color: "var(--ink)", outline: "none" }} />
              <button className="rune on" disabled={busy || !request.trim()}
                onClick={() => send()} style={{ opacity: busy || !request.trim() ? .5 : 1 }}>
                ✦ send
              </button>
            </div>
            <div style={{ display: "flex", gap: 7, marginTop: 10, flexWrap: "wrap" }}>
              {SUGGESTIONS.map((s) => {
                const worn = equipped.includes(s.label);
                return (
                  <button key={s.label} disabled={busy} onClick={() => setRequest(s.label)}
                    title={worn ? `already on — ✕ it below to take it off`
                                : `writes “${s.label}” into the box`}
                    style={{ display: "flex", alignItems: "center", gap: 6,
                      padding: "4px 11px 4px 5px", borderRadius: 12, fontSize: 12.5, fontWeight: 600,
                      cursor: busy ? "default" : "pointer",
                      border: worn ? "1.5px solid var(--mint)" : "1.5px solid var(--gold)",
                      background: worn ? "rgba(111,199,173,.16)" : "rgba(255,247,225,.9)",
                      color: worn ? "var(--mint)" : "var(--gold-deep)",
                      opacity: busy ? .55 : 1 }}>
                    <img src={s.icon} alt="" width={22} height={22}
                      style={{ borderRadius: 7, display: "block", opacity: worn ? .8 : 1 }} />
                    {s.label}{worn ? " ✓" : ""}
                  </button>
                );
              })}
            </div>
          </div>

          {/* ── the reference: which picture goes in the envelope ───────────── */}
          <div className="glass" style={{ padding: "12px 16px", marginBottom: 14 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 9 }}>
              <div className="mono" style={{ fontSize: 10.5, letterSpacing: ".2em",
                color: "var(--violet-soft)" }}>WORK FROM THIS PICTURE</div>
              <div style={{ fontSize: 12, color: identityLock ? "var(--mint)" : "var(--rose)" }}>
                {identityLock
                  ? "identity lock is on — before_tool will overrule your pick and use canon"
                  : "lock is off — your pick is honoured, and every render copies the last one"}
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {gallery().map((g, i) => {
                const on = g.id === refId;
                return (
                  <button key={`${g.id}-${i}`} disabled={busy} onClick={() => setRefId(g.id)}
                    title={g.id}
                    style={{ padding: 3, borderRadius: 12, cursor: busy ? "default" : "pointer",
                      border: on ? "2.5px solid var(--violet)" : "1.5px solid var(--gold)",
                      background: "transparent", lineHeight: 0,
                      opacity: identityLock && !on ? .45 : 1 }}>
                    <img src={g.src} alt={g.label} width={54} height={54}
                      style={{ borderRadius: 9, display: "block", objectFit: "cover" }} />
                    <div className="mono" style={{ fontSize: 9, marginTop: 3, lineHeight: 1.2,
                      color: on ? "var(--violet)" : "var(--gold-deep)" }}>{g.label}</div>
                  </button>
                );
              })}
            </div>
          </div>

          <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap", alignItems: "center" }}>
            {turns >= 2 && !busy && !finished && (
              <button className="rune on" onClick={finish}>✨ finish</button>
            )}
            {turns > 0 && !busy && <button className="rune" onClick={startOver}>↺ start over</button>}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, alignItems: "stretch" }}>
            <CharacterForge heroSrc={hero || claimed?.src} heroName={claimed?.name}
              anchor={identityLock ? "canon" : "latest"} equipped={equipped} history={history}
              busy={busy} onRemove={(it) => send(it, "unequip")} />
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
