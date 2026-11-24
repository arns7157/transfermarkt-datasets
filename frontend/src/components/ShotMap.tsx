import type { FotmobShot } from "../api";

const LINE = "rgba(255,255,255,0.22)";

export default function ShotMap({ shots }: { shots: FotmobShot[] }) {
  if (shots.length === 0) {
    return <div className="empty-state">Geen schoten beschikbaar.</div>;
  }

  return (
    <svg viewBox="-4 -4 108 58" width="100%" style={{ maxWidth: 420, display: "block", margin: "0 auto" }}>
      {/* pitch outline - aanvalshelft, doel bovenaan */}
      <rect x={0} y={0} width={100} height={50} fill="none" stroke={LINE} strokeWidth={0.6} />
      <rect x={21} y={0} width={58} height={17} fill="none" stroke={LINE} strokeWidth={0.6} />
      <rect x={37} y={0} width={26} height={5.8} fill="none" stroke={LINE} strokeWidth={0.6} />
      <line x1={45} y1={0} x2={55} y2={0} stroke={LINE} strokeWidth={1.4} />
      <circle cx={50} cy={17} r={0.6} fill={LINE} />

      {shots.map((s, i) => {
        const cx = s.y;
        const cy = 100 - s.x;
        if (cx < -5 || cx > 105 || cy < -5 || cy > 55) return null;
        const isGoal = s.event_type === "Goal";
        const r = Math.sqrt(Math.max(s.expected_goals ?? 0, 0)) * 6 + 1.4;
        return (
          <circle
            key={i}
            cx={cx}
            cy={cy}
            r={r}
            fill={isGoal ? "var(--pos-attack)" : "var(--accent)"}
            fillOpacity={isGoal ? 0.85 : 0.55}
            stroke={isGoal ? "#fff" : "none"}
            strokeWidth={isGoal ? 0.5 : 0}
          >
            <title>
              Minuut {s.minute} - {s.event_type} - xG {s.expected_goals?.toFixed(2)}
            </title>
          </circle>
        );
      })}
    </svg>
  );
}
