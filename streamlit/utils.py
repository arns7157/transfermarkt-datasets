import ast
import base64
import json
import re
from pathlib import Path

import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "csv"
COMPETITIONS_DIR = Path(__file__).resolve().parent.parent / "data" / "competitions"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"

POSITION_COLORS = {
    "Goalkeeper": "#F59E0B",
    "Defender": "#3B82F6",
    "Midfield": "#22C55E",
    "Attack": "#EF4444",
}

PAGE_ICONS = {
    "Spelers zoeken": "🔍",
    "Potentie": "🌱",
    "Spelerprofiel": "📊",
    "Vergelijken": "⚖️",
    "Signalen": "🚨",
    "Jupiler Pro League": "⚽",
}


def _read_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / f"{name}.csv.gz", compression="gzip", low_memory=False)


def _extract_club_name(value):
    """transfers.csv's from/to club columns sometimes hold a stringified
    API object instead of a plain name - pull clubName out of it."""
    if not isinstance(value, str) or not value.startswith("{"):
        return value
    try:
        parsed = ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return value
    return parsed.get("clubName", value) if isinstance(parsed, dict) else value


@st.cache_data(ttl=3600)
def _allowed_competition_ids() -> set:
    """Competition codes we've actually (re-)scraped under the current
    batch system (core + big5 + eastern_europe + world_other). Other
    leagues (world_americas, continental_cups, national_teams, ...)
    still show old pre-project data that hasn't been refreshed yet -
    hidden from the app until their batch has run successfully, then
    added back."""
    ids = set()
    for fname in ("core.json", "big5.json", "eastern_europe.json", "world_other.json"):
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
    return ids


@st.cache_data(ttl=3600)
def load_clubs() -> pd.DataFrame:
    df = _read_csv("clubs")
    return df[df["domestic_competition_id"].isin(_allowed_competition_ids())]


@st.cache_data(ttl=3600)
def load_competitions() -> pd.DataFrame:
    return _read_csv("competitions")


def competition_logo_url(competition_id) -> str:
    """Competition logo, built directly from Transfermarkt's own CDN path
    convention - confirmed live for every tracked competition_id,
    including ones with no clubs of their own (Champions League, Europa
    League, Conference League, World Cup, Euro, Nations League, Copa
    America, AFCON, ...) where clubs.csv has nothing to derive it from.
    A made-up/nonexistent code 404s cleanly rather than returning a
    generic placeholder, so this is safe to apply universally."""
    if competition_id is None or (isinstance(competition_id, float) and pd.isna(competition_id)):
        return ""
    cid = str(competition_id).strip()
    if not cid or cid.lower() == "nan":
        return ""
    return f"https://img.a.transfermarkt.technology/logo/homepageWappen150x150/{cid.lower()}.png"


def _competition_image_fallbacks() -> tuple[dict, dict]:
    """competition_id -> logo_url / flag_url, from the bundled reference
    table. flag_url has no CDN-path equivalent (no single "country" for a
    competition like the World Cup), so this stays the fallback for flags;
    logo_url is kept only for callers that still want the dict form."""
    competitions = load_competitions()
    logo_map = competitions.dropna(subset=["logo_url"]).set_index("competition_id")["logo_url"].to_dict()
    flag_map = competitions.dropna(subset=["flag_url"]).set_index("competition_id")["flag_url"].to_dict()
    return logo_map, flag_map


def _enrich_with_club_images(players: pd.DataFrame, clubs: pd.DataFrame) -> pd.DataFrame:
    """Guarantee best-effort club_crest_url / competition_logo_url /
    country_flag_url / citizenship_flag_url columns for every player.
    Prefers what the player's own scrape found; falls back to clubs.csv
    (a different batch run may have (re-)scraped that same club more
    recently), then to the bundled competitions reference table."""
    players = players.copy()
    clubs_by_id = clubs.copy()
    clubs_by_id["club_id"] = pd.to_numeric(clubs_by_id["club_id"], errors="coerce").astype("Int64")
    cur_id = pd.to_numeric(players.get("current_club_id"), errors="coerce").astype("Int64")

    def club_fallback(col: str) -> pd.Series:
        return clubs_by_id.dropna(subset=[col]).drop_duplicates("club_id").set_index("club_id")[col]

    _, comp_flag_fallback = _competition_image_fallbacks()
    comp_id = players.get("current_club_domestic_competition_id")

    players["club_crest_url"] = players.get("current_club_crest_url").fillna(
        cur_id.map(club_fallback("crest_url"))
    )
    players["competition_logo_url"] = (
        players.get("current_club_competition_logo_url")
        .fillna(cur_id.map(club_fallback("competition_logo_url")))
        .fillna(comp_id.map(competition_logo_url))
    )
    players["country_flag_url"] = (
        players.get("current_club_country_flag_url")
        .fillna(cur_id.map(club_fallback("country_flag_url")))
        .fillna(comp_id.map(comp_flag_fallback))
    )
    players["citizenship_flag_url"] = players.get("country_of_citizenship_flag_url")
    # ImageColumn renders a missing/NaN cell as the literal text "None"
    # instead of a blank cell - empty string displays cleanly instead.
    for col in ("club_crest_url", "competition_logo_url", "country_flag_url", "citizenship_flag_url"):
        players[col] = players[col].fillna("")
    return players


