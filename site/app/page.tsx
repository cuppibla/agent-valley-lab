import Link from "next/link";
import SaveChip from "@/components/SaveChip";

const WORLD = "Agent Valley";
const SERIES = "https://github.com/cuppibla/agent-valley-lab";

// The map IS the course. One district is open — the rest arrive with the series.
// Concept chips (01 · CONTROL) are the wayfinding; district names are flavor.
const DISTRICTS = [
  { id: "grove", img: "/world/zones/grove.jpg", chip: "01 · CONTROL",
    name: "The Summoning Grove", href: "/w1", open: true, status: "OPEN" },
  { id: "buildyard", img: "/world/zones/buildyard.jpg", chip: "02 · DECOMPOSE",
    name: "The Buildyard", open: false, status: "WEEK 2" },
  { id: "market", img: "/world/zones/market.jpg", chip: "03 · COORDINATE",
    name: "Market Street", open: false, status: "WEEK 3" },
  { id: "archive", img: "/world/zones/archive.jpg", chip: "04 · REMEMBER",
    name: "The Archive", open: false, status: "WEEK 4" },
  { id: "nightmarket", img: "/world/zones/nightmarket.jpg", chip: "05 · LIVE",
    name: "The Night Market", open: false, status: "WEEK 5" },
];

export default function Title() {
  return (
    <div className="wrap">
      <div style={{ display: "grid", gridTemplateColumns: "1.15fr 1fr", gap: 22, alignItems: "center",
        marginBottom: 26 }}>
        <div>
          <div className="eyebrow">AGENT 101 · CHAPTER ONE</div>
          <h1 className="serif" style={{ fontWeight: 500, fontSize: 46, margin: "10px 0 8px",
            color: "var(--ink)", lineHeight: 1.02 }}>
            {WORLD}
          </h1>
          <p style={{ color: "var(--sub)", fontSize: 15, margin: 0, maxWidth: "40ch", lineHeight: 1.6 }}>
            Summon a familiar. Watch an agent do it.
          </p>
          <div style={{ display: "flex", gap: 10, marginTop: 18, alignItems: "center" }}>
            <Link href="/w1" style={{ textDecoration: "none", padding: "12px 26px", borderRadius: 13,
              fontWeight: 600, fontSize: 15, color: "#fff",
              background: "linear-gradient(180deg,#a996ff,#8a6bff)",
              boxShadow: "0 8px 24px rgba(138,107,255,.35)" }}>
              ▶ Start
            </Link>
            <SaveChip />
          </div>
        </div>
        <div style={{ borderRadius: 24, overflow: "hidden", border: "1px solid var(--line)",
          boxShadow: "0 18px 50px rgba(150,130,200,.25)", animation: "floaty 5s ease-in-out infinite" }}>
          <img src="/world/zones/square.jpg" alt={`${WORLD} village square`} width="100%"
            style={{ display: "block", aspectRatio: "1.25", objectFit: "cover" }} />
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12 }}>
        {DISTRICTS.map((d) => {
          const card = (
            <div className="glass" style={{ overflow: "hidden", height: "100%", padding: 0,
              display: "flex", flexDirection: "column",
              borderColor: d.open ? "rgba(230,192,105,.65)" : "var(--line)",
              boxShadow: d.open ? "0 0 26px rgba(230,192,105,.35)" : undefined,
              animation: d.open ? "floaty 4.5s ease-in-out infinite" : "none" }}>
              <div style={{ position: "relative" }}>
                <img src={d.img} alt={d.name} width="100%"
                  style={{ display: "block", aspectRatio: "1.05", objectFit: "cover",
                    filter: d.open ? "none" : "grayscale(0.75) saturate(0.7) brightness(1.04)",
                    opacity: d.open ? 1 : 0.55 }} />
                {!d.open && (
                  <div aria-hidden style={{ position: "absolute", inset: 0,
                    background: "linear-gradient(180deg, rgba(238,241,255,.15), rgba(238,241,255,.65))" }} />
                )}
              </div>
              <div style={{ padding: "10px 12px 12px", display: "flex", flexDirection: "column", gap: 4, flex: 1 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span className="mono" style={{ fontSize: 10, letterSpacing: ".14em",
                    color: d.open ? "var(--gold-deep)" : "var(--faint)" }}>{d.chip}</span>
                  <span className="mono" style={{ fontSize: 9, padding: "3px 8px", borderRadius: 999,
                    color: d.open ? "var(--mint)" : "var(--faint)",
                    border: `1px solid ${d.open ? "rgba(111,199,173,.55)" : "var(--line)"}` }}>
                    {d.status}
                  </span>
                </div>
                <div className="serif" style={{ fontSize: 16.5, color: d.open ? "var(--ink)" : "var(--sub)",
                  lineHeight: 1.15 }}>{d.name}</div>
              </div>
            </div>
          );
          return d.open && d.href
            ? <Link key={d.id} href={d.href} style={{ textDecoration: "none" }}>{card}</Link>
            : <div key={d.id} title={`opens with ${d.status}`}>{card}</div>;
        })}
      </div>

      <div className="mono" style={{ fontSize: 11, color: "var(--faint)", marginTop: 14, textAlign: "center" }}>
        <a href={SERIES} target="_blank" rel="noreferrer" style={{ color: "var(--violet-soft)" }}>
          four more districts arrive with the live series ↗
        </a>
      </div>
    </div>
  );
}
