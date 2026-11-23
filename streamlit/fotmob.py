"""Loaders voor de FotMob-datadump in data/Fotmob/ (momenteel enkel BE1).

Elke submap van data/Fotmob/ is 1 competitie-seizoen, rechtstreeks
overgenomen uit FotMob's eigen interne API-respons - niet door deze app
zelf opgehaald, en geen onderdeel van de reguliere Transfermarkt-pijplijn.
FotMob-IDs (team/speler) komen nergens overeen met Transfermarkt-IDs, dus
alle koppeling naar de rest van de app (crests, klikbare spelerprofielen)
gebeurt hier via een expliciete team-mapping (klein, vast ledental - dat
is betrouwbaarder dan naam-matching met afkortingen/accenten zoals
"St.Truiden" vs "Sint-Truidense VV") en, voor spelers, matching op
genormaliseerde achternaam binnen de gekoppelde club.
"""
import json
import re
import unicodedata
from pathlib import Path

import pandas as pd
import streamlit as st

from utils import load_clubs, load_players

FOTMOB_DIR = Path(__file__).resolve().parent.parent / "data" / "Fotmob"

LEAGUE_LABELS = {
    "First_Division_A-2026-2027": "Jupiler Pro League",
}

# FotMob team_id -> Transfermarkt club_id (handmatig opgezocht tegen
# data/csv/clubs.csv.gz - 18 clubs, eenmalig en stabiel).
_BE1_TEAM_ID_MAP = {
    7978: 3948,     # Union St.Gilloise -> Union Saint-Gilloise
    8342: 2282,     # Club Brugge -> Club Brugge KV
    9986: 172,      # Sporting Charleroi -> Royal Charleroi SC
    9991: 157,      # Gent -> KAA Gent
    8635: 58,       # Anderlecht -> RSC Anderlecht
    9987: 1184,     # Genk -> KRC Genk
    9985: 3057,     # Standard Liege -> Standard Liege
    6702: 5026,     # Lommel -> Lommel SK
    10001: 968,     # Westerlo -> KVC Westerlo
    8475: 28643,    # SK Beveren -> SK Beveren
    9997: 475,      # St.Truiden -> Sint-Truidense VV
    9988: 1096,     # Royal Antwerp -> Royal Antwerp FC
    1773: 2727,     # OH Leuven -> Oud-Heverlee Leuven
    9984: 520,      # Cercle Brugge -> Cercle Brugge
    10000: 3508,    # Zulte Waregem -> Zulte Waregem
    8203: 354,      # KV Mechelen -> KV Mechelen
    1218969: 3901,  # RAAL La Louviere -> RAAL La Louviere
    8571: 601,      # Kortrijk -> KV Kortrijk
}
_TEAM_ID_MAPS = {"First_Division_A-2026-2027": _BE1_TEAM_ID_MAP}

