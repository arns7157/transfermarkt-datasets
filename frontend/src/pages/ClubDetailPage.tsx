import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getClub, type ClubDetail } from "../api";
import PositionBadge from "../components/PositionBadge";
import { formatValue } from "../format";

export default function ClubDetailPage() {
  const { clubId } = useParams();
  const [data, setData] = useState<ClubDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!clubId) return;
    setData(null);
    getClub(Number(clubId)).then(setData).catch((err) => setError(String(err)));
  }, [clubId]);

  if (error) return <p className="error">{error}</p>;
  if (!data)
    return (
      <div className="page">
        <div className="skeleton" style={{ height: 72, width: 72, borderRadius: 10, marginBottom: 20 }} />
      </div>
    );

  const { club, squad } = data;

  return (
    <div className="page">
      <Link className="back-link" to="/clubs">
        &larr; Terug naar clubs
      </Link>
      <div className="profile-header">
        {club.crest_url && <img className="crest-lg" src={String(club.crest_url)} alt="" />}
        <div>
          <h1>{club.name}</h1>
          <span className="muted">
            {club.stadium_name} &middot; {club.squad_size} spelers
          </span>
        </div>
      </div>

      <h2>Selectie</h2>
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th></th>
              <th>Naam</th>
              <th>Positie</th>
              <th className="num">Leeftijd</th>
              <th className="num">Marktwaarde</th>
            </tr>
          </thead>
          <tbody>
            {squad.map((p) => (
              <tr key={p.player_id}>
                <td>{p.image_url && <img className="avatar" src={p.image_url} alt="" />}</td>
                <td>
                  <Link to={`/spelers/${p.player_id}`}>{p.name}</Link>
                </td>
                <td>
                  <PositionBadge position={p.position} />
                </td>
                <td className="num">{p.age}</td>
                <td className="num badge-value">{formatValue(p.market_value_in_eur)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
