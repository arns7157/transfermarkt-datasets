"""
Doorbraak-kandidaten: jonge spelers die recent meer speeltijd krijgen of
beginnen te scoren, vergeleken met de periode ervoor dit seizoen. Exacte
pandas-portering van streamlit/utils.py's compute_breakout_candidates(),
zodat beide apps hetzelfde algoritme gebruiken.
"""
import re

import pandas as pd
from fastapi import APIRouter, Query

from app.db import allowed_competitions_sql, fill_missing_crests, get_allowed_competition_ids, get_connection, to_records

router = APIRouter(prefix="/api/potential", tags=["potential"])

TIER_LABELS_NL = {
    "First Tier": "1e", "Second Tier": "2e", "Third Tier": "3e", "Fourth Tier": "4e",
    "Fifth Tier": "5e", "Sixth Tier": "6e", "Play-Offs": "Play-offs",
    "Reserve league": "Reserveliga", "Regional Championship": "Regionaal",
}

_RESERVE_TEAM_SUFFIX_RE = re.compile(r"(\bU1[6-9]\b|\bU2[0-3]\b|\bII$| B$)", re.IGNORECASE)
_RESERVE_TEAM_EXACT_NAMES = {
    "Real Madrid Castilla", "Juventus Next Gen", "CA Osasuna Promesas",
    "Sevilla Atlético", "Atlético Madrileño", "Betis Deportivo Balompié",
    "RC Deportivo Fabril",
}


def _is_reserve_team(club_name) -> bool:
    if not isinstance(club_name, str):
        return False
    return bool(_RESERVE_TEAM_SUFFIX_RE.search(club_name)) or club_name in _RESERVE_TEAM_EXACT_NAMES


def _season_start_for(date: pd.Timestamp) -> pd.Timestamp:
    year = date.year if date.month >= 7 else date.year - 1
    return pd.Timestamp(year=year, month=7, day=1)


@router.get("")
def breakout_candidates(
    max_age: int = Query(23, ge=14, le=40),
    recent_days: int = Query(30, ge=7, le=120),
    min_recent_matches: int = Query(2, ge=1, le=20),
):
    allowlist_sql, allowlist_params = allowed_competitions_sql(
        "p.current_club_domestic_competition_id", get_allowed_competition_ids()
    )
    con = get_connection()
    try:
        appearances = con.execute(
            "SELECT appearance_id, player_id, date, minutes_played, goals, assists FROM tm_appearances"
        ).fetchdf()
        players = con.execute(
            f"""
            SELECT p.player_id, p.name, p.age, p.position, p.current_club_id, p.current_club_name,
                   p.current_club_crest_url, p.market_value_in_eur,
                   p.country_of_citizenship AS country, p.current_club_domestic_competition_id,
                   c.name AS competition_name, c.tier
            FROM tm_players p
            LEFT JOIN tm_competitions c ON c.competition_id = p.current_club_domestic_competition_id
            WHERE {allowlist_sql}
            """,
            allowlist_params,
        ).fetchdf()
        players = fill_missing_crests(con, players)
    finally:
        con.close()

    dated = appearances.dropna(subset=["date"])
    if dated.empty:
        return []

    latest_date = dated["date"].max()
    season_start = _season_start_for(latest_date)
    season_apps = dated[dated["date"] >= season_start]
    recent_cutoff = latest_date - pd.Timedelta(days=recent_days)
    recent = season_apps[season_apps["date"] >= recent_cutoff]
    earlier = season_apps[season_apps["date"] < recent_cutoff]

    def aggregate(df: pd.DataFrame) -> pd.DataFrame:
        g = df.groupby("player_id").agg(
            matches=("appearance_id", "count"),
            minutes=("minutes_played", "sum"),
            goals=("goals", "sum"),
            assists=("assists", "sum"),
        )
        g["avg_minutes"] = g["minutes"] / g["matches"]
        minutes_90 = (g["minutes"] / 90).replace(0, pd.NA)
        g["ga_per90"] = (g["goals"] + g["assists"]) / minutes_90
        return g.fillna(0.0)

    recent_agg = aggregate(recent).add_prefix("recent_")
    earlier_agg = aggregate(earlier).add_prefix("earlier_")

    merged = recent_agg.join(earlier_agg, how="left")
    for col in earlier_agg.columns:
        merged[col] = merged[col].fillna(0.0)
    merged = merged[merged["recent_matches"] >= min_recent_matches]
    if merged.empty:
        return []

    merged["minutes_trend"] = merged["recent_avg_minutes"] - merged["earlier_avg_minutes"]
    merged["scoring_trend"] = merged["recent_ga_per90"] - merged["earlier_ga_per90"]
    merged["just_broke_through"] = merged["earlier_matches"] == 0
    merged["potential_score"] = (
        merged["minutes_trend"].clip(lower=0) / 90.0
        + merged["scoring_trend"].clip(lower=0) * 2.0
        + merged["just_broke_through"].astype(float) * 1.5
    )

    result = merged.join(players.set_index("player_id"), how="inner")
    result["age"] = pd.to_numeric(result["age"], errors="coerce")
    result = result[result["age"] <= max_age]
    result = result[~result["current_club_name"].map(_is_reserve_team)]
    result = result.sort_values("potential_score", ascending=False).reset_index()

    niveau = result["tier"].map(lambda t: TIER_LABELS_NL.get(t, t))
    suffix = niveau.fillna("").map(lambda v: f" ({v})" if v else "")
    result["competition_display"] = (result["competition_name"].fillna("") + suffix)

    out = result[[
        "player_id", "name", "age", "position", "current_club_name", "current_club_crest_url",
        "competition_display", "country", "market_value_in_eur",
        "recent_matches", "recent_avg_minutes", "recent_goals", "recent_assists",
        "minutes_trend", "scoring_trend", "just_broke_through",
    ]].round({"recent_avg_minutes": 1, "minutes_trend": 1, "scoring_trend": 3})
    return to_records(out)
