"use client";
import { useEffect, useState } from "react";
import { getSave, type SaveFile } from "@/lib/save";

// Your familiar, following you across the valley — portrait · name · ✦ sparks · stamps.
// Reads localStorage after mount (no SSR mismatch); renders nothing before a first claim.

export default function SaveChip() {
  const [save, setSave] = useState<SaveFile | null>(null);
  useEffect(() => {
    const refresh = () => setSave(getSave());
    refresh();
    window.addEventListener("a101-save", refresh);     // same tab
    window.addEventListener("storage", refresh);       // other tabs
    return () => {
      window.removeEventListener("a101-save", refresh);
      window.removeEventListener("storage", refresh);
    };
  }, []);
  if (!save?.name) return null;
  const stamped = save.stamps.filter(Boolean).length;

  return (
    <div className="glass" style={{ display: "flex", alignItems: "center", gap: 9,
      padding: "6px 12px 6px 7px", borderRadius: 999 }}>
      {save.portrait && (
        <img src={save.portrait} alt={save.name} width={30} height={30}
          style={{ borderRadius: "50%", objectFit: "cover", display: "block",
            border: "2px solid var(--gold)" }} />
      )}
      <span style={{ fontSize: 13, fontWeight: 600, color: "var(--ink)" }}>{save.name}</span>
      <span className="mono" style={{ fontSize: 11.5, color: "var(--gold-deep)" }}>✦ {save.sparks}</span>
      <span className="mono" style={{ fontSize: 10.5, color: "var(--faint)" }}>{stamped}/5</span>
    </div>
  );
}
