"""
Shared data contract for all indicator results.
Every data source produces IndicatorResult objects; every scoring/UI
module consumes them. Nothing else is shared between layers.
"""
from dataclasses import dataclass, field
from typing import Optional
import pandas as pd


@dataclass
class IndicatorResult:
    # Identity
    id: str                         # e.g. "hy_spreads"
    name: str                       # e.g. "HY Credit Spreads"
    category: str                   # "credit" | "economy" | "valuations" | "sentiment" | "earnings"
    description: str                # 1-2 sentences for tooltip
    units: str                      # e.g. "bps", "%", "index", "ratio"

    # Current reading
    current_value: Optional[float]  # Latest data point value
    current_date: Optional[pd.Timestamp]  # Date of latest data point

    # Historical series (full available history)
    series: Optional[pd.Series]     # DatetimeIndex → float

    # Scoring (populated by scoring engine)
    percentile: Optional[float] = None   # 0-100, 15-year rolling
    score: Optional[float] = None        # 0-100 cycle danger score
    phase: Optional[str] = None          # "Early" | "Mid" | "Late" | "Contraction"
    trend: Optional[float] = None        # delta vs prior period (same units as value)

    # Display config
    higher_is_riskier: bool = True   # True → high value = late cycle / contraction
    format_str: str = "{:.1f}"       # How to display current_value
    invert_display: bool = False     # Flip chart y-axis for display clarity
    lookback_years: int = 15         # Rolling window for percentile scoring

    # Source verification
    source_url: str = ""            # Direct link to the raw data series
    source_name: str = ""           # Short label for the source, e.g. "FRED · BAMLH0A0HYM2"
    scoring_note: str = ""          # Plain-English explanation of the scoring direction

    # Data quality
    error: Optional[str] = None     # Set if fetch failed; card shows "unavailable"
    is_stub: bool = False           # True for indicators with no free data source


@dataclass
class CycleReading:
    """Composite output from the scoring engine."""
    composite_score: float          # 0-100
    phase: str                      # "Early" | "Mid" | "Late" | "Contraction"
    phase_color: str                # hex colour for UI

    # Category sub-scores (0-100 each)
    credit_score: float
    economy_score: float
    valuations_score: float
    sentiment_score: float
    earnings_score: float

    # Recession warning flag
    recession_warning: bool
    recession_conditions_active: int   # count of 5 conditions that fired
    recession_conditions: dict         # {condition_name: bool}

    # Metadata
    as_of_date: pd.Timestamp
    stalest_indicator: str          # name of the indicator with oldest data
