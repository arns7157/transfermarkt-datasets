import pandas as pd
import plotly.express as px
import streamlit as st

from utils import format_money, load_appearances, load_players, load_valuations, player_label

st.set_page_config(page_title="Spelers vergelijken", page_icon="⚖️", layout="wide")
st.title("⚖️ Spelers vergelijken")

players = load_players().sort_values("name")
appearances = load_appearances()
valuations = load_valuations()

labels = {pid: player_label(row) for pid, row in zip(players["player_id"], players.to_dict("records"))}

selected_ids = st.multiselect(
    "Kies 2 tot 4 spelers",
    players["player_id"].tolist(),
    format_func=lambda pid: labels.get(pid, str(pid)),
    max_selections=4,
)

if len(selected_ids) < 2:
    st.info("Kies minstens 2 spelers om te vergelijken.")
    st.stop()

selected_players = players[players["player_id"].isin(selected_ids)]

rows = []
for _, p in selected_players.iterrows():
    apps = appearances[appearances["player_id"] == p["player_id"]]
    rows.append(
        {
            "Speler": p["name"],
            "Club": p.get("current_club_name", "–"),
            "Leeftijd": p.get("age", "–"),
            "Positie": p.get("position", "–"),
            "Marktwaarde": format_money(p.get("market_value_in_eur")),
            "Wedstrijden (seizoen)": len(apps),
            "Goals (seizoen)": int(apps["goals"].sum()),
            "Assists (seizoen)": int(apps["assists"].sum()),
            "Minuten (seizoen)": int(apps["minutes_played"].sum()),
        }
    )

comparison = pd.DataFrame(rows).set_index("Speler").T.astype(str)
st.dataframe(comparison, width="stretch")

st.divider()
st.subheader("Marktwaarde-verloop")
history = valuations[valuations["player_id"].isin(selected_ids)].copy()
if history.empty:
    st.info("Geen marktwaarde-historiek beschikbaar voor deze spelers.")
else:
    history["Speler"] = history["player_id"].map(lambda pid: labels.get(pid, str(pid)))
    fig = px.line(
        history.sort_values("date"),
        x="date",
        y="market_value_in_eur",
        color="Speler",
        markers=True,
        labels={"date": "Datum", "market_value_in_eur": "Marktwaarde (€)"},
    )
    st.plotly_chart(fig, width="stretch")
