import { Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Appearance, Competition } from "../api";
import { formatDate } from "../format";

function seasonStartFor(date: Date): Date {
  const year = date.getUTCMonth() >= 6 ? date.getUTCFullYear() : date.getUTCFullYear() - 1;
  return new Date(Date.UTC(year, 6, 1));
}

export default function FormCurve({
  appearances,
  competitions,
}: {
  appearances: Appearance[];
  competitions: Competition[];
}) {
  if (appearances.length === 0) {
    return <div className="empty-state">Geen wedstrijdstatistieken beschikbaar voor deze speler.</div>;
  }

  const compByCode = new Map(competitions.map((c) => [c.competition_id, c]));
  const sorted = [...appearances].sort((a, b) => a.date.localeCompare(b.date));
  const latestDate = new Date(sorted[sorted.length - 1].date);
  const seasonStart = seasonStartFor(latestDate);
  const seasonApps = sorted.filter((a) => new Date(a.date) >= seasonStart);

  const summaryMap = new Map<string, { matches: number; goals: number; assists: number; minutes: number; yellow: number; red: number }>();
  for (const a of seasonApps) {
    const row = summaryMap.get(a.competition_id) ?? { matches: 0, goals: 0, assists: 0, minutes: 0, yellow: 0, red: 0 };
    row.matches += 1;
    row.goals += a.goals ?? 0;
    row.assists += a.assists ?? 0;
    row.minutes += a.minutes_played ?? 0;
    row.yellow += a.yellow_cards ?? 0;
    row.red += a.red_cards ?? 0;
    summaryMap.set(a.competition_id, row);
  }

  const chartData = seasonApps.map((a) => ({
    date: formatDate(a.date),
    minuten: a.minutes_played ?? 0,
    ga: ((a.goals ?? 0) + (a.assists ?? 0)) * 10,
  }));

  const recent = [...sorted].reverse().slice(0, 10);

  return (
    <>
      {seasonApps.length === 0 ? (
        <div className="empty-state">Geen wedstrijdstatistieken beschikbaar voor deze speler dit seizoen.</div>
      ) : (
        <>
          <div className="table-wrap" style={{ marginBottom: 16 }}>
            <table className="data">
              <thead>
                <tr>
                  <th></th>
                  <th>Competitie</th>
                  <th className="num">Wedstr.</th>
                  <th className="num">Goals</th>
                  <th className="num">Assists</th>
                  <th className="num">Minuten</th>
                  <th className="num">Geel</th>
                  <th className="num">Rood</th>
                </tr>
              </thead>
              <tbody>
                {[...summaryMap.entries()].map(([code, row]) => {
                  const comp = compByCode.get(code);
                  return (
                    <tr key={code}>
                      <td>{comp?.logo_url && <img className="crest" src={comp.logo_url} alt="" />}</td>
                      <td>{comp?.name ?? code}</td>
                      <td className="num">{row.matches}</td>
                      <td className="num">{row.goals}</td>
                      <td className="num">{row.assists}</td>
                      <td className="num">{row.minutes}</td>
                      <td className="num">{row.yellow}</td>
                      <td className="num">{row.red}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="card" style={{ marginBottom: 16 }}>
            <ResponsiveContainer width="100%" height={220}>
              <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="var(--border)" vertical={false} />
                <XAxis dataKey="date" tick={{ fill: "var(--text-faint)", fontSize: 10 }} interval="preserveStartEnd" tickLine={false} axisLine={{ stroke: "var(--border)" }} />
                <YAxis tick={{ fill: "var(--text-faint)", fontSize: 10.5 }} axisLine={false} tickLine={false} width={36} />
                <Tooltip
                  contentStyle={{ background: "var(--surface-raised)", border: "1px solid var(--border)", borderRadius: 8, fontSize: "0.8rem" }}
                  formatter={(value: number, name: string) => (name === "ga" ? [value / 10, "Goals + assists"] : [value, "Minuten"])}
                />
                <Bar dataKey="minuten" fill="var(--pos-defender)" radius={[2, 2, 0, 0]} isAnimationActive={false} />
                <Line type="monotone" dataKey="ga" stroke="var(--pos-attack)" strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </>
      )}

      <h3 style={{ marginBottom: 10 }}>Recente wedstrijden</h3>
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>Datum</th>
              <th></th>
              <th>Competitie</th>
              <th className="num">Goals</th>
              <th className="num">Assists</th>
              <th className="num">Minuten</th>
              <th className="num">Geel</th>
              <th className="num">Rood</th>
            </tr>
          </thead>
          <tbody>
            {recent.map((a) => {
              const comp = compByCode.get(a.competition_id);
              return (
                <tr key={a.appearance_id}>
                  <td className="muted">{formatDate(a.date)}</td>
                  <td>{comp?.logo_url && <img className="crest" src={comp.logo_url} alt="" />}</td>
                  <td>{comp?.name ?? a.competition_id}</td>
                  <td className="num">{a.goals}</td>
                  <td className="num">{a.assists}</td>
                  <td className="num">{a.minutes_played}</td>
                  <td className="num">{a.yellow_cards}</td>
                  <td className="num">{a.red_cards}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
