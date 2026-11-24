import type { SortOrder } from "../api";

export default function SortHeader({
  label,
  field,
  sort,
  order,
  onSort,
  align,
}: {
  label: string;
  field: string;
  sort: string;
  order: SortOrder;
  onSort: (field: string) => void;
  align?: "num";
}) {
  const active = sort === field;
  return (
    <th className={align === "num" ? "num" : undefined}>
      <button
        onClick={() => onSort(field)}
        style={{
          background: "none",
          border: "none",
          cursor: "pointer",
          color: active ? "var(--accent-text)" : "inherit",
          font: "inherit",
          textTransform: "inherit",
          letterSpacing: "inherit",
          padding: 0,
        }}
      >
        {label} {active ? (order === "desc" ? "↓" : "↑") : ""}
      </button>
    </th>
  );
}
