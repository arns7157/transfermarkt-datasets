from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from utils import (
    attach_competition_info,
    format_money,
    inject_theme,
    load_competitions,
    load_players,
    load_valuations,
    render_header,
    render_player_table,
)

st.set_page_config(page_title="Signalen", page_icon="🚨", layout="wide")
inject_theme()
render_header(
    "Signalen",
    "Aflopende contracten en de grootste stijgers/dalers in marktwaarde. Klik op een "
    "rij om naar het spelerprofiel te gaan.",
)

players = load_players()
players = attach_competition_info(players, load_competitions())
valuations = load_valuations()

tab_contract, tab_value = st.tabs(["Aflopende contracten", "Snel veranderende marktwaarde"])

with tab_contract:
    months = st.slider("Binnen hoeveel maanden loopt het contract af?", 1, 24, 6, key="contract_months")
    cutoff = pd.Timestamp(datetime.now() + timedelta(days=months * 30))
    soon = players[
        players["contract_expiration_date"].notna() & (players["contract_expiration_date"] <= cutoff)
    ].sort_values("contract_expiration_date")

    st.caption(f"{len(soon)} spelers met een contract dat afloopt vóór {cutoff:%d/%m/%Y}")
    soon = soon.copy()
    soon["market_value_fmt"] = soon["market_value_in_eur"].map(format_money)
    render_player_table(
        soon,
        {
            "club_crest_url": "Logo",
            "name": "Naam",
            "age": "Lft.",
            "position": "Positie",
            "current_club_name": "Club",
            "competition_display": "Competitie",
            "country": "Land",
            "contract_expiration_date": "Contract tot",
            "market_value_fmt": "Marktwaarde",
            "citizenship_flag_url": "Nat.",
        },
        key="signalen_contract_table",
        extra_column_config={
            "Logo": st.column_config.ImageColumn(width=32),
            "Naam": st.column_config.TextColumn(width=120),
            "Lft.": st.column_config.NumberColumn(width=32),
            "Positie": st.column_config.TextColumn(width=70),
            "Club": st.column_config.TextColumn(width=120),
            "Competitie": st.column_config.TextColumn(width=165),
            "Land": st.column_config.TextColumn(width=60),
            "Contract tot": st.column_config.DateColumn(format="DD/MM/YYYY", width=85),
            "Marktwaarde": st.column_config.TextColumn(width=70),
            "Nat.": st.column_config.ImageColumn(width=32),
        },
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
    # inner, niet left: valuations.csv bevat ook spelers buiten de gevolgde
    # competities (oude restdata), die laten anders rijen vol "None" achter
    # mét een willekeurige/vervalste waardesprong erbij.
    joined = joined.join(
        players.set_index("player_id")[
            [
                "name",
                "current_club_name",
                "competition_display",
                "country",
                "position",
                "club_crest_url",
                "citizenship_flag_url",
            ]
        ],
        how="inner",
    )

    def _render_value_table(df, key):
        df = df.copy()
        df["market_value_in_eur_toen"] = df["market_value_in_eur_toen"].map(format_money)
        df["market_value_in_eur_nu"] = df["market_value_in_eur_nu"].map(format_money)
        df["verandering_pct"] = df["verandering_pct"].round(1)
        render_player_table(
            df,
            {
                "club_crest_url": "Logo",
                "name": "Naam",
                "position": "Positie",
                "current_club_name": "Club",
                "competition_display": "Competitie",
                "country": "Land",
                "market_value_in_eur_toen": "Toen",
                "market_value_in_eur_nu": "Nu",
                "verandering_pct": "% verandering",
                "citizenship_flag_url": "Nat.",
            },
            key=key,
            extra_column_config={
                "Logo": st.column_config.ImageColumn(width=32),
                "Naam": st.column_config.TextColumn(width=120),
                "Positie": st.column_config.TextColumn(width=70),
                "Club": st.column_config.TextColumn(width=120),
                "Competitie": st.column_config.TextColumn(width=165),
                "Land": st.column_config.TextColumn(width=60),
                "Toen": st.column_config.TextColumn(width=70),
                "Nu": st.column_config.TextColumn(width=70),
                "% verandering": st.column_config.NumberColumn(width=75),
                "Nat.": st.column_config.ImageColumn(width=32),
            },
        )

    # Onder elkaar i.p.v. naast elkaar: met Competitie/Land/Niveau erbij heeft
    # elke tabel de volle breedte nodig om zonder horizontaal scrollen te passen.
    st.subheader("Grootste stijgers")
    top_up = joined.sort_values("verandering_pct", ascending=False).head(20)
    _render_value_table(top_up, key="signalen_stijgers_table")

    st.subheader("Grootste dalers")
    top_down = joined.sort_values("verandering_pct", ascending=True).head(20)
    _render_value_table(top_down, key="signalen_dalers_table")
