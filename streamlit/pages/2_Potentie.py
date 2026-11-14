import streamlit as st

from utils import compute_breakout_candidates, inject_theme, load_appearances, load_players, render_header

st.set_page_config(page_title="Potentie", page_icon="🌱", layout="wide")
inject_theme()
render_header(
    "Potentie",
    "Jonge spelers die net doorbreken: meer speelminuten krijgen, of beginnen te "
    "scoren, vergeleken met eerder dit seizoen.",
)

players = load_players()
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


def render_table(df, extra_cols=None):
    cols = {
        "name": "Naam",
        "age": "Leeftijd",
        "position": "Positie",
        "current_club_name": "Club",
        "recent_matches": "Wedstrijden (recent)",
        "recent_avg_minutes": "Min/wedstrijd (recent)",
        "earlier_avg_minutes": "Min/wedstrijd (eerder)",
        "recent_ga_per90": "G+A/90 (recent)",
        "earlier_ga_per90": "G+A/90 (eerder)",
        "market_value_m": "Marktwaarde (M€)",
    }
    shown = df[list(cols.keys())].rename(columns=cols)
    st.dataframe(
        shown,
        width="stretch",
        hide_index=True,
        column_config={
            "Min/wedstrijd (recent)": st.column_config.NumberColumn(format="%.0f"),
            "Min/wedstrijd (eerder)": st.column_config.NumberColumn(format="%.0f"),
            "G+A/90 (recent)": st.column_config.NumberColumn(format="%.2f"),
            "G+A/90 (eerder)": st.column_config.NumberColumn(format="%.2f"),
            "Marktwaarde (M€)": st.column_config.NumberColumn(format="%.1f"),
        },
    )


with tab_all:
    st.caption(f"{len(candidates)} spelers, gesorteerd op potentie-score")
    render_table(candidates)

with tab_broke:
    broke = candidates[candidates["just_broke_through"]]
    st.caption(f"{len(broke)} spelers zonder speeltijd eerder dit seizoen, nu wel aan de bak")
    render_table(broke)

with tab_minutes:
    minutes_up = candidates[candidates["minutes_trend"] > 10].sort_values("minutes_trend", ascending=False)
    st.caption(f"{len(minutes_up)} spelers die duidelijk meer minuten krijgen dan eerder dit seizoen")
    render_table(minutes_up)

with tab_scoring:
    scoring_up = candidates[candidates["scoring_trend"] > 0].sort_values("scoring_trend", ascending=False)
    st.caption(f"{len(scoring_up)} spelers met een stijgende goal+assist-bijdrage per 90 minuten")
    render_table(scoring_up)

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

        Dit is een signaal, geen eindoordeel — bekijk altijd het spelerprofiel
        voor context (blessures, tegenstanders, speelpositie).
        """
    )
