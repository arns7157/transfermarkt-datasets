import { useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { comparePlayers, searchPlayers, type CompareResult, type PlayerSummary } from "../api";
import { formatDate, formatValue } from "../format";

const LINE_COLORS = ["#22C55E", "#3B82F6", "#F59E0B", "#EF4444"];

export default function ComparePage() {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<PlayerSummary[]>([]);
  const [selected, setSelected] = useState<PlayerSummary[]>([]);
  const [result, setResult] = useState<CompareResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!query) {
      setSuggestions([]);
      return;
    }
    const handle = setTimeout(() => {
      searchPlayers({ q: query }, "market_value", "desc", 8).then((res) => setSuggestions(res.items));
    }, 200);
    return () => clearTimeout(handle);
  }, [query]);

  useEffect(() => {
    if (selected.length < 2) {
      setResult(null);
      return;
    }
    comparePlayers(selected.map((p) => p.player_id))
      .then(setResult)
      .catch((err) => setError(String(err)));
  }, [selected]);

  function addPlayer(p: PlayerSummary) {
    if (selected.length >= 4 || selected.some((s) => s.player_id === p.player_id)) return;
    setSelected((s) => [...s, p]);
    setQuery("");
    setSuggestions([]);
  }

  function removePlayer(playerId: number) {
    setSelected((s) => s.filter((p) => p.player_id !== playerId));
  }

  const rows: [string, (p: CompareResult["players"][number]) => string][] = [
    ["Club", (p) => p.current_club_name ?? "-"],
    ["Leeftijd", (p) => p.age ?? "-"],
    ["Positie", (p) => p.position ?? "-"],
    ["Marktwaarde", (p) => formatValue(p.market_value_in_eur)],
    ["Wedstrijden (seizoen)", (p) => String(p.season_totals.matches)],
    ["Goals (seizoen)", (p) => String(p.season_totals.goals)],
    ["Assists (seizoen)", (p) => String(p.season_totals.assists)],
    ["Minuten (seizoen)", (p) => String(p.season_totals.minutes)],
  ];

  const byPlayerId = new Map<number, { date: string; value: number }[]>();
  if (result) {
    for (const v of result.valuations) {
      const list = byPlayerId.get(v.player_id) ?? [];
      list.push({ date: v.date, value: v.market_value_in_eur });
      byPlayerId.set(v.player_id, list);
    }
  }
  const allDates = [...new Set(result?.valuations.map((v) => v.date) ?? [])].sort();
  const chartData = allDates.map((date) => {
    const row: Record<string, number | string> = { date: formatDate(date) };
    for (const p of result?.players ?? []) {
      const point = byPlayerId.get(p.player_id)?.find((v) => v.date === date);
      if (point) row[p.name] = point.value;
    }
    return row;
  });

  return (
    <div className="page-wide">
      <h1>Vergelijken</h1>
      <p className="subtitle">Zet 2 tot 4 spelers naast elkaar.</p>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 12 }}>
        {selected.map((p) => (
          <span key={p.player_id} className="badge" style={{ background: "var(--surface-raised)", color: "var(--text)", border: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 6 }}>
            {p.name}
            <button
              onClick={() => removePlayer(p.player_id)}
              style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", padding: 0, fontSize: "0.9rem" }}
            >
              &times;
            </button>
          </span>
        ))}
      </div>

      {selected.length < 4 && (
        <div style={{ position: "relative", maxWidth: 420, marginBottom: 20 }}>
          <input
            className="input"
            placeholder="Zoek speler op naam..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {suggestions.length > 0 && (
            <div className="card" style={{ position: "absolute", zIndex: 10, width: "100%", padding: 6, marginTop: -8 }}>
              {suggestions.map((p) => (
                <div
                  key={p.player_id}
                  onClick={() => addPlayer(p)}
                  style={{ padding: "8px 10px", borderRadius: 6, cursor: "pointer", fontSize: "0.88rem" }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface-raised)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                >
                  {p.name} <span className="muted">({p.current_club_name ?? "onbekende club"})</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {error && <p className="error">{error}</p>}
      {selected.length < 2 ? (
        <div className="empty-state">Kies minstens 2 spelers om te vergelijken.</div>
      ) : !result ? (
        <div className="skeleton" style={{ height: 200 }} />
      ) : (
        <>
          <div style={{ display: "grid", gridTemplateColumns: `repeat(${result.players.length}, 1fr)`, gap: 16, marginBottom: 20 }}>
            {result.players.map((p) => (
              <div key={p.player_id} className="card" style={{ textAlign: "center" }}>
                {p.image_url && <img src={p.image_url} alt="" style={{ width: 88, height: 88, borderRadius: "50%", objectFit: "cover", marginBottom: 8 }} />}
                <div style={{ fontWeight: 700 }}>{p.name}</div>
                <div className="muted" style={{ fontSize: "0.82rem" }}>
                  {p.current_club_crest_url && <img className="crest" src={p.current_club_crest_url} alt="" />}
                  {p.current_club_name}
                </div>
                <div className="muted" style={{ fontSize: "0.82rem" }}>
                  {p.country_of_citizenship_flag_url && <img className="crest" src={p.country_of_citizenship_flag_url} alt="" />}
                  {p.country_of_citizenship}
                </div>
              </div>
            ))}
          </div>

          <div className="table-wrap" style={{ marginBottom: 24 }}>
            <table className="data">
              <tbody>
                {rows.map(([label, getValue]) => (
                  <tr key={label}>
                    <td className="muted" style={{ fontWeight: 600 }}>
                      {label}
                    </td>
                    {result.players.map((p) => (
                      <td key={p.player_id}>{getValue(p)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h2>Marktwaarde-verloop</h2>
          {chartData.length === 0 ? (
            <div className="empty-state">Geen marktwaarde-historiek beschikbaar voor deze spelers.</div>
          ) : (
            <div className="card">
              <ResponsiveContainer width="100%" height={320}>
                <LineChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                  <CartesianGrid stroke="var(--border)" vertical={false} />
                  <XAxis dataKey="date" tick={{ fill: "var(--text-faint)", fontSize: 10 }} tickLine={false} axisLine={{ stroke: "var(--border)" }} />
                  <YAxis tickFormatter={(v) => formatValue(v)} tick={{ fill: "var(--text-faint)", fontSize: 10.5 }} axisLine={false} tickLine={false} width={56} />
                  <Tooltip
                    formatter={(v: number) => formatValue(v)}
                    contentStyle={{ background: "var(--surface-raised)", border: "1px solid var(--border)", borderRadius: 8, fontSize: "0.8rem" }}
                  />
                  <Legend wrapperStyle={{ fontSize: "0.82rem" }} />
                  {result.players.map((p, i) => (
                    <Line
                      key={p.player_id}
                      type="monotone"
                      dataKey={p.name}
                      stroke={LINE_COLORS[i % LINE_COLORS.length]}
                      strokeWidth={2}
                      dot={{ r: 3 }}
                      connectNulls
                      isAnimationActive={false}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}
    </div>
  );
}
