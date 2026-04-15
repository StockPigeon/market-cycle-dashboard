"""
Market data via yfinance (no API key needed).
Fetches VIX, S&P 500, and CBOE Put/Call ratio.
"""
import io
import requests
import pandas as pd
import streamlit as st
import yfinance as yf


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_vix(start: str = "2000-01-01") -> pd.Series:
    """VIX closing price."""
    ticker = yf.Ticker("^VIX")
    hist = ticker.history(start=start, auto_adjust=True)
    if hist.empty:
        raise ValueError("yfinance returned no VIX data.")
    s = hist["Close"].dropna()
    s.index = pd.to_datetime(s.index).tz_localize(None)
    s.name = "VIX"
    return s


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_sp500(start: str = "2000-01-01") -> pd.Series:
    """S&P 500 closing price."""
    ticker = yf.Ticker("^GSPC")
    hist = ticker.history(start=start, auto_adjust=True)
    if hist.empty:
        raise ValueError("yfinance returned no S&P 500 data.")
    s = hist["Close"].dropna()
    s.index = pd.to_datetime(s.index).tz_localize(None)
    s.name = "SP500"
    return s


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_put_call_ratio() -> pd.Series:
    """
    CBOE Equity Put/Call Ratio monthly average.
    Low = call buying frenzy = complacency = danger.
    High = put buying = fear = potential opportunity.
    Data from CBOE public CSV (no auth required).
    """
    url = "https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/equitypc.csv"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; market-cycle-monitor/1.0)"}
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text))
    # Normalise column names — CBOE uses "DATE", "CALL", "PUT", "TOTAL"
    df.columns = [c.strip().upper() for c in df.columns]
    if "DATE" not in df.columns or "CALL" not in df.columns or "PUT" not in df.columns:
        raise ValueError(f"Unexpected CBOE CSV columns: {list(df.columns)}")
    df["date"] = pd.to_datetime(df["DATE"], errors="coerce")
    df = df.dropna(subset=["date"]).set_index("date").sort_index()
    df["CALL"] = pd.to_numeric(df["CALL"], errors="coerce")
    df["PUT"] = pd.to_numeric(df["PUT"], errors="coerce")
    df = df.dropna(subset=["CALL", "PUT"])
    df = df[df["CALL"] > 0]
    pc = (df["PUT"] / df["CALL"]).resample("MS").mean()
    pc.name = "PUT_CALL"
    return pc.dropna()
