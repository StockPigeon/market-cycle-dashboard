"""
Per-indicator signal logic.

Each indicator has a direction:
  higher_is_riskier=True  → high percentile = high cycle danger score (maps directly)
  higher_is_riskier=False → high percentile = LOW cycle danger score (invert: 100 - pct)

Special cases handled here:
  - VIX: LOW vix = complacency/late cycle danger → higher_is_riskier=False means
    invert, so low VIX → high danger score. Correct.
  - Yield curve: NEGATIVE spread = danger. We invert so low (negative) values
    map to high danger scores.
  - Consumer Sentiment: HIGH sentiment = complacency. Score: 100 - percentile.
  - AAII Bull-Bear: HIGH spread = bullish excess. Score: 100 - percentile.
"""
from src.data.schemas import IndicatorResult
from src.scoring.percentile import historical_percentile

import pandas as pd

LOOKBACK_YEARS = 15


def score_indicator(ind: IndicatorResult) -> IndicatorResult:
    """
    Populate ind.percentile, ind.score, ind.phase, and ind.trend.
    Returns the same object (mutated in place) for convenience.
    """
    if ind.error or ind.current_value is None or ind.series is None:
        ind.percentile = None
        ind.score = None
        ind.phase = None
        ind.trend = None
        return ind

    # --- Percentile (use per-indicator lookback if set) ---
    pct = historical_percentile(ind.series, ind.current_value, ind.lookback_years)
    ind.percentile = pct

    # --- Danger score (0-100, higher = more late-cycle / contraction risk) ---
    if ind.higher_is_riskier:
        danger = pct
    else:
        danger = 100.0 - pct

    ind.score = round(danger, 1)

    # --- Phase label ---
    ind.phase = _score_to_phase(danger)

    # --- Trend (delta vs prior observation) ---
    if len(ind.series) >= 2:
        ind.trend = float(ind.series.iloc[-1] - ind.series.iloc[-2])
    else:
        ind.trend = 0.0

    return ind


def _score_to_phase(score: float) -> str:
    if score < 25:
        return "Early"
    elif score < 50:
        return "Mid"
    elif score < 75:
        return "Late"
    else:
        return "Contraction"


PHASE_COLORS = {
    "Early": "#4CAF50",        # green
    "Mid": "#8BC34A",          # yellow-green
    "Late": "#FF9800",         # orange
    "Contraction": "#F44336",  # red
}

PHASE_BG_COLORS = {
    "Early": "rgba(76,175,80,0.15)",
    "Mid": "rgba(139,195,74,0.15)",
    "Late": "rgba(255,152,0,0.15)",
    "Contraction": "rgba(244,67,54,0.15)",
}
