"""
Page layout helpers — section headers, grid rendering, summary bar.
"""
import streamlit as st
import pandas as pd
from typing import List

from src.data.schemas import IndicatorResult, CycleReading
from src.scoring.signals import PHASE_COLORS
from src.ui.indicator_card import render_indicator_card


def render_section_header(title: str, subtitle: str = ""):
    st.markdown(f"""
<div style="margin:18px 0 10px 0;padding-bottom:6px;border-bottom:1px solid #2a2f3e;">
  <span style="font-size:14px;font-weight:700;color:#ddd;letter-spacing:0.5px;">
    {title.upper()}
  </span>
  {"<span style='font-size:11px;color:#666;margin-left:8px;'>" + subtitle + "</span>" if subtitle else ""}
</div>
""", unsafe_allow_html=True)


def render_category_grid(indicators: List[IndicatorResult], cols: int = 4):
    """Render a row of indicator cards in `cols` columns."""
    columns = st.columns(cols)
    for i, ind in enumerate(indicators):
        with columns[i % cols]:
            render_indicator_card(ind)


def render_recession_banner(reading: CycleReading):
    """Show recession warning banner if 3+ conditions are active."""
    if not reading.recession_warning:
        return

    active = [k for k, v in reading.recession_conditions.items() if v]
    inactive = [k for k, v in reading.recession_conditions.items() if not v]

    active_html = "".join(
        f"<span style='background:#F4433622;color:#F44336;border:1px solid #F4433644;"
        f"border-radius:3px;padding:1px 7px;font-size:11px;margin:2px;display:inline-block;'>"
        f"✓ {c}</span>" for c in active
    )
    inactive_html = "".join(
        f"<span style='background:#33333322;color:#555;border:1px solid #33333344;"
        f"border-radius:3px;padding:1px 7px;font-size:11px;margin:2px;display:inline-block;'>"
        f"✗ {c}</span>" for c in inactive
    )

    st.markdown(f"""
<div style="
    background:rgba(244,67,54,0.1);
    border:1px solid rgba(244,67,54,0.4);
    border-radius:8px;
    padding:12px 16px;
    margin-bottom:16px;
">
  <span style="color:#F44336;font-weight:700;font-size:14px;">
    ⚠ RECESSION WATCH — {reading.recession_conditions_active}/5 conditions active
  </span>
  <div style="margin-top:8px;">
    {active_html}
    {inactive_html}
  </div>
  <div style="font-size:11px;color:#888;margin-top:8px;">
    Warning triggers when 3 or more of 5 Howard Marks / macro-consensus conditions are simultaneously active.
  </div>
</div>
""", unsafe_allow_html=True)


def render_summary_bar(reading: CycleReading):
    """Category sub-score summary below the gauge."""
    cats = [
        ("Credit", reading.credit_score),
        ("Economy", reading.economy_score),
        ("Valuations", reading.valuations_score),
        ("Sentiment", reading.sentiment_score),
        ("Earnings", reading.earnings_score),
    ]
    cols = st.columns(len(cats))
    for col, (label, score) in zip(cols, cats):
        phase = _score_to_phase(score)
        color = PHASE_COLORS[phase]
        with col:
            st.markdown(f"""
<div style="text-align:center;padding:8px 4px;">
  <div style="font-size:11px;color:#888;margin-bottom:2px;">{label}</div>
  <div style="font-size:22px;font-weight:700;color:{color};">{score:.0f}</div>
  <div style="font-size:10px;color:{color};opacity:0.8;">{phase}</div>
</div>
""", unsafe_allow_html=True)


def render_data_freshness(reading: CycleReading):
    try:
        date_str = pd.Timestamp(reading.as_of_date).strftime("%b %d, %Y")
    except Exception:
        date_str = "unknown"
    st.caption(
        f"Stalest data: **{reading.stalest_indicator}** ({date_str}). "
        f"Quarterly indicators (GDP, Corp. Profits) update ~45 days after quarter end."
    )


def _score_to_phase(score: float) -> str:
    if score < 25:
        return "Early"
    elif score < 50:
        return "Mid"
    elif score < 75:
        return "Late"
    else:
        return "Contraction"
