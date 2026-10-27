"""Reusable Plotly helpers, KPI cards and CSS for the sales dashboard."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

PALETTE = ["#0F766E", "#F59E0B", "#6366F1", "#EF4444", "#06B6D4", "#8B5CF6", "#EC4899", "#64748B"]
YEAR_COLORS = {"2023": "#94A3B8", "2024": "#06B6D4", "2025": "#0F766E"}
FONT = "Inter, Segoe UI, sans-serif"

CSS = """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1400px;}
.hero {background: linear-gradient(120deg,#0F766E 0%,#0891B2 55%,#6366F1 100%);
       padding: 1.6rem 2rem; border-radius: 18px; color: white; margin-bottom: 1.2rem;
       box-shadow: 0 10px 30px rgba(15,118,110,.25);}
.hero h1 {margin:0; font-size: 2rem; color:white;}
.hero p {margin:.3rem 0 0 0; opacity:.92; font-size:1rem;}
.kpi {background:white; border-radius:16px; padding:1rem 1.2rem; border:1px solid #E2E8F0;
      box-shadow:0 2px 10px rgba(15,23,42,.05); border-left:6px solid var(--accent,#0F766E);}
.kpi .label {font-size:.76rem; text-transform:uppercase; letter-spacing:.06em; color:#64748B; font-weight:600;}
.kpi .value {font-size:1.7rem; font-weight:700; color:#0F172A; line-height:1.25;}
.kpi .sub {font-size:.8rem; color:#64748B;}
.insight {background:#ECFEFF; border-left:5px solid #0891B2; padding:.7rem 1rem; border-radius:10px;
          margin-bottom:.55rem; color:#1E293B; font-size:.95rem;}
.insight.warn {background:#FEF2F2; border-left-color:#EF4444;}
.insight.good {background:#ECFDF5; border-left-color:#10B981;}
.insight.amber {background:#FFFBEB; border-left-color:#F59E0B;}
h3 {color:#134E4A;}
div[data-testid="stTabs"] button {font-weight:600;}
</style>
"""


def pkr(x: float, prefix: bool = True) -> str:
    """Compact PKR formatting: 8.73M, 412.5K, 980."""
    s = "PKR " if prefix else ""
    a = abs(x)
    if a >= 1e6:
        return f"{s}{x / 1e6:,.2f}M"
    if a >= 1e3:
        return f"{s}{x / 1e3:,.1f}K"
    return f"{s}{x:,.0f}"


def kpi(label: str, value: str, sub: str = "", accent: str = "#0F766E") -> str:
    return (f'<div class="kpi" style="--accent:{accent}"><div class="label">{label}</div>'
            f'<div class="value">{value}</div><div class="sub">{sub}&nbsp;</div></div>')


def insight(text: str, kind: str = "") -> str:
    return f'<div class="insight {kind}">{text}</div>'


def style(fig: go.Figure, height: int = 380, title: str | None = None) -> go.Figure:
    fig.update_layout(
        template="plotly_white", height=height, font=dict(family=FONT, size=13),
        margin=dict(l=10, r=10, t=50 if title else 20, b=10),
        title=dict(text=title, x=0.01, font=dict(size=16)) if title else None,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def bar_sum(df: pd.DataFrame, by: str, value: str = "NetSales", title: str | None = None,
            horizontal: bool = False, order: list | None = None, top: int | None = None,
            height: int = 380, color: str | None = None) -> go.Figure:
    g = df.groupby(by, observed=True)[value].sum().reset_index()
    if order:
        g[by] = pd.Categorical(g[by], categories=[o for o in order if o in set(g[by])], ordered=True)
        g = g.sort_values(by)
    else:
        g = g.sort_values(value, ascending=horizontal)
        if top:
            g = g.tail(top) if horizontal else g.head(top)
    g["Label"] = g[value].map(lambda v: pkr(v, prefix=False))
    if horizontal:
        fig = px.bar(g, x=value, y=by, orientation="h", text="Label", color=value,
                     color_continuous_scale=["#99F6E4", "#0F766E"])
    else:
        fig = px.bar(g, x=by, y=value, text="Label", color=value,
                     color_continuous_scale=["#99F6E4", "#0F766E"])
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_coloraxes(showscale=False)
    return style(fig, height, title)


def donut(df: pd.DataFrame, by: str, value: str = "NetSales", title: str | None = None,
          height: int = 340) -> go.Figure:
    g = df.groupby(by, observed=True)[value].sum().reset_index()
    fig = px.pie(g, names=by, values=value, hole=0.6, color_discrete_sequence=PALETTE)
    fig.update_traces(textinfo="percent+label", textposition="outside")
    fig.update_layout(showlegend=False)
    return style(fig, height, title)


def heatmap(pivot: pd.DataFrame, title: str | None = None, fmt: str = ",.0f", height: int = 400,
            scale: str = "Teal") -> go.Figure:
    fig = px.imshow(pivot, text_auto=fmt, aspect="auto", color_continuous_scale=scale)
    fig.update_coloraxes(showscale=False)
    return style(fig, height, title)
