"""
Central module that assembles all IndicatorResult objects.
Each function fetches its data and returns a populated IndicatorResult.
The main function `load_all_indicators()` collects them all.
Errors in individual indicators are caught and returned as error stubs
so one bad data source does not crash the whole dashboard.
"""
from typing import List
import pandas as pd

from src.data.schemas import IndicatorResult
from src.data import fred_client as fred
from src.data import market_client as mkt
from src.data import aaii_client as aaii


def _safe(fn, *args, **kwargs):
    """Run fn; return (result, None) or (None, error_string)."""
    try:
        return fn(*args, **kwargs), None
    except Exception as e:
        return None, str(e)


def _make_result(series: pd.Series, **kwargs) -> IndicatorResult:
    """Create an IndicatorResult from a Series, filling current value/date."""
    if series is not None and not series.empty:
        kwargs["series"] = series
        kwargs["current_value"] = float(series.iloc[-1])
        kwargs["current_date"] = series.index[-1]
    return IndicatorResult(**kwargs)


# ---------------------------------------------------------------------------
# Credit & Liquidity
# ---------------------------------------------------------------------------

def load_hy_spreads() -> IndicatorResult:
    s, err = _safe(fred.fetch_series, "BAMLH0A0HYM2")
    return _make_result(
        s,
        id="hy_spreads",
        name="HY Credit Spreads",
        category="credit",
        description=(
            "ICE BofA US High Yield Option-Adjusted Spread. "
            "Marks: tight spreads = investors not being paid for risk = complacency = danger. "
            "Wide spreads = fear is priced in = potential opportunity."
        ),
        units="bps",
        higher_is_riskier=False,
        format_str="{:.0f}",
        source_url="https://fred.stlouisfed.org/series/BAMLH0A0HYM2",
        source_name="FRED · BAMLH0A0HYM2",
        scoring_note=(
            "Lower spread = higher danger score (inverted). "
            "Howard Marks: when spreads are tight, investors aren't being paid to take risk — "
            "that IS the risk. Tight spreads (<300 bps) signal complacency and late-cycle conditions. "
            "Wide spreads (>600 bps) signal fear and potential opportunity. "
            "Note: the Recession Watch banner separately flags spreads >500 bps as a crisis signal. "
            "Score = 100 minus percentile rank within 15-year history."
        ),
        error=err,
    )


def load_ig_spreads() -> IndicatorResult:
    s, err = _safe(fred.fetch_series, "BAMLC0A0CM")
    return _make_result(
        s,
        id="ig_spreads",
        name="IG Credit Spreads",
        category="credit",
        description=(
            "ICE BofA US Corporate (Investment Grade) Option-Adjusted Spread. "
            "Used to compute the HY/IG ratio."
        ),
        units="bps",
        higher_is_riskier=True,
        format_str="{:.0f}",
        source_url="https://fred.stlouisfed.org/series/BAMLC0A0CM",
        source_name="FRED · BAMLC0A0CM",
        scoring_note="Internal series — used to calculate HY/IG ratio. Not shown as a standalone card.",
        error=err,
    )


def load_hy_ig_ratio() -> IndicatorResult:
    s, err = _safe(fred.fetch_hy_ig_ratio)
    return _make_result(
        s,
        id="hy_ig_ratio",
        name="HY/IG Spread Ratio",
        category="credit",
        description=(
            "Ratio of high-yield to investment-grade credit spreads. "
            "Low ratio = junk barely yields more than IG = investors ignoring credit risk = complacency. "
            "High ratio = fear; investors demanding much more for junk = risk-off."
        ),
        units="ratio",
        higher_is_riskier=False,
        format_str="{:.2f}",
        source_url="https://fred.stlouisfed.org/series/BAMLH0A0HYM2",
        source_name="FRED · BAMLH0A0HYM2 ÷ BAMLC0A0CM",
        scoring_note=(
            "Lower ratio = higher danger score (inverted). "
            "Computed as HY OAS (BAMLH0A0HYM2) divided by IG OAS (BAMLC0A0CM). "
            "When the ratio is low, junk debt is barely yielding more than investment grade — "
            "investors are not being compensated for credit risk, a hallmark of complacency. "
            "A high ratio signals fear and risk aversion (potential opportunity). "
            "Score = 100 minus percentile rank within 15-year history."
        ),
        error=err,
    )


