import {
  Calendar,
  Coins,
  Crosshair,
  FileClock,
  Flag,
  Footprints,
  LogIn,
  MapPin,
  RefreshCw,
  Ruler,
  Shirt,
  Star,
  TrendingUp,
  UserRound,
} from "lucide-react";
import type { ComponentType, ReactNode } from "react";
import { formatDate, formatValue } from "../format";

function Field({
  icon: Icon,
  label,
  value,
}: {
  icon: ComponentType<{ size?: number }>;
  label: string;
  value: ReactNode;
}) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: 30,
          height: 30,
          borderRadius: 8,
          background: "var(--accent-dim)",
          color: "var(--accent-text)",
          flexShrink: 0,
          marginTop: 1,
        }}
      >
        <Icon size={15} />
      </div>
      <div style={{ minWidth: 0 }}>
        <div className="muted" style={{ fontSize: "0.66rem", textTransform: "uppercase", letterSpacing: "0.04em" }}>
          {label}
        </div>
        <div style={{ marginTop: 2, fontSize: "0.9rem", fontWeight: 600, overflowWrap: "break-word" }}>{value}</div>
      </div>
    </div>
  );
}

export default function BioCard({ player }: { player: Record<string, unknown> }) {
  const str = (k: string) => (player[k] as string | null)?.trim() || undefined;
  const num = (k: string) => (player[k] as number | null) ?? undefined;
  const dateField = (k: string) => (str(k) ? formatDate(str(k)) : undefined);
  const valueField = (k: string) => (num(k) ? formatValue(num(k)) : undefined);

  return (
    <div className="card">
      <h3 style={{ marginBottom: 16 }}>Biografie</h3>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))", gap: "20px 16px" }}>
        <Field icon={Calendar} label="Geboortedatum" value={str("date_of_birth")} />
        <Field
          icon={MapPin}
          label="Geboorteplaats"
          value={[str("place_of_birth_city"), str("country_of_birth")].filter(Boolean).join(", ") || undefined}
        />
        <Field icon={Flag} label="Nationaliteit" value={str("country_of_citizenship")} />
        <Field icon={Ruler} label="Lengte" value={num("height_in_cm") ? `${num("height_in_cm")} cm` : undefined} />
        <Field icon={Footprints} label="Voet" value={str("foot")} />
        <Field icon={Crosshair} label="Sub-positie" value={str("sub_position")} />
        <Field icon={Coins} label="Huidige marktwaarde" value={valueField("market_value_in_eur")} />
        <Field icon={TrendingUp} label="Hoogste marktwaarde ooit" value={valueField("highest_market_value_in_eur")} />
        <Field icon={FileClock} label="Contract tot" value={dateField("contract_expiration_date")} />
        <Field icon={LogIn} label="Bij club sinds" value={dateField("joined")} />
        <Field icon={RefreshCw} label="Laatste contractverlenging" value={dateField("day_of_last_contract_extension")} />
        <Field icon={UserRound} label="Zaakwaarnemer" value={str("player_agent_name")} />
        <Field icon={Shirt} label="Uitrusting" value={str("outfitter")} />
        <Field
          icon={Star}
          label="Debuut hoogste klasse"
          value={
            str("debut_highest_division_date")
              ? `${dateField("debut_highest_division_date")} - ${str("debut_highest_division_club") ?? ""}`
              : undefined
          }
        />
      </div>
      {str("url") && (
        <div style={{ paddingTop: 16, marginTop: 16, borderTop: "1px solid var(--border)" }}>
          <a href={str("url")} target="_blank" rel="noreferrer" style={{ fontSize: "0.85rem", color: "var(--accent-text)" }}>
            Volledig profiel op Transfermarkt &rarr;
          </a>
        </div>
      )}
    </div>
  );
}
