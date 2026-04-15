"""
Rolling historical percentile engine.
Converts a current value into its percentile rank within the trailing
`lookback_years` of history. This is the foundation of the scoring system.
"""
import numpy as np
import pandas as pd
from scipy import stats


def historical_percentile(
    series: pd.Series,
    current_value: float,
    lookback_years: int = 15,
) -> float:
    """
    Return the percentile rank (0-100) of `current_value` within all
    available history of `series` (expanding window).

    Using the full available history gives a consistent benchmark: a reading
    that was extreme in 2007 scores the same whether you're computing it in
    2007 or 2024. This keeps the gauge aligned with the composite history chart.

    `lookback_years` is retained for signature compatibility but not used.
    """
    if series is None or series.empty:
        return 50.0  # neutral fallback

    window = series.dropna()

    if len(window) < 2:
        return 50.0

    pct = stats.percentileofscore(window.values, current_value, kind="rank")
    return round(float(pct), 1)


def rolling_percentile_series(
    series: pd.Series,
    lookback_years: int = 15,
    resample_freq: str = "MS",
    expanding: bool = False,
) -> pd.Series:
    """
    Compute the rolling historical percentile at each point in time.
    Used to back-test the composite score history.
    Each value = percentile of that observation within the preceding
    `lookback_years` of data (or all available history if expanding=True).

    expanding=True uses an expanding window — each point is ranked against
    all data from the start of the series up to that date. This gives a more
    stable baseline for the composite history chart: e.g. 2006-07 credit
    tightness is judged against the full 1990-2007 history rather than just
    1991-2006, making late-cycle extremes register before recessions.

    Returns a monthly series aligned to `resample_freq`.
    """
    if series is None or series.empty:
        return pd.Series(dtype=float)

    monthly = series.resample(resample_freq).last()
    # Forward-fill up to 6 months so quarterly/lagging series (GDP, corp profits,
    # Buffett) contribute to recent months rather than going NaN between releases.
    monthly = monthly.ffill(limit=6).dropna()
    lookback_obs = lookback_years * 12  # approximate monthly observations

    pcts = []
    for i in range(len(monthly)):
        start = 0 if expanding else max(0, i - lookback_obs)
        window = monthly.iloc[start:i + 1]
        if len(window) < 2:
            pcts.append(50.0)
        else:
            val = window.iloc[-1]
            pct = stats.percentileofscore(window.values, val, kind="rank")
            pcts.append(round(float(pct), 1))

    return pd.Series(pcts, index=monthly.index)