def load_nfci() -> IndicatorResult:
    s, err = _safe(fred.fetch_series, "NFCI")
    return _make_result(
        s,
        id="nfci",
        name="Nat'l Financial Conditions",
        category="credit",
        description=(
            "Chicago Fed National Financial Conditions Index (weekly). "
            "Negative = loose/accommodative (early-to-mid cycle); "
            "positive = tight financial conditions."
        ),
        units="index",
        higher_is_riskier=True,
        format_str="{:.2f}",
        source_url="https://fred.stlouisfed.org/series/NFCI",
        source_name="FRED · NFCI",
        scoring_note=(
            "Higher (more positive) = higher danger score. "
            "The NFCI is a composite of 105 weekly measures of financial activity. "
            "Positive values = tighter-than-average conditions. "
            "Negative values = looser-than-average (accommodative for growth). "
            "Score = percentile rank within 15-year history."
        ),
        error=err,
    )


def load_ffr_roc() -> IndicatorResult:
    s, err = _safe(fred.fetch_feds_rate_roc)
    return _make_result(
        s,
        id="ffr_roc",
        name="Fed Funds Rate (12m change)",
        category="credit",
        description=(
            "Federal Funds Rate 12-month rate-of-change. "
            "Positive = hiking cycle (tightening, late-cycle risk). "
            "Negative = cutting cycle (easing, supportive of equities)."
        ),
        units="pp",
        higher_is_riskier=True,
        format_str="{:+.2f}",
        source_url="https://fred.stlouisfed.org/series/FEDFUNDS",
        source_name="FRED · FEDFUNDS",
        scoring_note=(
            "Higher 12-month change = higher danger score. "
            "Computed as current FFR minus FFR 12 months ago. "
            "A strongly positive reading means the Fed is actively tightening — "
            "historically associated with late-cycle and eventual slowdowns. "
            "Score = percentile rank within 15-year history."
        ),
        error=err,
    )


# ---------------------------------------------------------------------------
# Economic Activity
# ---------------------------------------------------------------------------

def load_gdp() -> IndicatorResult:
    s, err = _safe(fred.fetch_gdp_yoy)
    return _make_result(
        s,
        id="gdp",
        name="GDP Growth (YoY%)",
        category="economy",
        description=(
            "Real US GDP year-over-year % change (quarterly, ~45-day lag). "
            "Two consecutive negative quarters signals a technical recession."
        ),
        units="%",
        higher_is_riskier=False,
        format_str="{:+.1f}",
        source_url="https://fred.stlouisfed.org/series/GDPC1",
        source_name="FRED · GDPC1",
        scoring_note=(
            "Lower growth = higher danger score. "
            "Computed as (GDPC1 current quarter / GDPC1 4 quarters ago - 1) × 100. "
            "Score = 100 minus percentile rank within 15-year history. "
            "Note: GDP data is published with a ~45-day lag after quarter end — "
            "the date shown reflects the reference quarter, not the release date."
        ),
        error=err,
    )


def load_unemployment() -> IndicatorResult:
    s, err = _safe(fred.fetch_unemployment_roc)
    return _make_result(
        s,
        id="unemployment",
        name="Unemployment (3m change)",
        category="economy",
        description=(
            "US Unemployment Rate 3-month rate-of-change. "
            "Rising unemployment = contraction; falling = recovery/expansion."
        ),
        units="pp",
        higher_is_riskier=True,
        format_str="{:+.2f}",
        source_url="https://fred.stlouisfed.org/series/UNRATE",
        source_name="FRED · UNRATE",
        scoring_note=(
            "Rising unemployment (positive 3m change) = higher danger score. "
            "Computed as current UNRATE minus UNRATE 3 months ago. "
            "The Sahm Rule threshold: when the 3-month average rises ≥0.5pp above "
            "the prior 12-month low, a recession has typically already begun. "
            "Score = percentile rank within 15-year history."
        ),
        error=err,
    )


