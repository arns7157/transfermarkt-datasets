"""Spelers naast elkaar vergelijken (2-4): bio-samenvatting, seizoenstotalen
en marktwaarde-verloop - portering van streamlit/pages/4_Vergelijken.py."""
import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from app.db import fill_missing_crests, get_connection, to_record, to_records

router = APIRouter(prefix="/api/compare", tags=["compare"])


def _season_start_for(date: pd.Timestamp) -> pd.Timestamp:
    year = date.year if date.month >= 7 else date.year - 1
    return pd.Timestamp(year=year, month=7, day=1)


@router.get("")
def compare_players(ids: str = Query(..., description="Kommagescheiden player_ids, 2 tot 4")):
    try:
        player_ids = [int(x) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Ongeldige ids")
    if not (2 <= len(player_ids) <= 4):
        raise HTTPException(status_code=400, detail="Kies 2 tot 4 spelers")

    con = get_connection()
    try:
        placeholders = ",".join("?" for _ in player_ids)
        players = con.execute(
            f"""
            SELECT player_id, name, age, position, current_club_id, current_club_name,
                   current_club_crest_url, country_of_citizenship, country_of_citizenship_flag_url,
                   market_value_in_eur, image_url
            FROM tm_players WHERE player_id IN ({placeholders})
            """,
            player_ids,
        ).fetchdf()
        if players.empty:
            raise HTTPException(status_code=404, detail="Geen spelers gevonden")
        players = fill_missing_crests(con, players)

        appearances = con.execute(
            f"""
            SELECT player_id, date, minutes_played, goals, assists
            FROM tm_appearances WHERE player_id IN ({placeholders})
            """,
            player_ids,
        ).fetchdf()

        valuations = con.execute(
            f"""
            SELECT player_id, date, market_value_in_eur
            FROM tm_player_valuations WHERE player_id IN ({placeholders})
            ORDER BY date
            """,
            player_ids,
        ).fetchdf()
    finally:
        con.close()

    dated = appearances.dropna(subset=["date"])
    season_apps = pd.DataFrame(columns=appearances.columns)
    if not dated.empty:
        season_start = _season_start_for(dated["date"].max())
        season_apps = dated[dated["date"] >= season_start]

    season_totals = {}
    for pid in player_ids:
        apps = season_apps[season_apps["player_id"] == pid]
        season_totals[pid] = {
            "matches": int(len(apps)),
            "goals": int(apps["goals"].sum()) if not apps.empty else 0,
            "assists": int(apps["assists"].sum()) if not apps.empty else 0,
            "minutes": int(apps["minutes_played"].sum()) if not apps.empty else 0,
        }

    # Volgorde van de output = volgorde van de gevraagde ids, niet DB-volgorde.
    players_by_id = players.set_index("player_id")
    items = []
    for pid in player_ids:
        if pid not in players_by_id.index:
            continue
        row = to_record(players_by_id.loc[[pid]].reset_index())
        row["season_totals"] = season_totals.get(pid, {"matches": 0, "goals": 0, "assists": 0, "minutes": 0})
        items.append(row)

    return {
        "players": items,
        "valuations": to_records(valuations),
    }
