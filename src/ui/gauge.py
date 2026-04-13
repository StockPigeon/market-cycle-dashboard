"""
Composite cycle gauge — a Plotly arc gauge showing 0-100 score.
Four colour zones: Early (green) → Mid (yellow-green) → Late (orange) → Contraction (red).
"""
import plotly.graph_objects as go
from src.data.schemas import CycleReading


def make_cycle_gauge(reading: CycleReading) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=reading.composite_score,
        number={
            "font": {"size": 48, "color": reading.phase_color},
            "suffix": "",
        },
        gauge={
            "axis": {
                "range": [0, 100],
                "tickwidth": 1,
                "tickcolor": "#555",
                "tickvals": [0, 25, 50, 75, 100],
                "ticktext": ["0", "25", "50", "75", "100"],
                "tickfont": {"color": "#aaa", "size": 11},
            },
            "bar": {"color": reading.phase_color, "thickness": 0.25},
            "bgcolor": "#1a1f2e",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 25],  "color": "rgba(76,175,80,0.25)"},
                {"range": [25, 50], "color": "rgba(139,195,74,0.20)"},
                {"range": [50, 75], "color": "rgba(255,152,0,0.25)"},
                {"range": [75, 100],"color": "rgba(244,67,54,0.30)"},
            ],
            "threshold": {
                "line": {"color": reading.phase_color, "width": 3},
                "thickness": 0.75,
                "value": reading.composite_score,
            },
        },
        title={
            "text": (
                f"<b>{reading.phase.upper()} CYCLE</b><br>"
                f"<span style='font-size:13px;color:#aaa'>"
                f"Composite Score</span>"
            ),
            "font": {"size": 18, "color": "#fafafa"},
            "align": "center",
        },
        domain={"x": [0, 1], "y": [0, 1]},
    ))

    fig.update_layout(
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        margin=dict(t=60, b=10, l=20, r=20),
        height=280,
        font={"color": "#fafafa"},
    )
    return fig


def make_mini_gauge(score: float, label: str, color: str) -> go.Figure:
    """Small gauge for category sub-scores."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={"font": {"size": 22, "color": color}, "suffix": ""},
        gauge={
            "axis": {"range": [0, 100], "visible": False},
            "bar": {"color": color, "thickness": 0.3},
            "bgcolor": "#1a1f2e",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 25],  "color": "rgba(76,175,80,0.2)"},
                {"range": [25, 50], "color": "rgba(139,195,74,0.15)"},
                {"range": [50, 75], "color": "rgba(255,152,0,0.2)"},
                {"range": [75, 100],"color": "rgba(244,67,54,0.25)"},
            ],
        },
        title={
            "text": f"<span style='font-size:11px;color:#aaa'>{label}</span>",
            "font": {"size": 11},
        },
        domain={"x": [0, 1], "y": [0, 1]},
    ))
    fig.update_layout(
        paper_bgcolor="#0e1117",
        margin=dict(t=30, b=0, l=5, r=5),
        height=130,
    )
    return fig