PLAYER_STAT_LABELS = {
    "_expected_goals_and_expected_assists_per_90": "xG+xA per 90",
    "_goals_and_goal_assist": "Goals + assists",
    "_goals_prevented": "Goals voorkomen (tov xG tegen)",
    "_save_percentage": "Reddingspercentage",
    "accurate_long_balls": "Nauwkeurige lange passes",
    "accurate_pass": "Nauwkeurige passes",
    "ball_recovery": "Balveroveringen",
    "big_chance_created": "Grote kansen gecreeerd",
    "big_chance_missed": "Grote kansen gemist",
    "clean_sheet": "Clean sheets",
    "defensive_contributions": "Defensieve bijdrages",
    "effective_clearance": "Geslaagde clearances",
    "expected_assists": "xA (expected assists)",
    "expected_assists_per_90": "xA per 90",
    "expected_goals": "xG (expected goals)",
    "expected_goals_per_90": "xG per 90",
    "expected_goalsontarget": "xG on target",
    "fouls": "Overtredingen",
    "goal_assist": "Assists",
    "goals": "Goals",
    "goals_conceded": "Tegengoals",
    "goals_per_90": "Goals per 90",
    "interception": "Onderscheppingen",
    "lbp_total": "Lange ballen (totaal)",
    "mins_played": "Minuten gespeeld",
    "ontarget_scoring_att": "Schoten op doel",
    "outfielder_block": "Geblokte schoten (veldspeler)",
    "penalty_conceded": "Toegestane penalty's",
    "penalty_save": "Gestopte penalty's",
    "penalty_won": "Uitgelokte penalty's",
    "poss_won_att_3rd": "Balverovering laatste derde",
    "rating": "Gemiddeld rapportcijfer",
    "red_card": "Rode kaarten",
    "saves": "Reddingen",
    "total_att_assist": "Pogingen tot assist",
    "total_high_claim": "Hoge ballen gevangen",
    "total_keeper_sweeper": "Acties als sweeper-keeper",
    "total_scoring_att": "Schotpogingen",
    "total_tackle": "Tackles",
    "won_contest": "Gewonnen dribbels",
    "yellow_card": "Gele kaarten",
}

TEAM_STAT_LABELS = {
    "_set_piece_goals_conceded_team": "Tegengoals uit standaardsituaties",
    "_set_piece_goals_team": "Goals uit standaardsituaties",
    "_xg_diff_team": "xG-verschil",
    "accurate_cross_team": "Nauwkeurige voorzetten",
    "accurate_long_balls_team": "Nauwkeurige lange passes",
    "accurate_pass_team": "Nauwkeurige passes",
    "big_chance_missed_team": "Grote kansen gemist",
    "big_chance_team": "Grote kansen gecreeerd",
    "clean_sheet_team": "Clean sheets",
    "corner_taken_team": "Hoekschoppen",
    "effective_clearance_team": "Geslaagde clearances",
    "expected_goals_conceded_team": "xG tegen",
    "expected_goals_team": "xG voor",
    "fk_foul_lost_team": "Overtredingen begaan",
    "goals_conceded_team_match": "Tegengoals per wedstrijd",
    "goals_team_match": "Goals per wedstrijd",
    "home_attendance_team": "Gemiddelde opkomst (thuis)",
    "interception_team": "Onderscheppingen",
    "ontarget_scoring_att_team": "Schoten op doel",
    "penalty_conceded_team": "Toegestane penalty's",
    "penalty_won_team": "Uitgelokte penalty's",
    "poss_won_att_3rd_team": "Balverovering laatste derde",
    "possession_percentage_team": "Balbezit %",
    "rating_team": "Gemiddeld rapportcijfer",
    "saves_team": "Reddingen",
    "squad_value_team": "Marktwaarde selectie",
    "total_red_card_team": "Rode kaarten",
    "total_tackle_team": "Tackles",
    "total_yel_card_team": "Gele kaarten",
    "touches_in_opp_box_team": "Balcontacten in strafschopgebied tegenstander",
}

# Meest bekeken statistieken eerst in de selectbox / als metric-tegels op
# het spelerprofiel, de rest alfabetisch op label.
PRIORITY_STATS = [
    "goals", "goal_assist", "rating",
    "expected_goals", "expected_assists", "mins_played",
]


def stat_label(stat_key: str, labels: dict) -> str:
    if stat_key in labels:
        return labels[stat_key]
    cleaned = stat_key.lstrip("_")
    if cleaned.endswith("_team"):
        cleaned = cleaned[: -len("_team")]
    return cleaned.replace("_", " ").capitalize()


def order_stat_keys(stat_keys: list, labels: dict) -> list:
    def sort_key(k):
        prio = PRIORITY_STATS.index(k) if k in PRIORITY_STATS else len(PRIORITY_STATS)
        return (prio, stat_label(k, labels))

    return sorted(stat_keys, key=sort_key)


