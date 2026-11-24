"""
Endpoints op de FotMob-tabellen (gevuld door scripts/fotmob_to_duckdb.py) -
standenlijsten, spelers-/teamleaderboards en wedstrijden over alle 99
competities (binnenlandse competities, bekers, interlands/EK/WK/CL/EL/ECL).

Bevat ook /player-match/{player_id}, dat een Transfermarkt-speler aan zijn
FotMob-seizoensdata koppelt (zelfde naam-matching-aanpak als
streamlit/fotmob.py, hier een eigen, globale - niet land-geschaalde -
kopie, zie _match_team()/_match_player() hieronder).
"""
import json
import re
import unicodedata

from fastapi import APIRouter, HTTPException, Query

from app.db import FOTMOB_DIR, get_connection, to_records

router = APIRouter(prefix="/api/fotmob", tags=["fotmob"])

_SEASON_SUFFIX = re.compile(r"-\d{4}(-\d{4})?$")


def _label(league_key: str) -> str:
    return _SEASON_SUFFIX.sub("", league_key).replace("_", " ")


# --- Transfermarkt <-> FotMob matching -------------------------------
# Zelfde voorzichtige aanpak als streamlit/fotmob.py: automatische naam-
# matching, geen gok bij twijfel. Hier bewust GLOBAAL over alle 99
# competities (geen land-scoping zoals in de Streamlit-versie) - makkelijker
# te onderhouden (geen tweede kopie van de competitie->land-tabel), en de
# "kleinste overschot aan extra woorden, enkel bij eenduidigheid"-regel
# houdt foute matches ook globaal zeldzaam.
def _normalize(name) -> str:
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z ]", "", s.lower()).strip()


def _tokens(name) -> set:
    return set(_normalize(name).split())


def _match_team(con, club_name: str):
    """FotMob-namen zijn meestal KORTER dan Transfermarkt's volledige
    officiële naam (bv. FotMob "Napoli" vs TM "SSC Napoli") - de FotMob-
    tokens moeten dus een subset zijn van de TM-tokens, niet omgekeerd."""
    target = _tokens(club_name)
    if not target:
        return None
    teams = con.execute("SELECT DISTINCT league_key, team_id, name FROM teams").fetchdf()
    candidates = []
    for _, row in teams.iterrows():
        fm_tokens = _tokens(row["name"])
        if fm_tokens and fm_tokens.issubset(target):
            candidates.append((row["league_key"], int(row["team_id"]), len(target - fm_tokens)))
    if not candidates:
        return None
    min_extra = min(c[2] for c in candidates)
    best = [c for c in candidates if c[2] == min_extra]

    # Dezelfde club staat vaak onder hetzelfde team_id in meerdere
    # league_keys (competitie + beker + Europees bekertoernooi, bv. "Napoli"
    # in Serie_A + Coppa Italia + Champions League) - dat is geen echte
    # ambiguïteit (1 club), enkel de keuze van league_key staat nog open.
    team_ids = {c[1] for c in best}
    if len(team_ids) != 1:
        return None
    team_id = team_ids.pop()
    league_keys = [c[0] for c in best]
    if len(league_keys) == 1:
        return league_keys[0], team_id

    # Kies de competitie met de meeste spelersstatistiek-data voor deze club
    # - vrijwel altijd de binnenlandse competitie (veel meer wedstrijden dan
    # een bekertoernooi), en daar wil je sowieso de seizoensstats van tonen.
    placeholders = ",".join("?" for _ in league_keys)
    row = con.execute(
        f"""
        SELECT league_key, count(*) AS n FROM player_match_stats
        WHERE team_id = ? AND league_key IN ({placeholders})
        GROUP BY league_key ORDER BY n DESC LIMIT 1
        """,
        [team_id] + league_keys,
    ).fetchone()
    return (row[0], team_id) if row else (league_keys[0], team_id)


def _match_player(con, league_key: str, team_id: int, last_name: str, full_name: str):
    roster = con.execute(
        "SELECT DISTINCT fotmob_id, name FROM leaderboard_player_stats WHERE league_key = ? AND team_id = ?",
        [league_key, team_id],
    ).fetchdf()
    if roster.empty:
        return None

    def fm_last_word(n):
        norm = _normalize(n)
        return norm.split()[-1] if norm else ""

    target_last = _normalize(last_name or "").split()[-1] if last_name else ""
    if target_last:
        cands = roster[roster["name"].map(fm_last_word) == target_last]
        if len(cands) == 1:
            return int(cands.iloc[0]["fotmob_id"]), cands.iloc[0]["name"]

    target_full = _normalize(full_name or "")
    if target_full:
        cands = roster[roster["name"].map(_normalize) == target_full]
        if len(cands) == 1:
            return int(cands.iloc[0]["fotmob_id"]), cands.iloc[0]["name"]
    return None


