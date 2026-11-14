import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import (
    current_season_appearances,
    format_money,
    inject_theme,
    load_appearances,
    load_players,
    load_transfers,
    load_valuations,
    player_label,
    position_badge,
    render_header,
)

st.set_page_config(page_title="Spelerprofiel", page_icon="📊", layout="wide")
inject_theme()
render_header("Spelerprofiel", "Bio, marktwaarde-verloop, vormcurve en transferhistorie.")

players = load_players().sort_values("name")
appearances = load_appearances()
transfers = load_transfers()
valuations = load_valuations()

labels = {pid: player_label(row) for pid, row in zip(players["player_id"], players.to_dict("records"))}

search = st.text_input("Zoek speler op naam")
candidates = players
if search:
    candidates = players[players["name"].str.contains(search, case=False, na=False)]

if candidates.empty:
    st.info("Geen speler gevonden.")
    st.stop()

selected_id = st.selectbox(
    "Speler",
    candidates["player_id"].tolist(),
    format_func=lambda pid: labels.get(pid, str(pid)),
)
player = players[players["player_id"] == selected_id].iloc[0]

col_img, col_info = st.columns([1, 3])
with col_img:
    if isinstance(player.get("image_url"), str) and player["image_url"]:
        st.image(player["image_url"], width=180)
with col_info:
    st.subheader(player["name"])
    st.markdown(position_badge(player.get("position")), unsafe_allow_html=True)
    st.write("")
    contract = player.get("contract_expiration_date")
    contract_str = contract.strftime("%d/%m/%Y") if contract is not None and not isinstance(contract, float) else "–"
    st.markdown(
        f"**Leeftijd:** {player.get('age', '–')} &nbsp;·&nbsp; "
        f"**Voet:** {player.get('foot', '–')} &nbsp;·&nbsp; "
        f"**Lengte:** {player.get('height_in_cm', '–')} cm  \n"
        f"**Nationaliteit:** {player.get('country_of_citizenship', '–')}  \n"
        f"**Huidige club:** {player.get('current_club_name', '–')}  \n"
        f"**Contract tot:** {contract_str}"
    )

col1, col2 = st.columns(2)
col1.metric("Huidige marktwaarde", format_money(player.get("market_value_in_eur")))
col2.metric("Hoogste marktwaarde", format_money(player.get("highest_market_value_in_eur")))

st.divider()
st.subheader("Marktwaarde-verloop")
player_val_history = valuations[valuations["player_id"] == selected_id].sort_values("date")
if player_val_history.empty:
    st.info("Geen marktwaarde-historiek beschikbaar voor deze speler.")
else:
    fig = px.line(
        player_val_history,
        x="date",
        y="market_value_in_eur",
        markers=True,
        labels={"date": "Datum", "market_value_in_eur": "Marktwaarde (€)"},
    )
    fig.update_traces(line_color="#22C55E", marker_color="#22C55E")
    fig.update_layout(plot_bgcolor="#0B0F14", paper_bgcolor="#0B0F14", font_color="#E5E7EB")
    st.plotly_chart(fig, width="stretch")

st.divider()
st.subheader("Vormcurve dit seizoen")
all_player_apps = appearances[appearances["player_id"] == selected_id].sort_values("date")
player_apps = current_season_appearances(all_player_apps)
if player_apps.empty:
    st.info("Geen wedstrijdstatistieken beschikbaar voor deze speler.")
else:
    summary = (
        player_apps.groupby("competition_id")
        .agg(
            wedstrijden=("appearance_id", "count"),
            goals=("goals", "sum"),
            assists=("assists", "sum"),
            minuten=("minutes_played", "sum"),
            gele_kaarten=("yellow_cards", "sum"),
            rode_kaarten=("red_cards", "sum"),
        )
        .reset_index()
        .rename(columns={"competition_id": "Competitie"})
    )
    st.dataframe(summary, width="stretch", hide_index=True)

    fig = go.Figure()
    fig.add_bar(x=player_apps["date"], y=player_apps["minutes_played"], name="Minuten", marker_color="#3B82F6")
    fig.add_scatter(
        x=player_apps["date"],
        y=(player_apps["goals"] + player_apps["assists"]) * 10,
        name="Goals + assists (x10 voor schaal)",
        mode="markers+lines",
        marker_color="#EF4444",
    )
    fig.update_layout(
        plot_bgcolor="#0B0F14",
        paper_bgcolor="#0B0F14",
        font_color="#E5E7EB",
        legend=dict(orientation="h", y=1.1),
    )
    st.plotly_chart(fig, width="stretch")

    st.subheader("Recente wedstrijden")
    recent = all_player_apps.sort_values("date", ascending=False).head(10)[
        ["date", "competition_id", "goals", "assists", "minutes_played", "yellow_cards", "red_cards"]
    ]
    recent.columns = ["Datum", "Competitie", "Goals", "Assists", "Minuten", "Geel", "Rood"]
    st.dataframe(recent, width="stretch", hide_index=True)

st.divider()
st.subheader("Transferhistorie")
player_transfers = transfers[transfers["player_id"] == selected_id].sort_values("transfer_date", ascending=False)
if player_transfers.empty:
    st.info("Geen transfers geregistreerd voor deze speler.")
else:
    tdisp = player_transfers[
        ["transfer_date", "from_club_name", "to_club_name", "transfer_fee", "market_value_at_transfer"]
    ].copy()
    tdisp.columns = ["Datum", "Van", "Naar", "Transfersom", "Marktwaarde bij transfer"]
    st.dataframe(tdisp, width="stretch", hide_index=True)
