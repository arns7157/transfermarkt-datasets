import streamlit as st

from utils import inject_theme, load_clubs, load_competitions, load_players, load_transfers

st.set_page_config(page_title="Scouting platform", page_icon="⚽", layout="wide")
inject_theme()

players = load_players()
clubs = load_clubs()
competitions = load_competitions()
transfers = load_transfers()

n_competities = players["current_club_domestic_competition_id"].nunique()

competition_logos = (
    players[players["competition_logo_url"].fillna("") != ""]
    .drop_duplicates("current_club_domestic_competition_id")
    .sort_values("current_club_domestic_competition_id")["competition_logo_url"]
    .tolist()
)

st.markdown(
    '<div class="app-header"><span style="font-size:1.9rem">⚽</span>'
    "<h1>Scouting platform</h1></div>",
    unsafe_allow_html=True,
)
st.markdown(
    f'<div class="app-subtitle">Spelers uit {n_competities} competities: zoeken, profileren, '
    "vergelijken, en signaleren wie er doorbreekt.</div>",
    unsafe_allow_html=True,
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Spelers", f"{len(players):,}".replace(",", "."))
col2.metric("Clubs", f"{len(clubs):,}".replace(",", "."))
col3.metric("Competities", n_competities)
col4.metric("Transfers", f"{len(transfers):,}".replace(",", "."))

if competition_logos:
    st.write("")
    st.image(competition_logos, width=42)

st.write("")
st.markdown("#### Waar wil je naartoe?")

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(
        "**🔍 Spelers zoeken**  \nFilter op competitie, club, positie, leeftijd, "
        "marktwaarde en meer."
    )
    st.markdown(
        "**🌱 Potentie**  \nSpelers die net doorbreken: meer minuten, "
        "beginnen te scoren."
    )
with c2:
    st.markdown("**📊 Spelerprofiel**  \nBio, marktwaarde-verloop, vormcurve, transfers.")
    st.markdown("**⚖️ Vergelijken**  \n2 tot 4 spelers naast elkaar.")
with c3:
    st.markdown(
        "**🚨 Signalen**  \nAflopende contracten, grootste stijgers en dalers "
        "in marktwaarde."
    )

st.caption(
    "Data komt uit data/csv/ (wekelijks ververst via de 'Weekly Transfermarkt "
    "Scrape' GitHub Action)."
)
