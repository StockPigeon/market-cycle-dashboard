"""
Full-history interactive charts with NBER recession shading.
"""
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.data.schemas import IndicatorResult

# NBER recession start/end dates (approximate monthly)
NBER_RECESSIONS = [
    ("1990-07-01", "1991-03-01"),
    ("2001-03-01", "2001-11-01"),
    ("2007-12-01", "2009-06-01"),
    ("2020-02-01", "2020-04-01"),
]


def _add_recession_shading(fig: go.Figure, y_min: float, y_max: float):
    for start, end in NBER_RECESSIONS:
        fig.add_vrect(
            x0=start, x1=end,
            fillcolor="rgba(200,60,60,0.12)",
            layer="below",
            line_width=0,
            annotation_text="Recession",
            annotation_position="top left",
            annotation_font_size=9,
            annotation_font_color="#aaa",
        )


def make_history_chart(
    ind: IndicatorResult,
    title: Optional[str] = None,
    height: int = 300,
) -> go.Figure:
    """Full-history line chart for a single indicator."""
    from typing import Optional

    series = ind.series
    phase_color = _phase_color(ind.phase)
    title = title or ind.name

    if series is None or series.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data available", x=0.5, y=0.5,
                           showarrow=False, font=dict(color="#aaa"))
        _style(fig, title, height)
        return fig

    fig = go.Figure()

    y_min = float(series.min())
    y_max = float(series.max())
    _add_recession_shading(fig, y_min, y_max)

    # Zero line for spread-type series
    if y_min < 0 < y_max:
        fig.add_hline(y=0, line_dash="dash", line_color="#555", line_width=1)

    fig.add_trace(go.Scatter(
        x=series.index,
        y=series.values,
        mode="lines",
        line=dict(color=phase_color, width=1.8),
        name=ind.name,
        hovertemplate=f"%{{x|%b %Y}}: %{{y:{ind.format_str.replace('{}','')}}}{ind.units}<extra></extra>",
    ))

    # Mark current value
    if ind.current_value is not None and ind.current_date is not None:
        fig.add_trace(go.Scatter(
            x=[ind.current_date],
            y=[ind.current_value],
            mode="markers",
            marker=dict(color=phase_color, size=8, line=dict(color="white", width=1.5)),
            name="Current",
            hovertemplate=f"Current: %{{y:.2f}}{ind.units}<extra></extra>",
        ))

    _style(fig, title, height)
    return fig


def make_composite_history_chart(composite: pd.Series, height: int = 320) -> go.Figure:
    """Chart for the back-calculated composite score history."""
    fig = go.Figure()

    _add_recession_shading(fig, 0, 100)

    # Phase zone fills
    for zone_min, zone_max, color, label in [
        (0,  25,  "rgba(76,175,80,0.12)",  "Early"),
        (25, 50,  "rgba(139,195,74,0.10)", "Mid"),
        (50, 75,  "rgba(255,152,0,0.12)",  "Late"),
        (75, 100, "rgba(244,67,54,0.14)",  "Contraction"),
    ]:
        fig.add_hrect(y0=zone_min, y1=zone_max, fillcolor=color,
                      line_width=0, layer="below")
        fig.add_annotation(x=composite.index[0], y=(zone_min + zone_max) / 2,
                           text=label, showarrow=False,
                           font=dict(size=9, color="#666"), xanchor="left")

    fig.add_trace(go.Scatter(
        x=composite.index,
        y=composite.values,
        mode="lines",
        line=dict(color="#64B5F6", width=2),
        name="Composite Score",
        hovertemplate="%{x|%b %Y}: %{y:.1f}<extra></extra>",
    ))

    _style(fig, "Composite Cycle Score History", height)
    fig.update_yaxes(range=[0, 100])
    return fig


def make_yield_curve_chart(ind: IndicatorResult, height: int = 300) -> go.Figure:
    """Special yield curve chart with inversion zones highlighted."""
    series = ind.series
    if series is None or series.empty:
        return make_history_chart(ind, height=height)

    fig = go.Figure()
    _add_recession_shading(fig, float(series.min()), float(series.max()))
    fig.add_hline(y=0, line_color="#F44336", line_width=1.5, line_dash="dash")

    # Split into positive and negative for dual colouring
    pos = series.where(series >= 0)
    neg = series.where(series < 0)

    fig.add_trace(go.Scatter(x=series.index, y=pos.values, mode="lines",
                             line=dict(color="#4CAF50", width=1.8),
                             fill="tozeroy", fillcolor="rgba(76,175,80,0.15)",
                             name="Normal (positive)"))
    fig.add_trace(go.Scatter(x=series.index, y=neg.values, mode="lines",
                             line=dict(color="#F44336", width=1.8),
                             fill="tozeroy", fillcolor="rgba(244,67,54,0.2)",
                             name="Inverted (negative)"))

    if ind.current_value is not None:
        fig.add_trace(go.Scatter(
            x=[ind.current_date], y=[ind.current_value],
            mode="markers",
            marker=dict(color="#F44336" if ind.current_value < 0 else "#4CAF50",
                        size=8, line=dict(color="white", width=1.5)),
            name="Current",
        ))

    _style(fig, "Yield Curve (10yr - 2yr Treasury Spread)", height)
    return fig


def _phase_color(phase: str) -> str:
    colors = {
        "Early": "#4CAF50",
        "Mid": "#8BC34A",
        "Late": "#FF9800",
        "Contraction": "#F44336",
    }
    return colors.get(phase, "#64B5F6")


def _style(fig: go.Figure, title: str, height: int):
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color="#ddd"), x=0),
        paper_bgcolor="#0e1117",
        plot_bgcolor="#1a1f2e",
        font=dict(color="#aaa"),
        height=height,
        margin=dict(t=40, b=30, l=40, r=20),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=10),
            orientation="h",
            y=-0.15,
        ),
        xaxis=dict(
            gridcolor="#252a3a",
            showgrid=True,
            zeroline=False,
        ),
        yaxis=dict(
            gridcolor="#252a3a",
            showgrid=True,
            zeroline=False,
        ),
        hovermode="x unified",
    )


