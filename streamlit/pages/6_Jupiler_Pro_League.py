import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from fotmob import (
    PLAYER_STAT_LABELS,
    TEAM_STAT_LABELS,
    available_match_ids,
    list_fotmob_leagues,
    list_player_stats,
    list_team_stats,
    load_fixtures,
    load_match,
    load_player_stat,
    load_table,
    load_team_stat,
    match_lineup,
    match_momentum,
    match_shots,
    match_top_stats,
    order_stat_keys,
    resolve_club,
    resolve_player,
    stat_bar_html,
    stat_label,
)
from utils import inject_theme, inline_img, render_header, style_chart, truncate_text

st.set_page_config(page_title="Jupiler Pro League", page_icon="⚽", layout="wide")
inject_theme()

leagues = list_fotmob_leagues()
if not leagues:
    render_header("Jupiler Pro League", "Geavanceerde statistieken via FotMob.")
    st.info("Geen FotMob-data gevonden in data/Fotmob/.")
    st.stop()

# Vooralsnog altijd precies 1 competitie beschikbaar (BE1) - zodra er een
# 2e submap bijkomt, wordt dit een st.selectbox net als de andere filters.
league_key = next(iter(leagues))
league_label = leagues[league_key]

render_header(
    league_label,
    "Standenlijst, spelers-/teamstatistieken (xG, xA, ...) en wedstrijddetails via FotMob - "
    "aanvullend op de Transfermarkt-data, los van die pijplijn.",
)

tab_table, tab_players, tab_teams, tab_matches = st.tabs(
    ["Standenlijst", "Spelersstatistieken", "Teamstatistieken", "Wedstrijden"]
)

with tab_table:
    table_df, legend = load_table(league_key)
    disp = table_df.copy()
    disp["crest"] = disp["id"].map(lambda tid: resolve_club(league_key, tid).get("crest_url", ""))
    disp = disp[
        ["idx", "crest", "name", "played", "wins", "draws", "losses", "scoresStr", "goalConDiff", "pts"]
    ]
    disp.columns = ["#", "Logo", "Club", "Gesp.", "W", "G", "V", "Doelpunten", "Saldo", "Ptn"]
    st.dataframe(
        disp,
        hide_index=True,
        width="stretch",
        column_config={
            "#": st.column_config.NumberColumn(width=32),
            "Logo": st.column_config.ImageColumn(width=28),
            "Club": st.column_config.TextColumn(width=160),
            "Ptn": st.column_config.NumberColumn(width=50),
        },
    )
    if legend:
        legend_html = " &nbsp;&nbsp; ".join(
            f'<span style="display:inline-block;width:10px;height:10px;background:{item["color"]};'
            f'border-radius:2px;margin-right:4px;"></span>{item["title"]}'
            for item in legend
        )
        st.markdown(f'<div style="font-size:0.85rem;">{legend_html}</div>', unsafe_allow_html=True)

with tab_players:
    stat_keys = list_player_stats(league_key)
    ordered = order_stat_keys(stat_keys, PLAYER_STAT_LABELS)
    labels = [stat_label(k, PLAYER_STAT_LABELS) for k in ordered]
    choice = st.selectbox("Statistiek", labels, key="fm_player_stat")
    selected_key = ordered[labels.index(choice)]

    df = load_player_stat(league_key, selected_key)
    if df.empty:
        st.info("Geen data voor deze statistiek.")
    else:
        df = df.sort_values("value", ascending=False).head(30).reset_index(drop=True)
        df["crest"] = df["teamId"].map(lambda tid: resolve_club(league_key, tid).get("crest_url", ""))
        df["club"] = df["teamId"].map(lambda tid: resolve_club(league_key, tid).get("name", ""))
        df["tm_player_id"] = df.apply(
            lambda r: resolve_player(league_key, r["teamId"], r["name"]), axis=1
        )
        df["value_disp"] = df["value"].map(lambda v: round(v, 2) if isinstance(v, float) else v)
        disp = df[["rank", "crest", "name", "club", "value_disp"]].copy()
        disp.columns = ["#", "Logo", "Speler", "Club", choice]
        event = st.dataframe(
            disp,
            hide_index=True,
            width="stretch",
            column_config={
                "#": st.column_config.NumberColumn(width=32),
                "Logo": st.column_config.ImageColumn(width=28),
                "Club": st.column_config.TextColumn(width=160),
            },
            on_select="rerun",
            selection_mode="single-row",
            key=f"fm_players_{selected_key}",
        )
        rows = event.selection.get("rows", []) if event and event.selection else []
        if rows:
            pid = df.iloc[rows[0]]["tm_player_id"]
            if pd.notna(pid):
                st.session_state["jump_to_player_id"] = int(pid)
                st.switch_page("pages/3_Spelerprofiel.py")
        st.caption("Klik op een rij om naar het Transfermarkt-spelerprofiel te gaan (indien herkend).")

