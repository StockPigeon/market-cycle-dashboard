"""
Weighted composite cycle score and recession warning flag.

Category weights (Howard Marks' emphasis on credit and psychology):
  Credit & Liquidity     30%
  Economic Activity      25%
  Valuations             20%
  Sentiment/Psychology   15%
  Earnings/Yield Curve   10%
"""
from typing import List, Dict
import pandas as pd

from src.data.schemas import IndicatorResult, CycleReading
from src.scoring.signals import score_indicator, _score_to_phase, PHASE_COLORS
from src.scoring.percentile import rolling_percentile_series

CATEGORY_WEIGHTS: Dict[str, float] = {
    "credit": 0.30,
    "economy": 0.25,
    "valuations": 0.20,
    "sentiment": 0.15,
    "earnings": 0.10,
}

# Indicator IDs → categories (for quick lookup)
CATEGORY_MAP: Dict[str, str] = {
    "hy_spreads": "credit",
    "hy_ig_ratio": "credit",
    "nfci": "credit",
    "ffr_roc": "credit",
    "gdp": "economy",
    "unemployment": "economy",
    "lei": "economy",
    "cfnai": "economy",
    "cape": "valuations",
    "buffett": "valuations",
    "erp": "valuations",
    "vix": "sentiment",
    "consumer_sentiment": "sentiment",
    "aaii": "sentiment",
    "yield_curve": "earnings",
    "corp_profits": "earnings",
    "m2_yoy": "credit",
    "put_call": "sentiment",
    "biz_apps": "sentiment",
}


def compute_cycle_reading(indicators: List[IndicatorResult]) -> CycleReading:
    """
    Score all indicators and compute the composite CycleReading.
    """
    # Score each indicator
    scored = [score_indicator(ind) for ind in indicators]

    # Collect valid scores per category
    category_scores: Dict[str, List[float]] = {k: [] for k in CATEGORY_WEIGHTS}
    for ind in scored:
        cat = CATEGORY_MAP.get(ind.id, ind.category)
        if ind.score is not None and cat in category_scores:
            category_scores[cat].append(ind.score)

    # Average within each category
    cat_averages: Dict[str, float] = {}
    for cat, scores in category_scores.items():
        if scores:
            cat_averages[cat] = sum(scores) / len(scores)
        else:
            cat_averages[cat] = 50.0  # neutral when no data

    # Weighted composite
    composite = sum(
        cat_averages[cat] * weight
        for cat, weight in CATEGORY_WEIGHTS.items()
    )
    composite = round(composite, 1)
    phase = _score_to_phase(composite)

    # Recession warning: 3+ of 5 conditions active
    recession_conditions = _check_recession_conditions(scored)
    n_active = sum(recession_conditions.values())
    recession_warning = n_active >= 3

    # Stalest indicator (oldest current_date)
    dated = [i for i in scored if i.current_date is not None]
    stalest = min(dated, key=lambda i: i.current_date).name if dated else "unknown"
    as_of = dated[-1].current_date if dated else pd.Timestamp.now()

    return CycleReading(
        composite_score=composite,
        phase=phase,
        phase_color=PHASE_COLORS[phase],
        credit_score=round(cat_averages["credit"], 1),
        economy_score=round(cat_averages["economy"], 1),
        valuations_score=round(cat_averages["valuations"], 1),
        sentiment_score=round(cat_averages["sentiment"], 1),
        earnings_score=round(cat_averages["earnings"], 1),
        recession_warning=recession_warning,
        recession_conditions_active=n_active,
        recession_conditions=recession_conditions,
        as_of_date=as_of,
        stalest_indicator=stalest,
    )


def _check_recession_conditions(indicators: List[IndicatorResult]) -> Dict[str, bool]:
    """
    Five Howard Marks / macro-consensus recession conditions.
    Return dict of {condition_name: bool}.
    """
    by_id = {ind.id: ind for ind in indicators}

    def get_series_value(ind_id: str):
        ind = by_id.get(ind_id)
        if ind and ind.current_value is not None:
            return ind.current_value, ind.series
        return None, None

    conditions = {}

    # 1. Yield curve inverted (negative) — use 3-month rolling mean for stability
    val, series = get_series_value("yield_curve")
    if series is not None and len(series) >= 63:
        three_month_avg = series.iloc[-63:].mean()  # ~63 trading days
        conditions["Yield curve inverted 3m+"] = three_month_avg < 0
    elif val is not None:
        conditions["Yield curve inverted 3m+"] = val < 0
    else:
        conditions["Yield curve inverted 3m+"] = False

    # 2. Jobless claims rising YoY for 2+ consecutive months (leading recession signal)
    val, series = get_series_value("lei")
    if series is not None and len(series) >= 2:
        recent = series.dropna().iloc[-2:]
        conditions["Jobless claims rising 2m+"] = bool((recent > 5).all())  # >5% YoY = meaningful rise
    elif val is not None:
        conditions["Jobless claims rising 2m+"] = val > 5
    else:
        conditions["Jobless claims rising 2m+"] = False

    # 3. CFNAI-MA3 below -0.7
    val, _ = get_series_value("cfnai")
    conditions["CFNAI-MA3 below -0.7"] = val is not None and val < -0.7

    # 4. Unemployment rising (3-month RoC > 0)
    val, _ = get_series_value("unemployment")
    conditions["Unemployment rising"] = val is not None and val > 0

    # 5. HY spreads above 500bps
    val, _ = get_series_value("hy_spreads")
    conditions["HY spreads > 500bps"] = val is not None and val > 500

    return conditions


def build_composite_history(indicators: List[IndicatorResult]) -> pd.Series:
    """
    Back-calculate composite score history (monthly, 2005-present).
    Uses rolling percentiles for each indicator, then applies weights.
    Computationally intensive — call once and cache the result.
    """
    category_series: Dict[str, List[pd.Series]] = {k: [] for k in CATEGORY_WEIGHTS}

    for ind in indicators:
        cat = CATEGORY_MAP.get(ind.id, ind.category)
        if ind.series is None or cat not in category_series:
            continue
        pct_series = rolling_percentile_series(ind.series, lookback_years=15, expanding=True)
        if ind.higher_is_riskier:
            danger_series = pct_series
        else:
            danger_series = 100.0 - pct_series
        category_series[cat].append(danger_series)

    # Average within categories
    cat_avg_series: Dict[str, pd.Series] = {}
    for cat, series_list in category_series.items():
        if not series_list:
            continue
        combined = pd.concat(series_list, axis=1).mean(axis=1)
        cat_avg_series[cat] = combined

    if not cat_avg_series:
        return pd.Series(dtype=float)

    # Weighted composite — align on common dates
    all_series = []
    weight_list = []
    for cat, weight in CATEGORY_WEIGHTS.items():
        if cat in cat_avg_series:
            all_series.append(cat_avg_series[cat] * weight)
            weight_list.append(weight)

    composite_df = pd.concat(all_series, axis=1)

    # Normalise by the sum of weights actually present for each date so that
    # months where some categories have no data (e.g. early in the series)
    # still produce a valid 0-100 score rather than being understated.
    present_weight = composite_df.notna().mul(weight_list).sum(axis=1).clip(lower=0.01)
    composite = composite_df.sum(axis=1, skipna=True) / present_weight
    composite.name = "Composite Score"

    # Restrict to 2005 onwards where data coverage is reasonable
    composite = composite[composite.index >= "2005-01-01"]
    return composite.dropna()
