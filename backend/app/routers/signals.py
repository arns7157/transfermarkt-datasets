"""Aflopende contracten en de grootste marktwaarde-stijgers/dalers -
portering van streamlit/pages/5_Signalen.py."""
from datetime import datetime, timedelta

import pandas as pd
from fastapi import APIRouter, Query

from app.db import allowed_competitions_sql, fill_missing_crests, get_allowed_competition_ids, get_connection, to_records

router = APIRouter(prefix="/api/signals", tags=["signals"])

TIER_LABELS_NL = {
    "First Tier": "1e", "Second Tier": "2e", "Third Tier": "3e", "Fourth Tier": "4e",
    "Fifth Tier": "5e", "Sixth Tier": "6e", "Play-Offs": "Play-offs",
    "Reserve league": "Reserveliga", "Regional Championship": "Regionaal",
}

_PLAYER_COLS = """
    p.player_id, p.name, p.age, p.position, p.current_club_id, p.current_club_name,
    p.current_club_crest_url, p.country_of_citizenship AS country,
    p.country_of_citizenship_flag_url, p.contract_expiration_date, p.market_value_in_eur,
    c.name AS competition_name, c.tier
"""


def _with_competition_display(df: pd.DataFrame) -> pd.DataFrame:
    niveau = df["tier"].map(lambda t: TIER_LABELS_NL.get(t, t))
    suffix = niveau.fillna("").map(lambda v: f" ({v})" if v else "")
    df["competition_display"] = df["competition_name"].fillna("") + suffix
    return df


@router.get("/contracts")
def expiring_contracts(months: int = Query(6, ge=1, le=24)):
    cutoff = pd.Timestamp(datetime.now() + timedelta(days=months * 30))
    allowlist_sql, allowlist_params = allowed_competitions_sql(
        "p.current_club_domestic_competition_id", get_allowed_competition_ids()
    )
    con = get_connection()
    try:
        rows = con.execute(
            f"""
            SELECT {_PLAYER_COLS}
            FROM tm_players p
            LEFT JOIN tm_competitions c ON c.competition_id = p.current_club_domestic_competition_id
            WHERE TRY_STRPTIME(p.contract_expiration_date, '%d/%m/%Y') IS NOT NULL
              AND TRY_STRPTIME(p.contract_expiration_date, '%d/%m/%Y') <= ?
              AND {allowlist_sql}
            ORDER BY TRY_STRPTIME(p.contract_expiration_date, '%d/%m/%Y')
            """,
            [cutoff] + allowlist_params,
        ).fetchdf()
        rows = fill_missing_crests(con, rows)
    finally:
        con.close()
    if rows.empty:
        return []
    return to_records(_with_competition_display(rows))


@router.get("/value-changes")
def value_changes(months_back: int = Query(6, ge=1, le=24), direction: str = Query("up", pattern="^(up|down)$"), limit: int = Query(20, le=100)):
    cutoff = pd.Timestamp(datetime.now() - timedelta(days=months_back * 30))
    allowlist_sql, allowlist_params = allowed_competitions_sql(
        "p.current_club_domestic_competition_id", get_allowed_competition_ids()
    )
    con = get_connection()
    try:
        valuations = con.execute("SELECT player_id, date, market_value_in_eur FROM tm_player_valuations").fetchdf()
        players = con.execute(
            f"""
            SELECT {_PLAYER_COLS}
            FROM tm_players p
            LEFT JOIN tm_competitions c ON c.competition_id = p.current_club_domestic_competition_id
            WHERE {allowlist_sql}
            """,
            allowlist_params,
        ).fetchdf()
        players = fill_missing_crests(con, players)
    finally:
        con.close()

    latest = valuations.sort_values("date").groupby("player_id").tail(1).set_index("player_id")
    history_before = valuations[valuations["date"] <= cutoff]
    baseline = history_before.sort_values("date").groupby("player_id").tail(1).set_index("player_id")

    joined = latest[["market_value_in_eur"]].join(
        baseline[["market_value_in_eur"]], how="inner", lsuffix="_nu", rsuffix="_toen"
    )
    joined = joined[joined["market_value_in_eur_toen"] > 0]
    joined["verandering_pct"] = (
        (joined["market_value_in_eur_nu"] - joined["market_value_in_eur_toen"])
        / joined["market_value_in_eur_toen"] * 100
    ).round(1)
    # inner, niet left: tm_player_valuations bevat ook spelers buiten de
    # gevolgde competities (oude restdata) - die geven anders vervalste rijen.
    joined = joined.join(players.set_index("player_id"), how="inner")
    joined = _with_competition_display(joined)

    ascending = direction == "down"
    top = joined.sort_values("verandering_pct", ascending=ascending).head(limit).reset_index()
    out = top[[
        "player_id", "name", "age", "position", "current_club_name", "current_club_crest_url",
        "competition_display", "country", "country_of_citizenship_flag_url",
        "market_value_in_eur_toen", "market_value_in_eur_nu", "verandering_pct",
    ]]
    return to_records(out)