with tab_teams:
    stat_keys = list_team_stats(league_key)
    ordered = order_stat_keys(stat_keys, TEAM_STAT_LABELS)
    labels = [stat_label(k, TEAM_STAT_LABELS) for k in ordered]
    choice = st.selectbox("Statistiek", labels, key="fm_team_stat")
    selected_key = ordered[labels.index(choice)]

    df = load_team_stat(league_key, selected_key)
    if df.empty:
        st.info("Geen data voor deze statistiek.")
    else:
        df = df.sort_values("value", ascending=False).reset_index(drop=True)
        df["crest"] = df["teamId"].map(lambda tid: resolve_club(league_key, tid).get("crest_url", ""))
        df["value_disp"] = df["value"].map(lambda v: round(v, 2) if isinstance(v, float) else v)
        disp = df[["rank", "crest", "name", "value_disp"]].copy()
        disp.columns = ["#", "Logo", "Club", choice]
        st.dataframe(
            disp,
            hide_index=True,
            width="stretch",
            column_config={
                "#": st.column_config.NumberColumn(width=32),
                "Logo": st.column_config.ImageColumn(width=28),
                "Club": st.column_config.TextColumn(width=200),
            },
        )

with tab_matches:
    fixtures = load_fixtures(league_key)
    avail = available_match_ids(league_key)
    playable = fixtures[fixtures["match_id"].isin(avail)].sort_values("date").reset_index(drop=True)

    if playable.empty:
        st.info("Geen gedetailleerde wedstrijddata beschikbaar.")
    else:
        def _match_label(row) -> str:
            date_str = f" ({row['date']:%d/%m/%Y})" if pd.notna(row["date"]) else ""
            score = row["score"] or "-"
            return f"Speeldag {row['round']}: {row['home']} {score} {row['away']}{date_str}"

        match_labels = [_match_label(r) for _, r in playable.iterrows()]
        default_idx = len(match_labels) - 1
        picked = st.selectbox(
            "Kies een wedstrijd", range(len(match_labels)), index=default_idx,
            format_func=lambda i: match_labels[i], key="fm_match_picker",
        )
        match_id = int(playable.iloc[picked]["match_id"])
        match = load_match(league_key, match_id)
        payload = match["payload"]
        general = payload["general"]
        header = payload["header"]
        home_team, away_team = header["teams"]
        team_colors = (general.get("teamColors") or {}).get("lightMode", {})
        home_color = team_colors.get("home", "#3B82F6")
        away_color = team_colors.get("away", "#EF4444")

        col_h, col_mid, col_a = st.columns([3, 2, 3])
        with col_h:
            st.markdown(
                f'<div style="text-align:right;font-size:1.2rem;font-weight:700;">'
                f'{home_team["name"]} {inline_img(home_team.get("imageUrl"), height=28)}</div>',
                unsafe_allow_html=True,
            )
        with col_mid:
            st.markdown(
                f'<div style="text-align:center;font-size:1.6rem;font-weight:800;">'
                f'{header["status"].get("scoreStr", "-")}</div>'
                f'<div style="text-align:center;color:#6B7280;font-size:0.85rem;">'
                f'{header["status"].get("reason", {}).get("long", "")}</div>',
                unsafe_allow_html=True,
            )
        with col_a:
            st.markdown(
                f'<div style="text-align:left;font-size:1.2rem;font-weight:700;">'
                f'{inline_img(away_team.get("imageUrl"), height=28)} {away_team["name"]}</div>',
                unsafe_allow_html=True,
            )

        st.divider()
        st.subheader("Statistieken")
        stats_rows = match_top_stats(match)
        if not stats_rows:
            st.info("Geen wedstrijdstatistieken beschikbaar voor deze wedstrijd.")
        else:
            for row in stats_rows:
                st.markdown(
                    stat_bar_html(row["title"], row["home"], row["away"], home_color, away_color),
                    unsafe_allow_html=True,
                )

        st.divider()
        st.subheader("Shotmap")
        shots = match_shots(match)
        if shots.empty:
            st.info("Geen shotmap beschikbaar voor deze wedstrijd.")
        else:
            fig = go.Figure()
            # Vereenvoudigde aanvalshelft - FotMob normaliseert shots altijd
            # naar dezelfde aanvalsrichting (x -> 100 = doel), ongeacht team.
            pitch_shapes = [
                dict(type="rect", x0=50, x1=100, y0=0, y1=100, line=dict(color="#CBD5E1")),
                dict(type="rect", x0=83, x1=100, y0=21, y1=79, line=dict(color="#CBD5E1")),
                dict(type="rect", x0=94.2, x1=100, y0=37, y1=63, line=dict(color="#CBD5E1")),
                dict(type="line", x0=100, x1=100, y0=45, y1=55, line=dict(color="#CBD5E1", width=4)),
            ]
            for side, color, name in ((0, home_color, home_team["name"]), (1, away_color, away_team["name"])):
                team_id = home_team["id"] if side == 0 else away_team["id"]
                team_shots = shots[shots["teamId"] == team_id]
                if team_shots.empty:
                    continue
                is_goal = team_shots["eventType"] == "Goal"
                sizes = (team_shots["expectedGoals"].fillna(0).clip(lower=0) ** 0.5 * 32 + 8)
                fig.add_trace(
                    go.Scatter(
                        x=team_shots["x"],
                        y=team_shots["y"],
                        mode="markers",
                        name=name,
                        marker=dict(
                            size=sizes,
                            color=color,
                            symbol=["star" if g else "circle" for g in is_goal],
                            line=dict(width=1, color="#1F2937"),
                            opacity=0.85,
                        ),
                        customdata=team_shots[["playerName", "eventType", "expectedGoals", "min"]],
                        hovertemplate=(
                            "%{customdata[0]}<br>Minuut %{customdata[3]}<br>"
                            "%{customdata[1]} - xG %{customdata[2]:.2f}<extra></extra>"
                        ),
                    )
                )
            fig.update_layout(shapes=pitch_shapes)
            # Geen scaleanchor (geen gedwongen 1:1 schaal) - dat perste de
            # helft-breedte (y: 0-100) vs helft-lengte (x: 50-100) anders in
            # een veel te smalle, naar rechts weggedrukte strook. Gewoon
            # laten uitrekken over de volledige grafiekbreedte oogt duidelijker.
            fig.update_xaxes(range=[48, 102], showgrid=False, zeroline=False, showticklabels=False)
            fig.update_yaxes(range=[-5, 105], showgrid=False, zeroline=False, showticklabels=False)
            style_chart(fig, legend=dict(orientation="h", y=1.08), height=420)
            st.plotly_chart(fig, width="stretch")
            st.caption("Grootte van de marker = xG van het schot. Ster = doelpunt.")

        st.divider()
        st.subheader("Momentum")
        momentum = match_momentum(match)
        if momentum.empty:
            st.info("Geen momentum-data beschikbaar voor deze wedstrijd.")
        else:
            colors = [home_color if v >= 0 else away_color for v in momentum["value"]]
            fig = go.Figure()
            fig.add_bar(x=momentum["minute"], y=momentum["value"], marker_color=colors)
            style_chart(fig, height=260, showlegend=False)
            fig.update_yaxes(showticklabels=False, title="")
            fig.update_xaxes(title="Minuut")
            st.plotly_chart(fig, width="stretch")
            st.caption(f"Boven de lijn = momentum {home_team['name']}, onder = momentum {away_team['name']}.")

        st.divider()
        st.subheader("Opstellingen")
        lineup = match_lineup(match)
        col1, col2 = st.columns(2)
        for col, side in ((col1, "homeTeam"), (col2, "awayTeam")):
            team = lineup.get(side) or {}
            with col:
                st.markdown(f"**{team.get('name', '-')}** - {team.get('formation', '?')}")
                starters = team.get("starters", [])
                rows = [
                    {
                        "Nr": p.get("shirtNumber"),
                        "Naam": truncate_text(p.get("name", ""), 22),
                        "Rapportcijfer": (p.get("performance") or {}).get("rating"),
                    }
                    for p in starters
                ]
                st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=390)
                subs = team.get("subs", [])
                if subs:
                    sub_names = ", ".join(truncate_text(p.get("name", ""), 20) for p in subs)
                    st.caption(f"Bank: {sub_names}")