def list_fotmob_leagues() -> dict:
    """{map_naam: weergavenaam} voor elke submap van data/Fotmob/."""
    if not FOTMOB_DIR.exists():
        return {}
    return {
        d.name: LEAGUE_LABELS.get(d.name, d.name.replace("_", " "))
        for d in sorted(FOTMOB_DIR.iterdir())
        if d.is_dir()
    }


def _dir(league_key: str) -> Path:
    return FOTMOB_DIR / league_key


def _load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _normalize(name) -> str:
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z ]", "", s.lower()).strip()


@st.cache_data(ttl=3600)
def _club_lookup() -> pd.DataFrame:
    return load_clubs().set_index("club_id")


def resolve_club(league_key: str, team_id) -> dict:
    """FotMob team_id -> {club_id, name, crest_url}, of {} als onbekend."""
    if team_id is None:
        return {}
    try:
        team_id = int(team_id)
    except (TypeError, ValueError):
        return {}
    club_id = _TEAM_ID_MAPS.get(league_key, {}).get(team_id)
    if club_id is None:
        return {}
    clubs = _club_lookup()
    if club_id not in clubs.index:
        return {}
    row = clubs.loc[club_id]
    return {"club_id": club_id, "name": row["name"], "crest_url": row.get("crest_url", "") or ""}


@st.cache_data(ttl=3600)
def _players_by_club() -> dict:
    players = load_players()
    return {cid: df for cid, df in players.groupby("current_club_id")}


def resolve_player(league_key: str, team_id, fotmob_name: str):
    """FotMob (team_id, naam) -> Transfermarkt player_id, of None.

    Matcht op genormaliseerde achternaam binnen de kern van de gekoppelde
    club. Bij twijfel (geen club-match, geen/dubbele naam-match) geen gok
    wagen - een foute profiel-link is erger dan geen link."""
    club = resolve_club(league_key, team_id)
    if not club or not fotmob_name:
        return None
    squad = _players_by_club().get(club["club_id"])
    if squad is None or squad.empty:
        return None
    target_last = _normalize(fotmob_name.split()[-1])
    if target_last:
        candidates = squad[squad["last_name"].map(_normalize) == target_last]
        if len(candidates) == 1:
            return int(candidates.iloc[0]["player_id"])
    target_full = _normalize(fotmob_name)
    candidates = squad[squad["name"].map(_normalize) == target_full]
    if len(candidates) == 1:
        return int(candidates.iloc[0]["player_id"])
    if target_last:
        # FotMob toont soms maar het eerste deel van een samengestelde
        # achternaam (bv. "Dennis Eckert" voor TM's "Dennis Eckert Ayensa") -
        # match dan op het eerste woord van TM's last_name.
        candidates = squad[squad["last_name"].map(lambda n: _normalize(n).split()[:1] == [target_last])]
        if len(candidates) == 1:
            return int(candidates.iloc[0]["player_id"])
    return None


def fotmob_team_id_for_club(league_key: str, club_id) -> int | None:
    """Transfermarkt club_id -> FotMob team_id (omgekeerde van de
    team-mapping), of None als deze club niet gevolgd wordt in FotMob."""
    try:
        club_id = int(club_id)
    except (TypeError, ValueError):
        return None
    for fm_id, tm_id in _TEAM_ID_MAPS.get(league_key, {}).items():
        if tm_id == club_id:
            return fm_id
    return None


@st.cache_data(ttl=3600)
def _fotmob_roster(league_key: str) -> pd.DataFrame:
    """Alle unieke (id, teamId, name)-combinaties over alle spelers-
    statistiekbestanden heen - geen enkel bestand bevat gegarandeerd de
    volledige kern (een speler zonder minuten staat zelfs niet in
    mins_played), dus de unie van alle bestanden is de beste benadering
    van 'wie zit er in deze competitie'."""
    frames = []
    for key in list_player_stats(league_key):
        df = load_player_stat(league_key, key)
        if not df.empty and {"id", "teamId", "name"}.issubset(df.columns):
            frames.append(df[["id", "teamId", "name"]])
    if not frames:
        return pd.DataFrame(columns=["id", "teamId", "name"])
    return pd.concat(frames, ignore_index=True).drop_duplicates(subset=["id"])


