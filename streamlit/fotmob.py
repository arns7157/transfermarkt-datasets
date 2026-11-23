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
import plotly.graph_objects as go
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


def half_pitch_shapes(line_color: str = "#CBD5E1") -> list:
    """Plotly shapes voor een vereenvoudigde aanvalshelft, doel BOVENAAN -
    de gebruikelijke oriëntatie voor een shotmap (Understat/FBref/FotMob
    doen dit ook zo). Hoort bij plot_shots_on_pitch(), die de schot-
    coördinaten (x = lengte, y = breedte) naar dezelfde schermassen omzet
    (scherm-x = breedte, scherm-y = lengte) - dit NIET los gebruiken met de
    rauwe x/y-kolommen, die staan nog in de oorspronkelijke (liggende)
    oriëntatie."""
    return [
        dict(type="rect", x0=0, x1=100, y0=50, y1=100, line=dict(color=line_color)),
        dict(type="rect", x0=21, x1=79, y0=83, y1=100, line=dict(color=line_color)),
        dict(type="rect", x0=37, x1=63, y0=94.2, y1=100, line=dict(color=line_color)),
        dict(type="line", x0=45, x1=55, y0=100, y1=100, line=dict(color=line_color, width=4)),
    ]


def plot_shots_on_pitch(fig, shots: pd.DataFrame, color: str, name: str, show_player: bool = False) -> None:
    """Voegt 1 Scatter-trace met schoten toe aan fig, in de verticale
    (doel-bovenaan) oriëntatie van half_pitch_shapes() - wisselt x/y om
    (scherm-x = pitch-breedte, scherm-y = pitch-lengte) t.o.v. de rauwe
    FotMob-coördinaten (x = lengte, y = breedte). show_player=True zet de
    spelersnaam vooraan in de hover-tekst (wedstrijd-shotmap, meerdere
    spelers per kleur); False laat die weg (seizoenskaart van 1 speler,
    overbodige herhaling)."""
    if shots.empty:
        return
    is_goal = shots["eventType"] == "Goal"
    sizes = shots["expectedGoals"].fillna(0).clip(lower=0) ** 0.5 * 32 + 8
    hover_cols = (["playerName"] if show_player else []) + ["eventType", "expectedGoals", "min"]
    prefix = "%{customdata[0]}<br>" if show_player else ""
    i_type, i_xg, i_min = (1, 2, 3) if show_player else (0, 1, 2)
    fig.add_trace(
        go.Scatter(
            x=shots["y"],
            y=shots["x"],
            mode="markers",
            name=name,
            marker=dict(
                size=sizes,
                color=color,
                symbol=["star" if g else "circle" for g in is_goal],
                line=dict(width=1, color="#1F2937"),
                opacity=0.85,
            ),
            customdata=shots[hover_cols],
            hovertemplate=(
                f"{prefix}Minuut %{{customdata[{i_min}]}}<br>"
                f"%{{customdata[{i_type}]}} - xG %{{customdata[{i_xg}]:.2f}}<extra></extra>"
            ),
        )
    )


def style_pitch_axes(fig) -> None:
    """Dwingt een correcte, niet-uitgerekte verhouding af voor een shotmap
    in de oriëntatie van half_pitch_shapes() - zonder dit groeit de
    aanvalshelft mee met de volle breedte van de pagina terwijl de hoogte
    vast blijft, met een helemaal uitgerekt en naar 1 kant weggedrukt veld
    als gevolg."""
    fig.update_xaxes(range=[-3, 103], showgrid=False, zeroline=False, showticklabels=False)
    fig.update_yaxes(
        range=[47, 103], showgrid=False, zeroline=False, showticklabels=False,
        scaleanchor="x", scaleratio=1,
    )


def _as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# Stats die een gemiddelde zijn i.p.v. een optelbaar aantal - optellen over
# wedstrijden heen zou onzin opleveren. "Shot accuracy" zag er aanvankelijk
# ook zo uit, maar bleek in de praktijk altijd exact gelijk aan "Shots on
# target" (een dubbel veld) - die staat daarom in MATCH_STAT_SKIP, niet hier.
RATE_STAT_NAMES = {"FotMob rating"}

