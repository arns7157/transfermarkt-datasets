import ast
import re

from fastapi import APIRouter, HTTPException, Query

from app.db import (
    allowed_competitions_sql,
    fill_missing_crests,
    get_allowed_competition_ids,
    get_connection,
    to_record,
    to_records,
)

router = APIRouter(prefix="/api/players", tags=["players"])

# PATCH: ~54% van transfers.csv's from/to_club_name-kolommen bevat een
# gestringifyde Python-dict i.p.v. de uitgepakte naam (een historische bug
# verder terug in de pijplijn, van vóór de club_name()-fix in
# scripts/merge_csv.py - niet elke oude rij is ooit herscraped). De dict
# zelf bevat wel nog de echte naam (sleutel "clubName"), dus die herstellen
# we hier i.p.v. gewoon weg te laten.
def _recover_club_name(value):
    if isinstance(value, str) and value.startswith("{'"):
        try:
            return ast.literal_eval(value).get("clubName", "") or value
        except (ValueError, SyntaxError):
            return value
    return value


_HTML_TAG = re.compile(r"<[^>]+>")


def _clean_fee(value):
    """PATCH: sommige fee-waarden bevatten rauwe HTML uit de brontekst
    (bv. "Loan fee:<br /><i class=...>450K</i>") i.p.v. enkel platte tekst,
    en "M"/"K"-eenheden staan soms in hoofdletters, soms niet (bv. "€76.00M"
    vs "€76.00m" voor dezelfde transfer) - allebei genormaliseerd zodat
    identieke transfers ook als identiek gededupliceerd worden."""
    if not isinstance(value, str):
        return value
    cleaned = _HTML_TAG.sub("", value).strip() if "<" in value else value
    return re.sub(r"(\d)([mk])\b", lambda m: m.group(1) + m.group(2).upper(), cleaned)

LIST_COLUMNS = """
    player_id, name, position, current_club_id, current_club_name,
    current_club_crest_url, current_club_domestic_competition_id,
    market_value_in_eur, date_of_birth, age, foot, height_in_cm,
    contract_expiration_date,
    country_of_citizenship, country_of_citizenship_flag_url, image_url
"""




# query-param sorteerveld -> echte SQL-kolom (whitelist - nooit de
# query-string rechtstreeks in een ORDER BY zetten).
_SORT_COLUMNS = {
    "name": "name",
    "market_value": "market_value_in_eur",
    "age": "TRY_CAST(age AS INTEGER)",
}


@router.get("/meta/nationalities")
def list_nationalities():
    allowlist_sql, allowlist_params = allowed_competitions_sql(
        "current_club_domestic_competition_id", get_allowed_competition_ids()
    )
    con = get_connection()
    try:
        rows = con.execute(
            f"""
            SELECT country_of_citizenship, count(*) AS n FROM tm_players
            WHERE country_of_citizenship IS NOT NULL AND country_of_citizenship != ''
              AND {allowlist_sql}
            GROUP BY country_of_citizenship ORDER BY country_of_citizenship
            """,
            allowlist_params,
        ).fetchall()
        return [{"name": r[0], "count": r[1]} for r in rows]
    finally:
        con.close()


