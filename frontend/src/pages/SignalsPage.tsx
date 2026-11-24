import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  getExpiringContracts,
  getValueChanges,
  type ContractSignal,
  type ValueChangeSignal,
} from "../api";
import PositionBadge from "../components/PositionBadge";
import Skeleton from "../components/Skeleton";
import { formatDate, formatValue } from "../format";

type Tab = "contracts" | "value";

export default function SignalsPage() {
  const [tab, setTab] = useState<Tab>("contracts");
  const [months, setMonths] = useState(6);
  const [monthsBack, setMonthsBack] = useState(6);
  const [contracts, setContracts] = useState<ContractSignal[]>([]);
  const [gainers, setGainers] = useState<ValueChangeSignal[]>([]);
  const [losers, setLosers] = useState<ValueChangeSignal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (tab !== "contracts") return;
    setLoading(true);
    getExpiringContracts(months)
      .then(setContracts)
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, [tab, months]);

  useEffect(() => {
    if (tab !== "value") return;
    setLoading(true);
    Promise.all([
      getValueChanges(monthsBack, "up", 20),
      getValueChanges(monthsBack, "down", 20),
    ])
      .then(([up, down]) => {
        setGainers(up);
        setLosers(down);
      })
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, [tab, monthsBack]);

  return (
    <div className="page-wide">
      <h1>Signalen</h1>
      <p className="subtitle">Aflopende contracten en de grootste stijgers/dalers in marktwaarde.</p>

      <div className="tab-bar">
        <button className={tab === "contracts" ? "active" : ""} onClick={() => setTab("contracts")}>
          Aflopende contracten
        </button>
        <button className={tab === "value" ? "active" : ""} onClick={() => setTab("value")}>
          Snel veranderende marktwaarde
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      {tab === "contracts" ? (
        <>
          <div className="filter-bar">
            <div>
              <label>Binnen hoeveel maanden loopt het contract af: {months}</label>
              <input className="input" type="range" min={1} max={24} value={months} onChange={(e) => setMonths(Number(e.target.value))} />
            </div>
          </div>
          {loading ? (
            <Skeleton rows={10} />
          ) : contracts.length === 0 ? (
            <div className="empty-state">Geen spelers gevonden binnen deze periode.</div>
          ) : (
            <>
              <p className="muted" style={{ marginBottom: 10 }}>
                {contracts.length} spelers met een aflopend contract
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
                      <th>Contract tot</th>
                      <th className="num">Marktwaarde</th>
                    </tr>
                  </thead>
                  <tbody>
                    {contracts.map((c) => (
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
                        <td className="muted">{formatDate(c.contract_expiration_date)}</td>
                        <td className="num badge-value">{formatValue(c.market_value_in_eur)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      ) : (
        <>
          <div className="filter-bar">
            <div>
              <label>Vergelijk met hoeveel maanden geleden: {monthsBack}</label>
              <input className="input" type="range" min={1} max={24} value={monthsBack} onChange={(e) => setMonthsBack(Number(e.target.value))} />
            </div>
          </div>
          {loading ? (
            <Skeleton rows={10} />
          ) : (
            <>
              {([
                ["Grootste stijgers", gainers],
                ["Grootste dalers", losers],
              ] as const).map(([title, rows]) => (
                <div key={title} style={{ marginBottom: 28 }}>
                  <h2>{title}</h2>
                  {rows.length === 0 ? (
                    <div className="empty-state">Geen data.</div>
                  ) : (
                    <div className="table-wrap">
                      <table className="data">
                        <thead>
                          <tr>
                            <th></th>
                            <th>Naam</th>
                            <th>Positie</th>
                            <th>Club</th>
                            <th>Competitie</th>
                            <th className="num">Toen</th>
                            <th className="num">Nu</th>
                            <th className="num">% verandering</th>
                          </tr>
                        </thead>
                        <tbody>
                          {rows.map((r) => (
                            <tr key={r.player_id}>
                              <td>{r.current_club_crest_url && <img className="crest" src={r.current_club_crest_url} alt="" />}</td>
                              <td>
                                <Link to={`/spelers/${r.player_id}`}>{r.name}</Link>
                              </td>
                              <td>
                                <PositionBadge position={r.position} />
                              </td>
                              <td className="muted">{r.current_club_name}</td>
                              <td className="muted">{r.competition_display}</td>
                              <td className="num">{formatValue(r.market_value_in_eur_toen)}</td>
                              <td className="num">{formatValue(r.market_value_in_eur_nu)}</td>
                              <td className="num badge-value">
                                {r.verandering_pct > 0 ? "+" : ""}
                                {r.verandering_pct.toFixed(1)}%
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              ))}
            </>
          )}
        </>
      )}
    </div>
  );
}
