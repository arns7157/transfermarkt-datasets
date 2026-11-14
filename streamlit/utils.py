import ast
from pathlib import Path

import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "csv"

POSITION_COLORS = {
    "Goalkeeper": "#F59E0B",
    "Defender": "#3B82F6",
    "Midfield": "#22C55E",
    "Attack": "#EF4444",
}

PAGE_ICONS = {
    "Spelers zoeken": "🔍",
    "Potentie": "🌱",
    "Spelerprofiel": "📊",
    "Vergelijken": "⚖️",
    "Signalen": "🚨",
}


def _read_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / f"{name}.csv.gz", compression="gzip", low_memory=False)


def _extract_club_name(value):
    """transfers.csv's from/to club columns sometimes hold a stringified
    API object instead of a plain name - pull clubName out of it."""
    if not isinstance(value, str) or not value.startswith("{"):
        return value
    try:
        parsed = ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return value
    return parsed.get("clubName", value) if isinstance(parsed, dict) else value


@st.cache_data(ttl=3600)
def load_players() -> pd.DataFrame:
    df = _read_csv("players")
    df["market_value_in_eur"] = pd.to_numeric(df["market_value_in_eur"], errors="coerce")
    df["highest_market_value_in_eur"] = pd.to_numeric(df["highest_market_value_in_eur"], errors="coerce")
    df["date_of_birth"] = pd.to_datetime(df["date_of_birth"], format="%d/%m/%Y", errors="coerce")
    df["contract_expiration_date"] = pd.to_datetime(df["contract_expiration_date"], format="%d/%m/%Y", errors="coerce")
    df["age"] = pd.to_numeric(df["age"], errors="coerce").round().astype("Int64")
    df["market_value_m"] = df["market_value_in_eur"] / 1_000_000
    return df


@st.cache_data(ttl=3600)
def load_clubs() -> pd.DataFrame:
    return _read_csv("clubs")


@st.cache_data(ttl=3600)
def load_competitions() -> pd.DataFrame:
    return _read_csv("competitions")


@st.cache_data(ttl=3600)
def load_transfers() -> pd.DataFrame:
    df = _read_csv("transfers")
    df["from_club_name"] = df["from_club_name"].map(_extract_club_name)
    df["to_club_name"] = df["to_club_name"].map(_extract_club_name)
    df["transfer_date"] = pd.to_datetime(df["transfer_date"], format="%d/%m/%Y", errors="coerce")
    return df


@st.cache_data(ttl=3600)
def load_valuations() -> pd.DataFrame:
    df = _read_csv("player_valuations")
    df["market_value_in_eur"] = pd.to_numeric(df["market_value_in_eur"], errors="coerce")
    df["date"] = pd.to_datetime(df["date"], format="%d/%m/%Y", errors="coerce")
    return df


