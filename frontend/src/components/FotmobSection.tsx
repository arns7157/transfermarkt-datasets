import { Activity, Clock, Share2, Star, Target, TrendingUp } from "lucide-react";
import { useEffect, useState } from "react";
import type { ComponentType } from "react";
import { PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer } from "recharts";
import { getFotmobPlayerMatch, type FotmobPlayerMatch } from "../api";
import { GROUP_ORDER, HEADLINE_STAT_NAMES, MATCH_STAT_GROUP_LABELS_NL, statLabel } from "../statLabels";
import ShotMap from "./ShotMap";

const RADAR_LABELS: Record<string, string> = {
  Goals: "Doelpunten",
  "Total shots": "Schotpogingen",
  "Chances created": "Kansen gecreëerd",
  Touches: "Balcontacten",
  "Aerial duels won": "Luchtduels",
  "Defensive actions": "Verdediging",
};

const HEADLINE_STATS: [string, string, ComponentType<{ size?: number }>][] = [
  ["Goals", "Doelpunten", Target],
  ["Assists", "Assists", Share2],
  ["FotMob rating", "Rapportcijfer", Star],
  ["Expected goals (xG)", "xG", TrendingUp],
  ["Expected assists (xA)", "xA", Activity],
  ["Minutes played", "Minuten", Clock],
];

export default function FotmobSection({ playerId }: { playerId: number }) {
  const [data, setData] = useState<FotmobPlayerMatch | null>(null);

  useEffect(() => {
    setData(null);
    getFotmobPlayerMatch(playerId).then(setData).catch(() => setData({ matched: false }));
  }, [playerId]);

  if (!data) {
    return (
      <>
        <h2>FotMob-statistieken</h2>
        <div className="skeleton" style={{ height: 160 }} />
      </>
    );
  }

  if (!data.matched) {
    return (
      <>
        <h2>FotMob-statistieken</h2>
        <div className="empty-state">
          Geen geavanceerde FotMob-statistieken gevonden voor deze speler (geen eenduidige club-/naammatch).
        </div>
      </>
    );
  }

  const totals = data.totals ?? {};
  const radarData = Object.entries(RADAR_LABELS).map(([key, label]) => ({
    stat: label,
    value: data.percentiles?.[key] ?? 0,
  }));

  const byGroup = new Map<string, [string, number][]>();
  for (const [name, entry] of Object.entries(totals)) {
    if (HEADLINE_STAT_NAMES.has(name)) continue;
    const list = byGroup.get(entry.group) ?? [];
    list.push([name, entry.value]);
    byGroup.set(entry.group, list);
  }
  return (
    <>
      <h2>FotMob-statistieken</h2>
      <p className="muted" style={{ marginTop: -8, marginBottom: 16 }}>
        {data.league_label} &middot; {data.matches_played} wedstrijden met data
      </p>

      <div className="stat-grid" style={{ marginBottom: 24 }}>
        {HEADLINE_STATS.map(([key, label, Icon]) => (
          <div key={key} className="stat-tile">
            <div className="stat-label">
              <Icon size={13} />
              {label}
            </div>
            <div className="stat-value">{totals[key]?.value ?? "-"}</div>
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, alignItems: "start" }}>
        <div className="card">
          <h3 style={{ marginBottom: 8 }}>Percentiel t.o.v. competitie</h3>
          <ResponsiveContainer width="100%" height={280}>
            <RadarChart data={radarData} outerRadius="58%" margin={{ top: 10, bottom: 10, left: 30, right: 30 }}>
              <PolarGrid stroke="var(--border)" />
              <PolarAngleAxis dataKey="stat" tick={{ fill: "var(--text-muted)", fontSize: 10.5 }} />
              <Radar
                dataKey="value"
                stroke="var(--accent)"
                fill="var(--accent)"
                fillOpacity={0.35}
                isAnimationActive={false}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h3 style={{ marginBottom: 8 }}>Shotmap (seizoen)</h3>
          <ShotMap shots={data.shots ?? []} />
          <p className="muted" style={{ textAlign: "center", marginTop: 8, marginBottom: 0, fontSize: "0.78rem" }}>
            Grootte = xG &middot; rood = doelpunt
          </p>
        </div>
      </div>

      <h3 style={{ marginTop: 28, marginBottom: 12 }}>Alle seizoensstatistieken</h3>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
        {GROUP_ORDER.filter((g) => byGroup.has(g)).map((group) => {
          const entries = byGroup.get(group)!.sort((a, b) => b[1] - a[1]);
          const maxValue = Math.max(1, ...entries.map(([, v]) => v));
          return (
          <div key={group} className="card">
            <h3 style={{ marginBottom: 10, fontSize: "0.85rem", color: "var(--text-muted)" }}>
              {MATCH_STAT_GROUP_LABELS_NL[group] ?? group}
            </h3>
            {entries.map(([name, value]) => (
                <div key={name} style={{ marginBottom: 10 }}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: "0.82rem",
                      marginBottom: 3,
                    }}
                  >
                    <span className="muted">{statLabel(name)}</span>
                    <span style={{ fontWeight: 600 }}>{value}</span>
                  </div>
                  <div style={{ height: 4, background: "var(--border)", borderRadius: 2 }}>
                    <div
                      style={{
                        height: "100%",
                        width: `${Math.min(100, (value / maxValue) * 100)}%`,
                        background: "var(--accent)",
                        borderRadius: 2,
                      }}
                    />
                  </div>
                </div>
              ))}
          </div>
          );
        })}
      </div>
    </>
  );
}
