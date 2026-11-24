"""
Databank-verbinding voor de API.

Leest voorlopig uit het lokale DuckDB-bestand (data/fotmob.duckdb, gevuld
door scripts/fotmob_to_duckdb.py + scripts/transfermarkt_to_duckdb.py) -
dit is bewust dezelfde databank die we lokaal getest hebben, zodat de API
meteen werkt zonder dat er al een gehoste Postgres moet zijn.

Omschakelen naar Postgres later is enkel deze functie aanpassen (een
psycopg2/asyncpg-connectie i.p.v. duckdb.connect) - de routers hieronder
praten enkel via standaard-SQL, niet via DuckDB-specifieke syntax, zodat
die overstap geen herschrijf van de routers vereist.
"""
import json
from functools import lru_cache
from pathlib import Path

import duckdb
import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "fotmob.duckdb"
FOTMOB_DIR = DB_PATH.parent / "Fotmob"
COMPETITIONS_DIR = DB_PATH.parent / "competitions"

# Competitiebatches die we effectief (opnieuw) scrapen onder het huidige
# project (zie monthly_update.yml) - zelfde lijst als
# streamlit/utils.py's _allowed_competition_ids(). Andere competities in
# tm_clubs/tm_players bevatten oude restdata van vóór dit project (vaak
# met lege naam/crest_url/... velden), en moeten dus ook hier verborgen
# blijven i.p.v. kapot-ogende rijen te tonen.
_ALLOWLIST_FILES = ("core.json", "big5.json", "eastern_europe.json", "world_other.json")


@lru_cache(maxsize=1)
def get_allowed_competition_ids() -> frozenset[str]:
    ids = set()
    for fname in _ALLOWLIST_FILES:
        fpath = COMPETITIONS_DIR / fname
        if not fpath.exists():
            continue
        with open(fpath, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                code = json.loads(line).get("country_code")
                if code:
                    ids.add(code)
    return frozenset(ids)


def allowed_competitions_sql(column: str, ids: frozenset[str]) -> tuple[str, list[str]]:
    """(SQL-fragment, params) voor 'column IN (...)' over de allowlist."""
    id_list = list(ids)
    placeholders = ",".join("?" for _ in id_list)
    return f"{column} IN ({placeholders})", id_list


def fill_missing_crests(
    con,
    rows: pd.DataFrame,
    club_id_col: str = "current_club_id",
    crest_col: str = "current_club_crest_url",
) -> pd.DataFrame:
    """PATCH: crest_col ontbreekt bij ~22% van de spelers (ook binnen de
    allowlist) terwijl tm_clubs.crest_url voor diezelfde club_id vaak wel
    ingevuld is (een andere scrape-run haalde die club recenter op) -
    zelfde fallback als streamlit/utils.py's _enrich_with_club_images()."""
    if rows.empty or club_id_col not in rows.columns or crest_col not in rows.columns:
        return rows
    missing = rows[crest_col].isna() | (rows[crest_col] == "")
    if not missing.any():
        return rows
    club_ids = [int(x) for x in rows.loc[missing, club_id_col].dropna().unique()]
    if not club_ids:
        return rows
    placeholders = ",".join("?" for _ in club_ids)
    crest_map = dict(
        con.execute(
            f"SELECT club_id, crest_url FROM tm_clubs WHERE club_id IN ({placeholders}) "
            "AND crest_url IS NOT NULL AND crest_url != ''",
            club_ids,
        ).fetchall()
    )
    rows.loc[missing, crest_col] = rows.loc[missing, club_id_col].map(crest_map)
    return rows


def get_connection():
    """Nieuwe read-only connectie per call - DuckDB staat geen gelijktijdige
    schrijf+lees-connecties op hetzelfde bestand toe, en de API doet toch
    enkel lezen."""
    return duckdb.connect(str(DB_PATH), read_only=True)


def to_records(df: pd.DataFrame) -> list:
    """df.to_dict(orient="records") met NaN -> None. Zonder dit crasht elk
    endpoint zodra 1 rij ergens een ontbrekende waarde heeft (bv. een club
    zonder crest_url) - Python's json.dumps kan geen NaN serialiseren, en
    dat gooit de HELE respons om, niet enkel dat ene veld."""
    return df.astype(object).where(df.notna(), None).to_dict(orient="records")


def to_record(df: pd.DataFrame) -> dict:
    """Zelfde, voor een dataframe met exact 1 rij (bv. 1 speler/club)."""
    return to_records(df)[0]
