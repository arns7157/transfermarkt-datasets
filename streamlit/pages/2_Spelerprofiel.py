import plotly.express as px
import streamlit as st

from utils import format_money, load_appearances, load_players, load_transfers, load_valuations, player_label

st.set_page_config(page_title="Spelerprofiel", page_icon="📊", layout="wide")
st.title("📊 Spelerprofiel")

players = load_players()
appearances = load_appearances()
transfers = load_transfers()

players = players.sort_values("name")
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
    st.write(
        f"**Positie:** {player.get('position', '–')} ({player.get('sub_position', '–')})  \n"
        f"**Leeftijd:** {player.get('age', '–')}  \n"
        f"**Voet:** {player.get('foot', '–')}  \n"
        f"**Lengte:** {player.get('height_in_cm', '–')} cm  \n"
        f"**Nationaliteit:** {player.get('country_of_citizenship', '–')}  \n"
        f"**Huidige club:** {player.get('current_club_name', '–')}  \n"
        f"**Contract tot:** "
        + (
            player["contract_expiration_date"].strftime("%d/%m/%Y")
            if player.get("contract_expiration_date") is not None
            and not isinstance(player["contract_expiration_date"], float)
            else "–"
        )
    )

col1, col2 = st.columns(2)
col1.metric("Huidige marktwaarde", format_money(player.get("market_value_in_eur")))
col2.metric("Hoogste marktwaarde", format_money(player.get("highest_market_value_in_eur")))

st.divider()
st.subheader("Marktwaarde-verloop")
valuations = load_valuations()
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
    st.plotly_chart(fig, width="stretch")

st.divider()
st.subheader("Prestaties dit seizoen (per competitie)")
player_apps = appearances[appearances["player_id"] == selected_id]
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

    st.subheader("Recente wedstrijden")
    recent = player_apps.sort_values("date", ascending=False).head(10)[
        ["date", "competition_id", "goals", "assists", "minutes_played", "yellow_cards", "red_cards"]
    ]
    recent.columns = ["Datum", "Competitie", "Goals", "Assists", "Minuten", "Geel", "Rood"]
    st.dataframe(recent, width="stretch", hide_index=True)

st.divider()
st.subheader("Transferhistorie")
player_transfers = transfers[transfers["player_id"] == selected_id].sort_values(
    "transfer_date", ascending=False
)
if player_transfers.empty:
    st.info("Geen transfers geregistreerd voor deze speler.")
else:
    tdisp = player_transfers[
        ["transfer_date", "from_club_name", "to_club_name", "transfer_fee", "market_value_at_transfer"]
    ].copy()
    tdisp.columns = ["Datum", "Van", "Naar", "Transfersom", "Marktwaarde bij transfer"]
    st.dataframe(tdisp, width="stretch", hide_index=True)