def fotmob_player_for_tm_player(league_key: str, player_row) -> dict | None:
    """Omgekeerde van resolve_player(): Transfermarkt-speler -> FotMob
    {id, team_id, name}, of None. Zelfde voorzichtige matching-aanpak -
    enkel koppelen bij een eenduidige naam-match binnen de gekoppelde club."""
    team_id = fotmob_team_id_for_club(league_key, player_row.get("current_club_id"))
    if team_id is None:
        return None
    roster = _fotmob_roster(league_key)
    squad = roster[roster["teamId"] == team_id]
    if squad.empty:
        return None

    def fm_last_word(name) -> str:
        n = _normalize(name)
        return n.split()[-1] if n else ""

    tm_last = _normalize(player_row.get("last_name") or "")
    tm_full = _normalize(player_row.get("name") or "")
    tm_last_first_word = tm_last.split()[0] if tm_last else ""

    if tm_last:
        candidates = squad[squad["name"].map(lambda n: fm_last_word(n) == tm_last)]
        if len(candidates) == 1:
            r = candidates.iloc[0]
            return {"id": int(r["id"]), "team_id": team_id, "name": r["name"]}
    if tm_full:
        candidates = squad[squad["name"].map(lambda n: _normalize(n) == tm_full)]
        if len(candidates) == 1:
            r = candidates.iloc[0]
            return {"id": int(r["id"]), "team_id": team_id, "name": r["name"]}
    if tm_last_first_word:
        # Omgekeerd geval van resolve_player()'s samengestelde-achternaam-fix:
        # TM "Dennis Eckert Ayensa" vs FotMob "Dennis Eckert".
        candidates = squad[squad["name"].map(lambda n: fm_last_word(n) == tm_last_first_word)]
        if len(candidates) == 1:
            r = candidates.iloc[0]
            return {"id": int(r["id"]), "team_id": team_id, "name": r["name"]}
    return None


def fotmob_player_stats(league_key: str, fotmob_player_id: int) -> dict:
    """{label: waarde} voor elke spelersstatistiek waarin deze FotMob-speler
    voorkomt - niet elke speler staat in elk bestand (bv. een speler zonder
    enige kaart staat niet in yellow_card.json)."""
    out = {}
    for key in list_player_stats(league_key):
        df = load_player_stat(league_key, key)
        if df.empty:
            continue
        row = df[df["id"] == fotmob_player_id]
        if row.empty:
            continue
        value = row.iloc[0]["value"]
        out[key] = round(value, 2) if isinstance(value, float) else value
    return out


@st.cache_data(ttl=3600)
def load_table(league_key: str):
    """Geeft (standen_df, legende) terug. Elke rij heeft al een 'qualColor'."""
    data = _load_json(_dir(league_key) / "table.json")
    block = data[0]["data"]
    df = pd.DataFrame(block["table"]["all"])
    return df, block.get("legend", [])


@st.cache_data(ttl=3600)
def load_fixtures(league_key: str) -> pd.DataFrame:
    data = _load_json(_dir(league_key) / "fixtures.json")
    rows = []
    for m in data["allMatches"]:
        status = m.get("status", {})
        rows.append(
            {
                "match_id": int(m["id"]),
                "round": m.get("roundName") or m.get("round"),
                "date": status.get("utcTime"),
                "home": m["home"]["name"],
                "home_id": int(m["home"]["id"]),
                "away": m["away"]["name"],
                "away_id": int(m["away"]["id"]),
                "score": status.get("scoreStr"),
                "finished": status.get("finished", False),
            }
        )
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True).dt.tz_localize(None)
    return df


