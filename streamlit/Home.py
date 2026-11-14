import streamlit as st

from utils import inject_theme, load_clubs, load_competitions, load_players, load_transfers

st.set_page_config(page_title="Scouting platform", page_icon="⚽", layout="wide")
inject_theme()

st.markdown(
    '<div class="app-header"><span style="font-size:1.9rem">⚽</span>'
    "<h1>Scouting platform</h1></div>",
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="app-subtitle">Spelers uit 6 competities: zoeken, profileren, vergelijken, '
    "en signaleren wie er doorbreekt.</div>",
    unsafe_allow_html=True,
)

players = load_players()
clubs = load_clubs()
competitions = load_competitions()
transfers = load_transfers()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Spelers", f"{len(players):,}".replace(",", "."))
col2.metric("Clubs", f"{len(clubs):,}".replace(",", "."))
col3.metric("Competities", competitions["competition_id"].nunique())
col4.metric("Transfers", f"{len(transfers):,}".replace(",", "."))

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
