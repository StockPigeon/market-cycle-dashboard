"""
Market data via yfinance (no API key needed).
Fetches VIX and S&P 500 closing prices.
"""
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
