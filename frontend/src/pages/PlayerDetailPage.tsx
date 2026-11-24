import { Cake, FileClock, Footprints, Ruler, TrendingUp } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getPlayer, listCompetitions, type Competition, type PlayerDetail } from "../api";
import BioCard from "../components/BioCard";
import FormCurve from "../components/FormCurve";
import FotmobSection from "../components/FotmobSection";
import MarketValueChart from "../components/MarketValueChart";
import PositionBadge from "../components/PositionBadge";
import { formatDate, formatValue } from "../format";

type Tab = "overview" | "form" | "fotmob" | "history";

const TABS: { key: Tab; label: string }[] = [
  { key: "overview", label: "Overzicht" },
  { key: "form", label: "Vormcurve" },
  { key: "fotmob", label: "FotMob" },
  { key: "history", label: "Transfers & Blessures" },
];

export default function PlayerDetailPage() {
  const { playerId } = useParams();
  const [data, setData] = useState<PlayerDetail | null>(null);
  const [competitions, setCompetitions] = useState<Competition[]>([]);
  const [tab, setTab] = useState<Tab>("overview");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listCompetitions().then(setCompetitions).catch(() => {});
  }, []);

  useEffect(() => {
    if (!playerId) return;
    setData(null);
    setTab("overview");
    getPlayer(Number(playerId))
      .then(setData)
      .catch((err) => setError(String(err)));
  }, [playerId]);

  if (error) return <p className="error">{error}</p>;
  if (!data)
    return (
      <div className="page-wide">
        <div className="skeleton" style={{ height: 140, borderRadius: 14, marginBottom: 20 }} />
        <div className="skeleton" style={{ height: 300, borderRadius: 14 }} />
      </div>
    );

  const { player, transfers, injuries, valuations } = data;
  const competition = competitions.find((c) => c.competition_id === player.current_club_domestic_competition_id);

  return (
    <div className="page-wide">
      <Link className="back-link" to="/">
        &larr; Terug naar spelers zoeken
      </Link>

      <div className="profile-hero">
        {player.image_url && <img className="avatar-lg" src={String(player.image_url)} alt="" />}
        <div style={{ minWidth: 0 }}>
          <h1>{player.name}</h1>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <PositionBadge position={player.position} />
            <span className="badge-value" style={{ fontSize: "1rem" }}>
              {formatValue(player.market_value_in_eur)}
            </span>
          </div>
          <div className="profile-meta-row">
            {player.current_club_crest_url && (
              <Link
                className="meta-chip"
                to={player.current_club_id != null ? `/clubs/${player.current_club_id}` : "#"}
                style={{ textDecoration: "none" }}
              >
                <img className="crest" src={String(player.current_club_crest_url)} alt="" />
                {player.current_club_name}
              </Link>
            )}
            {competition && (
              <Link className="meta-chip" to="/competities" style={{ textDecoration: "none" }}>
                {competition.logo_url && <img className="crest" src={competition.logo_url} alt="" />}
                {competition.name}
              </Link>
            )}
            {player.country_of_citizenship_flag_url && (
              <span className="meta-chip">
                <img className="crest" src={String(player.country_of_citizenship_flag_url)} alt="" />
                {player.country_of_citizenship}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="stat-grid" style={{ marginBottom: 24 }}>
        <div className="stat-tile">
          <div className="stat-label">
            <Cake size={13} />
            Leeftijd
          </div>
          <div className="stat-value">{String(player.age ?? "-")}</div>
        </div>
        <div className="stat-tile">
          <div className="stat-label">
            <Footprints size={13} />
            Voet
          </div>
          <div className="stat-value">{String(player.foot ?? "-")}</div>
        </div>
        <div className="stat-tile">
          <div className="stat-label">
            <Ruler size={13} />
            Lengte
          </div>
          <div className="stat-value">{player.height_in_cm ? `${player.height_in_cm} cm` : "-"}</div>
        </div>
        <div className="stat-tile">
          <div className="stat-label">
            <FileClock size={13} />
            Contract tot
          </div>
          <div className="stat-value" style={{ fontSize: "1.05rem" }}>
            {formatDate(player.contract_expiration_date ?? null)}
          </div>
        </div>
        <div className="stat-tile">
          <div className="stat-label">
            <TrendingUp size={13} />
            Hoogste waarde
          </div>
          <div className="stat-value" style={{ fontSize: "1.05rem" }}>
            {formatValue((player as Record<string, unknown>).highest_market_value_in_eur as number | null)}
          </div>
        </div>
      </div>

      <div className="tab-bar">
        {TABS.map((t) => (
          <button key={t.key} className={tab === t.key ? "active" : ""} onClick={() => setTab(t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="tab-panel" key={tab}>
        {tab === "overview" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            <BioCard player={player} />
            <MarketValueChart valuations={valuations} />
          </div>
        )}

        {tab === "form" && <FormCurve appearances={data.appearances} competitions={competitions} />}

        {tab === "fotmob" && <FotmobSection playerId={Number(playerId)} />}

        {tab === "history" && (
          <>
            <h2 style={{ marginTop: 0 }}>Transfers</h2>
            {transfers.length === 0 ? (
              <div className="empty-state">Geen transfers gekend.</div>
            ) : (
              <div className="table-wrap" style={{ marginBottom: 24 }}>
                <table className="data">
                  <thead>
                    <tr>
                      <th>Datum</th>
                      <th>Van</th>
                      <th>Naar</th>
                      <th className="num">Bedrag</th>
                    </tr>
                  </thead>
                  <tbody>
                    {transfers.map((t, i) => (
                      <tr key={i}>
                        <td className="muted">{formatDate(t.transfer_date)}</td>
                        <td>
                          {t.from_club_crest_url && <img className="crest" src={t.from_club_crest_url} alt="" />}
                          {t.from_club_name}
                        </td>
                        <td>
                          {t.to_club_crest_url && <img className="crest" src={t.to_club_crest_url} alt="" />}
                          {t.to_club_name}
                        </td>
                        <td className="num">{t.transfer_fee}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {injuries.length > 0 && (
              <>
                <h2>Blessures</h2>
                <div className="table-wrap">
                  <table className="data">
                    <thead>
                      <tr>
                        <th>Seizoen</th>
                        <th>Blessure</th>
                        <th>Van</th>
                        <th>Tot</th>
                        <th className="num">Dagen</th>
                      </tr>
                    </thead>
                    <tbody>
                      {injuries.map((inj, i) => (
                        <tr key={i}>
                          <td className="muted">{inj.season}</td>
                          <td>{inj.injury}</td>
                          <td>{inj.from_date}</td>
                          <td>{inj.until_date}</td>
                          <td className="num">{inj.days}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
