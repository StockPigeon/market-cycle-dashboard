"""
Indicator card component.
Each card shows: name, current value, percentile badge, trend arrow,
phase colour pill, mini sparkline, and a drill-down expander with
scoring breakdown, source link, and verification guidance.
"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from typing import Optional

from src.data.schemas import IndicatorResult
from src.scoring.signals import PHASE_COLORS, PHASE_BG_COLORS


def _sparkline(series: pd.Series, phase_color: str) -> go.Figure:
    """24-month mini sparkline."""
    if series is None or series.empty:
        fig = go.Figure()
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=60, margin=dict(t=0, b=0, l=0, r=0),
        )
        return fig

    cutoff = series.index[-1] - pd.DateOffset(months=24)
    s = series[series.index >= cutoff].dropna()

    # Convert #RRGGBB hex to rgba() for Plotly fill colour compatibility
    def _hex_to_rgba(hex_color: str, alpha: float = 0.1) -> str:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"

    fill_color = _hex_to_rgba(phase_color, 0.12) if phase_color.startswith("#") else phase_color

    fig = go.Figure(go.Scatter(
        x=s.index, y=s.values,
        mode="lines",
        line=dict(color=phase_color, width=1.5),
        fill="tozeroy",
        fillcolor=fill_color,
        hovertemplate="%{x|%b %Y}: %{y:.3g}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=60,
        margin=dict(t=2, b=2, l=2, r=2),
    )
    return fig


def _trend_arrow(trend: Optional[float], higher_is_riskier: bool) -> str:
    if trend is None or trend == 0:
        return "<span style='color:#888'>→</span>"
    if trend > 0:
        color = "#F44336" if higher_is_riskier else "#4CAF50"
        return f"<span style='color:{color}'>↑</span>"
    else:
        color = "#4CAF50" if higher_is_riskier else "#F44336"
        return f"<span style='color:{color}'>↓</span>"


def _phase_badge_html(phase: str, color: str) -> str:
    return (
        f"<span style='"
        f"background:{color}33;color:{color};"
        f"border:1px solid {color}66;border-radius:4px;"
        f"padding:1px 7px;font-size:10px;font-weight:700;letter-spacing:0.5px;"
        f"'>{phase.upper()}</span>"
    )


def render_indicator_card(ind: IndicatorResult):
    """Render a single indicator card with drill-down."""
    phase = ind.phase or "Mid"
    phase_color = PHASE_COLORS.get(phase, "#888")
    phase_bg = PHASE_BG_COLORS.get(phase, "rgba(128,128,128,0.1)")

    with st.container():
        if ind.error or ind.current_value is None:
            _render_error_card(ind)
            return

        try:
            value_str = ind.format_str.format(ind.current_value)
        except Exception:
            value_str = f"{ind.current_value:.2f}"

        pct_str = f"{ind.percentile:.0f}th pctile" if ind.percentile is not None else "—"
        arrow = _trend_arrow(ind.trend, ind.higher_is_riskier)

        if ind.current_date is not None:
            try:
                date_str = pd.Timestamp(ind.current_date).strftime("%b %Y")
            except Exception:
                date_str = ""
        else:
            date_str = ""

        # ── Card face ──────────────────────────────────────────────────────
        st.markdown(f"""
<div style="
    background:{phase_bg};
    border:1px solid {phase_color}44;
    border-radius:8px;
    padding:12px 14px 6px 14px;
    margin-bottom:4px;
">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
    <span style="font-size:12px;color:#aaa;font-weight:500;letter-spacing:0.3px;">
      {ind.name.upper()}
    </span>
    {_phase_badge_html(phase, phase_color)}
  </div>
  <div style="display:flex;align-items:baseline;gap:6px;margin:4px 0 2px 0;">
    <span style="font-size:26px;font-weight:700;color:#fafafa;">{value_str}</span>
    <span style="font-size:13px;color:#888;">{ind.units}</span>
    <span style="font-size:16px;">{arrow}</span>
  </div>
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <span style="background:#ffffff11;color:#ccc;border-radius:3px;padding:1px 6px;font-size:11px;">
      {pct_str} · 15yr
    </span>
    <span style="font-size:11px;color:#666;">{date_str}</span>
  </div>
