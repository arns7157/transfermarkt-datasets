import type { FotmobMatchShot } from "../api";

const LINE = "rgba(255,255,255,0.22)";

export default function TeamShotMap({
  groups,
}: {
  groups: { shots: FotmobMatchShot[]; color: string; label: string }[];
}) {
  const hasShots = groups.some((g) => g.shots.length > 0);
  if (!hasShots) {
    return <div className="empty-state">Geen shotmap beschikbaar voor deze wedstrijd.</div>;
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "center", gap: 18, marginBottom: 8, fontSize: "0.82rem" }}>
        {groups.map((g) => (
          <span key={g.label} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 10, height: 10, borderRadius: "50%", background: g.color, display: "inline-block" }} />
            {g.label}
          </span>
        ))}
      </div>
      <svg viewBox="-4 -4 108 58" width="100%" style={{ maxWidth: 420, display: "block", margin: "0 auto" }}>
        <rect x={0} y={0} width={100} height={50} fill="none" stroke={LINE} strokeWidth={0.6} />
        <rect x={21} y={0} width={58} height={17} fill="none" stroke={LINE} strokeWidth={0.6} />
        <rect x={37} y={0} width={26} height={5.8} fill="none" stroke={LINE} strokeWidth={0.6} />
        <line x1={45} y1={0} x2={55} y2={0} stroke={LINE} strokeWidth={1.4} />
        <circle cx={50} cy={17} r={0.6} fill={LINE} />

        {groups.map((g) =>
          g.shots.map((s, i) => {
            const cx = s.y;
            const cy = 100 - s.x;
            if (cx < -5 || cx > 105 || cy < -5 || cy > 55) return null;
            const isGoal = s.event_type === "Goal";
            const r = Math.sqrt(Math.max(s.expected_goals ?? 0, 0)) * 6 + 1.4;
            return (
              <circle
                key={`${g.label}-${i}`}
                cx={cx}
                cy={cy}
                r={r}
                fill={g.color}
                fillOpacity={isGoal ? 0.95 : 0.6}
                stroke={isGoal ? "#fff" : "none"}
                strokeWidth={isGoal ? 0.6 : 0}
              >
                <title>
                  {s.player_name} &middot; minuut {s.minute} &middot; {s.event_type} &middot; xG {s.expected_goals?.toFixed(2)}
                </title>
              </circle>
            );
          }),
        )}
      </svg>
      <p className="muted" style={{ textAlign: "center", marginTop: 8, fontSize: "0.78rem" }}>
        Grootte van de marker = xG van het schot.
      </p>
    </div>
  );
}