def available_match_ids(league_key: str) -> set:
    d = _dir(league_key) / "matches"
    if not d.exists():
        return set()
    return {int(p.stem) for p in d.glob("*.json")}


@st.cache_data(ttl=3600)
def load_match(league_key: str, match_id: int) -> dict:
    return _load_json(_dir(league_key) / "matches" / f"{match_id}.json")


@st.cache_data(ttl=3600)
def list_player_stats(league_key: str) -> list:
    d = _dir(league_key) / "stats" / "players"
    return sorted(p.stem for p in d.glob("*.json")) if d.exists() else []


@st.cache_data(ttl=3600)
def list_team_stats(league_key: str) -> list:
    d = _dir(league_key) / "stats" / "teams"
    return sorted(p.stem for p in d.glob("*.json")) if d.exists() else []


def _load_stat(path: Path) -> pd.DataFrame:
    data = _load_json(path)
    df = pd.DataFrame(data.get("statsData", []))
    if df.empty:
        return df
    df["value"] = df["statValue"].map(lambda v: v.get("value") if isinstance(v, dict) else v)
    return df


@st.cache_data(ttl=3600)
def load_player_stat(league_key: str, stat_key: str) -> pd.DataFrame:
    return _load_stat(_dir(league_key) / "stats" / "players" / f"{stat_key}.json")


@st.cache_data(ttl=3600)
def load_team_stat(league_key: str, stat_key: str) -> pd.DataFrame:
    return _load_stat(_dir(league_key) / "stats" / "teams" / f"{stat_key}.json")


def match_top_stats(match_payload: dict, period: str = "All") -> list:
    """[{title, home, away}, ...] - enkel 2-zijdige (home/away) statistieken."""
    periods = match_payload["payload"]["content"].get("stats", {}).get("Periods", {})
    block = periods.get(period) or periods.get("All") or {}
    rows = []
    for group in block.get("stats", []):
        for s in group.get("stats", []):
            vals = s.get("stats", [])
            if len(vals) == 2:
                rows.append({"title": s.get("title", ""), "home": vals[0], "away": vals[1]})
    return rows


def match_shots(match_payload: dict) -> pd.DataFrame:
    shots = match_payload["payload"]["content"].get("shotmap", {}).get("shots", [])
    return pd.DataFrame(shots)


def match_momentum(match_payload: dict) -> pd.DataFrame:
    main = (match_payload["payload"]["content"].get("momentum") or {}).get("main") or {}
    return pd.DataFrame(main.get("data", []))


def match_lineup(match_payload: dict) -> dict:
    return match_payload["payload"]["content"].get("lineup") or {}


def _as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def stat_bar_html(title: str, home_val, away_val, home_color: str, away_color: str) -> str:
    """2-zijdige vergelijkingsbalk (thuis vs uit) voor 1 wedstrijdstatistiek.
    Valt terug op kale tekst zonder balk als een van beide waarden niet
    numeriek is (bv. "FT")."""
    home_num, away_num = _as_float(home_val), _as_float(away_val)
    if home_num is None or away_num is None or home_num + away_num <= 0:
        home_pct = away_pct = 50
    else:
        total = home_num + away_num
        home_pct = home_num / total * 100
        away_pct = 100 - home_pct
    return (
        '<div class="fm-stat-row">'
        f'<div class="fm-stat-val">{home_val}</div>'
        '<div class="fm-stat-bar">'
        f'<div class="fm-stat-bar-home" style="width:{home_pct:.1f}%;background:{home_color};"></div>'
        f'<div class="fm-stat-bar-away" style="width:{away_pct:.1f}%;background:{away_color};"></div>'
        "</div>"
        f'<div class="fm-stat-val">{away_val}</div>'
        "</div>"
        f'<div class="fm-stat-title">{title}</div>'
    )
