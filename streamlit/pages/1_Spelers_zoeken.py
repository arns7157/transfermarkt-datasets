import streamlit as st

from utils import current_season_appearances, inject_theme, load_appearances, load_competitions, load_players, render_header

st.set_page_config(page_title="Spelers zoeken", page_icon="🔍", layout="wide")
inject_theme()

players = load_players()
competitions = load_competitions()
appearances = load_appearances()

comp_names = competitions.set_index("competition_id")["name"].to_dict()
comp_countries = competitions.set_index("competition_id")["country"].to_dict()
players["competition_name"] = players["current_club_domestic_competition_id"].map(comp_names)
players["country"] = players["current_club_domestic_competition_id"].map(comp_countries)

n_competities = players["current_club_domestic_competition_id"].nunique()
render_header("Spelers zoeken", f"Filter het volledige spelersbestand van de {n_competities} gevolgde competities.")

season_apps = current_season_appearances(appearances)
season_matches = season_apps.groupby("player_id").size().rename("matches_this_season")
players = players.merge(season_matches, left_on="player_id", right_index=True, how="left")
players["matches_this_season"] = players["matches_this_season"].fillna(0).astype(int)

with st.sidebar:
    st.header("Filters")

    country_options = sorted(players["country"].dropna().unique())
    selected_countries = st.multiselect("Land", country_options)

    country_scoped = players[players["country"].isin(selected_countries)] if selected_countries else players

    comp_options = sorted(country_scoped["competition_name"].dropna().unique())
    selected_comps = st.multiselect("Competitie", comp_options)

    scoped = country_scoped[country_scoped["competition_name"].isin(selected_comps)] if selected_comps else country_scoped

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

st.caption(f"{len(filtered):,} spelers".replace(",", "."))

display = filtered[
    [
        "club_crest_url",
        "name",
        "age",
        "position",
        "sub_position",
        "foot",
        "current_club_name",
        "competition_logo_url",
        "country_flag_url",
        "country",
        "competition_name",
        "matches_this_season",
        "market_value_m",
        "contract_expiration_date",
        "citizenship_flag_url",
        "country_of_citizenship",
    ]
].rename(
    columns={
        "club_crest_url": "Logo",
        "name": "Naam",
        "age": "Leeftijd",
        "position": "Positie",
        "sub_position": "Subpositie",
        "foot": "Voet",
        "current_club_name": "Club",
        "competition_logo_url": "Comp.",
        "country_flag_url": "Vlag",
        "country": "Land",
        "competition_name": "Competitie",
        "matches_this_season": "Wedstrijden (seizoen)",
        "market_value_m": "Marktwaarde (M€)",
        "contract_expiration_date": "Contract tot",
        "citizenship_flag_url": "Nat.",
        "country_of_citizenship": "Nationaliteit",
    }
)

st.caption("Klik op een rij om naar het spelerprofiel te gaan.")
event = st.dataframe(
    display,
    width="stretch",
    hide_index=True,
    height=560,
    column_config={
        "Logo": st.column_config.ImageColumn(width="small"),
        "Comp.": st.column_config.ImageColumn(width="small"),
        "Vlag": st.column_config.ImageColumn(width="small"),
        "Nat.": st.column_config.ImageColumn(width="small"),
        "Marktwaarde (M€)": st.column_config.NumberColumn(format="%.1f"),
        "Contract tot": st.column_config.DateColumn(format="DD/MM/YYYY"),
    },
    on_select="rerun",
    selection_mode="single-row",
)

selected_rows = event.selection.get("rows", []) if event and event.selection else []
if selected_rows:
    clicked_player_id = filtered.iloc[selected_rows[0]]["player_id"]
    st.session_state["jump_to_player_id"] = clicked_player_id
    st.switch_page("pages/3_Spelerprofiel.py")