RADAR_STATS = ["Goals", "Total shots", "Chances created", "Touches", "Aerial duels won", "Defensive actions"]
RATE_STATS = {"FotMob rating"}
# Interne/overbodige velden - "Shot accuracy" bleek in de praktijk altijd
# exact gelijk aan "Shots on target" (dubbel veld, geen percentage), zelfde
# bevinding als eerder al gedaan voor de Streamlit-versie.
SKIP_STATS = {"Shotmap", "Fantasy assists", "xG + xA", "Shot accuracy"}


@router.get("/player-match/{player_id}")
def fotmob_for_player(player_id: int):
    """FotMob-koppeling + seizoensstats/percentielen/schoten voor 1
    Transfermarkt-speler, of {"matched": false} als er geen eenduidige
    koppeling gevonden is (club- of naammatch mislukt)."""
    con = get_connection()
    try:
        prow = con.execute(
            "SELECT name, last_name, current_club_name FROM tm_players WHERE player_id = ?", [player_id]
        ).fetchdf()
        if prow.empty:
            return {"matched": False}
        p = prow.iloc[0]
        if p.isna()["current_club_name"] or not p["current_club_name"]:
            return {"matched": False}

        team_match = _match_team(con, p["current_club_name"])
        if not team_match:
            return {"matched": False}
        league_key, team_id = team_match

        player_match = _match_player(con, league_key, team_id, p["last_name"], p["name"])
        if not player_match:
            return {"matched": False, "league_key": league_key}
        fm_id, fm_name = player_match

        stats_df = con.execute(
            """
            SELECT stat_name, stat_group, value
            FROM player_match_stats WHERE league_key = ? AND player_id = ?
            """,
            [league_key, fm_id],
        ).fetchdf()
        matches_played = con.execute(
            """
            SELECT count(DISTINCT match_id) FROM player_match_stats
            WHERE league_key = ? AND player_id = ?
            """,
            [league_key, fm_id],
        ).fetchone()[0]

        totals: dict = {}
        if not stats_df.empty:
            for name in stats_df["stat_name"].unique():
                if name in SKIP_STATS:
                    continue
                sub = stats_df[stats_df["stat_name"] == name]
                value = sub["value"].mean() if name in RATE_STATS else sub["value"].sum()
                totals[name] = {"group": sub.iloc[0]["stat_group"], "value": round(float(value), 2)}

        percentiles = {}
        if matches_played >= 3:
            placeholders = ",".join("?" for _ in RADAR_STATS)
            peers = con.execute(
                f"""
                WITH per_player_matches AS (
                    SELECT player_id, count(DISTINCT match_id) AS matches
                    FROM player_match_stats WHERE league_key = ?
                    GROUP BY player_id
                )
                SELECT s.player_id, s.stat_name, sum(s.value) AS total
                FROM player_match_stats s
                JOIN per_player_matches m ON m.player_id = s.player_id
                WHERE s.league_key = ? AND s.stat_name IN ({placeholders}) AND m.matches >= 3
                GROUP BY s.player_id, s.stat_name
                """,
                [league_key, league_key] + RADAR_STATS,
            ).fetchdf()
            for stat_name in RADAR_STATS:
                values = peers[peers["stat_name"] == stat_name]["total"]
                if len(values) < 2:
                    continue
                mine = totals.get(stat_name, {}).get("value", 0)
                rank = (values <= mine).sum()
                percentiles[stat_name] = round(float(rank) / len(values) * 100)

        shots = con.execute(
            """
            SELECT x, y, event_type, expected_goals, minute, situation, shot_type
            FROM shots WHERE league_key = ? AND player_id = ?
            """,
            [league_key, fm_id],
        ).fetchdf()

        return {
            "matched": True,
            "league_key": league_key,
            "league_label": _label(league_key),
            "fotmob_name": fm_name,
            "matches_played": int(matches_played),
            "totals": totals,
            "percentiles": percentiles,
            "shots": to_records(shots),
        }
    finally:
        con.close()


@router.get("/leagues")
def list_leagues():
    con = get_connection()
    try:
        rows = con.execute("SELECT DISTINCT league_key FROM teams ORDER BY league_key").fetchall()
        leagues = [{"key": r[0], "label": _label(r[0])} for r in rows]
        return sorted(leagues, key=lambda x: x["label"])
    finally:
        con.close()


@router.get("/leagues/{league_key}/standings")
def get_standings(league_key: str):
    con = get_connection()
    try:
        rows = con.execute(
            """
            SELECT group_name, team_id, name, idx, played, wins, draws, losses,
                   scores_str, goal_con_diff, pts
            FROM standings WHERE league_key = ?
            ORDER BY group_name NULLS FIRST, idx
            """,
            [league_key],
        ).fetchdf()
        return to_records(rows)
    finally:
        con.close()


