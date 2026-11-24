#!/usr/bin/env python3
"""
Laadt de bestaande, voorbereide Transfermarkt-CSV's (data/csv/*.csv.gz) als
tabellen in hetzelfde lokale DuckDB-bestand als scripts/fotmob_to_duckdb.py
(data/fotmob.duckdb) - zodat we 1 uniforme lokale databank hebben met zowel
de Transfermarkt- als de FotMob-data, als test vóór de overstap naar een
gehoste Postgres.

In tegenstelling tot de FotMob-JSON (die eerst geflattened moet worden) zijn
dit al nette, platte CSV's - DuckDB leest die rechtstreeks in, geen eigen
parsing nodig.

Laadt bewust NIET de "_jpl"-gesuffixte bestanden (clubs_jpl.csv.gz,
players_jpl.csv.gz, ...) - dat zijn losse testbestanden van een eerdere
Jupiler Pro League-poging, niet de bestanden die de Streamlit-app effectief
leest (zie streamlit/utils.py _read_csv()).

Gebruik:
    python scripts/transfermarkt_to_duckdb.py
"""
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
CSV_DIR = ROOT / "data" / "csv"
DB_PATH = ROOT / "data" / "fotmob.duckdb"

# tabelnaam -> bronbestand (zonder "_jpl"-varianten, zie moduledocstring)
TABLES = {
    "tm_clubs": "clubs.csv.gz",
    "tm_competitions": "competitions.csv.gz",
    "tm_players": "players.csv.gz",
    "tm_games": "games.csv.gz",
    "tm_appearances": "appearances.csv.gz",
    "tm_transfers": "transfers.csv.gz",
    "tm_player_valuations": "player_valuations.csv.gz",
    "tm_injuries": "injuries.csv.gz",
}


def main():
    con = duckdb.connect(str(DB_PATH))
    for table, filename in TABLES.items():
        path = CSV_DIR / filename
        if not path.exists():
            print(f"  overgeslagen (niet gevonden): {filename}")
            continue
        con.execute(f"DROP TABLE IF EXISTS {table}")
        con.execute(
            f"CREATE TABLE {table} AS SELECT * FROM read_csv_auto(?, ignore_errors=true)",
            [str(path)],
        )
        count = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count:,} rijen (uit {filename})")

    con.close()
    size_mb = DB_PATH.stat().st_size / 1024 / 1024
    print(f"\n{DB_PATH} nu in totaal: {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