</div>
""", unsafe_allow_html=True)

        # Sparkline
        spark = _sparkline(ind.series, phase_color)
        st.plotly_chart(spark, use_container_width=True, config={"displayModeBar": False})

        # ── Drill-down expander ────────────────────────────────────────────
        with st.expander("🔍 Drill down", expanded=False):
            _render_drilldown(ind, phase, phase_color, value_str, date_str)


def _render_drilldown(
    ind: IndicatorResult,
    phase: str,
    phase_color: str,
    value_str: str,
    date_str: str,
):
    """Full detail panel: scoring breakdown + source link."""

    # ── What it measures ────────────────────────────────────────────────
    st.markdown(f"**What it measures**")
    st.caption(ind.description)

    st.markdown("---")

    # ── Scoring breakdown ───────────────────────────────────────────────
    st.markdown("**How the score is calculated**")

    danger_direction = "Higher value → more risk" if ind.higher_is_riskier else "Lower value → more risk"
    pct_val = f"{ind.percentile:.1f}th percentile" if ind.percentile is not None else "N/A"
    score_val = f"{ind.score:.1f} / 100" if ind.score is not None else "N/A"
    pct_formula = (
        f"percentile rank = {ind.percentile:.1f}th" if ind.higher_is_riskier
        else f"100 − {ind.percentile:.1f}th percentile = {ind.score:.1f}"
    ) if ind.percentile is not None else "N/A"

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""
<div style="background:#ffffff08;border-radius:6px;padding:8px 10px;text-align:center;">
  <div style="font-size:10px;color:#888;margin-bottom:2px;">CURRENT VALUE</div>
  <div style="font-size:18px;font-weight:700;color:#fafafa;">{value_str} <span style="font-size:11px;color:#666;">{ind.units}</span></div>
  <div style="font-size:10px;color:#666;">as of {date_str}</div>
</div>
""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
<div style="background:#ffffff08;border-radius:6px;padding:8px 10px;text-align:center;">
  <div style="font-size:10px;color:#888;margin-bottom:2px;">15-YEAR PERCENTILE</div>
  <div style="font-size:18px;font-weight:700;color:#fafafa;">{pct_val}</div>
  <div style="font-size:10px;color:#666;">{danger_direction}</div>
</div>
""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
<div style="background:{phase_color}22;border:1px solid {phase_color}44;border-radius:6px;padding:8px 10px;text-align:center;">
  <div style="font-size:10px;color:#888;margin-bottom:2px;">DANGER SCORE</div>
  <div style="font-size:18px;font-weight:700;color:{phase_color};">{score_val}</div>
  <div style="font-size:10px;color:{phase_color};opacity:0.8;">{phase} Cycle</div>
</div>
""", unsafe_allow_html=True)

    # Scoring logic explanation
    if ind.scoring_note:
        st.markdown(f"""
<div style="background:#ffffff06;border-left:3px solid {phase_color}88;border-radius:0 6px 6px 0;
     padding:8px 12px;margin-top:10px;font-size:12px;color:#bbb;line-height:1.5;">
{ind.scoring_note}
</div>
""", unsafe_allow_html=True)

    st.markdown("---")

    # ── Source verification ─────────────────────────────────────────────
    st.markdown("**Verify the source data**")

    col_src, col_btn = st.columns([3, 1])
    with col_src:
        st.markdown(f"""
<div style="font-size:12px;color:#888;margin-top:4px;">
  Source: <code style="background:#ffffff11;padding:1px 5px;border-radius:3px;color:#aaa;">
  {ind.source_name or "—"}
  </code>
</div>
""", unsafe_allow_html=True)
    with col_btn:
        if ind.source_url:
            st.link_button("Open source ↗", ind.source_url, use_container_width=True)

    # Show last 5 data points as a quick sanity-check table
    if ind.series is not None and not ind.series.empty:
        st.markdown("<div style='font-size:11px;color:#666;margin-top:8px;'>Recent observations (last 5):</div>",
                    unsafe_allow_html=True)
        recent = ind.series.dropna().tail(5).sort_index(ascending=False)
        rows = []
        for dt, val in recent.items():
            try:
                d = pd.Timestamp(dt).strftime("%b %d, %Y")
            except Exception:
                d = str(dt)
            try:
                v = ind.format_str.format(val) + f" {ind.units}"
            except Exception:
                v = f"{val:.4g} {ind.units}"
            rows.append({"Date": d, "Value": v})
        st.dataframe(
            rows,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Date": st.column_config.TextColumn("Date", width="medium"),
                "Value": st.column_config.TextColumn("Value", width="medium"),
            },
        )


def _render_error_card(ind: IndicatorResult):
    st.markdown(f"""
<div style="
    background:rgba(100,100,100,0.08);
    border:1px solid #333;
    border-radius:8px;
    padding:12px 14px;
    margin-bottom:4px;
">
  <span style="font-size:12px;color:#888;font-weight:500;">{ind.name.upper()}</span><br>
  <span style="font-size:13px;color:#555;margin-top:4px;display:block;">Data unavailable</span>
  <span style="font-size:11px;color:#444;">{ind.error or ''}</span>
</div>
""", unsafe_allow_html=True)
    if ind.source_url:
        with st.expander("🔍 Source", expanded=False):
            st.markdown(f"**Source:** {ind.source_name}")
            st.link_button("Open source ↗", ind.source_url)
            if ind.description:
                st.caption(ind.description)