SHOT_SITUATION_LABELS_NL = {
    "RegularPlay": "Gewoon spel",
    "FastBreak": "Snelle uitbraak",
    "SetPiece": "Standaardsituatie",
    "FromCorner": "Via hoekschop",
    "Penalty": "Penalty",
    "FreeKick": "Vrije trap",
    "ThrowInSetPiece": "Na inworp",
    "IndividualPlay": "Individuele actie",
}
SHOT_TYPE_LABELS_NL = {
    "RightFoot": "Rechtervoet",
    "LeftFoot": "Linkervoet",
    "Header": "Kopbal",
    "OtherBodyParts": "Ander lichaamsdeel",
}

RADAR_STAT_NAMES = ["Goals", "Total shots", "Chances created", "Touches", "Aerial duels won", "Defensive actions"]
RADAR_LABELS_NL = {
    "Goals": "Doelpunten",
    "Total shots": "Schotpogingen",
    "Chances created": "Kansen gecreeerd",
    "Touches": "Balcontacten",
    "Aerial duels won": "Luchtduels gewonnen",
    "Defensive actions": "Verdedigende acties",
}

# Nederlandse labels voor de per-wedstrijd playerStats-velden (match-niveau,
# niet dezelfde set/namen als PLAYER_STAT_LABELS, dat is de aparte
# leaderboard-databron van stats/players/*.json).
MATCH_STAT_LABELS_NL = {
    "Accurate crosses": "Nauwkeurige voorzetten",
    "Accurate long balls": "Nauwkeurige lange passes",
    "Accurate passes": "Nauwkeurige passes",
    "Acted as sweeper": "Acties als sweeper-keeper",
    "Aerial duels won": "Luchtduels gewonnen",
    "Assists": "Assists",
    "Big chances created": "Grote kansen gecreeerd",
    "Big chances missed": "Grote kansen gemist",
    "Blocked shots": "Geblokte schoten",
    "Blocks": "Blocks",
    "Chances created": "Kansen gecreeerd",
    "Clearance off the line": "Clearance van de lijn",
    "Clearances": "Clearances",
    "Conceded penalty": "Toegestane penalty",
    "Corners": "Hoekschoppen",
    "Defensive actions": "Defensieve acties",
    "Dispossessed": "Bal verloren onder druk",
    "Diving save": "Reddende duik",
    "Dribbled past": "Gepasseerd",
    "Duels lost": "Duels verloren",
    "Duels won": "Duels gewonnen",
    "Error led to goal": "Fout leidde tot goal",
    "Expected assists (xA)": "Verwachte assists (xA)",
    "Expected goals (xG)": "Verwachte goals (xG)",
    "Expected goals on target (xGOT)": "xG op doel (xGOT)",
    "FotMob rating": "FotMob-rapportcijfer",
    "Fouls committed": "Overtredingen",
    "Goals": "Doelpunten",
    "Goals conceded": "Tegendoelpunten",
    "Goals prevented": "Doelpunten voorkomen",
    "Ground duels won": "Grondduels gewonnen",
    "Headed clearance": "Clearance met het hoofd",
    "High claim": "Hoge bal gevangen",
    "Hit woodwork": "Paal/lat geraakt",
    "Interceptions": "Onderscheppingen",
    "Last man tackle": "Tackle als laatste man",
    "Line breaking passes": "Linie-doorbrekende passes",
    "Minutes played": "Minuten gespeeld",
    "Missed penalty": "Gemiste penalty",
    "Offsides": "Buitenspel",
    "Own goal": "Eigen doelpunt",
    "Passes into final third": "Passes naar laatste derde",
    "Penalties won": "Uitgelokte penalty's",
    "Punches": "Weggeboksde ballen",
    "Recoveries": "Balveroveringen",
    "Saved penalties": "Gestopte penalty's",
    "Saves": "Reddingen",
    "Saves inside box": "Reddingen in de zestien",
    "Shot accuracy": "Schotnauwkeurigheid",
    "Shots off target": "Schoten naast",
    "Shots on target": "Schoten op doel",
    "Successful dribbles": "Geslaagde dribbels",
    "Tackles": "Tackles",
    "Throws": "Ingooien",
    "Total shots": "Totaal schoten",
    "Touches": "Balcontacten",
    "Touches in opposition box": "Balcontacten in strafschopgebied",
    "Was fouled": "Gefouleerd",
    "xG Non-penalty": "xG zonder penalty's",
    "xGOT faced": "xGOT tegen",
}