@st.cache_data(ttl=3600)
def load_appearances() -> pd.DataFrame:
    df = _read_csv("appearances")
    df["date"] = pd.to_datetime(df["date"], format="%d/%m/%y", errors="coerce")
    for col in ("yellow_cards", "red_cards", "goals", "assists", "minutes_played"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def format_money(value) -> str:
    if pd.isna(value):
        return "–"
    value = float(value)
    sign = "-" if value < 0 else ""
    value = abs(value)
    if value >= 1_000_000:
        return f"{sign}€{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{sign}€{value / 1_000:.0f}K"
    return f"{sign}€{value:.0f}"


def player_label(row) -> str:
    club = row.get("current_club_name") or "onbekende club"
    return f"{row['name']} ({club})"


def position_badge(position: str) -> str:
    color = POSITION_COLORS.get(position, "#6B7280")
    label = position or "–"
    return (
        f'<span style="background:{color}22;color:{color};border:1px solid {color}55;'
        f'padding:1px 9px;border-radius:999px;font-size:0.78rem;font-weight:600;'
        f'white-space:nowrap;">{label}</span>'
    )


def inject_theme() -> None:
    st.markdown(
        """
        <style>
        #MainMenu, footer, header {visibility: hidden;}
        .block-container {padding-top: 2rem; max-width: 1200px;}
        div[data-testid="stMetric"] {
            background: #151B23;
            border: 1px solid #22293380;
            border-radius: 10px;
            padding: 14px 16px;
        }
        div[data-testid="stMetricValue"] {font-size: 1.6rem;}
        section[data-testid="stSidebar"] {border-right: 1px solid #222933;}
        .app-header {
            display: flex;
            align-items: baseline;
            gap: 10px;
            margin-bottom: 0.2rem;
        }
        .app-header h1 {margin: 0; font-size: 1.9rem;}
        .app-subtitle {color: #8B95A1; font-size: 0.95rem; margin-bottom: 1.4rem;}
        .pill-row {display: flex; gap: 6px; flex-wrap: wrap; margin: 4px 0 12px 0;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(title: str, subtitle: str = "") -> None:
    icon = PAGE_ICONS.get(title, "")
    st.markdown(
        f'<div class="app-header"><span style="font-size:1.7rem">{icon}</span>'
        f"<h1>{title}</h1></div>",
        unsafe_allow_html=True,
    )
    if subtitle:
        st.markdown(f'<div class="app-subtitle">{subtitle}</div>', unsafe_allow_html=True)


def current_season_appearances(appearances: pd.DataFrame) -> pd.DataFrame:
    """appearances.csv holds every season back to ~2014 - most 'this season'
    views should only look at matches from the current season onward."""
    dated = appearances.dropna(subset=["date"])
    if dated.empty:
        return dated
    season_start = season_start_for(dated["date"].max())
    return dated[dated["date"] >= season_start]


def season_start_for(date: pd.Timestamp) -> pd.Timestamp:
    """European football seasons roll over in July."""
    year = date.year if date.month >= 7 else date.year - 1
    return pd.Timestamp(year=year, month=7, day=1)


def compute_breakout_candidates(
    players: pd.DataFrame,
    appearances: pd.DataFrame,
    recent_days: int = 30,
    max_age: int = 23,
    min_recent_matches: int = 2,
) -> pd.DataFrame:
    """Flag players whose minutes or goal contribution are trending up this
    season: recently playing more, or recently starting to score/assist,
    compared to the earlier part of the same season."""
    dated = appearances.dropna(subset=["date"])
    if dated.empty:
        return players.iloc[0:0].copy()

    latest_date = dated["date"].max()
    season_start = season_start_for(latest_date)
    season_apps = dated[dated["date"] >= season_start]
    recent_cutoff = latest_date - pd.Timedelta(days=recent_days)
    recent = season_apps[season_apps["date"] >= recent_cutoff]
    earlier = season_apps[season_apps["date"] < recent_cutoff]

    def aggregate(df: pd.DataFrame) -> pd.DataFrame:
        g = df.groupby("player_id").agg(
            matches=("appearance_id", "count"),
            minutes=("minutes_played", "sum"),
            goals=("goals", "sum"),
            assists=("assists", "sum"),
        )
        g["avg_minutes"] = g["minutes"] / g["matches"]
        minutes_90 = (g["minutes"] / 90).replace(0, pd.NA)
        g["ga_per90"] = (g["goals"] + g["assists"]) / minutes_90
        return g.fillna(0.0)

    recent_agg = aggregate(recent).add_prefix("recent_")
    earlier_agg = aggregate(earlier).add_prefix("earlier_")

    merged = recent_agg.join(earlier_agg, how="left")
    for col in earlier_agg.columns:
        merged[col] = merged[col].fillna(0.0)
    merged = merged[merged["recent_matches"] >= min_recent_matches]

    merged["minutes_trend"] = merged["recent_avg_minutes"] - merged["earlier_avg_minutes"]
    merged["scoring_trend"] = merged["recent_ga_per90"] - merged["earlier_ga_per90"]
    merged["just_broke_through"] = merged["earlier_matches"] == 0

    merged["potential_score"] = (
        merged["minutes_trend"].clip(lower=0) / 90.0
        + merged["scoring_trend"].clip(lower=0) * 2.0
        + merged["just_broke_through"].astype(float) * 1.5
    )

    result = merged.join(players.set_index("player_id"), how="inner")
    result = result[result["age"] <= max_age]
    return result.sort_values("potential_score", ascending=False)
