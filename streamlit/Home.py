import streamlit as st

from utils import load_clubs, load_competitions, load_players, load_transfers

st.set_page_config(page_title="Scouting platform", page_icon="⚽", layout="wide")

st.title("⚽ Scouting platform")
st.markdown(
    """
    Verken spelers uit de gevolgde competities, bekijk spelerprofielen met
    marktwaarde- en prestatiegeschiedenis, vergelijk spelers naast elkaar, en
    laat opvallende spelers automatisch signaleren (aflopende contracten,
    snel veranderende marktwaarde, hoge output voor hun leeftijd).

    Gebruik de pagina's in de zijbalk om te beginnen.
    """
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

st.caption(
    "Data komt uit data/csv/ (wekelijks ververst via de 'Weekly Transfermarkt "
    "Scrape' GitHub Action)."
)