MATCH_STAT_GROUP_LABELS_NL = {"Top stats": "Topstatistieken", "Attack": "Aanval", "Defense": "Verdediging", "Duels": "Duels"}

# Interne/fantasy-achtige velden zonder duidelijke waarde voor deze app -
# niet tonen in de seizoensstatistieken-tabel.
MATCH_STAT_SKIP = {"Shotmap", "Fantasy assists", "xG + xA", "Shot accuracy"}

# Al als metric-tegel getoond op het spelerprofiel - niet dubbel in de
# gedetailleerde, gegroepeerde tabel eronder.
MATCH_STAT_HEADLINE = {"Goals", "Assists", "FotMob rating", "Expected goals (xG)", "Expected assists (xA)", "Minutes played"}


def match_stat_label(name: str) -> str:
    return MATCH_STAT_LABELS_NL.get(name, name)


def _flatten_player_match_stats(info: dict) -> dict:
    """{stat_naam: (groep, waarde)} voor 1 speler in 1 wedstrijd. Een stat
    die in meerdere groepen voorkomt (bv. "Defensive actions" staat zowel
    in "Top stats" als in "Defense") krijgt de laatst-verwerkte, specifiekere
    groep - "Top stats" staat in de brondata altijd eerst, dus dict-overwrite
    doet dit vanzelf correct."""
    out = {}
    for group in info.get("stats", []):
        title = group.get("title", "")
        for name, stat_info in group.get("stats", {}).items():
            out[name] = (title, (stat_info.get("stat") or {}).get("value"))
    return out


@st.cache_data(ttl=3600)
def _player_match_log(league_key: str) -> dict:
    """fotmob_player_id -> lijst van {match_id, team_id, stats} - 1x alle
    lokaal beschikbare wedstrijdbestanden inlezen en hergebruiken voor elk
    spelerprofiel, i.p.v. ze telkens opnieuw te scannen."""
    log: dict = {}
    for match_id in available_match_ids(league_key):
        match = load_match(league_key, match_id)
        player_stats = match["payload"]["content"].get("playerStats") or {}
        for pid_str, info in player_stats.items():
            try:
                pid = int(pid_str)
            except (TypeError, ValueError):
                continue
            log.setdefault(pid, []).append(
                {
                    "match_id": match_id,
                    "team_id": info.get("teamId"),
                    "stats": _flatten_player_match_stats(info),
                }
            )
    return log


def player_match_log(league_key: str, fotmob_player_id: int) -> list:
    return _player_match_log(league_key).get(fotmob_player_id, [])


def player_season_totals(league_key: str, fotmob_player_id: int) -> dict:
    """{stat_naam: {"group":, "value":}} - opgeteld over elke wedstrijd waar
    deze speler speelstatistieken voor heeft, behalve de gemiddelde/
    percentage-achtige stats (zie RATE_STAT_NAMES), die gemiddeld worden."""
    entries = player_match_log(league_key, fotmob_player_id)
    sums: dict = {}
    counts: dict = {}
    groups: dict = {}
    for entry in entries:
        for name, (group, value) in entry["stats"].items():
            if value is None:
                continue
            groups[name] = group
            sums[name] = sums.get(name, 0) + value
            counts[name] = counts.get(name, 0) + 1
    result = {}
    for name, total in sums.items():
        value = total / counts[name] if name in RATE_STAT_NAMES else total
        result[name] = {"group": groups[name], "value": round(value, 2) if isinstance(value, float) else value}
    return result


@st.cache_data(ttl=3600)
def _season_totals_all_players(league_key: str) -> pd.DataFrame:
    """1 rij per FotMob-speler met zijn seizoenstotalen voor de
    RADAR_STAT_NAMES - gebruikt om percentielen te berekenen t.o.v. de rest
    van de competitie."""
    log = _player_match_log(league_key)
    rows = []
    for pid, entries in log.items():
        totals = player_season_totals(league_key, pid)
        row = {"fotmob_id": pid, "team_id": entries[0]["team_id"], "matches": len(entries)}
        for stat_name in RADAR_STAT_NAMES:
            row[stat_name] = totals.get(stat_name, {}).get("value", 0) or 0
        rows.append(row)
    return pd.DataFrame(rows)


