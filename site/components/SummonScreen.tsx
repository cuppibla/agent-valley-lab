"use client";
import { useState } from "react";
import DialogueBox from "@/components/DialogueBox";

type Cand = { id: string; src: string };
const SPECIES = ["fox", "cat", "owl", "dragon", "deer", "bunny", "bear", "dog"];
const EXAMPLES = [
  "moonlit, with silver star freckles",
  "chubby and cloud-grey, tiny and brave",
  "the colour of dawn, with a tiny crown",
];
const NAMES = ["Mochi", "Pip", "Nimbus", "Sora", "Bao", "Yuki"];

export default function SummonScreen(
  { onClaim }: { onClaim: (name: string, src: string, id: string, sessionId: string) => void },
) {
  const [sessionId, setSessionId] = useState("");
  const [desc, setDesc] = useState("");
  const [species, setSpecies] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "summoning" | "done">("idle");
  const [cands, setCands] = useState<Cand[]>([]);
  const [picked, setPicked] = useState<string | null>(null);
  const [name, setName] = useState("Mochi");

  // One kind, or none. Picking a second used to ADD to the list, which sent the
  // forge "a fox or cat or owl" and let the model settle the argument for you.
  const pick = (n: string) => setSpecies((s) => (s === n ? null : n));

  async function summon() {
    setStatus("summoning"); setPicked(null);
    const kind = species ? `${/^[aeiou]/.test(species) ? "an" : "a"} ${species}` : "";
    const description = [kind, desc].filter(Boolean).join(", ") || "a cute animal familiar";
    const res = await fetch("/api/w1/cast", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ description }),
    }).then((r) => r.json()).catch(() => ({ candidates: [] }));
    if (res.session_id) setSessionId(res.session_id);   // the agent's session — /adorn reuses it
    const got: Cand[] = res.candidates || [];
    setCands(got);
    if (got.length === 1) setPicked(got[0].id);   // nothing to choose between
    setStatus("done");
  }

  const line = status === "summoning" ? "The forge is singing…"
    : status === "done" && cands.length > 0
      ? (cands.length > 1 ? "They answered. Claim the one that looks back."
                          : "It answered. Name it, and it's yours.")
    : "Pick a kind — I'll strike the forge.";

  const label = (t: string) => (
    <div className="mono" style={{ fontSize: 11, letterSpacing: ".2em", color: "var(--violet-soft)" }}>{t}</div>
  );

  return (
    <>
      <DialogueBox portrait="/world/npc/maren.jpg" speaker="Maren" role="the Forgekeeper" text={line} />

      {label("PICK A KIND")}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
        {SPECIES.map((n) => {
          const on = species === n;
          return (
            <button key={n} onClick={() => pick(n)}
              style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 14, fontWeight: 600,
                padding: "6px 14px 6px 7px", borderRadius: 13, cursor: "pointer", textTransform: "capitalize",
                border: on ? "2px solid var(--violet)" : "1px solid var(--line)",
                background: on ? "linear-gradient(180deg,#efeaff,#e3dcff)" : "rgba(255,255,255,.6)",
                color: on ? "var(--violet)" : "var(--sub)" }}>
              <img src={`/world/icons/species/${n}.jpg`} alt="" width={30} height={30}
                style={{ borderRadius: 9, display: "block",
                  boxShadow: on ? "0 0 8px rgba(138,107,255,.4)" : "none" }} />
              {n}
            </button>
          );
        })}
      </div>

      <div style={{ marginTop: 16 }}>{label("ADD A TWIST")}</div>
      <div style={{ display: "flex", gap: 8, marginTop: 8, maxWidth: 720 }}>
        <input value={desc} onChange={(e) => setDesc(e.target.value)}
          placeholder="moonlit, silver freckles, a tiny crown…"
          style={{ flex: 1, padding: "13px 15px", borderRadius: 14, border: "1.5px solid var(--line-strong)",
            background: "#fff", fontSize: 15, color: "var(--ink)", outline: "none" }} />
        <button onClick={summon} disabled={status === "summoning"}
          style={{ padding: "0 20px", borderRadius: 12, border: "none", fontWeight: 600, fontSize: 14, color: "#fff",
            background: "linear-gradient(180deg,#a996ff,#8a6bff)", opacity: status === "summoning" ? .7 : 1 }}>
          {status === "summoning" ? "summoning…" : "✦ Summon"}
        </button>
      </div>
      <div style={{ marginTop: 10 }}>
        {EXAMPLES.map((ex) => (
          <button key={ex} onClick={() => setDesc(ex)}
            style={{ fontSize: 12, background: "rgba(176,143,224,.12)", color: "#7a5bb0", border: "1px solid var(--line)",
              borderRadius: 999, padding: "4px 11px", margin: "0 5px 5px 0", cursor: "pointer" }}>{ex}</button>
        ))}
      </div>

      {status === "summoning" && (
        <div style={{ marginTop: 24, textAlign: "center", padding: 30, color: "var(--violet)" }}>
          <div style={{ fontSize: 30, animation: "floaty 1.4s ease-in-out infinite" }}>✦</div>
        </div>
      )}

      {status === "done" && cands.length > 0 && (
        <div style={{ marginTop: 20, maxWidth: 720 }}>
          {label(cands.length > 1 ? "CLAIM ONE" : "YOUR FAMILIAR")}
          <div style={{ display: "grid", gap: 10, marginTop: 10, maxWidth: cands.length > 1 ? "none" : 260,
            gridTemplateColumns: `repeat(${Math.min(cands.length, 4)},1fr)` }}>
            {cands.map((c) => (
              <button key={c.id} onClick={() => setPicked(c.id)}
                style={{ padding: 0, border: "none", background: "none", cursor: "pointer",
                  opacity: picked && picked !== c.id ? .45 : 1 }}>
                <img src={c.src} alt="" width="100%"
                  style={{ aspectRatio: "1", objectFit: "cover", borderRadius: 12, display: "block",
                    border: picked === c.id ? "3px solid var(--gold)" : "1px solid var(--line)",
                    boxShadow: picked === c.id ? "0 0 18px rgba(230,192,105,.5)" : "none" }} />
              </button>
            ))}
          </div>
          {picked && (
            <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 14 }}>
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="name it"
                style={{ width: 140, padding: "9px 13px", borderRadius: 10, border: "1px solid var(--line-strong)",
                  background: "#fff", fontSize: 14, color: "var(--ink)", outline: "none" }} />
              <button onClick={() => setName(NAMES[Math.floor(Math.random() * NAMES.length)])}
                style={{ padding: "8px 10px", borderRadius: 10, border: "1px solid var(--line)",
                  background: "rgba(255,255,255,.6)", cursor: "pointer" }}>🎲</button>
              <button onClick={() => onClaim(name || "Mochi", cands.find((c) => c.id === picked)!.src,
                                     picked!, sessionId)}
                style={{ padding: "9px 18px", borderRadius: 11, border: "none", fontWeight: 600,
                  background: "linear-gradient(180deg,#ffd98a,#e6c069)", cursor: "pointer", color: "#5a3d10" }}>
                Claim ✦
              </button>
            </div>
          )}
        </div>
      )}
    </>
  );
}