@router.get("/meta/feet")
def list_feet():
    allowlist_sql, allowlist_params = allowed_competitions_sql(
        "current_club_domestic_competition_id", get_allowed_competition_ids()
    )
    con = get_connection()
    try:
        rows = con.execute(
            f"""
            SELECT DISTINCT foot FROM tm_players
            WHERE foot IS NOT NULL AND foot != '' AND {allowlist_sql}
            ORDER BY foot
            """,
            allowlist_params,
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        con.close()


@router.get("")
def search_players(
    q: str | None = Query(None, description="Zoekterm op spelersnaam"),
    club_id: int | None = None,
    competition_id: str | None = None,
    position: str | None = None,
    nationality: str | None = None,
    foot: str | None = None,
    min_age: int | None = None,
    max_age: int | None = None,
    min_value: float | None = None,
    max_value: float | None = None,
    sort: str = Query("market_value", pattern="^(name|market_value|age)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    con = get_connection()
    try:
        allowlist_sql, allowlist_params = allowed_competitions_sql(
            "current_club_domestic_competition_id", get_allowed_competition_ids()
        )
        where, params = [allowlist_sql], list(allowlist_params)
        if q:
            where.append("name ILIKE ?")
            params.append(f"%{q}%")
        if club_id is not None:
            where.append("current_club_id = ?")
            params.append(club_id)
        if competition_id:
            where.append("current_club_domestic_competition_id = ?")
            params.append(competition_id)
        if position:
            where.append("position = ?")
            params.append(position)
        if nationality:
            where.append("country_of_citizenship = ?")
            params.append(nationality)
        if foot:
            where.append("foot = ?")
            params.append(foot)
        if min_age is not None:
            where.append("TRY_CAST(age AS INTEGER) >= ?")
            params.append(min_age)
        if max_age is not None:
            where.append("TRY_CAST(age AS INTEGER) <= ?")
            params.append(max_age)
        if min_value is not None:
            where.append("market_value_in_eur >= ?")
            params.append(min_value)
        if max_value is not None:
            where.append("market_value_in_eur <= ?")
            params.append(max_value)
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        order_sql = f"{_SORT_COLUMNS[sort]} {order.upper()} NULLS LAST"

        total = con.execute(f"SELECT count(*) FROM tm_players {where_sql}", params).fetchone()[0]
        rows = con.execute(
            f"""
            SELECT {LIST_COLUMNS} FROM tm_players {where_sql}
            ORDER BY {order_sql}
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        ).fetchdf()
        rows = fill_missing_crests(con, rows)
        return {"total": total, "items": to_records(rows)}
    finally:
        con.close()


@router.get("/{player_id}")
def get_player(player_id: int):
    con = get_connection()
    try:
        row = con.execute(
            "SELECT * FROM tm_players WHERE player_id = ?", [player_id]
        ).fetchdf()
        if row.empty:
            raise HTTPException(status_code=404, detail="Speler niet gevonden")
        row = fill_missing_crests(con, row)

        transfers = con.execute(
            """
            SELECT transfer_date, transfer_season, from_club_name, to_club_name,
                   from_club_crest_url, to_club_crest_url, transfer_fee,
                   market_value_at_transfer
            FROM tm_transfers WHERE player_id = ?
            ORDER BY transfer_date DESC
            """,
            [player_id],
        ).fetchdf()
        if not transfers.empty:
            transfers["from_club_name"] = transfers["from_club_name"].map(_recover_club_name)
            transfers["to_club_name"] = transfers["to_club_name"].map(_recover_club_name)
            transfers["transfer_fee"] = transfers["transfer_fee"].map(_clean_fee)
            # PATCH: dezelfde transfer staat soms dubbel (1x met de kapotte
            # dict-naam, 1x met de propere naam uit een latere herscrape) -
            # na het herstellen hierboven zijn beide identiek, dus dedupen.
            transfers = transfers.drop_duplicates(
                subset=["transfer_date", "from_club_name", "to_club_name", "transfer_fee"]
            )

        valuations = con.execute(
            """
            SELECT v.date, v.market_value_in_eur, v.club_name, cl.crest_url AS club_crest_url
            FROM tm_player_valuations v
            LEFT JOIN tm_clubs cl ON cl.name = v.club_name
            WHERE v.player_id = ? ORDER BY v.date
            """,
            [player_id],
        ).fetchdf()

        injuries = con.execute(
            """
            SELECT season, injury, from_date, until_date, days, games_missed
            FROM tm_injuries WHERE player_id = ? ORDER BY from_date DESC
            """,
            [player_id],
        ).fetchdf()

        appearances = con.execute(
            """
            SELECT appearance_id, date, competition_id, goals, assists,
                   minutes_played, yellow_cards, red_cards
            FROM tm_appearances WHERE player_id = ? ORDER BY date
            """,
            [player_id],
        ).fetchdf()

        return {
            "player": to_record(row),
            "transfers": to_records(transfers),
            "valuations": to_records(valuations),
            "injuries": to_records(injuries),
            "appearances": to_records(appearances),
        }
    finally:
        con.close()
