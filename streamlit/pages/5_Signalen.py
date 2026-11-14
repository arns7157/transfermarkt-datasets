from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from utils import format_money, inject_theme, load_players, load_valuations, render_header

st.set_page_config(page_title="Signalen", page_icon="🚨", layout="wide")
inject_theme()
render_header("Signalen", "Aflopende contracten en de grootste stijgers/dalers in marktwaarde.")

players = load_players()
valuations = load_valuations()

tab_contract, tab_value = st.tabs(["Aflopende contracten", "Snel veranderende marktwaarde"])

with tab_contract:
    months = st.slider("Binnen hoeveel maanden loopt het contract af?", 1, 24, 6, key="contract_months")
    cutoff = pd.Timestamp(datetime.now() + timedelta(days=months * 30))
    soon = players[
        players["contract_expiration_date"].notna() & (players["contract_expiration_date"] <= cutoff)
    ].sort_values("contract_expiration_date")

    st.caption(f"{len(soon)} spelers met een contract dat afloopt vóór {cutoff:%d/%m/%Y}")
    disp = soon[
        ["name", "age", "position", "current_club_name", "contract_expiration_date", "market_value_in_eur"]
    ].copy()
    disp["market_value_in_eur"] = disp["market_value_in_eur"].map(format_money)
    disp.columns = ["Naam", "Leeftijd", "Positie", "Club", "Contract tot", "Marktwaarde"]
    st.dataframe(
        disp,
        width="stretch",
        hide_index=True,
        column_config={"Contract tot": st.column_config.DateColumn(format="DD/MM/YYYY")},
    )

with tab_value:
    months_back = st.slider("Vergelijk met hoeveel maanden geleden?", 1, 24, 6, key="value_months")
    cutoff = pd.Timestamp(datetime.now() - timedelta(days=months_back * 30))

    latest = valuations.sort_values("date").groupby("player_id").tail(1).set_index("player_id")
    history_before = valuations[valuations["date"] <= cutoff]
    baseline = history_before.sort_values("date").groupby("player_id").tail(1).set_index("player_id")

    joined = latest[["market_value_in_eur"]].join(
        baseline[["market_value_in_eur"]], how="inner", suffixes=("_nu", "_toen")
    )
    joined = joined[joined["market_value_in_eur_toen"] > 0]
    joined["verandering_pct"] = (
        (joined["market_value_in_eur_nu"] - joined["market_value_in_eur_toen"])
        / joined["market_value_in_eur_toen"]
        * 100
    )
    joined = joined.join(players.set_index("player_id")[["name", "current_club_name", "position"]])

    col_up, col_down = st.columns(2)
    with col_up:
        st.subheader("Grootste stijgers")
        top_up = joined.sort_values("verandering_pct", ascending=False).head(20)
        disp_up = top_up[["name", "current_club_name", "position", "market_value_in_eur_toen", "market_value_in_eur_nu", "verandering_pct"]].copy()
        disp_up["market_value_in_eur_toen"] = disp_up["market_value_in_eur_toen"].map(format_money)
        disp_up["market_value_in_eur_nu"] = disp_up["market_value_in_eur_nu"].map(format_money)
        disp_up["verandering_pct"] = disp_up["verandering_pct"].round(1)
        disp_up.columns = ["Naam", "Club", "Positie", "Toen", "Nu", "% verandering"]
        st.dataframe(disp_up, width="stretch", hide_index=True)

    with col_down:
        st.subheader("Grootste dalers")
        top_down = joined.sort_values("verandering_pct", ascending=True).head(20)
        disp_down = top_down[["name", "current_club_name", "position", "market_value_in_eur_toen", "market_value_in_eur_nu", "verandering_pct"]].copy()
        disp_down["market_value_in_eur_toen"] = disp_down["market_value_in_eur_toen"].map(format_money)
        disp_down["market_value_in_eur_nu"] = disp_down["market_value_in_eur_nu"].map(format_money)
        disp_down["verandering_pct"] = disp_down["verandering_pct"].round(1)
        disp_down.columns = ["Naam", "Club", "Positie", "Toen", "Nu", "% verandering"]
        st.dataframe(disp_down, width="stretch", hide_index=True)