@st.cache_data(ttl=3600)
def club_crest_by_name() -> dict:
    """Best-effort club name -> crest_url, for places that only have a club
    *name* to work with (e.g. transfers.csv's from/to club columns)."""
    clubs = load_clubs()
    return clubs.dropna(subset=["crest_url"]).drop_duplicates("name").set_index("name")["crest_url"].to_dict()


_CLUB_NAME_STOPWORDS = {
    "fc", "cf", "sc", "ac", "afc", "cd", "ud", "sv", "sk", "bk", "if", "hk", "ec", "ca", "cp",
    "real", "club", "united", "city", "town", "athletic", "atletico", "deportivo", "sporting",
    "olympique", "dynamo", "dinamo", "inter", "international", "national", "nacional",
    "de", "do", "la", "le", "1", "1.",
}


def _name_tokens(name: str) -> set:
    words = re.findall(r"[a-z0-9]+", str(name).lower())
    return {w for w in words if len(w) >= 4 and w not in _CLUB_NAME_STOPWORDS}


@st.cache_data(ttl=3600)
def _stale_transferred_away_ids() -> set:
    """player_id's die volgens hun eigen transferhistorie naar een club
    buiten alle gevolgde competities zijn vertrokken.

    players.csv' current_club-veld wordt enkel ververst zolang een speler
    in het kader van een gevolgde club opduikt - vertrekt hij daarbuiten
    (bv. naar Brazilië, dat nog niet gescraped is), dan blijft dat veld
    voor altijd op zijn laatste gekende (wél gevolgde) club staan, terwijl
    transfers.csv (een losse, speler-specifieke API-call, niet afhankelijk
    van kaderlijsten) wél gewoon de echte, nieuwe club toont. Die twee
    tonen dan tegenstrijdige info (club zegt A, transferhistorie zegt B) -
    zo'n speler eruit filteren is minder verwarrend dan hem met half-juiste
    data te tonen.

    to_club_id/to_club_crest_url zijn voor de meeste transfers leeg (enkel
    recent ingevulde rijen hebben ze), en to_club_name is vaak een
    afkorting ("Man City", "Dortmund") die nooit letterlijk matcht met
    clubs.csv' volledige naam ("Manchester City", "Borussia Dortmund") -
    vandaar matching op gedeelde naam-tokens i.p.v. exacte match/ID, met
    een stopwoordenlijst voor generieke clubwoorden. Bij twijfel (geen
    bruikbare tokens, bv. "Man City" zonder "City" als stopwoord) NIET
    uitfilteren - een speler onterecht tonen is minder erg dan hem
    onterecht laten verdwijnen."""
    transfers = load_transfers()
    dated = transfers.dropna(subset=["transfer_date"])
    now = pd.Timestamp.now()
    # Dezelfde foutieve toekomst-datums als bij de "net getransfereerd"-badge.
    dated = dated[dated["transfer_date"] <= now]
    if dated.empty:
        return set()
    latest = dated.sort_values("transfer_date").drop_duplicates("player_id", keep="last")

    tracked_tokens = set()
    for name in load_clubs()["name"]:
        tracked_tokens |= _name_tokens(name)

    def moved_to_untracked_club(to_name) -> bool:
        tokens = _name_tokens(to_name)
        if not tokens:
            return False
        return tokens.isdisjoint(tracked_tokens)

    moved_away = latest[latest["to_club_name"].map(moved_to_untracked_club)]
    return set(moved_away["player_id"])


