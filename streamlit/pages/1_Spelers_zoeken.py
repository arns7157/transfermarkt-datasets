import pandas as pd
import streamlit as st

from utils import (
    attach_competition_info,
    current_season_appearances,
    image_multiselect,
    inject_theme,
    load_appearances,
    load_competitions,
    load_players,
    load_transfers,
    render_header,
    render_player_table,
    truncate_text,
)

st.set_page_config(page_title="Spelers zoeken", page_icon="🔍", layout="wide")
inject_theme()

players = load_players()
competitions = load_competitions()
appearances = load_appearances()
transfers = load_transfers()

players = attach_competition_info(players, competitions)

# Laatste transfer per speler, enkel als waarschuwing als die recent is -
# anders lijkt een speler soms "niets gepresteerd" terwijl hij net van
# club wisselde en nog geen wedstrijd voor zijn nieuwe club speelde.
latest_transfer = transfers.sort_values("transfer_date", ascending=False).drop_duplicates("player_id")
now = pd.Timestamp.now()
recent_cutoff = now - pd.Timedelta(days=90)
# <= now uitsluiten van toekomstige datums: transfers.csv bevat af en toe
# een foutieve datum ver in de toekomst (vermoedelijk een verwisselde
# contract-einddatum), die anders ook als "recent" zou meetellen.
recent_transfer_ids = set(
    latest_transfer.loc[
        latest_transfer["transfer_date"].between(recent_cutoff, now), "player_id"
    ]
)
players["transfer_marker"] = players["player_id"].map(lambda pid: "⚠️" if pid in recent_transfer_ids else "")

n_competities = players["current_club_domestic_competition_id"].nunique()
render_header("Spelers zoeken", f"Filter het volledige spelersbestand van de {n_competities} gevolgde competities.")

season_apps = current_season_appearances(appearances)
season_stats = season_apps.groupby("player_id").agg(
    matches_this_season=("appearance_id", "count"), goals_this_season=("goals", "sum")
)
players = players.merge(season_stats, left_on="player_id", right_index=True, how="left")
players["matches_this_season"] = players["matches_this_season"].fillna(0).astype(int)
players["goals_this_season"] = players["goals_this_season"].fillna(0).astype(int)

def _image_lookup(col: str, key: str) -> dict:
    return (
        players.dropna(subset=[col])
        .loc[lambda d: d[col] != ""]
        .drop_duplicates(key)
        .set_index(key)[col]
        .to_dict()
    )


country_flag_by_name = _image_lookup("country_flag_url", "country")
comp_logo_by_name = _image_lookup("competition_logo_url", "competition_name")
comp_flag_by_name = _image_lookup("country_flag_url", "competition_name")
club_crest_by_name_local = _image_lookup("club_crest_url", "current_club_name")
club_flag_by_name = _image_lookup("country_flag_url", "current_club_name")
club_comp_logo_by_name = _image_lookup("competition_logo_url", "current_club_name")
citizenship_flag_by_name = _image_lookup("citizenship_flag_url", "country_of_citizenship")

with st.sidebar:
    st.header("Filters")

    # Land/Competitie/Club/Nationaliteit gebruiken image_multiselect() i.p.v.
    # de standaard st.multiselect: die toont de échte logo/vlag-afbeelding(en)
    # naast elke optie in het dropdown-paneel zelf (via st.popover).
    country_options = sorted(players["country"].dropna().unique())
    selected_countries = image_multiselect("Land", country_options, country_flag_by_name, "land")

    country_scoped = players[players["country"].isin(selected_countries)] if selected_countries else players

    comp_options = sorted(country_scoped["competition_name"].dropna().unique())
    selected_comps = image_multiselect(
        "Competitie", comp_options, [comp_logo_by_name, comp_flag_by_name], "competitie"
    )

    scoped = country_scoped[country_scoped["competition_name"].isin(selected_comps)] if selected_comps else country_scoped

    club_options = sorted(scoped["current_club_name"].dropna().unique())
    selected_clubs = image_multiselect(
        "Club",
        club_options,
        [club_crest_by_name_local, club_flag_by_name, club_comp_logo_by_name],
        "club",
    )

    position_options = sorted(players["position"].dropna().unique())
    selected_positions = st.multiselect("Positie", position_options)

    nationality_options = sorted(players["country_of_citizenship"].dropna().unique())
    selected_nationalities = image_multiselect(
        "Nationaliteit", nationality_options, citizenship_flag_by_name, "nationaliteit"
    )

    foot_options = sorted(players["foot"].dropna().unique())
    selected_feet = st.multiselect("Voet", foot_options)

    data_min_age = int(players["age"].min(skipna=True) or 15)
    data_max_age = int(players["age"].max(skipna=True) or 45)
    age_range = st.slider("Leeftijd", data_min_age, data_max_age, (data_min_age, data_max_age))

    data_max_value = float(players["market_value_m"].max(skipna=True) or 0)
    value_range = st.slider("Marktwaarde (M€)", 0.0, data_max_value, (0.0, data_max_value))

    only_playing = st.checkbox("Enkel spelers met minuten dit seizoen")
    name_search = st.text_input("Naam bevat")

    if st.button("Reset filters", width="stretch"):
        st.rerun()

