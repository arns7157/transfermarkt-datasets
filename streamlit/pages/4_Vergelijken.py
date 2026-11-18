import pandas as pd
import plotly.express as px
import streamlit as st

from utils import (
    club_crest_by_name,
    current_season_appearances,
    format_money,
    inject_theme,
    inline_img,
    load_appearances,
    load_players,
    load_valuations,
    player_label,
    render_header,
    safe_val,
    style_chart,
)

st.set_page_config(page_title="Spelers vergelijken", page_icon="⚖️", layout="wide")
inject_theme()
render_header("Vergelijken", "Zet 2 tot 4 spelers naast elkaar.")

players = load_players().sort_values("name")
appearances = current_season_appearances(load_appearances())
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

header_cols = st.columns(len(selected_players))
for col, (_, p) in zip(header_cols, selected_players.iterrows()):
    with col:
        if isinstance(p.get("image_url"), str) and p["image_url"]:
            st.image(p["image_url"], width=110)
        club_crest = inline_img(p.get("club_crest_url"))
        nat_flag = inline_img(p.get("citizenship_flag_url"))
        st.markdown(
            f"**{p['name']}**  \n{club_crest}{safe_val(p.get('current_club_name'))}  \n"
            f"{nat_flag}{safe_val(p.get('country_of_citizenship'))}",
            unsafe_allow_html=True,
        )

rows = []
for _, p in selected_players.iterrows():
    apps = appearances[appearances["player_id"] == p["player_id"]]
    rows.append(
        {
            "Speler": p["name"],
            "Club": safe_val(p.get("current_club_name")),
            "Leeftijd": safe_val(p.get("age")),
            "Positie": safe_val(p.get("position")),
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
        color_discrete_sequence=["#22C55E", "#3B82F6", "#F59E0B", "#EF4444"],
    )
    style_chart(fig)

    crest_by_name = club_crest_by_name()
    hist_sorted = history.sort_values("date")
    x_span = hist_sorted["date"].max() - hist_sorted["date"].min()
    if pd.isna(x_span) or x_span == pd.Timedelta(0):
        x_span = pd.Timedelta(days=365)
    x_span_ms = x_span / pd.Timedelta(milliseconds=1)
    y_span = hist_sorted["market_value_in_eur"].max() - hist_sorted["market_value_in_eur"].min()
    if not y_span:
        y_span = hist_sorted["market_value_in_eur"].max() or 1
    for _, row in hist_sorted.iterrows():
        crest = crest_by_name.get(row.get("club_name"))
        if not crest:
            continue
        fig.add_layout_image(
            dict(
                source=crest,
                x=row["date"],
                y=row["market_value_in_eur"],
                xref="x",
                yref="y",
                sizex=x_span_ms * 0.035,
                sizey=y_span * 0.12,
                xanchor="center",
                yanchor="middle",
                layer="above",
            )
        )
    st.plotly_chart(fig, width="stretch")
