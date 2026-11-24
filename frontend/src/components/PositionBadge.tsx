import { POSITION_COLORS } from "../format";

export default function PositionBadge({ position }: { position: string | null | undefined }) {
  if (!position) return null;
  const color = POSITION_COLORS[position] ?? "var(--text-faint)";
  return (
    <span className="badge" style={{ background: color }}>
      {position}
    </span>
  );
}