def load_lei() -> IndicatorResult:
    s, err = _safe(fred.fetch_jobless_claims_trend)
    return _make_result(
        s,
        id="lei",
        name="Jobless Claims (YoY%)",
        category="economy",
        description=(
            "Initial Jobless Claims 4-week avg, year-over-year % change. "
            "Weekly data — one of the most timely labour market signals. "
            "Rising claims (positive YoY%) = job market deteriorating = reduce risk."
        ),
        units="%",
        higher_is_riskier=True,
        format_str="{:+.1f}",
        source_url="https://fred.stlouisfed.org/series/IC4WSA",
        source_name="FRED · IC4WSA",
        scoring_note=(
            "Higher (more positive) YoY change = higher danger score. "
            "Rising jobless claims are a leading indicator — they turn up before the "
            "unemployment rate, and before GDP turns negative. "
            "Historically, sustained YoY increases of >10-15% have preceded every recession. "
            "Score = percentile rank within 15-year history."
        ),
        error=err,
    )


def load_cfnai() -> IndicatorResult:
    s, err = _safe(fred.fetch_series, "CFNAIMA3")
    return _make_result(
        s,
        id="cfnai",
        name="CFNAI 3-month Avg",
        category="economy",
        description=(
            "Chicago Fed National Activity Index 3-month moving average. "
            "Below -0.7 following a period of economic expansion signals "
            "an increasing likelihood of recession."
        ),
        units="index",
        higher_is_riskier=False,
        format_str="{:+.2f}",
        source_url="https://fred.stlouisfed.org/series/CFNAIMA3",
        source_name="FRED · CFNAIMA3",
        scoring_note=(
            "Lower (more negative) = higher danger score. "
            "CFNAI is a weighted average of 85 monthly indicators. "
            "A value of 0 = national economic activity at its historical trend. "
            "CFNAI-MA3 below -0.7 after expansion = elevated recession risk. "
            "Score = 100 minus percentile rank within 15-year history."
        ),
        error=err,
    )


# ---------------------------------------------------------------------------
# Valuations
# ---------------------------------------------------------------------------

def load_cape() -> IndicatorResult:
    s, err = _safe(fred.fetch_shiller_cape)
    return _make_result(
        s,
        id="cape",
        name="Shiller CAPE P/E",
        category="valuations",
        description=(
            "Cyclically Adjusted Price-to-Earnings ratio (Shiller). "
            "High CAPE = expensive market = elevated late-cycle risk. "
            "Long-run average ~17x. >30x is historically extreme."
        ),
        units="x",
        higher_is_riskier=True,
        format_str="{:.1f}",
        lookback_years=30,
        source_url="http://www.econ.yale.edu/~shiller/data.htm",
        source_name="Yale / Robert Shiller · ie_data.xls",
        scoring_note=(
            "Higher CAPE = higher danger score. "
            "Uses 10 years of inflation-adjusted S&P 500 earnings to smooth cycle noise. "
            "Long-run average ~17x; >30x is historically extreme. "
            "Uses a 30-year percentile window so the post-2008 era doesn't distort the baseline — "
            "markets have been expensive for 15 years, so a 15-year window would understate current risk. "
            "Score = percentile rank within 30-year history."
        ),
        error=err,
    )


def load_buffett() -> IndicatorResult:
    s, err = _safe(fred.fetch_buffett_indicator)
    return _make_result(
        s,
        id="buffett",
        name="S&P 500 / GDP (Buffett proxy)",
        category="valuations",
        description=(
            "S&P 500 index level divided by nominal GDP (trillions) — "
            "a proxy for the Buffett Indicator (total market cap / GDP). "
            "Historical benchmarks: ~50 = cheap (2009), ~110 = fair, ~200+ = expensive."
        ),
        units="ratio",
        higher_is_riskier=True,
        format_str="{:.0f}",
        lookback_years=30,
        source_url="https://fred.stlouisfed.org/series/SP500",
        source_name="FRED · SP500 ÷ (GDP/1000)",
        scoring_note=(
            "Higher ratio = higher danger score. "
            "Computed as S&P 500 monthly close (SP500) divided by nominal GDP in trillions (GDP÷1000). "
            "Tracks closely with the published Buffett Indicator: ~50 at the 2009 trough, ~210 at 2021 peak. "
            "Buffett: 'probably the best single measure of where valuations stand at any given moment.' "
            "Uses a 30-year lookback so the post-2008 era of elevated valuations doesn't distort the baseline. "
            "Score = percentile rank within 30-year history."
        ),
        error=err,
    )