def player_percentiles(league_key: str, fotmob_player_id: int, min_matches: int = 3) -> dict:
    """Percentiel (0-100) van deze speler t.o.v. andere spelers in dezelfde
    competitie met minstens min_matches wedstrijden, voor elke
    RADAR_STAT_NAMES-statistiek. Geen aparte positiegroep (FotMob's eigen
    positiecode is niet 1-op-1 te herleiden uit deze dump) - een speler met
    weinig wedstrijden wordt uit de vergelijkingsgroep gehaald om te
    vermijden dat 1 goede invalbeurt een vertekend hoog percentiel geeft."""
    all_totals = _season_totals_all_players(league_key)
    peers = all_totals[all_totals["matches"] >= min_matches]
    if peers.empty or fotmob_player_id not in all_totals["fotmob_id"].values:
        return {}
    player_row = all_totals[all_totals["fotmob_id"] == fotmob_player_id].iloc[0]
    percentiles = {}
    for stat_name in RADAR_STAT_NAMES:
        if stat_name not in peers.columns or len(peers) < 2:
            continue
        values = peers[stat_name]
        rank = (values <= player_row[stat_name]).sum()
        percentiles[stat_name] = round(rank / len(values) * 100)
    return percentiles


def player_season_shots(league_key: str, fotmob_player_id: int) -> pd.DataFrame:
    """Alle schoten van deze speler over elke lokaal beschikbare wedstrijd
    heen - voor een seizoens-schotenkaart i.p.v. per-wedstrijd."""
    frames = []
    for match_id in available_match_ids(league_key):
        match = load_match(league_key, match_id)
        shots = match_shots(match)
        if shots.empty or "playerId" not in shots.columns:
            continue
        mine = shots[shots["playerId"] == fotmob_player_id].copy()
        if not mine.empty:
            mine["match_id"] = match_id
            frames.append(mine)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


@st.cache_data(ttl=3600)
def season_stat_max(league_key: str) -> dict:
    """stat_naam -> hoogste seizoenstotaal over alle spelers - gebruikt om
    de staafjes in de seizoensstatistieken-tabel relatief te schalen (zelfde
    soort schaal als FotMob's eigen tabel, al is hun exacte schaalkeuze niet
    gekend - dit is de duidelijkste, uitlegbare benadering)."""
    maxes: dict = {}
    for pid in _player_match_log(league_key):
        for name, info in player_season_totals(league_key, pid).items():
            value = info["value"]
            if name not in RATE_STAT_NAMES and isinstance(value, (int, float)):
                maxes[name] = max(maxes.get(name, 0), value)
    return maxes


@st.cache_data(ttl=3600)
def season_stat_max_per90(league_key: str) -> dict:
    """Zelfde als season_stat_max(), maar herleid naar per 90 minuten -
    anders zou de Per 90-weergave de staafjes vergelijken met een
    seizoenstotaal-schaal, wat ze allemaal bijna leeg zou laten lijken."""
    maxes: dict = {}
    for pid in _player_match_log(league_key):
        totals = player_season_totals(league_key, pid)
        mins = totals.get("Minutes played", {}).get("value", 0) or 0
        nineties = mins / 90 if mins else 0
        if not nineties:
            continue
        for name, info in totals.items():
            value = info["value"]
            if name in RATE_STAT_NAMES or name == "Minutes played" or not isinstance(value, (int, float)):
                continue
            maxes[name] = max(maxes.get(name, 0), value / nineties)
    return maxes


def season_stat_bar_html(label: str, value, max_value, color: str = "#22C55E") -> str:
    """1-zijdige staaf (seizoensstatistieken-tabel) - breedte relatief t.o.v.
    het hoogste seizoenstotaal in de competitie voor diezelfde statistiek."""
    pct = min(100, (value / max_value * 100)) if max_value else 0
    return (
        '<div class="fm-season-stat-row">'
        f'<div class="fm-season-stat-label">{label}</div>'
        f'<div class="fm-season-stat-val">{value}</div>'
        '<div class="fm-season-stat-bar">'
        f'<div class="fm-season-stat-fill" style="width:{pct:.1f}%;background:{color};"></div>'
        "</div></div>"
    )


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
