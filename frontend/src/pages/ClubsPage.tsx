import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { listClubs, type ClubSummary, type SortOrder } from "../api";
import Skeleton from "../components/Skeleton";
import SortHeader from "../components/SortHeader";

export default function ClubsPage() {
  const [searchParams] = useSearchParams();
  const competitionId = searchParams.get("competition_id") ?? undefined;
  const [clubs, setClubs] = useState<ClubSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sort, setSort] = useState("market_value");
  const [order, setOrder] = useState<SortOrder>("desc");

  function handleSort(field: string) {
    if (field === sort) {
      setOrder(order === "desc" ? "asc" : "desc");
    } else {
      setSort(field);
      setOrder(field === "name" ? "asc" : "desc");
    }
  }

  useEffect(() => {
    setLoading(true);
    listClubs(competitionId, sort, order)
      .then(setClubs)
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, [competitionId, sort, order]);

  if (error) return <p className="error">{error}</p>;

  return (
    <div className="page">
      <h1>Clubs</h1>
      <p className="subtitle">
        {competitionId ? (
          <>
            Gefilterd op competitie <strong>{competitionId}</strong> &middot;{" "}
            <Link to="/clubs">alle clubs tonen</Link>
          </>
        ) : (
          "Alle clubs - klik een kolomkop om te sorteren."
        )}
      </p>
      {loading ? (
        <Skeleton rows={10} />
      ) : (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th></th>
                <SortHeader label="Club" field="name" sort={sort} order={order} onSort={handleSort} />
                <th>Competitie</th>
                <SortHeader
                  label="Selectie"
                  field="squad_size"
                  sort={sort}
                  order={order}
                  onSort={handleSort}
                  align="num"
                />
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
              {clubs.map((c) => (
                <tr key={c.club_id}>
                  <td>{c.crest_url && <img className="crest" src={c.crest_url} alt="" />}</td>
                  <td>
                    <Link to={`/clubs/${c.club_id}`}>{c.name}</Link>
                  </td>
                  <td className="muted">{c.domestic_competition_id}</td>
                  <td className="num">{c.squad_size ?? "-"}</td>
                  <td className="num badge-value">{c.total_market_value ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
