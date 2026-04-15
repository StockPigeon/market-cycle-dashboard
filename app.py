"""
Market Cycle Monitor — Main Streamlit App
Based on Howard Marks' "Mastering the Market Cycle" framework.

Run locally:  streamlit run app.py
Deploy:       Push to GitHub → Streamlit Community Cloud → add FRED key in Secrets
"""
import streamlit as st
import pandas as pd
from datetime import datetime

# ── Page config must be first Streamlit call ──────────────────────────────────
st.set_page_config(
    page_title="Market Cycle Monitor",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Imports after page config ─────────────────────────────────────────────────
from src.data.indicators import load_all_indicators
from src.scoring.cycle_score import compute_cycle_reading, build_composite_history
from src.ui.gauge import make_cycle_gauge, make_mini_gauge
from src.ui.history_chart import (
    make_history_chart,
    make_composite_history_chart,
    make_yield_curve_chart,
)
from src.ui.layout import (
    render_section_header,
    render_category_grid,
    render_recession_banner,
    render_summary_bar,
    render_data_freshness,
)
from src.scoring.signals import PHASE_COLORS

# ── Global CSS tweaks ─────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Remove default Streamlit padding */
.block-container { padding-top: 1rem; padding-bottom: 2rem; }
/* Hide Streamlit branding */
#MainMenu, footer { visibility: hidden; }
/* Plotly chart spacing */
.stPlotlyChart { margin-bottom: -1rem; }
/* Expander styling */
.streamlit-expanderHeader { font-size: 11px !important; color: #666 !important; }
</style>
""", unsafe_allow_html=True)


# ── Cached data loading ───────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def get_indicators():
    return load_all_indicators()


@st.cache_data(ttl=3600, show_spinner=False)
def get_composite_history(indicators):
    return build_composite_history(indicators)


# ── Header ────────────────────────────────────────────────────────────────────

col_title, col_refresh = st.columns([5, 1])
with col_title:
    st.markdown("""
<h1 style="font-size:24px;font-weight:700;margin:0;color:#fafafa;">
  📊 Market Cycle Monitor
</h1>
<p style="font-size:12px;color:#666;margin:2px 0 0 0;">
  Based on Howard Marks' <em>Mastering the Market Cycle</em> · US Markets · Data via FRED &amp; yfinance
</p>
""", unsafe_allow_html=True)

with col_refresh:
    st.markdown("<div style='margin-top:10px;'>", unsafe_allow_html=True)
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

# Auto-refresh every hour (3600 seconds)
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=3_600_000, key="auto_refresh")
except ImportError:
    pass  # Optional — falls back to manual refresh only

st.markdown("<hr style='border-color:#1e2330;margin:8px 0 12px 0;'>", unsafe_allow_html=True)

# ── Load data with progress indicator ─────────────────────────────────────────

with st.spinner("Loading market data…"):
    indicators = get_indicators()

from src.scoring.cycle_score import compute_cycle_reading
reading = compute_cycle_reading(indicators)

# Group by category for layout
by_cat = {"credit": [], "economy": [], "valuations": [], "sentiment": [], "earnings": []}
for ind in indicators:
    from src.scoring.cycle_score import CATEGORY_MAP
    cat = CATEGORY_MAP.get(ind.id, ind.category)
    if cat in by_cat:
        by_cat[cat].append(ind)

# ── Recession warning banner ───────────────────────────────────────────────────
render_recession_banner(reading)

# ── Top section: Gauge + Summary ─────────────────────────────────────────────
gauge_col, summary_col = st.columns([1, 2])

with gauge_col:
    gauge_fig = make_cycle_gauge(reading)
    st.plotly_chart(gauge_fig, use_container_width=True, config={"displayModeBar": False})

with summary_col:
    phase_color = reading.phase_color
    st.markdown(f"""
<div style="padding:12px 0 0 16px;">
  <div style="font-size:13px;color:#aaa;font-weight:500;letter-spacing:0.5px;margin-bottom:4px;">
    CURRENT CYCLE PHASE
  </div>
  <div style="font-size:36px;font-weight:800;color:{phase_color};line-height:1.1;">
    {reading.phase.upper()} CYCLE
  </div>
  <div style="font-size:14px;color:#888;margin:6px 0 16px 0;">
    Composite score: <strong style="color:#ddd;">{reading.composite_score:.0f} / 100</strong>
    &nbsp;·&nbsp; Higher = more late-cycle / contraction risk
  </div>
</div>
""", unsafe_allow_html=True)

    render_summary_bar(reading)
    st.markdown("<div style='margin-top:8px;'>", unsafe_allow_html=True)
    render_data_freshness(reading)
    st.markdown("</div>", unsafe_allow_html=True)

    # Howard Marks context blurb
    with st.expander("📖 How to read this dashboard", expanded=False):
        st.markdown("""
**Cycle phases (0–100 danger score):**
- **0–25 Early Cycle** 🟢 — Recession is over or near. Credit is cheap, sentiment is low. This is historically the best time to deploy capital. Marks: *"The best returns are made when things move from terrible to merely bad."*
- **25–50 Mid Cycle** 🟡 — Economy expanding, earnings growing, sentiment improving. Solid risk-adjusted returns still available but alpha gets harder.
- **50–75 Late Cycle** 🟠 — Valuations stretched, credit spreads tight, sentiment optimistic. Marks: *"The market pendulum has swung to greed."* Reduce risk, tighten quality.
- **75–100 Contraction** 🔴 — Recession underway or imminent. Defensive positioning. Marks: *"When everyone believes something is risky, the unwillingness to buy usually reduces its price to the point where it's not risky at all."*

**Each indicator card** shows its current reading, where it sits in the last 15 years of history (percentile), and whether it's trending toward more or less risk.

**Recession Watch** fires when 3 of 5 leading indicators simultaneously signal stress — this has historically preceded each of the last four US recessions.

*Data refreshes automatically every hour. Click "Refresh Data" for an immediate update.*
        """)

st.markdown("<hr style='border-color:#1e2330;margin:14px 0;'>", unsafe_allow_html=True)

# ── Score Breakdown Table ─────────────────────────────────────────────────────
with st.expander("📊 Score Breakdown — how the composite is calculated", expanded=False):
    from src.scoring.cycle_score import CATEGORY_MAP, CATEGORY_WEIGHTS

    CAT_LABELS = {
        "credit":     "Credit & Liquidity",
        "economy":    "Economic Activity",
        "valuations": "Valuations",
        "sentiment":  "Sentiment & Psychology",
        "earnings":   "Earnings & Yield Curve",
    }

    # ── Indicator-level table ──────────────────────────────────────────────
    ind_rows = []
    for cat, weight in CATEGORY_WEIGHTS.items():
        cat_inds = by_cat.get(cat, [])
        valid = [i for i in cat_inds if i.score is not None]
        n = len(valid) if valid else 1
        cat_avg = sum(i.score for i in valid) / n if valid else 50.0

        for ind in cat_inds:
            if ind.score is not None:
                ind_contrib = round(ind.score / n * weight, 2)
            else:
                ind_contrib = None
            ind_rows.append({
                "Category": CAT_LABELS[cat],
                "Indicator": ind.name,
                "Value": (
                    ind.format_str.format(ind.current_value) + " " + ind.units
                    if ind.current_value is not None else "N/A"
                ),
                "Score": ind.score,
                "Phase": ind.phase or "N/A",
                "Contribution": ind_contrib,
            })

    df_ind = pd.DataFrame(ind_rows)

    def _score_color(val):
        if pd.isna(val):
            return "color: #666"
        if val < 25:
            return "color: #4CAF50"
        elif val < 50:
            return "color: #8BC34A"
        elif val < 75:
            return "color: #FF9800"
        else:
            return "color: #F44336"

    styled = (
        df_ind.style
        .applymap(_score_color, subset=["Score"])
        .format({"Score": "{:.1f}", "Contribution": "{:.2f}"}, na_rep="N/A")
    )
    st.dataframe(styled, use_container_width=True, hide_index=True, height=420)

    # ── Category rollup ────────────────────────────────────────────────────
    st.markdown("<div style='margin-top:12px;font-size:12px;color:#888;'>Category rollup → composite</div>",
                unsafe_allow_html=True)
    cat_rows = []
    for cat, weight in CATEGORY_WEIGHTS.items():
        cat_inds = by_cat.get(cat, [])
        valid = [i for i in cat_inds if i.score is not None]
        cat_avg = sum(i.score for i in valid) / len(valid) if valid else 50.0
        cat_rows.append({
            "Category": CAT_LABELS[cat],
            "Weight": f"{weight*100:.0f}%",
            "Category Avg Score": round(cat_avg, 1),
            "Weighted Points": round(cat_avg * weight, 2),
        })
    cat_rows.append({
        "Category": "COMPOSITE",
        "Weight": "100%",
        "Category Avg Score": None,
        "Weighted Points": reading.composite_score,
    })
    df_cat = pd.DataFrame(cat_rows)
    styled_cat = (
        df_cat.style
        .applymap(_score_color, subset=["Category Avg Score"])
        .format({
            "Category Avg Score": "{:.1f}",
            "Weighted Points": "{:.2f}",
        }, na_rep="—")
    )
    st.dataframe(styled_cat, use_container_width=True, hide_index=True)

st.markdown("<hr style='border-color:#1e2330;margin:14px 0;'>", unsafe_allow_html=True)

# ── Credit & Liquidity ────────────────────────────────────────────────────────
render_section_header(
    "Credit & Liquidity",
    "30% weight — Howard Marks' primary cycle driver"
)
render_category_grid(by_cat["credit"], cols=4)

# ── Economic Activity ─────────────────────────────────────────────────────────
render_section_header(
    "Economic Activity",
    "25% weight — leading & coincident indicators"
)
render_category_grid(by_cat["economy"], cols=4)

# ── Valuations ────────────────────────────────────────────────────────────────
render_section_header(
    "Valuations",
    "20% weight — are assets priced for risk or reward?"
)
render_category_grid(by_cat["valuations"], cols=3)

# ── Sentiment & Psychology ────────────────────────────────────────────────────
render_section_header(
    "Sentiment & Psychology",
    "15% weight — the risk attitude / pendulum"
)
render_category_grid(by_cat["sentiment"], cols=3)

# ── Earnings & Yield Curve ────────────────────────────────────────────────────
render_section_header(
    "Earnings & Yield Curve",
    "10% weight"
)
render_category_grid(by_cat["earnings"], cols=2)

st.markdown("<hr style='border-color:#1e2330;margin:14px 0;'>", unsafe_allow_html=True)

# ── Historical Charts ─────────────────────────────────────────────────────────
st.markdown("""
<h2 style="font-size:16px;font-weight:700;color:#ddd;margin-bottom:4px;">
  Historical Charts
</h2>
<p style="font-size:12px;color:#666;margin-bottom:12px;">
  Grey shading = NBER recessions. Click legend to show/hide traces.
</p>
""", unsafe_allow_html=True)

# Composite score history
with st.spinner("Building composite score history…"):
    composite_history = get_composite_history(indicators)

if not composite_history.empty:
    comp_fig = make_composite_history_chart(composite_history)
    st.plotly_chart(comp_fig, use_container_width=True, config={"displayModeBar": True})
else:
    st.info("Composite score history requires sufficient data across all indicators.")

# Yield curve chart
yc_ind = next((i for i in indicators if i.id == "yield_curve"), None)
if yc_ind and yc_ind.series is not None:
    yc_fig = make_yield_curve_chart(yc_ind)
    st.plotly_chart(yc_fig, use_container_width=True, config={"displayModeBar": True})

# HY Credit Spreads chart
hy_ind = next((i for i in indicators if i.id == "hy_spreads"), None)
if hy_ind and hy_ind.series is not None:
    hy_fig = make_history_chart(hy_ind, title="HY Credit Spreads (ICE BofA OAS)")
    st.plotly_chart(hy_fig, use_container_width=True, config={"displayModeBar": True})

# VIX history chart
vix_ind = next((i for i in indicators if i.id == "vix"), None)
if vix_ind and vix_ind.series is not None:
    vix_fig = make_history_chart(vix_ind, title="VIX — CBOE Volatility Index")
    st.plotly_chart(vix_fig, use_container_width=True, config={"displayModeBar": True})

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("<hr style='border-color:#1e2330;margin:20px 0 8px 0;'>", unsafe_allow_html=True)
st.markdown("""
<div style="font-size:11px;color:#444;text-align:center;padding-bottom:12px;">
  Market Cycle Monitor · Data: FRED (St. Louis Fed), CBOE via yfinance, AAII ·
  Inspired by Howard Marks' <em>Mastering the Market Cycle</em> ·
  <strong style="color:#555;">Not financial advice.</strong>
</div>
""", unsafe_allow_html=True)
