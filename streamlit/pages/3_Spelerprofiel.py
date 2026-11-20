import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import (
    club_crest_by_name,
    competition_logo_url,
    current_injury,
    current_season_appearances,
    format_money,
    inject_theme,
    injury_badge_html,
    inline_img,
    load_appearances,
    load_injuries,
    load_players,
    load_transfers,
    load_valuations,
    player_label,
    position_badge,
    render_header,
    safe_val,
    style_chart,
    transfer_badge_html,
)

st.set_page_config(page_title="Spelerprofiel", page_icon="📊", layout="wide")
inject_theme()
render_header("Spelerprofiel", "Bio, marktwaarde-verloop, vormcurve en transferhistorie.")

players = load_players().sort_values("name")
appearances = load_appearances()
transfers = load_transfers()
valuations = load_valuations()
injuries = load_injuries()

labels = {pid: player_label(row) for pid, row in zip(players["player_id"], players.to_dict("records"))}

# Komt de gebruiker hier binnen via een klik op een rij in "Spelers zoeken"?
# Dan die speler meteen selecteren i.p.v. een lege zoekopdracht te tonen.
jump_to_player_id = st.session_state.pop("jump_to_player_id", None)

search = st.text_input("Zoek speler op naam")
candidates = players
if search:
    candidates = players[players["name"].str.contains(search, case=False, na=False)]

if candidates.empty:
    st.info("Geen speler gevonden.")
    st.stop()

candidate_ids = candidates["player_id"].tolist()
default_index = 0
if jump_to_player_id is not None and jump_to_player_id in candidate_ids:
    default_index = candidate_ids.index(jump_to_player_id)

selected_id = st.selectbox(
    "Speler",
    candidate_ids,
    index=default_index,
    format_func=lambda pid: labels.get(pid, str(pid)),
)
player = players[players["player_id"] == selected_id].iloc[0]
player_transfers = transfers[transfers["player_id"] == selected_id].sort_values("transfer_date", ascending=False)
player_injuries = injuries[injuries["player_id"] == selected_id].sort_values("from_date", ascending=False)

col_img, col_info = st.columns([1, 3])
with col_img:
    if isinstance(player.get("image_url"), str) and player["image_url"]:
        st.image(player["image_url"], width=180)
with col_info:
    st.subheader(player["name"])
    st.markdown(position_badge(player.get("position")), unsafe_allow_html=True)
    injury_badge = injury_badge_html(player_injuries)
    if injury_badge:
        st.markdown(injury_badge, unsafe_allow_html=True)
    transfer_badge = transfer_badge_html(player_transfers)
    if transfer_badge:
        st.markdown(transfer_badge, unsafe_allow_html=True)
    st.write("")
    contract = player.get("contract_expiration_date")
    contract_str = contract.strftime("%d/%m/%Y") if pd.notna(contract) else "–"
    nat_flag = inline_img(player.get("citizenship_flag_url"))
    club_crest = inline_img(player.get("club_crest_url"))
    comp_logo = inline_img(player.get("competition_logo_url"))
    st.markdown(
        f"**Leeftijd:** {safe_val(player.get('age'))} &nbsp;·&nbsp; "
        f"**Voet:** {safe_val(player.get('foot'))} &nbsp;·&nbsp; "
        f"**Lengte:** {safe_val(player.get('height_in_cm'))} cm  \n"
        f"**Nationaliteit:** {nat_flag}{safe_val(player.get('country_of_citizenship'))}  \n"
        f"**Huidige club:** {club_crest}{safe_val(player.get('current_club_name'))} "
        f"{comp_logo}  \n"
        f"**Contract tot:** {contract_str}",
        unsafe_allow_html=True,
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
        hover_data={"club_name": True},
        labels={"date": "Datum", "market_value_in_eur": "Marktwaarde (€)", "club_name": "Club"},
    )
    fig.update_traces(line_color="#22C55E", marker_color="#22C55E")
    style_chart(fig)

    # Clublogo bij elk punt: welke club de speler was op dat moment.
    # Plotly's layout.image.sizex/sizey willen een kaal getal - op een
    # datum-as is dat het aantal milliseconden (de interne representatie),
    # een pandas.Timedelta-object zelf wordt geweigerd.
    crest_by_name = club_crest_by_name()
    x_span = player_val_history["date"].max() - player_val_history["date"].min()
    if pd.isna(x_span) or x_span == pd.Timedelta(0):
        x_span = pd.Timedelta(days=365)
    x_span_ms = x_span / pd.Timedelta(milliseconds=1)
    y_span = player_val_history["market_value_in_eur"].max() - player_val_history["market_value_in_eur"].min()
    if not y_span:
        y_span = player_val_history["market_value_in_eur"].max() or 1
    for _, row in player_val_history.iterrows():
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
                sizex=x_span_ms * 0.045,
                sizey=y_span * 0.16,
                xanchor="center",
                yanchor="middle",
                layer="above",
            )
        )
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
    summary.insert(0, "Logo", summary["Competitie"].map(competition_logo_url))
    st.dataframe(
        summary,
        width="stretch",
        hide_index=True,
        column_config={"Logo": st.column_config.ImageColumn(width="small")},
    )

    fig = go.Figure()
    fig.add_bar(x=player_apps["date"], y=player_apps["minutes_played"], name="Minuten", marker_color="#3B82F6")
    fig.add_scatter(
        x=player_apps["date"],
        y=(player_apps["goals"] + player_apps["assists"]) * 10,
        name="Goals + assists (x10 voor schaal)",
        mode="markers+lines",
        marker_color="#EF4444",
    )
    style_chart(fig, legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, width="stretch")

    st.subheader("Recente wedstrijden")
    recent = all_player_apps.sort_values("date", ascending=False).head(10)[
        ["date", "competition_id", "goals", "assists", "minutes_played", "yellow_cards", "red_cards"]
    ].copy()
    recent.insert(1, "Logo", recent["competition_id"].map(competition_logo_url))
    recent.columns = ["Datum", "Logo", "Competitie", "Goals", "Assists", "Minuten", "Geel", "Rood"]
    st.dataframe(
        recent,
        width="stretch",
        hide_index=True,
        column_config={
            "Datum": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Logo": st.column_config.ImageColumn(width="small"),
        },
    )

