from fastapi import APIRouter

from app.db import allowed_competitions_sql, get_allowed_competition_ids, get_connection, to_records

router = APIRouter(prefix="/api/competitions", tags=["competitions"])


@router.get("")
def list_competitions():
    """Enkel competities uit de effectief (opnieuw) gescrapete batches -
    zelfde allowlist als streamlit/utils.py's _allowed_competition_ids().
    De volledige tm_competitions-tabel bevat ~1700 referentie-competities
    wereldwijd; de meeste daarvan hebben enkel oude restdata van vóór dit
    project (clubs zonder naam/crest/...), vandaar de expliciete allowlist
    i.p.v. enkel "heeft minstens 1 club-rij" (die oude restdata telt daar
    ook voor mee)."""
    allowlist_sql, params = allowed_competitions_sql("c.competition_id", get_allowed_competition_ids())
    con = get_connection()
    try:
        rows = con.execute(
            f"""
            SELECT c.competition_id, c.name, c.country, c.tier, c.flag_url, c.logo_url,
                   count(cl.club_id) AS club_count
            FROM tm_competitions c
            JOIN tm_clubs cl ON cl.domestic_competition_id = c.competition_id
            WHERE {allowlist_sql}
            GROUP BY c.competition_id, c.name, c.country, c.tier, c.flag_url, c.logo_url
            ORDER BY c.country, c.tier
            """,
            params,
        ).fetchdf()
        return to_records(rows)
    finally:
        con.close()
