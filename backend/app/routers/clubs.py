from fastapi import APIRouter, HTTPException, Query

from app.db import allowed_competitions_sql, get_allowed_competition_ids, get_connection, to_record, to_records

router = APIRouter(prefix="/api/clubs", tags=["clubs"])

# total_market_value is een opgemaakte string ("€77.03M"), geen getal -
# sorteren op de ruwe tekst geeft een foute volgorde (bv. "€9.00M" >
# "€77.03M" lexicografisch). Haal het numerieke bedrag er zelf uit.
_MARKET_VALUE_SORT_KEY = """
    CASE
        WHEN total_market_value ILIKE '%m' THEN
            TRY_CAST(regexp_replace(total_market_value, '[^0-9.]', '', 'g') AS DOUBLE) * 1000000
        WHEN total_market_value ILIKE '%k' THEN
            TRY_CAST(regexp_replace(total_market_value, '[^0-9.]', '', 'g') AS DOUBLE) * 1000
        ELSE 0
    END
"""


_SORT_COLUMNS = {
    "name": "name",
    "market_value": _MARKET_VALUE_SORT_KEY,
    "squad_size": "squad_size",
}


@router.get("")
def list_clubs(
    competition_id: str | None = None,
    sort: str = Query("market_value", pattern="^(name|market_value|squad_size)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(100, le=500),
):
    con = get_connection()
    try:
        allowlist_sql, params = allowed_competitions_sql("domestic_competition_id", get_allowed_competition_ids())
        where = [allowlist_sql]
        if competition_id:
            where.append("domestic_competition_id = ?")
            params = params + [competition_id]
        where_sql = f"WHERE {' AND '.join(where)}"
        order_sql = f"{_SORT_COLUMNS[sort]} {order.upper()} NULLS LAST"
        rows = con.execute(
            f"""
            SELECT club_id, name, domestic_competition_id, squad_size,
                   average_age, total_market_value, crest_url, stadium_name
            FROM tm_clubs {where_sql}
            ORDER BY {order_sql}
            LIMIT ?
            """,
            params + [limit],
        ).fetchdf()
        return to_records(rows)
    finally:
        con.close()


@router.get("/{club_id}")
def get_club(club_id: int):
    con = get_connection()
    try:
        row = con.execute("SELECT * FROM tm_clubs WHERE club_id = ?", [club_id]).fetchdf()
        if row.empty:
            raise HTTPException(status_code=404, detail="Club niet gevonden")

        squad = con.execute(
            """
            SELECT player_id, name, position, market_value_in_eur, age, image_url
            FROM tm_players WHERE current_club_id = ?
            ORDER BY market_value_in_eur DESC NULLS LAST
            """,
            [club_id],
        ).fetchdf()

        return {"club": to_record(row), "squad": to_records(squad)}
    finally:
        con.close()