@st.cache_data(ttl=3600)
def load_players() -> pd.DataFrame:
    df = _read_csv("players")
    df = df[df["current_club_domestic_competition_id"].isin(_allowed_competition_ids())]
    df = df[~df["player_id"].isin(_stale_transferred_away_ids())]
    df["market_value_in_eur"] = pd.to_numeric(df["market_value_in_eur"], errors="coerce")
    df["highest_market_value_in_eur"] = pd.to_numeric(df["highest_market_value_in_eur"], errors="coerce")
    df["date_of_birth"] = pd.to_datetime(df["date_of_birth"], format="%d/%m/%Y", errors="coerce")
    df["contract_expiration_date"] = pd.to_datetime(df["contract_expiration_date"], format="%d/%m/%Y", errors="coerce")
    df["age"] = pd.to_numeric(df["age"], errors="coerce").round().astype("Int64")
    df["market_value_m"] = df["market_value_in_eur"] / 1_000_000
    return _enrich_with_club_images(df, load_clubs())


@st.cache_data(ttl=3600)
def load_transfers() -> pd.DataFrame:
    df = _read_csv("transfers")
    df["from_club_name"] = df["from_club_name"].map(_extract_club_name)
    df["to_club_name"] = df["to_club_name"].map(_extract_club_name)
    df["transfer_date"] = pd.to_datetime(df["transfer_date"], format="%d/%m/%Y", errors="coerce")
    # Older rows predate the from/to_club_crest_url columns - the merge
    # script backfills them on each row's next transfer-API refresh, but
    # until then the column may not exist on disk at all yet.
    for col in ("from_club_crest_url", "to_club_crest_url", "to_country_flag_url"):
        if col not in df.columns:
            df[col] = ""
        else:
            df[col] = df[col].fillna("")
    return df


@st.cache_data(ttl=3600)
def load_valuations() -> pd.DataFrame:
    df = _read_csv("player_valuations")
    df["market_value_in_eur"] = pd.to_numeric(df["market_value_in_eur"], errors="coerce")
    df["date"] = pd.to_datetime(df["date"], format="%d/%m/%Y", errors="coerce")
    return df


