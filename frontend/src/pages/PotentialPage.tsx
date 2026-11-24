import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getPotentialCandidates, type PotentialCandidate } from "../api";
import PositionBadge from "../components/PositionBadge";
import Skeleton from "../components/Skeleton";
import { formatValue } from "../format";

type Tab = "all" | "broke" | "minutes" | "scoring";

const TABS: { key: Tab; label: string }[] = [
  { key: "all", label: "Alles" },
  { key: "broke", label: "Net doorgebroken" },
  { key: "minutes", label: "Meer speeltijd" },
  { key: "scoring", label: "Begint te scoren" },
];

export default function PotentialPage() {
  const [maxAge, setMaxAge] = useState(23);
  const [recentDays, setRecentDays] = useState(30);
  const [minRecentMatches, setMinRecentMatches] = useState(2);
  const [tab, setTab] = useState<Tab>("all");
  const [candidates, setCandidates] = useState<PotentialCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handle = setTimeout(() => {
      setLoading(true);
      getPotentialCandidates(maxAge, recentDays, minRecentMatches)
        .then(setCandidates)
        .catch((err) => setError(String(err)))
        .finally(() => setLoading(false));
    }, 200);
    return () => clearTimeout(handle);
  }, [maxAge, recentDays, minRecentMatches]);

  const filtered =
    tab === "all"
      ? candidates
      : tab === "broke"
        ? candidates.filter((c) => c.just_broke_through)
        : tab === "minutes"
          ? candidates.filter((c) => c.minutes_trend > 10).sort((a, b) => b.minutes_trend - a.minutes_trend)
          : candidates.filter((c) => c.scoring_trend > 0).sort((a, b) => b.scoring_trend - a.scoring_trend);

  return (
    <div className="page-wide">
      <h1>Potentie</h1>
      <p className="subtitle">
        Jonge spelers die net doorbreken: meer speelminuten krijgen, of beginnen te scoren, vergeleken met eerder dit
        seizoen.
      </p>

      <div className="filter-bar">
        <div>
          <label>Maximale leeftijd: {maxAge}</label>
          <input className="input" type="range" min={16} max={28} value={maxAge} onChange={(e) => setMaxAge(Number(e.target.value))} />
        </div>
        <div>
          <label>Laatste... dagen tellen als "recent": {recentDays}</label>
          <input className="input" type="range" min={14} max={60} value={recentDays} onChange={(e) => setRecentDays(Number(e.target.value))} />
        </div>
        <div>
          <label>Min. aantal recente wedstrijden: {minRecentMatches}</label>
          <input
            className="input"
            type="range"
            min={1}
            max={6}
            value={minRecentMatches}
            onChange={(e) => setMinRecentMatches(Number(e.target.value))}
          />
        </div>
      </div>

      <div className="tab-bar">
        {TABS.map((t) => (
          <button key={t.key} className={tab === t.key ? "active" : ""} onClick={() => setTab(t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      {error && <p className="error">{error}</p>}
      {loading ? (
        <Skeleton rows={10} />
      ) : filtered.length === 0 ? (
        <div className="empty-state">Geen spelers gevonden die aan deze criteria voldoen.</div>
      ) : (
        <>
          <p className="muted" style={{ marginBottom: 10 }}>
            {filtered.length} spelers
          </p>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th></th>
                  <th>Naam</th>
                  <th className="num">Lft.</th>
                  <th>Positie</th>
                  <th>Club</th>
                  <th>Competitie</th>
                  <th className="num">Wedstr.</th>
                  <th className="num">Min/wed.</th>
                  <th className="num">Goals</th>
                  <th className="num">Assists</th>
                  <th className="num">Marktwaarde</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((c) => (
                  <tr key={c.player_id}>
                    <td>{c.current_club_crest_url && <img className="crest" src={c.current_club_crest_url} alt="" />}</td>
                    <td>
                      <Link to={`/spelers/${c.player_id}`}>{c.name}</Link>
                    </td>
                    <td className="num">{c.age}</td>
                    <td>
                      <PositionBadge position={c.position} />
                    </td>
                    <td className="muted">{c.current_club_name}</td>
                    <td className="muted">{c.competition_display}</td>
                    <td className="num">{c.recent_matches}</td>
                    <td className="num">{c.recent_avg_minutes.toFixed(0)}</td>
                    <td className="num">{c.recent_goals}</td>
                    <td className="num">{c.recent_assists}</td>
                    <td className="num badge-value">{formatValue(c.market_value_in_eur)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
