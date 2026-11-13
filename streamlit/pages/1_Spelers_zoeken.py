import streamlit as st

from utils import format_money, load_competitions, load_players

st.set_page_config(page_title="Spelers zoeken", page_icon="🔍", layout="wide")
st.title("🔍 Spelers zoeken")

players = load_players()
competitions = load_competitions()

comp_names = competitions.set_index("competition_id")["name"].to_dict()
players["competition_name"] = players["current_club_domestic_competition_id"].map(comp_names)

with st.sidebar:
    st.header("Filters")

    comp_options = sorted(players["competition_name"].dropna().unique())
    selected_comps = st.multiselect("Competitie", comp_options)

    filtered_for_clubs = players
    if selected_comps:
        filtered_for_clubs = players[players["competition_name"].isin(selected_comps)]
    club_options = sorted(filtered_for_clubs["current_club_name"].dropna().unique())
    selected_clubs = st.multiselect("Club", club_options)

    position_options = sorted(players["position"].dropna().unique())
    selected_positions = st.multiselect("Positie", position_options)

    min_age, max_age = int(players["age"].min(skipna=True) or 15), int(players["age"].max(skipna=True) or 45)
    age_range = st.slider("Leeftijd", min_age, max_age, (min_age, max_age))

    max_value = float(players["market_value_in_eur"].max(skipna=True) or 0)
    value_range = st.slider(
        "Marktwaarde",
        0.0,
        max_value,
        (0.0, max_value),
        format="€%.0f",
    )

    name_search = st.text_input("Naam bevat")

filtered = players.copy()
if selected_comps:
    filtered = filtered[filtered["competition_name"].isin(selected_comps)]
if selected_clubs:
    filtered = filtered[filtered["current_club_name"].isin(selected_clubs)]
if selected_positions:
    filtered = filtered[filtered["position"].isin(selected_positions)]
filtered = filtered[filtered["age"].between(*age_range) | filtered["age"].isna()]
filtered = filtered[
    filtered["market_value_in_eur"].between(*value_range) | filtered["market_value_in_eur"].isna()
]
if name_search:
    filtered = filtered[filtered["name"].str.contains(name_search, case=False, na=False)]

st.caption(f"{len(filtered):,} spelers".replace(",", "."))

filtered = filtered.sort_values("market_value_in_eur", ascending=False, na_position="last")

display = filtered[
    [
        "name",
        "age",
        "position",
        "sub_position",
        "foot",
        "current_club_name",
        "competition_name",
        "market_value_in_eur",
        "contract_expiration_date",
        "country_of_citizenship",
    ]
].copy()
display["market_value_in_eur"] = display["market_value_in_eur"].map(format_money)
display.columns = [
    "Naam",
    "Leeftijd",
    "Positie",
    "Subpositie",
    "Voet",
    "Club",
    "Competitie",
    "Marktwaarde",
    "Contract tot",
    "Nationaliteit",
]

st.dataframe(display, width="stretch", hide_index=True)
