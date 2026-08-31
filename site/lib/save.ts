// The save file — browser localStorage for now, Firestore later (deployment-plan).
// This little object IS W4's subject matter: what the world remembers about you.

export type SaveFile = {
  name: string;          // your familiar's name
  portrait?: string;     // its current look (small data URL)
  origin?: string;       // the claimed canon portrait — what every look is drawn from
  outfit: string[];      // what it is wearing right now
  sparks: number;        // ✦ earned by clearing trials; spent on Market Street (W3)
  stamps: boolean[];     // one per district, in order
  inventory: string[];   // adornments bought on Market Street
  loves?: string;        // the familiar's one stated preference (W4's profile store)
  updatedAt: number;
};

const KEY = "a101.save";
const EMPTY: SaveFile = { name: "", outfit: [], sparks: 0, stamps: [false, false, false, false, false],
  inventory: [], updatedAt: 0 };

export function getSave(): SaveFile | null {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? { ...EMPTY, ...JSON.parse(raw) } : null;
  } catch {
    return null;
  }
}

export function updateSave(patch: Partial<SaveFile>): SaveFile {
  const next = { ...(getSave() ?? EMPTY), ...patch, updatedAt: Date.now() };
  try { localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* full/blocked: play on */ }
  window.dispatchEvent(new Event("a101-save"));   // same-tab chips refresh live
  return next;
}
