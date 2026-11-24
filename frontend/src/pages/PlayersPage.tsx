import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  listCompetitions,
  listFeet,
  listNationalities,
  searchPlayers,
  type Competition,
  type NamedCount,
  type PlayerFilters,
  type PlayerSummary,
  type SortOrder,
} from "../api";
import PositionBadge from "../components/PositionBadge";
import Skeleton from "../components/Skeleton";
import SortHeader from "../components/SortHeader";
import { formatDate, formatValue } from "../format";

const POSITIONS = ["Goalkeeper", "Defender", "Midfield", "Attack"];

const EMPTY_FILTERS: PlayerFilters = {};

export default function PlayersPage() {
  const [filters, setFilters] = useState<PlayerFilters>({});
  const [sort, setSort] = useState("market_value");
  const [order, setOrder] = useState<SortOrder>("desc");
  const [players, setPlayers] = useState<PlayerSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [nationalities, setNationalities] = useState<NamedCount[]>([]);
  const [feet, setFeet] = useState<string[]>([]);
  const [competitions, setCompetitions] = useState<Competition[]>([]);

  useEffect(() => {
    listNationalities().then(setNationalities).catch(() => {});
    listFeet().then(setFeet).catch(() => {});
    listCompetitions().then(setCompetitions).catch(() => {});
  }, []);

  function set<K extends keyof PlayerFilters>(key: K, value: PlayerFilters[K]) {
    setFilters((f) => ({ ...f, [key]: value || undefined }));
  }

  function handleSort(field: string) {
    if (field === sort) {
      setOrder(order === "desc" ? "asc" : "desc");
    } else {
      setSort(field);
      setOrder(field === "name" ? "asc" : "desc");
    }
  }

  useEffect(() => {
    const handle = setTimeout(() => {
      setLoading(true);
      searchPlayers(filters, sort, order, 60)
        .then((res) => {
          setPlayers(res.items);
          setTotal(res.total);
          setError(null);
        })
        .catch((err) => setError(String(err)))
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(handle);
  }, [filters, sort, order]);

  const hasFilters = Object.keys(filters).length > 0;
  const competitionByCode = new Map(competitions.map((c) => [c.competition_id, c]));

  return (
    <div className="page-wide">
      <h1>Spelers zoeken</h1>
      <p className="subtitle">
        Doorzoek de volledige Transfermarkt-dataset
        {total > 0 && `: ${total.toLocaleString("nl-BE")} spelers over alle gevolgde competities`}.
      </p>

      <div className="filter-bar">
        <div>
          <label>Naam</label>
          <input
            className="input"
            placeholder="Zoek op naam..."
            value={filters.q ?? ""}
            onChange={(e) => set("q", e.target.value)}
          />
        </div>
        <div>
          <label>Positie</label>
          <select className="input" value={filters.position ?? ""} onChange={(e) => set("position", e.target.value)}>
            <option value="">Alle posities</option>
            {POSITIONS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label>Competitie</label>
          <select
            className="input"
            value={filters.competitionId ?? ""}
            onChange={(e) => set("competitionId", e.target.value)}
          >
            <option value="">Alle competities</option>
            {competitions.map((c) => (
              <option key={c.competition_id} value={c.competition_id}>
                {c.country} - {c.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label>Nationaliteit</label>
          <select className="input" value={filters.nationality ?? ""} onChange={(e) => set("nationality", e.target.value)}>
            <option value="">Alle nationaliteiten</option>
            {nationalities.map((n) => (
              <option key={n.name} value={n.name}>
                {n.name} ({n.count})
              </option>
            ))}
          </select>
        </div>
        <div>
          <label>Voet</label>
          <select className="input" value={filters.foot ?? ""} onChange={(e) => set("foot", e.target.value)}>
            <option value="">Alle</option>
            {feet.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label>Leeftijd</label>
          <div className="range-group">
            <input
              className="input"
              type="number"
              placeholder="Min"
              value={filters.minAge ?? ""}
              onChange={(e) => set("minAge", e.target.value ? Number(e.target.value) : undefined)}
            />
            <input
              className="input"
              type="number"
              placeholder="Max"
              value={filters.maxAge ?? ""}
              onChange={(e) => set("maxAge", e.target.value ? Number(e.target.value) : undefined)}
            />
          </div>
        </div>
        <div>
          <label>Marktwaarde (M€)</label>
          <div className="range-group">
            <input
              className="input"
              type="number"
              placeholder="Min"
              value={filters.minValue ?? ""}
              onChange={(e) => set("minValue", e.target.value ? Number(e.target.value) : undefined)}
            />
            <input
              className="input"
              type="number"
              placeholder="Max"
              value={filters.maxValue ?? ""}
              onChange={(e) => set("maxValue", e.target.value ? Number(e.target.value) : undefined)}
            />
          </div>
        </div>
        {hasFilters && (
          <div style={{ display: "flex", alignItems: "flex-end" }}>
            <button className="filter-reset" onClick={() => setFilters(EMPTY_FILTERS)}>
              Filters wissen
            </button>
          </div>
        )}
      </div>

      {error && <p className="error">{error}</p>}
      {loading ? (
        <Skeleton rows={12} />
      ) : players.length === 0 ? (
        <div className="empty-state">Geen spelers gevonden voor deze filters.</div>
      ) : (
        <>
          <p className="muted" style={{ marginBottom: 10 }}>
            {total.toLocaleString("nl-BE")} spelers gevonden{total > players.length ? ` (eerste ${players.length} getoond)` : ""}
          </p>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th></th>
                  <SortHeader label="Naam" field="name" sort={sort} order={order} onSort={handleSort} />
                  <th>Nationaliteit</th>
                  <th>Club</th>
                  <th>Competitie</th>
                  <th>Positie</th>
                  <th>Voet</th>
                  <SortHeader label="Leeftijd" field="age" sort={sort} order={order} onSort={handleSort} align="num" />
                  <th>Contract tot</th>
                  <SortHeader
                    label="Marktwaarde"
                    field="market_value"
                    sort={sort}
                    order={order}
                    onSort={handleSort}
                    align="num"
                  />
                </tr>
              </thead>
              <tbody>
                {players.map((p) => (
                  <tr key={p.player_id}>
                    <td>{p.image_url && <img className="avatar" src={p.image_url} alt="" />}</td>
                    <td>
                      <Link to={`/spelers/${p.player_id}`}>{p.name}</Link>
                    </td>
                    <td>
                      {p.country_of_citizenship_flag_url && (
                        <img className="crest" src={p.country_of_citizenship_flag_url} alt="" />
                      )}
                      {p.country_of_citizenship}
                    </td>
                    <td>
                      {p.current_club_crest_url && (
                        <img className="crest" src={p.current_club_crest_url} alt="" />
                      )}
                      {p.current_club_name}
                    </td>
                    <td className="muted">
                      {(() => {
                        const comp = competitionByCode.get(p.current_club_domestic_competition_id ?? "");
                        return comp ? (
                          <span style={{ display: "flex", alignItems: "center" }}>
                            {comp.logo_url && <img className="crest" src={comp.logo_url} alt="" />}
                            {comp.name}
                          </span>
                        ) : (
                          p.current_club_domestic_competition_id
                        );
                      })()}
                    </td>
                    <td>
                      <PositionBadge position={p.position} />
                    </td>
                    <td className="muted">{p.foot ?? "-"}</td>
                    <td className="num">{p.age}</td>
                    <td className="muted">{formatDate(p.contract_expiration_date)}</td>
                    <td className="num badge-value">{formatValue(p.market_value_in_eur)}</td>
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
