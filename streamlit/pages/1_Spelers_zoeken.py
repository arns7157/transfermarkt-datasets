import streamlit as st

from utils import current_season_appearances, inject_theme, load_appearances, load_competitions, load_players, render_header

st.set_page_config(page_title="Spelers zoeken", page_icon="🔍", layout="wide")
inject_theme()
render_header("Spelers zoeken", "Filter het volledige spelersbestand van de 6 gevolgde competities.")

players = load_players()
competitions = load_competitions()
appearances = load_appearances()

comp_names = competitions.set_index("competition_id")["name"].to_dict()
players["competition_name"] = players["current_club_domestic_competition_id"].map(comp_names)

season_apps = current_season_appearances(appearances)
season_matches = season_apps.groupby("player_id").size().rename("matches_this_season")
players = players.merge(season_matches, left_on="player_id", right_index=True, how="left")
players["matches_this_season"] = players["matches_this_season"].fillna(0).astype(int)

with st.sidebar:
    st.header("Filters")

    comp_options = sorted(players["competition_name"].dropna().unique())
    selected_comps = st.multiselect("Competitie", comp_options)

    scoped = players[players["competition_name"].isin(selected_comps)] if selected_comps else players

    club_options = sorted(scoped["current_club_name"].dropna().unique())
    selected_clubs = st.multiselect("Club", club_options)

    position_options = sorted(players["position"].dropna().unique())
    selected_positions = st.multiselect("Positie", position_options)

    nationality_options = sorted(players["country_of_citizenship"].dropna().unique())
    selected_nationalities = st.multiselect("Nationaliteit", nationality_options)

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

st.caption(f"{len(filtered):,} spelers".replace(",", "."))

display = filtered[
    [
        "name",
        "age",
        "position",
        "sub_position",
        "foot",
        "current_club_name",
        "competition_name",
        "matches_this_season",
        "market_value_m",
        "contract_expiration_date",
        "country_of_citizenship",
    ]
].rename(
    columns={
        "name": "Naam",
        "age": "Leeftijd",
        "position": "Positie",
        "sub_position": "Subpositie",
        "foot": "Voet",
        "current_club_name": "Club",
        "competition_name": "Competitie",
        "matches_this_season": "Wedstrijden (seizoen)",
        "market_value_m": "Marktwaarde (M€)",
        "contract_expiration_date": "Contract tot",
        "country_of_citizenship": "Nationaliteit",
    }
)

st.dataframe(
    display,
    width="stretch",
    hide_index=True,
    height=560,
    column_config={
        "Marktwaarde (M€)": st.column_config.NumberColumn(format="%.1f"),
        "Contract tot": st.column_config.DateColumn(format="DD/MM/YYYY"),
    },
)
