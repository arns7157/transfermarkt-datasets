import streamlit as st

from utils import (
    attach_competition_info,
    compute_breakout_candidates,
    inject_theme,
    load_appearances,
    load_competitions,
    load_players,
    render_header,
    render_player_table,
    truncate_text,
)

st.set_page_config(page_title="Potentie", page_icon="🌱", layout="wide")
inject_theme()
render_header(
    "Potentie",
    "Jonge spelers die net doorbreken: meer speelminuten krijgen, of beginnen te "
    "scoren, vergeleken met eerder dit seizoen. Klik op een rij om naar het "
    "spelerprofiel te gaan.",
)

players = load_players()
players = attach_competition_info(players, load_competitions())
appearances = load_appearances()

col_a, col_b, col_c = st.columns(3)
with col_a:
    max_age = st.slider("Maximale leeftijd", 16, 28, 23)
with col_b:
    recent_days = st.slider("Laatste... dagen tellen als 'recent'", 14, 60, 30)
with col_c:
    min_recent_matches = st.slider("Minstens aantal recente wedstrijden", 1, 6, 2)

candidates = compute_breakout_candidates(
    players, appearances, recent_days=recent_days, max_age=max_age, min_recent_matches=min_recent_matches
)

if candidates.empty:
    st.info("Geen spelers gevonden die aan deze criteria voldoen.")
    st.stop()

tab_all, tab_broke, tab_minutes, tab_scoring = st.tabs(
    ["Alles", "Net doorgebroken", "Meer speeltijd", "Begint te scoren"]
)


def render_table(df, key):
    df = df.copy()
    df["name_disp"] = df["name"].map(lambda v: truncate_text(v, 18))
    df["club_disp"] = df["current_club_name"].map(lambda v: truncate_text(v, 14))
    cols = {
        "club_crest_url": "Logo",
        "name_disp": "Naam",
        "age": "Lft.",
        "position": "Positie",
        "club_disp": "Club",
        "competition_display": "Competitie",
        "country": "Land",
        # (recent) staat niet in elk label - dit hele overzicht is al de
        # recente periode, dat scheelt kolombreedte op elk label.
        "recent_matches": "Wedstr.",
        "recent_avg_minutes": "Min/wed.",
        "recent_goals": "Goals",
        "recent_assists": "Assists",
        "market_value_m": "Marktwaarde (M€)",
    }
    render_player_table(
        df,
        cols,
        key=key,
        extra_column_config={
            # Exacte pixelbreedtes zodat alle kolommen samen passen zonder
            # horizontaal te moeten scrollen.
            "Logo": st.column_config.ImageColumn(width=32),
            "Naam": st.column_config.TextColumn(width=110),
            "Lft.": st.column_config.NumberColumn(width=36),
            "Positie": st.column_config.TextColumn(width=62),
            "Club": st.column_config.TextColumn(width=88),
            "Competitie": st.column_config.TextColumn(width=120),
            "Land": st.column_config.TextColumn(width=52),
            "Wedstr.": st.column_config.NumberColumn(width=55),
            "Min/wed.": st.column_config.NumberColumn(format="%.0f", width=60),
            "Goals": st.column_config.NumberColumn(width=48),
            "Assists": st.column_config.NumberColumn(width=55),
            "Marktwaarde (M€)": st.column_config.NumberColumn(format="%.1f", width=100),
        },
    )


with tab_all:
    st.caption(f"{len(candidates)} spelers, gesorteerd op potentie-score")
    render_table(candidates, key="pot_all")

with tab_broke:
    broke = candidates[candidates["just_broke_through"]]
    st.caption(f"{len(broke)} spelers zonder speeltijd eerder dit seizoen, nu wel aan de bak")
    render_table(broke, key="pot_broke")

with tab_minutes:
    minutes_up = candidates[candidates["minutes_trend"] > 10].sort_values("minutes_trend", ascending=False)
    st.caption(f"{len(minutes_up)} spelers die duidelijk meer minuten krijgen dan eerder dit seizoen")
    render_table(minutes_up, key="pot_minutes")

with tab_scoring:
    scoring_up = candidates[candidates["scoring_trend"] > 0].sort_values("scoring_trend", ascending=False)
    st.caption(f"{len(scoring_up)} spelers met een stijgende goal+assist-bijdrage per 90 minuten")
    render_table(scoring_up, key="pot_scoring")

st.divider()
with st.expander("Hoe wordt dit berekend?"):
    st.markdown(
        """
        Voor elke speler worden twee periodes van dit seizoen vergeleken: de
        **recente periode** (de ingestelde laatste N dagen) en de **periode
        ervoor**. De potentie-score combineert:

        - de stijging in gemiddelde speelminuten per wedstrijd,
        - de stijging in goals+assists per 90 minuten,
        - een bonus als de speler eerder dit seizoen nog geen minuten had.

        Spelers bij een U21/U23/B-elftal of andere reserve-ploeg worden eruit
        gefilterd: het gaat hier om doorbraak bij het eerste elftal.

        Dit is een signaal, geen eindoordeel — bekijk altijd het spelerprofiel
        voor context (blessures, tegenstanders, speelpositie).
        """
    )