@st.cache_data(ttl=3600)
def load_appearances() -> pd.DataFrame:
    df = _read_csv("appearances")
    df["date"] = pd.to_datetime(df["date"], format="%d/%m/%y", errors="coerce")
    for col in ("yellow_cards", "red_cards", "goals", "assists", "minutes_played"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


_INJURY_COLUMNS = ["injury_id", "player_id", "season", "injury", "from_date", "until_date", "days", "games_missed"]


@st.cache_data(ttl=3600)
def load_injuries() -> pd.DataFrame:
    """Blessurehistoriek per speler. injuries.csv.gz bestaat pas na de
    eerste scrape-run die de nieuwe 'injuries'-stap meeneemt - geeft tot
    dan een lege (maar correct gekolomde) dataframe terug i.p.v. te
    crashen op een ontbrekend bestand."""
    fpath = DATA_DIR / "injuries.csv.gz"
    if not fpath.exists():
        return pd.DataFrame(columns=_INJURY_COLUMNS)
    df = _read_csv("injuries")
    df["from_date"] = pd.to_datetime(df["from_date"], format="%d/%m/%Y", errors="coerce")
    df["until_date"] = pd.to_datetime(df["until_date"], format="%d/%m/%Y", errors="coerce")
    df["days"] = pd.to_numeric(df["days"], errors="coerce")
    df["games_missed"] = pd.to_numeric(df["games_missed"], errors="coerce").fillna(0).astype(int)
    return df


def format_money(value) -> str:
    if pd.isna(value):
        return "–"
    value = float(value)
    sign = "-" if value < 0 else ""
    value = abs(value)
    if value >= 1_000_000:
        return f"{sign}€{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{sign}€{value / 1_000:.0f}K"
    return f"{sign}€{value:.0f}"


def player_label(row) -> str:
    club = row.get("current_club_name") or "onbekende club"
    return f"{row['name']} ({club})"


TIER_LABELS_NL = {
    "First Tier": "1e",
    "Second Tier": "2e",
    "Third Tier": "3e",
    "Fourth Tier": "4e",
    "Fifth Tier": "5e",
    "Sixth Tier": "6e",
    "Play-Offs": "Play-offs",
    "Reserve league": "Reserveliga",
    "Regional Championship": "Regionaal",
}


def truncate_text(text, max_len: int) -> str:
    """Hard karaktercap met ellipsis - st.dataframe's column_config width is
    maar een richtwaarde, de kolom groeit toch mee met de langste
    celwaarde, dus dit is de enige manier om een kolom echt smal te
    houden."""
    if not isinstance(text, str):
        return text
    return text if len(text) <= max_len else text[: max_len - 1].rstrip() + "…"


def attach_competition_info(players: pd.DataFrame, competitions: pd.DataFrame) -> pd.DataFrame:
    """Voegt competition_name/country/niveau toe aan een players-dataframe,
    afgeleid van current_club_domestic_competition_id. competition_display
    combineert naam+niveau in één tekst (bv. "LaLiga (1e)") - scheelt een
    hele kolom in de tabellen, zonder dat de losse competition_name/niveau-
    kolommen verdwijnen (die blijven nodig voor filters). Een harde lengte-
    cap voorkomt dat één lange competitienaam de hele tabelbreedte opeist -
    st.dataframe's kolombreedte is maar een richtwaarde, de kolom groeit
    toch mee met de langste celwaarde."""
    comp = competitions.set_index("competition_id")
    cid = players["current_club_domestic_competition_id"]
    players = players.copy()
    players["competition_name"] = cid.map(comp["name"])
    players["country"] = cid.map(comp["country"])
    players["niveau"] = cid.map(comp["tier"]).map(lambda t: TIER_LABELS_NL.get(t, t))
    niveau_suffix = players["niveau"].fillna("").map(lambda v: f" ({v})" if v else "")
    display = players["competition_name"].fillna("") + niveau_suffix
    players["competition_display"] = display.map(lambda t: truncate_text(t, 24))
    return players


def render_player_table(
    df: pd.DataFrame,
    column_map: dict,
    key: str,
    extra_column_config: dict | None = None,
    height: int | None = None,
) -> None:
    """Compacte, klikbare spelerstabel. df moet een 'player_id'-kolom hebben
    (of player_id als index); column_map is {bronkolom: label} in
    weergavevolgorde. Bij het selecteren van een rij spring je naar het
    spelerprofiel - zelfde klikgedrag op elke pagina die deze helper
    gebruikt, dus wordt dat maar op één plek onderhouden."""
    if "player_id" in df.columns:
        player_ids = df["player_id"].reset_index(drop=True)
    else:
        player_ids = pd.Series(df.index, name="player_id").reset_index(drop=True)
    display = df[list(column_map.keys())].reset_index(drop=True).rename(columns=column_map)

    column_config = {
        label: st.column_config.ImageColumn(width="small")
        for label in display.columns
        if label in ("Logo", "Nat.", "Vlag", "Comp.")
    }
    if extra_column_config:
        column_config.update(extra_column_config)

    event = st.dataframe(
        display,
        width="stretch",
        hide_index=True,
        height=height or 480,
        column_config=column_config,
        on_select="rerun",
        selection_mode="single-row",
        key=key,
    )
    rows = event.selection.get("rows", []) if event and event.selection else []
    if rows:
        st.session_state["jump_to_player_id"] = player_ids.iloc[rows[0]]
        st.switch_page("pages/3_Spelerprofiel.py")


def image_multiselect(label: str, options: list, image_lookups, key_prefix: str, max_shown: int = 150) -> list:
    """Dropdown-achtige multiselect die één of meer échte logo/vlag-
    afbeeldingen naast elke optie toont. Een native <select>/st.multiselect
    kan dat niet - een <option>-element mag geen <img> bevatten, dat is een
    HTML-beperking, geen Streamlit-beperking. st.popover + losse checkboxes
    omzeilt dat: elke rij is een afbeelding(en) + checkbox, en het paneel
    opent/sluit als een dropdown.

    image_lookups is een dict (één afbeelding per rij) of een lijst van
    dicts (meerdere afbeeldingen per rij, in volgorde - bv. clublogo +
    competitievlag + competitielogo)."""
    if isinstance(image_lookups, dict):
        image_lookups = [image_lookups]

    state_key = f"{key_prefix}__selected"
    selected_before = st.session_state.get(state_key, [])

    # Geen live tellertje in de knop-tekst: st.popover open/sluiten en de
    # knop-tekst zelf triggeren geen script-rerun, dus een "(N)"-count hier
    # zou altijd één klik achterlopen. De checkboxes in het paneel zelf
    # tonen de actuele selectie wel meteen correct.
    with st.popover(label, width="stretch"):
        search = st.text_input(
            "Zoeken", key=f"{key_prefix}__search", label_visibility="collapsed", placeholder=f"Zoek {label.lower()}..."
        )
        matches = [o for o in options if not search or search.lower() in o.lower()]
        shown = matches[:max_shown]
        if len(matches) > max_shown:
            st.caption(f"{max_shown} van {len(matches)} getoond - verfijn je zoekopdracht voor meer.")
        for opt in shown:
            col_widths = [0.5] * len(image_lookups) + [5]
            cols = st.columns(col_widths, vertical_alignment="center", gap="small")
            for lookup, col in zip(image_lookups, cols[:-1]):
                img = lookup.get(opt)
                if img:
                    col.image(img, width=22)
            cols[-1].checkbox(opt, key=f"{key_prefix}__cb__{opt}", value=opt in selected_before)

    # Items buiten de huidige zoekfilter/weergavelimiet blijven geselecteerd
    # (hun checkbox is dit keer niet getekend, dus niet overschrijven).
    selected = [opt for opt in shown if st.session_state.get(f"{key_prefix}__cb__{opt}")]
    selected += [opt for opt in selected_before if opt not in shown]
    st.session_state[state_key] = selected
    return selected


def position_badge(position: str) -> str:
    color = POSITION_COLORS.get(position, "#6B7280")
    label = position or "–"
    return (
        f'<span style="background:{color}22;color:{color};border:1px solid {color}55;'
        f'padding:1px 9px;border-radius:999px;font-size:0.78rem;font-weight:600;'
        f'white-space:nowrap;">{label}</span>'
    )


def safe_val(value, default="–"):
    """row.get(key, default) only falls back when the KEY is missing - a
    present-but-NaN/pd.NA cell (common for nullable Int64 columns like age,
    or float columns like height_in_cm) sails straight through and renders
    as the literal text "nan"/"<NA>" - worse, inside unsafe_allow_html
    markdown, "<NA>" is swallowed as an (unknown) HTML tag and the value
    just vanishes. Use this instead of a bare .get(key, default) for any
    value that gets rendered to the page."""
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    return value


@st.cache_data(ttl=None)
def _asset_data_uri(filename: str) -> str:
    """Embed a local streamlit/assets/ image as a base64 data: URI - needed
    because st.column_config.ImageColumn and st.markdown's <img src=...> both
    need a browser-resolvable URL, and a plain local file path doesn't work
    (the browser, not this process, loads it) and this app doesn't have
    static file serving enabled."""
    path = ASSETS_DIR / filename
    mime = "image/webp" if path.suffix == ".webp" else "image/png"
    data = path.read_bytes()
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def injury_icon_url() -> str:
    return _asset_data_uri("injury_icon.webp")


def transfer_icon_url() -> str:
    return _asset_data_uri("transfer_icon.png")


def injury_icon_small_url() -> str:
    """Voor de overzichtstabel: zelfde icoon, maar met ingebouwde
    transparante marge zodat het kleiner oogt binnen de kolom - de
    kolombreedte van st.column_config.ImageColumn heeft een ondergrens en
    verkleint een volledig uitgevulde afbeelding zelf niet genoeg."""
    return _asset_data_uri("injury_icon_small.webp")


def transfer_icon_small_url() -> str:
    return _asset_data_uri("transfer_icon_small.png")


def inline_img(url, height: int = 18) -> str:
    """Small inline <img> tag for use inside st.markdown(unsafe_allow_html=True),
    e.g. next to a club/competition/country name. Returns '' for a missing URL
    so callers can splice it in unconditionally."""
    if not isinstance(url, str) or not url:
        return ""
    return f'<img src="{url}" height="{height}" style="vertical-align:middle;border-radius:3px;margin-right:4px;">'


def recent_transfer(player_transfers: pd.DataFrame, within_days: int = 90):
    """Meest recente transfer van deze speler, als die binnen within_days
    valt - anders None. player_transfers moet al tot één speler herleid
    zijn en een transfer_date-kolom hebben (van/naar hoeft niet gesorteerd
    te zijn, dat doet deze functie zelf)."""
    if player_transfers.empty:
        return None
    latest = player_transfers.sort_values("transfer_date", ascending=False).iloc[0]
    date = latest.get("transfer_date")
    if pd.isna(date):
        return None
    days_ago = (pd.Timestamp.now() - date).days
    # transfers.csv bevat af en toe een foutieve datum ver in de toekomst
    # (jaar 2028/3026, vermoedelijk een contract-einddatum die per
    # vergissing als transfer_date terechtkwam) - zo'n datum geeft een
    # NEGATIEF aantal dagen geleden, wat anders als "recent" doorglipt.
    if days_ago < 0 or days_ago > within_days:
        return None
    return latest


def transfer_badge_html(player_transfers: pd.DataFrame, within_days: int = 90) -> str:
    """Badge met waarschuwingsicoon - toont bij hover de 2 clubs (met logo)
    en de datum van de transfer. Lege string als er geen recente transfer
    is, zodat callers dit onvoorwaardelijk in st.markdown kunnen plakken."""
    latest = recent_transfer(player_transfers, within_days)
    if latest is None:
        return ""
    date = latest["transfer_date"]
    from_crest = inline_img(latest.get("from_club_crest_url"), height=20)
    to_crest = inline_img(latest.get("to_club_crest_url"), height=20)
    from_name = safe_val(latest.get("from_club_name"), "onbekend")
    to_name = safe_val(latest.get("to_club_name"), "onbekend")
    icon = inline_img(transfer_icon_url(), height=16)
    return (
        f'<span class="transfer-badge">{icon}Net getransfereerd'
        '<span class="transfer-tooltip">'
        f"{from_crest}{from_name} &nbsp;→&nbsp; {to_crest}{to_name}<br>"
        f"{date:%d/%m/%Y}"
        "</span></span>"
    )


def current_injury(player_injuries: pd.DataFrame, max_staleness_days: int = 120):
    """Lopende blessure van deze speler, als die er is - anders None.
    'Lopend' = until_date ontbreekt of ligt nog in de toekomst, ÉN from_date
    is niet te lang geleden - anders is een ontbrekende until_date
    waarschijnlijk gewoon onvolledige oude data, geen speler die al
    maanden/jaren geblesseerd is. player_injuries moet al tot één speler
    herleid zijn."""
    if player_injuries.empty:
        return None
    today = pd.Timestamp.now().normalize()
    dated = player_injuries.dropna(subset=["from_date"])
    if dated.empty:
        return None
    ongoing = dated[dated["until_date"].isna() | (dated["until_date"] >= today)]
    if ongoing.empty:
        return None
    latest = ongoing.sort_values("from_date", ascending=False).iloc[0]
    if latest["from_date"] < today - pd.Timedelta(days=max_staleness_days):
        return None
    return latest


def currently_injured_ids(injuries: pd.DataFrame, max_staleness_days: int = 120) -> set:
    """player_id's met een lopende blessure, volgens hetzelfde criterium als
    current_injury() - hier vectorized voor de volledige tabel i.p.v. per
    speler, voor gebruik in een overzichtstabel."""
    dated = injuries.dropna(subset=["from_date"])
    if dated.empty:
        return set()
    today = pd.Timestamp.now().normalize()
    ongoing = dated[dated["until_date"].isna() | (dated["until_date"] >= today)]
    ongoing = ongoing[ongoing["from_date"] >= today - pd.Timedelta(days=max_staleness_days)]
    return set(ongoing["player_id"])


def injury_badge_html(player_injuries: pd.DataFrame) -> str:
    """Badge met blessure-icoon - toont bij hover de blessure-naam en sinds
    wanneer. Lege string als er geen lopende blessure is, zodat callers dit
    onvoorwaardelijk in st.markdown kunnen plakken."""
    injury = current_injury(player_injuries)
    if injury is None:
        return ""
    name = safe_val(injury.get("injury"), "onbekende blessure")
    until = injury.get("until_date")
    until_str = f"verwacht terug op {until:%d/%m/%Y}" if pd.notna(until) else "nog geen terugkeerdatum"
    icon = inline_img(injury_icon_url(), height=16)
    return (
        f'<span class="injury-badge">{icon}Geblesseerd'
        '<span class="injury-tooltip">'
        f"{name}<br>sinds {injury['from_date']:%d/%m/%Y} ({until_str})"
        "</span></span>"
    )


def style_chart(fig, **extra_layout):
    """Apply a complete, self-consistent light style to a Plotly figure.

    Setting only plot_bgcolor/paper_bgcolor/font_color leaves sub-elements
    Plotly doesn't inherit that from (hover tooltips, legend swatches) on
    their dark-theme defaults - white text on a near-white background.
    template='plotly_white' covers those too; extra_layout can still
    override/add anything (e.g. a custom legend position).
    """
    fig.update_layout(
        template="plotly_white",
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        font_color="#31333F",
        hoverlabel=dict(bgcolor="#F0F2F6", font_color="#31333F"),
        **extra_layout,
    )
    return fig


def inject_theme() -> None:
    st.markdown(
        """
        <style>
        /* Verberg Deploy-knop en hamburger-menu, maar NIET de hele header: die
           bevat ook de "sidebar weer openen"-knop die verschijnt zodra de
           sidebar is ingeklapt. Hem verbergen laat je zonder navigatie en
           zonder manier om de sidebar terug te krijgen. */
        footer {display: none;}
        header[data-testid="stHeader"] {background: transparent;}
        div[data-testid="stAppDeployButton"],
        button[data-testid="stMainMenuButton"] {display: none;}
        /* Breder dan Streamlit's standaard 730px/1200px: de spelerstabellen
           hebben veel kolommen en moeten zoveel mogelijk passen zonder dat
           je horizontaal moet scrollen. */
        .block-container {padding-top: 2rem; max-width: 1800px;}
        div[data-testid="stMetric"] {
            background: #F0F2F6;
            border: 1px solid #D8DCE3;
            border-radius: 10px;
            padding: 14px 16px;
        }
        div[data-testid="stMetricValue"] {font-size: 1.6rem;}
        section[data-testid="stSidebar"] {border-right: 1px solid #E5E7EB;}
        .app-header {
            display: flex;
            align-items: baseline;
            gap: 10px;
            margin-bottom: 0.2rem;
        }
        .app-header h1 {margin: 0; font-size: 1.9rem;}
        .app-subtitle {color: #6B7280; font-size: 0.95rem; margin-bottom: 1.4rem;}
        .pill-row {display: flex; gap: 6px; flex-wrap: wrap; margin: 4px 0 12px 0;}
        /* image_multiselect()-paneel: elke rij (logo/vlag(en) + checkbox)
           is een stHorizontalBlock binnen de popover - wat strakker tegen
           elkaar, een hover-highlight, en de fullscreen-hover-knop op de
           kleine logo's (16x16) weggewerkt, die daar niets toevoegt. */
        div[data-testid="stPopoverBody"] div[data-testid="stHorizontalBlock"] {
            padding: 3px 6px;
            border-radius: 6px;
            align-items: center;
        }
        div[data-testid="stPopoverBody"] div[data-testid="stHorizontalBlock"]:hover {
            background: #F0F2F6;
        }
        div[data-testid="stPopoverBody"] div[data-testid="stElementToolbar"] {display: none;}
        div[data-testid="stPopoverBody"] div[data-testid="stImageContainer"] img {border-radius: 3px;}
        div[data-testid="stPopoverBody"] label[data-testid="stWidgetLabel"] p {font-size: 0.92rem;}
        /* transfer_badge_html(): klein label met een pure-CSS hover-tooltip
           (geen widget nodig, dus werkt ook binnen st.markdown) - de tooltip
           zelf staat standaard verborgen en verschijnt enkel on :hover. */
        .transfer-badge {
            position: relative;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: #FEF3C7;
            color: #92400E;
            border: 1px solid #FDE68A;
            border-radius: 999px;
            padding: 4px 12px;
            font-size: 0.85rem;
            font-weight: 600;
            cursor: default;
            margin-bottom: 12px;
        }
        .transfer-badge .transfer-tooltip {
            display: none;
            position: absolute;
            top: 130%;
            left: 0;
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 8px;
            padding: 10px 14px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.14);
            white-space: nowrap;
            font-weight: 400;
            font-size: 0.85rem;
            color: #31333F;
            z-index: 50;
        }
        .transfer-badge:hover .transfer-tooltip {display: block;}
        /* injury_badge_html(): zelfde pure-CSS hover-tooltip-patroon als
           .transfer-badge, maar rood om het duidelijk te onderscheiden van
           een transfer-waarschuwing. */
        .injury-badge {
            position: relative;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: #FEE2E2;
            color: #991B1B;
            border: 1px solid #FCA5A5;
            border-radius: 999px;
            padding: 4px 12px;
            font-size: 0.85rem;
            font-weight: 600;
            cursor: default;
            margin-bottom: 12px;
            margin-right: 8px;
        }
        .injury-badge .injury-tooltip {
            display: none;
            position: absolute;
            top: 130%;
            left: 0;
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 8px;
            padding: 10px 14px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.14);
            white-space: nowrap;
            font-weight: 400;
            font-size: 0.85rem;
            color: #31333F;
            z-index: 50;
        }
        .injury-badge:hover .injury-tooltip {display: block;}
        /* FotMob-wedstrijdstatistieken: 2-zijdige vergelijkingsbalk (thuis
           vs uit), schaal + kleur bepaald per rij door de pagina zelf. */
        .fm-stat-row {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-top: 10px;
        }
        .fm-stat-val {
            width: 48px;
            text-align: center;
            font-weight: 600;
            font-size: 0.85rem;
            flex-shrink: 0;
        }
        .fm-stat-bar {
            flex: 1;
            display: flex;
            height: 8px;
            border-radius: 4px;
            overflow: hidden;
            background: #E5E7EB;
        }
        .fm-stat-bar-home, .fm-stat-bar-away {height: 100%;}
        .fm-stat-title {
            text-align: center;
            color: #6B7280;
            font-size: 0.78rem;
            margin: 2px 0 0 0;
        }
        /* season_stat_bar_html() - 1-zijdige staaf in de FotMob-
           seizoensstatistieken-tabel op het spelerprofiel. */
        .fm-season-stat-row {
            display: flex;
            align-items: center;
            gap: 10px;
            margin: 5px 0;
        }
        .fm-season-stat-label {
            width: 190px;
            flex-shrink: 0;
            font-size: 0.85rem;
            color: #31333F;
        }
        .fm-season-stat-val {
            width: 42px;
            flex-shrink: 0;
            text-align: right;
            font-weight: 600;
            font-size: 0.85rem;
        }
        .fm-season-stat-bar {
            flex: 1;
            height: 7px;
            border-radius: 4px;
            background: #E5E7EB;
            overflow: hidden;
        }
        .fm-season-stat-fill {height: 100%;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(title: str, subtitle: str = "") -> None:
    icon = PAGE_ICONS.get(title, "")
    st.markdown(
        f'<div class="app-header"><span style="font-size:1.7rem">{icon}</span>'
        f"<h1>{title}</h1></div>",
        unsafe_allow_html=True,
    )
    if subtitle:
        st.markdown(f'<div class="app-subtitle">{subtitle}</div>', unsafe_allow_html=True)


def current_season_appearances(appearances: pd.DataFrame) -> pd.DataFrame:
    """appearances.csv holds every season back to ~2014 - most 'this season'
    views should only look at matches from the current season onward.

    Seizoensgrens bewust op de meest recente datum van het DOORGEGEVEN
    subset, niet op de volledige dataset: voor een pas getransfereerde
    speler (bv. net overgekomen uit Brazilië, nog geen wedstrijd bij zijn
    nieuwe club) toont dit dan nog zijn laatst gespeelde periode i.p.v.
    een kaal "0 wedstrijden" - minder letterlijk, maar minder verwarrend
    dan een actieve speler laten lijken alsof hij niets gedaan heeft."""
    dated = appearances.dropna(subset=["date"])
    if dated.empty:
        return dated
    season_start = season_start_for(dated["date"].max())
    return dated[dated["date"] >= season_start]


def season_start_for(date: pd.Timestamp) -> pd.Timestamp:
    """European football seasons roll over in July."""
    year = date.year if date.month >= 7 else date.year - 1
    return pd.Timestamp(year=year, month=7, day=1)


# U21/U23/B/II-suffixed clubs are reserve squads, not a first team - catches
# most of them by name (Ajax Amsterdam U21, VfB Stuttgart II, Villarreal CF B).
# A handful use a different naming convention with no common pattern, so
# those are listed explicitly.
_RESERVE_TEAM_SUFFIX_RE = re.compile(r"(\bU1[6-9]\b|\bU2[0-3]\b|\bII$| B$)", re.IGNORECASE)
_RESERVE_TEAM_EXACT_NAMES = {
    "Real Madrid Castilla",
    "Juventus Next Gen",
    "CA Osasuna Promesas",
    "Sevilla Atlético",
    "Atlético Madrileño",
    "Betis Deportivo Balompié",
    "RC Deportivo Fabril",
}


def _is_reserve_team(club_name) -> bool:
    if not isinstance(club_name, str):
        return False
    return bool(_RESERVE_TEAM_SUFFIX_RE.search(club_name)) or club_name in _RESERVE_TEAM_EXACT_NAMES


def compute_breakout_candidates(
    players: pd.DataFrame,
    appearances: pd.DataFrame,
    recent_days: int = 30,
    max_age: int = 23,
    min_recent_matches: int = 2,
) -> pd.DataFrame:
    """Flag players whose minutes or goal contribution are trending up this
    season: recently playing more, or recently starting to score/assist,
    compared to the earlier part of the same season."""
    dated = appearances.dropna(subset=["date"])
    if dated.empty:
        return players.iloc[0:0].copy()

    latest_date = dated["date"].max()
    season_start = season_start_for(latest_date)
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

    merged["minutes_trend"] = merged["recent_avg_minutes"] - merged["earlier_avg_minutes"]
    merged["scoring_trend"] = merged["recent_ga_per90"] - merged["earlier_ga_per90"]
    merged["just_broke_through"] = merged["earlier_matches"] == 0

    merged["potential_score"] = (
        merged["minutes_trend"].clip(lower=0) / 90.0
        + merged["scoring_trend"].clip(lower=0) * 2.0
        + merged["just_broke_through"].astype(float) * 1.5
    )

    result = merged.join(players.set_index("player_id"), how="inner")
    result = result[result["age"] <= max_age]
    result = result[~result["current_club_name"].map(_is_reserve_team)]
    return result.sort_values("potential_score", ascending=False)
