export function formatDate(value: string | null | undefined): string {
  if (!value) return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("nl-BE", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export function formatValue(value: number | null | undefined): string {
  if (!value) return "-";
  if (value >= 1_000_000) return `€${(value / 1_000_000).toFixed(1)}m`;
  if (value >= 1_000) return `€${(value / 1_000).toFixed(0)}k`;
  return `€${value}`;
}

export const POSITION_COLORS: Record<string, string> = {
  Goalkeeper: "var(--pos-goalkeeper)",
  Defender: "var(--pos-defender)",
  Midfield: "var(--pos-midfield)",
  Attack: "var(--pos-attack)",
};