filtered = players.copy()
if selected_countries:
    filtered = filtered[filtered["country"].isin(selected_countries)]
if selected_comps:
    filtered = filtered[filtered["competition_name"].isin(selected_comps)]
if selected_clubs:
    filtered = filtered[filtered["current_club_name"].isin(selected_clubs)]
if selected_positions:
    filtered = filtered[filtered["position"].isin(selected_positions)]
if selected_nationalities:
    filtered = filtered[filtered["country_of_citizenship"].isin(selected_nationalities)]
if selected_feet:
    filtered = filtered[filtered["foot"].isin(selected_feet)]
filtered = filtered[filtered["age"].between(*age_range) | filtered["age"].isna()]
filtered = filtered[
    filtered["market_value_m"].between(*value_range) | filtered["market_value_m"].isna()
]
if only_playing:
    filtered = filtered[filtered["matches_this_season"] > 0]
if name_search:
    filtered = filtered[filtered["name"].str.contains(name_search, case=False, na=False)]

filtered = filtered.sort_values("market_value_in_eur", ascending=False, na_position="last")

st.caption(f"{len(filtered):,} spelers - klik op een rij om naar het spelerprofiel te gaan.".replace(",", "."))

filtered = filtered.copy()
filtered["name_disp"] = filtered["name"].map(lambda v: truncate_text(v, 20))
filtered["club_disp"] = filtered["current_club_name"].map(lambda v: truncate_text(v, 16))
filtered["nationality_disp"] = filtered["country_of_citizenship"].map(lambda v: truncate_text(v, 12))

render_player_table(
    filtered,
    {
        "club_crest_url": "Logo",
        "name_disp": "Naam",
        "age": "Lft.",
        "position": "Positie",
        "transfer_marker": "Transfer",
        "club_disp": "Club",
        "competition_display": "Competitie",
        "country": "Land",
        "goals_this_season": "Goals",
        "matches_this_season": "Wedstrijden",
        "market_value_m": "Marktwaarde (M€)",
        "contract_expiration_date": "Contract tot",
        "nationality_disp": "Nationaliteit",
    },
    key="spelers_zoeken_table",
    height=560,
    extra_column_config={
        # Exacte pixelbreedtes houden maar als richtwaarde - de harde
        # cap zit in de getrunceerde tekst zelf (name_disp/club_disp/
        # competition_display), anders groeit een kolom toch mee met zijn
        # langste celwaarde en loop je weer tegen horizontaal scrollen aan.
        "Logo": st.column_config.ImageColumn(width=32),
        "Naam": st.column_config.TextColumn(width=108),
        "Lft.": st.column_config.NumberColumn(width=36),
        "Positie": st.column_config.TextColumn(width=62),
        "Transfer": st.column_config.TextColumn(width=32, help="⚠️ = binnen de laatste 90 dagen getransfereerd"),
        "Club": st.column_config.TextColumn(width=92),
        "Competitie": st.column_config.TextColumn(width=120),
        "Land": st.column_config.TextColumn(width=50),
        "Goals": st.column_config.NumberColumn(width=46),
        "Wedstrijden": st.column_config.NumberColumn(width=82),
        "Marktwaarde (M€)": st.column_config.NumberColumn(format="%.1f", width=108),
        "Contract tot": st.column_config.DateColumn(format="DD/MM/YYYY", width=78),
        "Nationaliteit": st.column_config.TextColumn(width=75),
    },
)
