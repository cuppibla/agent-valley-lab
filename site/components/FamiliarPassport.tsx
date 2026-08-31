"use client";

// The Familiar Passport — minted when a familiar is claimed, stamped once per district.
// Five stamps = a full passport. The shareable artifact of the whole series.

const STAMP_LABELS = ["01", "02", "03", "04", "05"];
const FOIL = "linear-gradient(135deg,#e6c069 0%,#f0dca8 18%,#a996ff 45%,#8a6bff 60%,#6fc7ad 85%,#e6c069 100%)";

export type PassportProps = {
  name: string;
  src?: string;          // the familiar's current look (data URL or path)
  turns: number;
  outfitCount: number;
  stamps: boolean[];     // one per district, in order
};

export default function FamiliarPassport({ name, src, turns, outfitCount, stamps }: PassportProps) {
  return (
    <div style={{ width: 300, borderRadius: 20, padding: 3, background: FOIL, flexShrink: 0,
      boxShadow: "0 14px 40px rgba(150,130,200,.35)" }}>
      <div style={{ borderRadius: 17, background: "linear-gradient(180deg,#fffdf8,#f6f1ff)", padding: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <span className="mono" style={{ fontSize: 9.5, letterSpacing: ".22em", color: "var(--violet-soft)" }}>
            AGENT VALLEY
          </span>
          <span className="mono" style={{ fontSize: 9, letterSpacing: ".12em", color: "var(--faint)" }}>
            AGENT 101 LIVE
          </span>
        </div>
        <div className="serif" style={{ fontSize: 15, color: "var(--ink)", margin: "2px 0 10px" }}>
          Familiar Passport
        </div>

        {src ? (
          <img src={src} alt={name} width="100%"
            style={{ aspectRatio: "1", objectFit: "cover", borderRadius: 13, display: "block",
              border: "1px solid var(--line)" }} />
        ) : (
          <div style={{ aspectRatio: "1", borderRadius: 13, background: "#f0ecf8" }} />
        )}

        <div className="serif" style={{ fontSize: 21, color: "var(--ink)", marginTop: 10, lineHeight: 1.1 }}>
          {name}
        </div>
        <div style={{ fontSize: 11.5, color: "var(--sub)", marginTop: 2 }}>
          Summoned in the Grove · {turns} turn{turns === 1 ? "" : "s"} · {outfitCount} adornment{outfitCount === 1 ? "" : "s"}
        </div>

        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          {STAMP_LABELS.map((lb, i) => {
            const on = !!stamps[i];
            return (
              <div key={lb} style={{ flex: 1, aspectRatio: "1", borderRadius: "50%", display: "grid",
                placeItems: "center", fontSize: on ? 15 : 9.5,
                color: on ? "#fff" : "var(--faint)",
                background: on ? "linear-gradient(180deg,#8fd8bd,#6fc7ad)" : "rgba(255,255,255,.7)",
                border: on ? "2px solid rgba(111,199,173,.8)" : "1.5px dashed var(--line-strong)",
                boxShadow: on ? "0 0 12px rgba(111,199,173,.45)" : "none" }}
                className={on ? undefined : "mono"}>
                {on ? "✦" : lb}
              </div>
            );
          })}
        </div>
        <div className="mono" style={{ fontSize: 8.5, letterSpacing: ".14em", color: "var(--faint)",
          textAlign: "center", marginTop: 8 }}>
          FIVE STAMPS · FIVE DISTRICTS · ONE FAMILIAR
        </div>
      </div>
    </div>
  );
}

// ── downloadable PNG (canvas-composed; no DOM-capture dependency) ────────────

function rr(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

export async function downloadPassport({ name, src, turns, outfitCount, stamps }: PassportProps) {
  const W = 640, H = 998, PAD = 34;
  const cv = document.createElement("canvas");
  cv.width = W; cv.height = H;
  const ctx = cv.getContext("2d")!;

  // foil frame
  const foil = ctx.createLinearGradient(0, 0, W, H);
  foil.addColorStop(0, "#e6c069"); foil.addColorStop(.35, "#a996ff");
  foil.addColorStop(.6, "#8a6bff"); foil.addColorStop(.85, "#6fc7ad"); foil.addColorStop(1, "#e6c069");
  rr(ctx, 0, 0, W, H, 40); ctx.fillStyle = foil; ctx.fill();

  // parchment body
  const body = ctx.createLinearGradient(0, 8, 0, H - 8);
  body.addColorStop(0, "#fffdf8"); body.addColorStop(1, "#f6f1ff");
  rr(ctx, 8, 8, W - 16, H - 16, 34); ctx.fillStyle = body; ctx.fill();

  // header
  ctx.fillStyle = "#9b8fc4"; ctx.font = "600 20px ui-monospace, Menlo, monospace";
  ctx.fillText("A G E N T   V A L L E Y", PAD, PAD + 26);
  ctx.fillStyle = "#b3aecb"; ctx.font = "500 16px ui-monospace, Menlo, monospace";
  const right = "AGENT 101 LIVE";
  ctx.fillText(right, W - PAD - ctx.measureText(right).width, PAD + 26);
  ctx.fillStyle = "#38304f"; ctx.font = "500 30px Georgia, serif";
  ctx.fillText("Familiar Passport", PAD, PAD + 66);

  // portrait
  if (src) {
    const img = new Image();
    await new Promise<void>((res, rej) => { img.onload = () => res(); img.onerror = () => rej(); img.src = src; });
    const S = W - PAD * 2, y0 = PAD + 90;
    ctx.save(); rr(ctx, PAD, y0, S, S, 26); ctx.clip();
    const side = Math.min(img.width, img.height);
    ctx.drawImage(img, (img.width - side) / 2, (img.height - side) / 2, side, side, PAD, y0, S, S);
    ctx.restore();
  }

  // name + line
  const yN = PAD + 90 + (W - PAD * 2) + 52;
  ctx.fillStyle = "#38304f"; ctx.font = "500 44px Georgia, serif";
  ctx.fillText(name, PAD, yN);
  ctx.fillStyle = "#7a7492"; ctx.font = "400 21px -apple-system, sans-serif";
  ctx.fillText(`Summoned in the Grove · ${turns} turn${turns === 1 ? "" : "s"} · ${outfitCount} adornment${outfitCount === 1 ? "" : "s"}`, PAD, yN + 34);

  // stamps
  const n = STAMP_LABELS.length, gap = 18, d = (W - PAD * 2 - gap * (n - 1)) / n, yS = yN + 66;
  STAMP_LABELS.forEach((lb, i) => {
    const x = PAD + i * (d + gap), on = !!stamps[i];
    ctx.beginPath(); ctx.arc(x + d / 2, yS + d / 2, d / 2 - 2, 0, Math.PI * 2);
    if (on) {
      const g = ctx.createLinearGradient(0, yS, 0, yS + d);
      g.addColorStop(0, "#8fd8bd"); g.addColorStop(1, "#6fc7ad");
      ctx.fillStyle = g; ctx.fill();
      ctx.fillStyle = "#fff"; ctx.font = "500 34px Georgia, serif";
      ctx.fillText("✦", x + d / 2 - 12, yS + d / 2 + 12);
    } else {
      ctx.setLineDash([6, 6]); ctx.strokeStyle = "#cfc7e2"; ctx.lineWidth = 2.5; ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = "#b3aecb"; ctx.font = "500 19px ui-monospace, Menlo, monospace";
      ctx.fillText(lb, x + d / 2 - 11, yS + d / 2 + 7);
    }
  });
  ctx.fillStyle = "#b3aecb"; ctx.font = "500 15px ui-monospace, Menlo, monospace";
  const foot = "FIVE STAMPS · FIVE DISTRICTS · ONE FAMILIAR";
  ctx.fillText(foot, (W - ctx.measureText(foot).width) / 2, yS + d + 40);

  const a = document.createElement("a");
  a.download = `${name.toLowerCase().replace(/\s+/g, "-")}-passport.png`;
  a.href = cv.toDataURL("image/png");
  a.click();
}
