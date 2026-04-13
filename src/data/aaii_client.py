"""
AAII Investor Sentiment Survey — Bull/Bear spread.
Fetches the public XLS file that AAII publishes weekly.
No API key required. Requires User-Agent header to avoid 403.
"""
import io
import pandas as pd
import requests
import streamlit as st

AAII_URL = "https://www.aaii.com/files/surveys/sentiment.xls"


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_aaii_bull_bear_spread() -> pd.Series:
    """
    Returns the weekly Bull% - Bear% spread.
    Positive = net bullish (complacency risk), negative = net bearish (contrarian buy).
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        resp = requests.get(AAII_URL, headers=headers, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        raise ValueError(f"Could not fetch AAII data: {e}")

    # The XLS has a header block; actual data starts a few rows down.
    # Column layout (0-indexed): 0=date, 1=bullish%, 2=neutral%, 3=bearish%
    try:
        df = pd.read_excel(io.BytesIO(resp.content), sheet_name=0, header=None)
    except Exception as e:
        raise ValueError(f"Could not parse AAII XLS: {e}")

    # Find the first row where column 0 looks like a date
    start_row = None
    for i, val in enumerate(df.iloc[:, 0]):
        try:
            pd.to_datetime(val)
            start_row = i
            break
        except Exception:
            continue

    if start_row is None:
        raise ValueError("Could not locate data rows in AAII XLS.")

    data = df.iloc[start_row:, [0, 1, 3]].copy()
    data.columns = ["date", "bullish", "bearish"]
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data = data.dropna(subset=["date"])
    data["bullish"] = pd.to_numeric(data["bullish"], errors="coerce")
    data["bearish"] = pd.to_numeric(data["bearish"], errors="coerce")
    data = data.dropna()

    # Values are stored as decimals (0.45) in older files or whole numbers
    # Normalise: if median > 1, assume they are percentages already
    if data["bullish"].median() < 1:
        data["bullish"] *= 100
        data["bearish"] *= 100

    data = data.set_index("date").sort_index()
    spread = data["bullish"] - data["bearish"]
    spread.name = "AAII_SPREAD"
    return spread
