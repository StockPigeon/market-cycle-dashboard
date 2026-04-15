"""
FRED API client with Streamlit caching.
All fetches are cached for 1 hour (ttl=3600). The API key is read from
st.secrets["fred"]["api_key"] when running in Streamlit, and from the
FRED_API_KEY environment variable as a fallback for local dev without secrets.
"""
import io
import os
from typing import Optional

import pandas as pd
import requests
import streamlit as st
from fredapi import Fred


def _get_fred() -> Fred:
    """Return an authenticated Fred client."""
    try:
        api_key = st.secrets["fred"]["api_key"]
    except Exception:
        api_key = os.environ.get("FRED_API_KEY", "")
    if not api_key or api_key == "YOUR_FRED_API_KEY_HERE":
        raise ValueError(
            "FRED API key not configured. Add it to .streamlit/secrets.toml "
            "under [fred] api_key, or set the FRED_API_KEY environment variable."
        )
    return Fred(api_key=api_key)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_series(series_id: str, start: str = "1990-01-01") -> pd.Series:
    """Fetch a FRED series with up to 3 retries for transient 500 errors."""
    import time
    fred_client = _get_fred()
    last_err = None
    for attempt in range(3):
        try:
            raw = fred_client.get_series(series_id, observation_start=start)
            if raw is None or raw.empty:
                raise ValueError(f"FRED series {series_id} returned no data.")
            raw = raw.dropna()
            raw.index = pd.to_datetime(raw.index)
            raw.name = series_id
            return raw
        except Exception as e:
            last_err = e
            if "Internal Server Error" in str(e) and attempt < 2:
                time.sleep(1.5 * (attempt + 1))  # 1.5s, 3s
                continue
            raise
    raise last_err


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_gdp_yoy() -> pd.Series:
    """Real GDP YoY % change (quarterly)."""
    gdp = fetch_series("GDPC1")
    yoy = gdp.pct_change(4) * 100
    yoy.name = "GDP_YOY"
    return yoy.dropna()


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_unemployment_roc() -> pd.Series:
    """Unemployment rate 3-month rate-of-change (positive = worsening)."""
    unrate = fetch_series("UNRATE")
    roc = unrate.diff(3)
    roc.name = "UNRATE_ROC"
    return roc.dropna()


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_jobless_claims_trend() -> pd.Series:
    """
    Initial Jobless Claims 4-week moving average (IC4WSA), in thousands.
    Weekly frequency — one of the most timely US labour-market indicators.
    Rising trend = job market deteriorating = late-cycle / contraction risk.
    We use the YoY % change to normalise for seasonal and structural shifts.
    """
    claims = fetch_series("IC4WSA")   # weekly, seasonally adjusted, 4wk avg
    # YoY % change removes seasonal effects and long-term structural trends
    # Resample to monthly for stability
    monthly = claims.resample("MS").last()
    yoy = monthly.pct_change(12) * 100
    yoy.name = "CLAIMS_YOY"
    return yoy.dropna()


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_shiller_cape() -> pd.Series:
    """
    Shiller CAPE from Robert Shiller's Yale dataset (authoritative source).
    Fetches the public Excel file and returns a monthly series back to 1881.
    Cached for 24h (data updates monthly).
    """
    url = "http://www.econ.yale.edu/~shiller/data/ie_data.xls"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; market-cycle-monitor/1.0)"}
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        raise ValueError(f"Could not fetch Shiller data from Yale: {e}")

    try:
        # Sheet "Data", skip the first 7 rows of description
        df = pd.read_excel(io.BytesIO(resp.content), sheet_name="Data", header=7)
    except Exception as e:
        raise ValueError(f"Could not parse Shiller XLS: {e}")

    # Date column is stored as decimal year (e.g. 2024.01 = Jan 2024)
    # CAPE is in column "CAPE" or the 10th data column
    df = df.dropna(subset=[df.columns[0]])  # drop rows with no date
    date_col = df.columns[0]
    df = df[pd.to_numeric(df[date_col], errors="coerce").notna()].copy()
    df[date_col] = pd.to_numeric(df[date_col])

    # Convert decimal year to datetime: 2024.01 → 2024-01-01
    def decimal_to_date(d):
        year = int(d)
        month = round((d - year) * 100)
        if month == 0:
            month = 1
        return pd.Timestamp(year=year, month=month, day=1)

    df["date"] = df[date_col].apply(decimal_to_date)

    # Find CAPE column (labelled "CAPE" in the header)
    cape_col = None
    for col in df.columns:
        if str(col).upper().strip() == "CAPE":
            cape_col = col
            break
    if cape_col is None:
        # Fallback: CAPE is typically the 11th column (index 10)
        cape_col = df.columns[10]

    df[cape_col] = pd.to_numeric(df[cape_col], errors="coerce")
    df = df.dropna(subset=["date"])
    series = df.set_index("date")[cape_col].sort_index()
    series.name = "CAPE"
    # Remove zeroes (placeholder rows) then forward-fill to current month.
    # Shiller's XLS often trails by several months because CAPE uses trailing
    # 10-year real earnings which are finalised with a lag. CAPE changes slowly
    # (10-year smoothed metric), so forward-filling is a reasonable approximation.
    series = series.replace(0, float("nan"))
    series = series.dropna()
    # Extend the DatetimeIndex to the current month so ffill has dates to fill into
    today = pd.Timestamp.today().to_period("M").to_timestamp()
    if series.index[-1] < today:
        full_index = pd.date_range(series.index[0], today, freq="MS")
        series = series.reindex(full_index)
        series = series.ffill(limit=24)  # cap at 24 months of carry-forward
    series = series.dropna()
    return series


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_buffett_indicator() -> pd.Series:
    """
    S&P 500 / (Nominal GDP / 1000) — proxy for Market Cap / GDP.
    Uses FRED SP500 (monthly) and GDP (quarterly, interpolated to monthly).
    Approximates the Buffett Indicator closely for post-1957 data.
    (SP500 level / GDP in trillions ≈ total market cap % of GDP within ~10-15%.)
    """
    sp500 = fetch_series("SP500")          # monthly S&P 500 close
    gdp = fetch_series("GDP")              # nominal GDP, quarterly, $billions
    # Interpolate quarterly GDP to monthly
    gdp_monthly = gdp.resample("MS").interpolate(method="time")
    sp500_monthly = sp500.resample("MS").last()
    combined = pd.concat([sp500_monthly, gdp_monthly], axis=1).dropna()
    # SP500 / (GDP_billions / 1000) = SP500 / GDP_trillions
    # Historically: 2009 trough ~50, 2000 peak ~170, 2021 peak ~210
    buffett = combined.iloc[:, 0] / (combined.iloc[:, 1] / 1000)
    buffett.name = "BUFFETT"
    return buffett.dropna()


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_erp() -> pd.Series:
    """
    Equity Risk Premium: CAPE earnings yield minus 10-year Treasury yield.
    ERP = (1/CAPE)*100 - GS10
    Negative = stocks expensive relative to bonds.
    """
    cape = fetch_shiller_cape()
    gs10 = fetch_series("GS10")   # 10yr Treasury yield, monthly

    earnings_yield = (1.0 / cape) * 100
    ey_monthly = earnings_yield.resample("MS").last()
    gs10_monthly = gs10.resample("MS").last()
    combined = pd.concat([ey_monthly, gs10_monthly], axis=1).dropna()
    erp = combined.iloc[:, 0] - combined.iloc[:, 1]
    erp.name = "ERP"
    return erp


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_corp_profits_pct_gdp() -> pd.Series:
    """Corporate profits as % of GDP (quarterly)."""
    cp = fetch_series("CP")
    gdp = fetch_series("GDP")
    combined = pd.concat([cp, gdp], axis=1).dropna()
    ratio = (combined.iloc[:, 0] / combined.iloc[:, 1]) * 100
    ratio.name = "CORP_PROFITS_PCT"
    return ratio


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_feds_rate_roc() -> pd.Series:
    """Fed Funds Rate 12-month rate-of-change (positive = hiking cycle)."""
    ffr = fetch_series("FEDFUNDS")
    roc = ffr.diff(12)
    roc.name = "FFR_ROC"
    return roc.dropna()


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_hy_ig_ratio() -> pd.Series:
    """HY spread / IG spread ratio — low = complacency, high = fear."""
    hy = fetch_series("BAMLH0A0HYM2")
    ig = fetch_series("BAMLC0A0CM")
    combined = pd.concat([hy, ig], axis=1).dropna()
    ratio = combined.iloc[:, 0] / combined.iloc[:, 1]
    ratio.name = "HY_IG_RATIO"
    return ratio


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_m2_yoy() -> pd.Series:
    """M2 Money Supply YoY% change — rapid growth = excess liquidity = speculation fuel."""
    m2 = fetch_series("M2SL", start="1990-01-01")
    yoy = m2.pct_change(12) * 100
    yoy.name = "M2_YOY"
    return yoy.dropna()


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_business_applications_yoy() -> pd.Series:
    """Total Business Applications YoY% — spikes during speculative formation booms."""
    apps = fetch_series("BABATOTALSAUS", start="2004-01-01")
    yoy = apps.pct_change(12) * 100
    yoy.name = "BIZAPPS_YOY"
    return yoy.dropna()