st.divider()
st.subheader("Transferhistorie")
if player_transfers.empty:
    st.info("Geen transfers geregistreerd voor deze speler.")
else:
    crest_by_name = club_crest_by_name()
    tdisp = player_transfers[
        ["transfer_date", "from_club_name", "to_club_name", "from_club_crest_url", "to_club_crest_url", "transfer_fee", "market_value_at_transfer"]
    ].copy()
    # De transferHistory-API geeft het logo rechtstreeks mee (betrouwbaar,
    # ook voor jeugdteams/obscure clubs) - enkel voor rijen die dat nog
    # niet hebben (van vóór deze fix) valt dit terug op naam-matching.
    tdisp["from_crest"] = tdisp["from_club_crest_url"].where(
        tdisp["from_club_crest_url"] != "", tdisp["from_club_name"].map(crest_by_name)
    ).fillna("")
    tdisp["to_crest"] = tdisp["to_club_crest_url"].where(
        tdisp["to_club_crest_url"] != "", tdisp["to_club_name"].map(crest_by_name)
    ).fillna("")
    tdisp = tdisp[
        ["transfer_date", "from_crest", "from_club_name", "to_crest", "to_club_name", "transfer_fee", "market_value_at_transfer"]
    ]
    tdisp.columns = ["Datum", "Logo (van)", "Van", "Logo (naar)", "Naar", "Transfersom", "Marktwaarde bij transfer"]
    st.dataframe(
        tdisp,
        width="stretch",
        hide_index=True,
        column_config={
            "Datum": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Logo (van)": st.column_config.ImageColumn(width="small"),
            "Logo (naar)": st.column_config.ImageColumn(width="small"),
        },
    )

st.divider()
st.subheader("Blessurehistorie")
if player_injuries.empty:
    st.info("Geen blessures geregistreerd voor deze speler.")
else:
    if current_injury(player_injuries) is not None:
        st.warning("Heeft recent een blessure zonder (bevestigde) terugkeerdatum - mogelijk nog altijd geblesseerd.")
    idisp = player_injuries[["season", "injury", "from_date", "until_date", "days", "games_missed"]].copy()
    idisp.columns = ["Seizoen", "Blessure", "Vanaf", "Tot", "Dagen", "Wedstrijden gemist"]
    st.dataframe(
        idisp,
        width="stretch",
        hide_index=True,
        column_config={
            "Vanaf": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Tot": st.column_config.DateColumn(format="DD/MM/YYYY"),
        },
    )
