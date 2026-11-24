import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listCompetitions, type Competition } from "../api";
import Skeleton from "../components/Skeleton";

export default function CompetitionsPage() {
  const [competitions, setCompetitions] = useState<Competition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listCompetitions()
      .then(setCompetitions)
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, []);

  if (error) return <p className="error">{error}</p>;
  if (loading)
    return (
      <div className="page">
        <h1>Competities</h1>
        <Skeleton rows={8} />
      </div>
    );

  const byCountry = new Map<string, Competition[]>();
  for (const c of competitions) {
    const list = byCountry.get(c.country) ?? [];
    list.push(c);
    byCountry.set(c.country, list);
  }

  return (
    <div className="page">
      <h1>Competities</h1>
      <p className="subtitle">{competitions.length} competities met gescrapede clubs, gegroepeerd per land.</p>
      {[...byCountry.entries()].map(([country, comps]) => (
        <div key={country} className="country-group">
          <h3>
            {comps[0].flag_url && <img className="crest" src={comps[0].flag_url} alt="" style={{ margin: 0 }} />}
            {country}
          </h3>
          <ul className="competition-list">
            {comps.map((c) => (
              <li key={c.competition_id}>
                <Link to={`/clubs?competition_id=${c.competition_id}`}>
                  {c.logo_url && <img className="crest" src={c.logo_url} alt="" style={{ margin: 0 }} />}
                  {c.name}
                  <span className="muted">
                    {c.tier}, {c.club_count} clubs
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