def load_erp() -> IndicatorResult:
    s, err = _safe(fred.fetch_erp)
    return _make_result(
        s,
        id="erp",
        name="Equity Risk Premium",
        category="valuations",
        description=(
            "CAPE earnings yield minus 10-year Treasury yield. "
            "Negative = stocks are offering LESS return than risk-free bonds — "
            "a historically rare and reliable late-cycle danger signal."
        ),
        units="%",
        higher_is_riskier=False,
        format_str="{:+.2f}",
        lookback_years=30,
        source_url="https://fred.stlouisfed.org/series/GS10",
        source_name="Yale CAPE + FRED · GS10",
        scoring_note=(
            "Lower (more negative) ERP = higher danger score. "
            "Formula: (1 / CAPE) × 100 − 10-year Treasury yield (GS10). "
            "When negative: stocks yield less than Treasuries on an earnings basis — "
            "historically this has only occurred near major market peaks (1999-2000, 2021-2022). "
            "Uses a 30-year lookback for the same reason as CAPE. "
            "Score = 100 minus percentile rank within 30-year history."
        ),
        error=err,
    )


# ---------------------------------------------------------------------------
# Sentiment & Psychology
# ---------------------------------------------------------------------------

def load_vix() -> IndicatorResult:
    s, err = _safe(mkt.fetch_vix)
    return _make_result(
        s,
        id="vix",
        name="VIX (Fear Index)",
        category="sentiment",
        description=(
            "CBOE Volatility Index — measures expected 30-day S&P 500 volatility. "
            "Low VIX (<15) signals complacency; high VIX (>30) signals fear. "
            "Howard Marks: low fear = late cycle, high fear = opportunity."
        ),
        units="pts",
        higher_is_riskier=False,  # Low VIX = complacency = danger
        format_str="{:.1f}",
        source_url="https://finance.yahoo.com/quote/%5EVIX/",
        source_name="CBOE via Yahoo Finance · ^VIX",
        scoring_note=(
            "Lower VIX = higher danger score (inverted). "
            "Howard Marks: when everyone feels safe, risk is highest. "
            "A VIX below 12-13 historically marks periods of peak complacency. "
            "A VIX above 30-40 often represents peak fear — historically good entry points. "
            "Score = 100 minus percentile rank within 15-year history."
        ),
        error=err,
    )


def load_consumer_sentiment() -> IndicatorResult:
    s, err = _safe(fred.fetch_series, "UMCSENT")
    return _make_result(
        s,
        id="consumer_sentiment",
        name="Consumer Sentiment",
        category="sentiment",
        description=(
            "University of Michigan Consumer Sentiment Index. "
            "Extreme optimism can signal late-cycle complacency; "
            "extreme pessimism is often a contrarian buy signal."
        ),
        units="index",
        higher_is_riskier=True,
        format_str="{:.1f}",
        source_url="https://fred.stlouisfed.org/series/UMCSENT",
        source_name="FRED · UMCSENT",
        scoring_note=(
            "Higher sentiment = higher danger score. "
            "Extreme optimism (high readings ~90-100) = late-cycle complacency = reduce risk. "
            "Extreme pessimism (low readings near 50-60) has historically been a contrarian buy signal = add risk. "
            "Score = percentile rank within 15-year history."
        ),
        error=err,
    )


