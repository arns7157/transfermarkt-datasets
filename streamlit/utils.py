import ast
from pathlib import Path

import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "csv"


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
    df["age"] = pd.to_numeric(df["age"], errors="coerce")
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
