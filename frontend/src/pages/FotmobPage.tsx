import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import {
  getFotmobMatchDetail,
  getFotmobMatches,
  getFotmobPlayerStatKeys,
  getFotmobPlayerStats,
  getFotmobStandings,
  getFotmobTeamStatKeys,
  getFotmobTeamStats,
  listFotmobLeagues,
  type FotmobLeaderboardRow,
  type FotmobLeague,
  type FotmobMatch,
  type FotmobMatchDetail,
  type FotmobStanding,
} from "../api";
import Skeleton from "../components/Skeleton";
import TeamShotMap from "../components/TeamShotMap";
import { formatDate } from "../format";

type Tab = "standings" | "players" | "teams" | "matches";

export default function FotmobPage() {
  const [leagues, setLeagues] = useState<FotmobLeague[]>([]);
  const [leagueKey, setLeagueKey] = useState<string>("");
  const [tab, setTab] = useState<Tab>("standings");
  const [standings, setStandings] = useState<FotmobStanding[]>([]);
  const [playerStatKeys, setPlayerStatKeys] = useState<string[]>([]);
  const [playerStat, setPlayerStat] = useState<string>("");
  const [playerLeaderboard, setPlayerLeaderboard] = useState<FotmobLeaderboardRow[]>([]);
  const [teamStatKeys, setTeamStatKeys] = useState<string[]>([]);
  const [teamStat, setTeamStat] = useState<string>("");
  const [teamLeaderboard, setTeamLeaderboard] = useState<FotmobLeaderboardRow[]>([]);
  const [matches, setMatches] = useState<FotmobMatch[]>([]);
  const [matchId, setMatchId] = useState<number | null>(null);
  const [matchDetail, setMatchDetail] = useState<FotmobMatchDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listFotmobLeagues()
      .then((ls) => {
        setLeagues(ls);
        if (ls.length > 0) setLeagueKey(ls[0].key);
      })
      .catch((err) => setError(String(err)));
  }, []);

  useEffect(() => {
    if (!leagueKey) return;
    setLoading(true);
    setMatchId(null);
    setMatchDetail(null);
    Promise.all([
      getFotmobStandings(leagueKey).then(setStandings),
      getFotmobPlayerStatKeys(leagueKey).then((keys) => {
        setPlayerStatKeys(keys);
        setPlayerStat(keys.includes("goals") ? "goals" : (keys[0] ?? ""));
      }),
      getFotmobTeamStatKeys(leagueKey).then((keys) => {
        setTeamStatKeys(keys);
        setTeamStat(keys[0] ?? "");
      }),
      getFotmobMatches(leagueKey).then((ms) => setMatches(ms.filter((m) => m.finished))),
    ])
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, [leagueKey]);

  useEffect(() => {
    if (!leagueKey || !playerStat) return;
    getFotmobPlayerStats(leagueKey, playerStat).then(setPlayerLeaderboard).catch((err) => setError(String(err)));
  }, [leagueKey, playerStat]);

  useEffect(() => {
    if (!leagueKey || !teamStat) return;
    getFotmobTeamStats(leagueKey, teamStat).then(setTeamLeaderboard).catch((err) => setError(String(err)));
  }, [leagueKey, teamStat]);

  useEffect(() => {
    if (!leagueKey || matchId == null) return;
    setMatchDetail(null);
    getFotmobMatchDetail(leagueKey, matchId).then(setMatchDetail).catch((err) => setError(String(err)));
  }, [leagueKey, matchId]);

  const sortedMatches = useMemo(
    () => [...matches].sort((a, b) => (a.date ?? "").localeCompare(b.date ?? "")),
    [matches],
  );

  useEffect(() => {
    if (tab === "matches" && matchId == null && sortedMatches.length > 0) {
      setMatchId(sortedMatches[sortedMatches.length - 1].match_id);
    }
  }, [tab, matchId, sortedMatches]);

  if (error) return <p className="error">{error}</p>;

  return (
    <div className="page">
      <h1>FotMob</h1>
      <p className="subtitle">
        Geavanceerde statistieken via FotMob - aanvullend op de Transfermarkt-data, los van die pijplijn.
      </p>

      <select className="input" value={leagueKey} onChange={(e) => setLeagueKey(e.target.value)}>
        {leagues.map((l) => (
          <option key={l.key} value={l.key}>
            {l.label}
          </option>
        ))}
      </select>

      <div className="tab-bar">
        <button className={tab === "standings" ? "active" : ""} onClick={() => setTab("standings")}>
          Standenlijst
        </button>
        <button className={tab === "players" ? "active" : ""} onClick={() => setTab("players")}>
          Spelersstatistieken
        </button>
        <button className={tab === "teams" ? "active" : ""} onClick={() => setTab("teams")}>
          Teamstatistieken
        </button>
        <button className={tab === "matches" ? "active" : ""} onClick={() => setTab("matches")}>
          Wedstrijden
        </button>
      </div>

      {loading ? (
        <Skeleton rows={8} />
      ) : tab === "standings" ? (
        standings.length === 0 ? (
          <div className="empty-state">Geen standenlijst beschikbaar (bv. een bekercompetitie).</div>
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th className="num">#</th>
                  <th>Club</th>
                  <th className="num">Gesp.</th>
                  <th className="num">W</th>
                  <th className="num">G</th>
                  <th className="num">V</th>
                  <th>Doelpunten</th>
                  <th className="num">Saldo</th>
                  <th className="num">Ptn</th>
                </tr>
              </thead>
              <tbody>
                {standings.map((s) => (
                  <tr key={`${s.group_name}-${s.team_id}`}>
                    <td className="num muted">{s.idx}</td>
                    <td>
                      {s.name}
                      {s.group_name && <span className="muted"> ({s.group_name})</span>}
                    </td>
                    <td className="num">{s.played}</td>
                    <td className="num">{s.wins}</td>
                    <td className="num">{s.draws}</td>
                    <td className="num">{s.losses}</td>
                    <td>{s.scores_str}</td>
                    <td className="num">{s.goal_con_diff}</td>
                    <td className="num badge-value">{s.pts}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      ) : tab === "players" ? (
        <>
          <select className="input" value={playerStat} onChange={(e) => setPlayerStat(e.target.value)}>
            {playerStatKeys.map((k) => (
              <option key={k} value={k}>
                {k.replace(/_/g, " ")}
              </option>
            ))}
          </select>
          {playerLeaderboard.length === 0 ? (
            <div className="empty-state">Geen data voor deze statistiek.</div>
          ) : (
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th className="num">#</th>
                    <th>Speler</th>
                    <th className="num">{playerStat.replace(/_/g, " ")}</th>
                  </tr>
                </thead>
                <tbody>
                  {playerLeaderboard.map((row) => (
                    <tr key={row.fotmob_id}>
                      <td className="num muted">{row.rank}</td>
                      <td>{row.name}</td>
                      <td className="num badge-value">{row.value}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      ) : tab === "teams" ? (
        <>
          <select className="input" value={teamStat} onChange={(e) => setTeamStat(e.target.value)}>
            {teamStatKeys.map((k) => (
              <option key={k} value={k}>
                {k.replace(/_/g, " ")}
              </option>
            ))}
          </select>
          {teamLeaderboard.length === 0 ? (
            <div className="empty-state">Geen data voor deze statistiek.</div>
          ) : (
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th className="num">#</th>
                    <th>Club</th>
                    <th className="num">{teamStat.replace(/_/g, " ")}</th>
                  </tr>
                </thead>
                <tbody>
                  {teamLeaderboard.map((row) => (
                    <tr key={row.team_id}>
                      <td className="num muted">{row.rank}</td>
                      <td>{row.name}</td>
                      <td className="num badge-value">{row.value}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      ) : sortedMatches.length === 0 ? (
        <div className="empty-state">Geen gedetailleerde wedstrijddata beschikbaar.</div>
      ) : (
        <>
          <select
            className="input"
            value={matchId ?? ""}
            onChange={(e) => setMatchId(Number(e.target.value))}
          >
            {sortedMatches.map((m) => (
              <option key={m.match_id} value={m.match_id}>
                Speeldag {m.round}: {m.home_name} {m.score ?? "-"} {m.away_name}
                {m.date ? ` (${formatDate(m.date)})` : ""}
              </option>
            ))}
          </select>

          {!matchDetail ? (
            <div className="skeleton" style={{ height: 300, marginTop: 16 }} />
          ) : (
            <MatchDetailView detail={matchDetail} />
          )}
        </>
      )}
    </div>
  );
}

function MatchDetailView({ detail }: { detail: FotmobMatchDetail }) {
  const { home, away, score_str, status_reason, top_stats, momentum, lineup, shots } = detail;

  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ display: "grid", gridTemplateColumns: "3fr 2fr 3fr", alignItems: "center", gap: 12 }}>
        <div style={{ textAlign: "right", fontSize: "1.2rem", fontWeight: 700 }}>
          {home.name} {home.image_url && <img src={home.image_url} height={28} style={{ verticalAlign: "middle", marginLeft: 8 }} alt="" />}
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "1.6rem", fontWeight: 800 }}>{score_str}</div>
          <div className="muted" style={{ fontSize: "0.85rem" }}>{status_reason}</div>
        </div>
        <div style={{ textAlign: "left", fontSize: "1.2rem", fontWeight: 700 }}>
          {away.image_url && <img src={away.image_url} height={28} style={{ verticalAlign: "middle", marginRight: 8 }} alt="" />} {away.name}
        </div>
      </div>

      <h2>Statistieken</h2>
      {top_stats.length === 0 ? (
        <div className="empty-state">Geen wedstrijdstatistieken beschikbaar voor deze wedstrijd.</div>
      ) : (
        top_stats.map((s, i) => <StatBar key={`${s.title}-${i}`} stat={s} homeColor={home.color} awayColor={away.color} />)
      )}

      <h2>Shotmap</h2>
      <TeamShotMap
        groups={[
          { shots: shots.filter((s) => s.team_id === home.id), color: home.color, label: home.name },
          { shots: shots.filter((s) => s.team_id === away.id), color: away.color, label: away.name },
        ]}
      />

      <h2>Momentum</h2>
      {momentum.length === 0 ? (
        <div className="empty-state">Geen momentum-data beschikbaar voor deze wedstrijd.</div>
      ) : (
        <div className="card">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={momentum} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <XAxis dataKey="minute" tick={{ fill: "var(--text-faint)", fontSize: 10 }} tickLine={false} axisLine={{ stroke: "var(--border)" }} />
              <YAxis hide />
              <Tooltip
                contentStyle={{ background: "var(--surface-raised)", border: "1px solid var(--border)", borderRadius: 8, fontSize: "0.8rem" }}
                labelFormatter={(m) => `Minuut ${m}`}
              />
              <Bar dataKey="value" isAnimationActive={false}>
                {momentum.map((m, i) => (
                  <Cell key={i} fill={m.value >= 0 ? home.color : away.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <p className="muted" style={{ textAlign: "center", fontSize: "0.78rem" }}>
            Boven de lijn = momentum {home.name}, onder = momentum {away.name}.
          </p>
        </div>
      )}

      <h2>Opstellingen</h2>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
        {[lineup.home, lineup.away].map((team, i) => (
          <div key={i}>
            <p style={{ fontWeight: 700, marginBottom: 8 }}>
              {team.name} - {team.formation}
            </p>
            <div className="table-wrap" style={{ marginBottom: 8 }}>
              <table className="data">
                <thead>
                  <tr>
                    <th className="num">Nr</th>
                    <th>Naam</th>
                    <th className="num">Rapportcijfer</th>
                  </tr>
                </thead>
                <tbody>
                  {team.starters.map((p, j) => (
                    <tr key={j}>
                      <td className="num muted">{p.shirt_number}</td>
                      <td>{p.name}</td>
                      <td className="num">{p.rating ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {team.subs.length > 0 && <p className="muted" style={{ fontSize: "0.82rem" }}>Bank: {team.subs.join(", ")}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}

function StatBar({
  stat,
  homeColor,
  awayColor,
}: {
  stat: { title: string; home: number | string; away: number | string };
  homeColor: string;
  awayColor: string;
}) {
  const home = Number(stat.home);
  const away = Number(stat.away);
  const total = Math.abs(home) + Math.abs(away) || 1;
  const homePct = (Math.abs(home) / total) * 100;
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem", marginBottom: 4 }}>
        <span style={{ fontWeight: 600 }}>{stat.home}</span>
        <span className="muted">{stat.title}</span>
        <span style={{ fontWeight: 600 }}>{stat.away}</span>
      </div>
      <div style={{ display: "flex", height: 6, borderRadius: 3, overflow: "hidden", background: "var(--border)" }}>
        <div style={{ width: `${homePct}%`, background: homeColor }} />
        <div style={{ width: `${100 - homePct}%`, background: awayColor }} />
      </div>
    </div>
  );
}