def load_aaii() -> IndicatorResult:
    s, err = _safe(aaii.fetch_aaii_bull_bear_spread)
    return _make_result(
        s,
        id="aaii",
        name="AAII Bull-Bear Spread",
        category="sentiment",
        description=(
            "AAII weekly individual investor sentiment: % Bullish minus % Bearish. "
            "Extreme positive readings = widespread optimism = late-cycle warning. "
            "Extreme negative = contrarian buy signal."
        ),
        units="pp",
        higher_is_riskier=True,
        format_str="{:+.1f}",
        source_url="https://www.aaii.com/sentimentsurvey",
        source_name="AAII Investor Sentiment Survey",
        scoring_note=(
            "Higher bull-bear spread = higher danger score. "
            "When individual investors are overwhelmingly bullish, markets tend to be overextended. "
            "Historically, spreads above +30pp have coincided with market peaks (reduce risk); "
            "spreads below -30pp with market troughs (add risk). "
            "Score = percentile rank within 15-year history."
        ),
        error=err,
    )


# ---------------------------------------------------------------------------
# Earnings & Yield Curve
# ---------------------------------------------------------------------------

def load_yield_curve() -> IndicatorResult:
    s, err = _safe(fred.fetch_series, "T10Y2Y")
    return _make_result(
        s,
        id="yield_curve",
        name="Yield Curve (10yr-2yr)",
        category="earnings",
        description=(
            "10-year minus 2-year US Treasury yield spread. "
            "Inversion (negative) is one of the most reliable leading recession "
            "indicators, typically preceding recession by 6-18 months."
        ),
        units="%",
        higher_is_riskier=False,
        format_str="{:+.2f}",
        source_url="https://fred.stlouisfed.org/series/T10Y2Y",
        source_name="FRED · T10Y2Y",
        scoring_note=(
            "Lower (more negative) spread = higher danger score. "
            "When short-term rates exceed long-term rates (inversion), banks "
            "tighten lending and economic growth typically slows 6-18 months later. "
            "Every US recession since 1955 has been preceded by an inversion. "
            "The Recession Watch banner uses a 3-month sustained inversion as its trigger. "
            "Score = 100 minus percentile rank within 15-year history."
        ),
        error=err,
    )


def load_corp_profits() -> IndicatorResult:
    s, err = _safe(fred.fetch_corp_profits_pct_gdp)
    return _make_result(
        s,
        id="corp_profits",
        name="Corp. Profits % of GDP",
        category="earnings",
        description=(
            "After-tax corporate profits as % of nominal GDP. "
            "High readings are historically mean-reverting — "
            "peak corporate margins often signal late-cycle conditions."
        ),
        units="%",
        higher_is_riskier=True,
        format_str="{:.1f}",
        source_url="https://fred.stlouisfed.org/series/CP",
        source_name="FRED · CP ÷ GDP",
        scoring_note=(
            "Higher profit share = higher danger score. "
            "Computed as after-tax corporate profits (CP) divided by nominal GDP. "
            "Corporate profits as a share of GDP mean-revert over time — "
            "when they reach historical peaks, margin compression tends to follow. "
            "Score = percentile rank within 15-year history."
        ),
        error=err,
    )


# ---------------------------------------------------------------------------
# Main loader
# ---------------------------------------------------------------------------

LOADERS = [
    load_hy_spreads,
    load_hy_ig_ratio,
    load_nfci,
    load_ffr_roc,
    load_gdp,
    load_unemployment,
    load_lei,
    load_cfnai,
    load_cape,
    load_buffett,
    load_erp,
    load_vix,
    load_consumer_sentiment,
    load_aaii,
    load_yield_curve,
    load_corp_profits,
]

# IG spreads is used internally by the ratio but not shown as a standalone card
INTERNAL_LOADERS = [load_ig_spreads]


def load_all_indicators() -> List[IndicatorResult]:
    """Load all displayable indicators. Errors are captured per-indicator."""
    results = []
    for loader in LOADERS:
        try:
            results.append(loader())
        except Exception as e:
            name = loader.__name__.replace("load_", "").replace("_", " ").title()
            results.append(IndicatorResult(
                id=loader.__name__,
                name=name,
                category="unknown",
                description="",
                units="",
                current_value=None,
                current_date=None,
                series=None,
                error=str(e),
            ))
    return results