@router.get("/leagues/{league_key}/player-stat-keys")
def list_player_stat_keys(league_key: str):
    con = get_connection()
    try:
        rows = con.execute(
            "SELECT DISTINCT stat_key FROM leaderboard_player_stats WHERE league_key = ? ORDER BY stat_key",
            [league_key],
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        con.close()


@router.get("/leagues/{league_key}/player-stats")
def get_player_leaderboard(league_key: str, stat: str = Query(...)):
    con = get_connection()
    try:
        rows = con.execute(
            """
            SELECT fotmob_id, team_id, name, value, rank
            FROM leaderboard_player_stats
            WHERE league_key = ? AND stat_key = ?
            ORDER BY rank
            LIMIT 50
            """,
            [league_key, stat],
        ).fetchdf()
        return to_records(rows)
    finally:
        con.close()


@router.get("/leagues/{league_key}/team-stat-keys")
def list_team_stat_keys(league_key: str):
    con = get_connection()
    try:
        rows = con.execute(
            "SELECT DISTINCT stat_key FROM leaderboard_team_stats WHERE league_key = ? ORDER BY stat_key",
            [league_key],
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        con.close()


@router.get("/leagues/{league_key}/team-stats")
def get_team_leaderboard(league_key: str, stat: str = Query(...)):
    con = get_connection()
    try:
        rows = con.execute(
            """
            SELECT team_id, name, value, rank
            FROM leaderboard_team_stats
            WHERE league_key = ? AND stat_key = ?
            ORDER BY rank
            """,
            [league_key, stat],
        ).fetchdf()
        return to_records(rows)
    finally:
        con.close()


@router.get("/leagues/{league_key}/matches")
def list_matches(league_key: str):
    con = get_connection()
    try:
        rows = con.execute(
            """
            SELECT match_id, round, date, home_id, home_name, away_id, away_name,
                   score, finished
            FROM matches WHERE league_key = ?
            ORDER BY date DESC
            """,
            [league_key],
        ).fetchdf()
        return to_records(rows)
    finally:
        con.close()


def _truncate(text, max_len: int) -> str:
    if not isinstance(text, str):
        return text
    return text if len(text) <= max_len else text[: max_len - 1].rstrip() + "…"


@router.get("/leagues/{league_key}/matches/{match_id}")
def get_match_detail(league_key: str, match_id: int):
    """Wedstrijddetail (topstatistieken, momentum, opstellingen) - gelezen
    rechtstreeks uit de ruwe FotMob-JSON (data/Fotmob/<league>/matches/),
    want lineup/momentum zitten bewust niet in de DuckDB-tabellen (zie
    scripts/fotmob_to_duckdb.py). Schoten komen wel uit DuckDB (shots-tabel),
    die is daar al wel voor gevuld."""
    path = FOTMOB_DIR / league_key / "matches" / f"{match_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Geen wedstrijddetail beschikbaar")
    with open(path, encoding="utf-8") as f:
        match = json.load(f)

    payload = match["payload"]
    general = payload["general"]
    header = payload["header"]
    home_team, away_team = header["teams"]
    colors = (general.get("teamColors") or {}).get("lightMode", {})

    content = payload["content"]
    periods = content.get("stats", {}).get("Periods", {})
    block = periods.get("All") or {}
    top_stats = [
        {"title": s.get("title", ""), "home": vals[0], "away": vals[1]}
        for group in block.get("stats", [])
        for s in group.get("stats", [])
        if len(vals := s.get("stats", [])) == 2
    ]

    momentum_main = ((content.get("momentum") or {}).get("main") or {}).get("data", [])
    momentum = [{"minute": m.get("minute"), "value": m.get("value")} for m in momentum_main]

    lineup = content.get("lineup") or {}

    def _team_lineup(side: str):
        team = lineup.get(side) or {}
        starters = [
            {
                "shirt_number": p.get("shirtNumber"),
                "name": _truncate(p.get("name", ""), 22),
                "rating": (p.get("performance") or {}).get("rating"),
            }
            for p in team.get("starters", [])
        ]
        subs = [_truncate(p.get("name", ""), 20) for p in team.get("subs", [])]
        return {"name": team.get("name", "-"), "formation": team.get("formation", "?"), "starters": starters, "subs": subs}

    con = get_connection()
    try:
        shots = con.execute(
            """
            SELECT x, y, player_id, player_name, team_id, event_type, expected_goals, minute, situation, shot_type
            FROM shots WHERE league_key = ? AND match_id = ?
            """,
            [league_key, match_id],
        ).fetchdf()
    finally:
        con.close()

    return {
        "home": {"id": home_team["id"], "name": home_team["name"], "image_url": home_team.get("imageUrl"), "color": colors.get("home", "#3B82F6")},
        "away": {"id": away_team["id"], "name": away_team["name"], "image_url": away_team.get("imageUrl"), "color": colors.get("away", "#EF4444")},
        "score_str": header["status"].get("scoreStr", "-"),
        "status_reason": (header["status"].get("reason") or {}).get("long", ""),
        "top_stats": top_stats,
        "momentum": momentum,
        "lineup": {"home": _team_lineup("homeTeam"), "away": _team_lineup("awayTeam")},
        "shots": to_records(shots),
    }
