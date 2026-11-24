#!/usr/bin/env python3
"""
Flattened de FotMob-JSON-dump (data/Fotmob/, ~2,6GB ruwe JSON over ~55
competities) naar nette, genormaliseerde tabellen in een lokaal DuckDB-
bestand (data/fotmob.duckdb, niet gecommit).

Doel: lokaal testen hoe groot/snel dit wordt vóórdat we beslissen wat er
naar een echte (gehoste) Postgres gaat - zie het gesprek in deze sessie
over DuckDB (lokale voorbereiding) vs Postgres (bediening van de live site).

Dekt: teams, standenlijst, wedstrijden, schoten (shotmap), spelersstats per
wedstrijd (lange vorm, want de veldnamen verschillen per speler/wedstrijd),
en de leaderboard-bestanden (stats/players, stats/teams). Dekt NIET (bewust,
voor deze eerste test): lineups/momentum - klein volume, lagere prioriteit.

Gebruik:
    python scripts/fotmob_to_duckdb.py
"""
import json
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
FOTMOB_DIR = ROOT / "data" / "Fotmob"
DB_PATH = ROOT / "data" / "fotmob.duckdb"


def _load(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _team_names(league_dir: Path) -> dict:
    """team_id -> naam, unie van alle home/away-vermeldingen in fixtures.json."""
    names = {}
    fixtures = _load(league_dir / "fixtures.json")
    for m in fixtures.get("allMatches", []):
        for side in ("home", "away"):
            team = m.get(side) or {}
            tid = team.get("id")
            if tid is not None:
                names[int(tid)] = team.get("name", "")
    return names


def _standings_rows(league_key: str, league_dir: Path) -> list:
    """Meeste competities hebben 1 tabel (data.table.all); competities met
    meerdere reeksen (bv. Primera Federacion Grupo I/II) hebben in de plaats
    data.tables, een lijst van groepstabellen - group_name onderscheidt ze."""
    path = league_dir / "table.json"
    if not path.exists():
        return []
    block = _load(path)[0]["data"]
    groups = [(None, block["table"])] if "table" in block else [
        (g.get("leagueName", ""), g["table"]) for g in block.get("tables", [])
    ]
    out = []
    for group_name, table in groups:
        for r in table.get("all", []):
            out.append(
                {
                    "league_key": league_key,
                    "group_name": group_name,
                    "team_id": r["id"],
                    "name": r.get("name", ""),
                    "idx": r.get("idx"),
                    "played": r.get("played"),
                    "wins": r.get("wins"),
                    "draws": r.get("draws"),
                    "losses": r.get("losses"),
                    "scores_str": r.get("scoresStr", ""),
                    "goal_con_diff": r.get("goalConDiff"),
                    "pts": r.get("pts"),
                }
            )
    return out


def _match_rows(league_key: str, league_dir: Path) -> list:
    path = league_dir / "fixtures.json"
    if not path.exists():
        return []
    data = _load(path)
    rows = []
    for m in data.get("allMatches", []):
        status = m.get("status", {})
        rows.append(
            {
                "league_key": league_key,
                "match_id": int(m["id"]),
                "round": m.get("roundName") or m.get("round"),
                "date": status.get("utcTime"),
                "home_id": int(m["home"]["id"]),
                "home_name": m["home"].get("name", ""),
                "away_id": int(m["away"]["id"]),
                "away_name": m["away"].get("name", ""),
                "score": status.get("scoreStr"),
                "finished": bool(status.get("finished", False)),
            }
        )
    return rows


def _shot_and_stat_rows(league_key: str, league_dir: Path) -> tuple:
    """1 keer over alle matches/*.json lopen, shots en player-match-stats
    allebei opbouwen (vermijdt het bestand 2x te parsen)."""
    match_dir = league_dir / "matches"
    shots, stats = [], []
    if not match_dir.exists():
        return shots, stats
    for path in match_dir.glob("*.json"):
        match_id = int(path.stem)
        content = _load(path)["payload"]["content"]

        for shot in (content.get("shotmap") or {}).get("shots", []):
            shots.append(
                {
                    "league_key": league_key,
                    "match_id": match_id,
                    "player_id": shot.get("playerId"),
                    "player_name": shot.get("playerName", ""),
                    "team_id": shot.get("teamId"),
                    "event_type": shot.get("eventType", ""),
                    "expected_goals": shot.get("expectedGoals"),
                    "minute": shot.get("min"),
                    "x": shot.get("x"),
                    "y": shot.get("y"),
                    "situation": shot.get("situation"),
                    "shot_type": shot.get("shotType"),
                }
            )

        for pid_str, info in (content.get("playerStats") or {}).items():
            try:
                player_id = int(pid_str)
            except (TypeError, ValueError):
                continue
            team_id = info.get("teamId")
            player_name = info.get("name", "")
            for group in info.get("stats", []):
                group_title = group.get("title", "")
                for stat_name, stat_info in group.get("stats", {}).items():
                    value = (stat_info.get("stat") or {}).get("value")
                    if value is None:
                        continue
                    stats.append(
                        {
                            "league_key": league_key,
                            "match_id": match_id,
                            "player_id": player_id,
                            "player_name": player_name,
                            "team_id": team_id,
                            "stat_group": group_title,
                            "stat_name": stat_name,
                            "value": value,
                        }
                    )
    return shots, stats


def _leaderboard_rows(league_key: str, league_dir: Path, kind: str) -> list:
    """kind: 'players' of 'teams' -> rijen uit stats/<kind>/*.json."""
    stat_dir = league_dir / "stats" / kind
    rows = []
    if not stat_dir.exists():
        return rows
    id_col = "fotmob_id" if kind == "players" else "team_id"
    for path in stat_dir.glob("*.json"):
        stat_key = path.stem
        data = _load(path)
        for entry in data.get("statsData", []):
            value = entry.get("statValue")
            value = value.get("value") if isinstance(value, dict) else value
            rows.append(
                {
                    "league_key": league_key,
                    "stat_key": stat_key,
                    id_col: entry.get("id"),
                    "team_id": entry.get("teamId"),
                    "name": entry.get("name", ""),
                    "value": value,
                    "rank": entry.get("rank"),
                }
            )
    return rows


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = duckdb.connect(str(DB_PATH))

    con.execute("""
        CREATE TABLE teams (league_key TEXT, team_id BIGINT, name TEXT)
    """)
    con.execute("""
        CREATE TABLE standings (
            league_key TEXT, group_name TEXT, team_id BIGINT, name TEXT, idx INTEGER,
            played INTEGER, wins INTEGER, draws INTEGER, losses INTEGER,
            scores_str TEXT, goal_con_diff INTEGER, pts INTEGER
        )
    """)
    con.execute("""
        CREATE TABLE matches (
            league_key TEXT, match_id BIGINT, round TEXT, date TIMESTAMP,
            home_id BIGINT, home_name TEXT, away_id BIGINT, away_name TEXT,
            score TEXT, finished BOOLEAN
        )
    """)
    con.execute("""
        CREATE TABLE shots (
            league_key TEXT, match_id BIGINT, player_id BIGINT, player_name TEXT,
            team_id BIGINT, event_type TEXT, expected_goals DOUBLE, minute INTEGER,
            x DOUBLE, y DOUBLE, situation TEXT, shot_type TEXT
        )
    """)
    con.execute("""
        CREATE TABLE player_match_stats (
            league_key TEXT, match_id BIGINT, player_id BIGINT, player_name TEXT,
            team_id BIGINT, stat_group TEXT, stat_name TEXT, value DOUBLE
        )
    """)
    con.execute("""
        CREATE TABLE leaderboard_player_stats (
            league_key TEXT, stat_key TEXT, fotmob_id BIGINT, team_id BIGINT,
            name TEXT, value DOUBLE, rank INTEGER
        )
    """)
    con.execute("""
        CREATE TABLE leaderboard_team_stats (
            league_key TEXT, stat_key TEXT, team_id BIGINT,
            name TEXT, value DOUBLE, rank INTEGER
        )
    """)

    league_dirs = sorted(d for d in FOTMOB_DIR.iterdir() if d.is_dir())
    print(f"{len(league_dirs)} competities gevonden")

    for i, league_dir in enumerate(league_dirs, 1):
        league_key = league_dir.name
        print(f"[{i}/{len(league_dirs)}] {league_key}")

        try:
            names = _team_names(league_dir)
            if names:
                df = pd.DataFrame(
                    [{"league_key": league_key, "team_id": tid, "name": n} for tid, n in names.items()]
                )
                con.execute("INSERT INTO teams SELECT * FROM df")
        except Exception as e:
            print(f"  WAARSCHUWING teams: {e}")

        try:
            standings = _standings_rows(league_key, league_dir)
            if standings:
                df = pd.DataFrame(standings)
                con.execute("INSERT INTO standings SELECT * FROM df")
        except Exception as e:
            print(f"  WAARSCHUWING standings: {e}")

        try:
            matches = _match_rows(league_key, league_dir)
            if matches:
                df = pd.DataFrame(matches)
                df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True).dt.tz_localize(None)
                con.execute("INSERT INTO matches SELECT * FROM df")
        except Exception as e:
            print(f"  WAARSCHUWING matches: {e}")

        try:
            shots, stats = _shot_and_stat_rows(league_key, league_dir)
            if shots:
                df = pd.DataFrame(shots)
                con.execute("INSERT INTO shots SELECT * FROM df")
            if stats:
                df = pd.DataFrame(stats)
                con.execute("INSERT INTO player_match_stats SELECT * FROM df")
        except Exception as e:
            print(f"  WAARSCHUWING shots/stats: {e}")

        try:
            player_lb = _leaderboard_rows(league_key, league_dir, "players")
            if player_lb:
                df = pd.DataFrame(player_lb)
                con.execute("INSERT INTO leaderboard_player_stats SELECT * FROM df")
        except Exception as e:
            print(f"  WAARSCHUWING leaderboard players: {e}")

        try:
            team_lb = _leaderboard_rows(league_key, league_dir, "teams")
            if team_lb:
                df = pd.DataFrame(team_lb)
                con.execute("INSERT INTO leaderboard_team_stats SELECT * FROM df")
        except Exception as e:
            print(f"  WAARSCHUWING leaderboard teams: {e}")

    print("\nRijtellingen:")
    for table in [
        "teams", "standings", "matches", "shots",
        "player_match_stats", "leaderboard_player_stats", "leaderboard_team_stats",
    ]:
        count = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count:,}")

    con.close()
    size_mb = DB_PATH.stat().st_size / 1024 / 1024
    print(f"\n{DB_PATH} geschreven: {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
