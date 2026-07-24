"""Plotly chart builders.

Each function takes a :class:`SimulationResults` and returns a Plotly figure. Charts
never run calculations beyond the percentile helpers already exposed by the results
object, which keeps the financial logic in one place.
"""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from models.monte_carlo import SimulationResults
from utils.formatting import format_currency

# Muted, print-friendly palette suited to a financial-services deliverable.
COLOR_PATH = "rgba(120, 140, 160, 0.28)"
COLOR_BAND = "rgba(31, 90, 140, 0.16)"
COLOR_MEDIAN = "#1f5a8c"
COLOR_MARKER = "#8c5a1f"
COLOR_GRID = "#e3e8ee"

_LAYOUT_DEFAULTS = dict(
    template="simple_white",
    hovermode="x unified",
    margin=dict(l=70, r=30, t=60, b=60),
    font=dict(family="Helvetica Neue, Helvetica, Arial, sans-serif", size=13, color="#33414f"),
    title_font=dict(size=17, color="#14304a"),
    plot_bgcolor="white",
    paper_bgcolor="white",
)


def _dollar_basis_label(results: SimulationResults) -> str:
    """Return the axis label suffix describing the dollar basis."""
    return (
        "today's dollars" if results.inputs.show_in_todays_dollars else "nominal dollars"
    )


def portfolio_paths_chart(
    results: SimulationResults, n_paths: int = 150
) -> go.Figure:
    """Build the portfolio projection chart.

    Shows a readable sample of individual simulation paths, a shaded 10th-to-90th
    percentile band, the median path, and a vertical marker at the retirement age.
    """
    ages = results.ages
    percentiles = results.percentile_paths(percentiles=(10, 50, 90))

    # Sample paths deterministically from the seed so the chart is reproducible.
    rng = np.random.default_rng(results.inputs.random_seed)
    sample_size = min(n_paths, results.n_simulations)
    sample_indices = rng.choice(results.n_simulations, size=sample_size, replace=False)

    figure = go.Figure()

    for i, index in enumerate(sample_indices):
        figure.add_trace(
            go.Scatter(
                x=ages,
                y=results.balances[index],
                mode="lines",
                line=dict(color=COLOR_PATH, width=0.7),
                hoverinfo="skip",
                showlegend=(i == 0),
                name=f"Individual paths (sample of {sample_size:,})",
                legendgroup="paths",
            )
        )

    # 10th-90th percentile band, drawn as an upper line filled down to the lower line.
    figure.add_trace(
        go.Scatter(
            x=ages,
            y=percentiles["p90"],
            mode="lines",
            line=dict(width=0),
            hoverinfo="skip",
            showlegend=False,
            legendgroup="band",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=ages,
            y=percentiles["p10"],
            mode="lines",
            line=dict(width=0),
            fill="tonexty",
            fillcolor=COLOR_BAND,
            name="10th-90th percentile range",
            legendgroup="band",
            hovertemplate="Age %{x}<br>10th percentile: %{y:$,.0f}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=ages,
            y=percentiles["p50"],
            mode="lines",
            line=dict(color=COLOR_MEDIAN, width=2.6),
            name="Median path",
            hovertemplate="Age %{x}<br>Median: %{y:$,.0f}<extra></extra>",
        )
    )

    figure.add_vline(
        x=results.inputs.retirement_age,
        line=dict(color=COLOR_MARKER, width=1.6, dash="dash"),
    )
    figure.add_annotation(
        x=results.inputs.retirement_age,
        y=1.03,
        yref="paper",
        text=f"Retirement (age {results.inputs.retirement_age})",
        showarrow=False,
        font=dict(color=COLOR_MARKER, size=12),
        xanchor="left",
        xshift=6,
    )

    figure.update_layout(
        title=f"Projected portfolio balance by age ({_dollar_basis_label(results)})",
        xaxis_title="Age",
        yaxis_title=f"Portfolio balance ({_dollar_basis_label(results)})",
        legend=dict(orientation="h", yanchor="bottom", y=-0.24, xanchor="left", x=0),
        height=520,
        **_LAYOUT_DEFAULTS,
    )
    figure.update_yaxes(tickprefix="$", separatethousands=True, gridcolor=COLOR_GRID)
    figure.update_xaxes(gridcolor=COLOR_GRID)
    return figure


def ending_balance_histogram(
    results: SimulationResults, n_bins: int = 60, clip_percentile: float = 99.0
) -> go.Figure:
    """Build a histogram of ending balances at life expectancy.

    The top ``100 - clip_percentile`` percent of outcomes are grouped into the final
    bin so a handful of extreme paths do not flatten the visible distribution.
    """
    ending = results.ending_balances
    upper = float(np.percentile(ending, clip_percentile))
    clipped = np.minimum(ending, upper) if upper > 0 else ending

    figure = go.Figure(
        go.Histogram(
            x=clipped,
            nbinsx=n_bins,
            marker=dict(color=COLOR_MEDIAN, line=dict(color="white", width=0.6)),
            hovertemplate="Ending balance near %{x:$,.0f}<br>%{y:,} simulations<extra></extra>",
            name="Simulations",
        )
    )

    median_value = results.median_ending_balance
    figure.add_vline(
        x=median_value, line=dict(color=COLOR_MARKER, width=1.8, dash="dash")
    )
    figure.add_annotation(
        x=median_value,
        y=1.03,
        yref="paper",
        text=f"Median {format_currency(median_value)}",
        showarrow=False,
        font=dict(color=COLOR_MARKER, size=12),
        xanchor="left",
        xshift=6,
    )

    figure.update_layout(
        title=(
            f"Distribution of portfolio balance at age {results.inputs.life_expectancy} "
            f"({_dollar_basis_label(results)})"
        ),
        xaxis_title=f"Ending portfolio balance ({_dollar_basis_label(results)})",
        yaxis_title="Number of simulations",
        bargap=0.02,
        showlegend=False,
        height=420,
        **_LAYOUT_DEFAULTS,
    )
    figure.update_xaxes(tickprefix="$", separatethousands=True, gridcolor=COLOR_GRID)
    figure.update_yaxes(separatethousands=True, gridcolor=COLOR_GRID)
    return figure


def percentile_band_chart(results: SimulationResults) -> go.Figure:
    """Build a clean percentile-only view (no individual paths) for client handouts."""
    percentiles = results.percentile_paths()
    ages = results.ages

    figure = go.Figure()
    shading = {"p10": 0.10, "p25": 0.18, "p75": 0.18, "p90": 0.10}
    for column in ("p90", "p75", "p50", "p25", "p10"):
        is_median = column == "p50"
        figure.add_trace(
            go.Scatter(
                x=ages,
                y=percentiles[column],
                mode="lines",
                name=("Median" if is_median else f"{column[1:]}th percentile"),
                line=dict(
                    color=COLOR_MEDIAN,
                    width=2.6 if is_median else 1.2,
                    dash=None if is_median else "dot",
                ),
                opacity=1.0 if is_median else 0.55 + shading.get(column, 0.0),
                hovertemplate="Age %{x}<br>%{y:$,.0f}<extra></extra>",
            )
        )

    figure.add_vline(
        x=results.inputs.retirement_age,
        line=dict(color=COLOR_MARKER, width=1.6, dash="dash"),
    )
    figure.update_layout(
        title=f"Percentile outcomes by age ({_dollar_basis_label(results)})",
        xaxis_title="Age",
        yaxis_title=f"Portfolio balance ({_dollar_basis_label(results)})",
        legend=dict(orientation="h", yanchor="bottom", y=-0.24, xanchor="left", x=0),
        height=460,
        **_LAYOUT_DEFAULTS,
    )
    figure.update_yaxes(tickprefix="$", separatethousands=True, gridcolor=COLOR_GRID)
    figure.update_xaxes(gridcolor=COLOR_GRID)
    return figure


# ---------------------------------------------------------------------------
# Scenario comparison charts
# ---------------------------------------------------------------------------
# A colour-blind-safe qualitative palette, muted to suit a financial deliverable.
SCENARIO_COLORS = [
    "#1f5a8c",  # deep blue
    "#8c5a1f",  # ochre
    "#3d7a5a",  # green
    "#7a3d5a",  # plum
    "#5a5a8c",  # slate violet
    "#8c7a3d",  # olive
]


def scenario_median_paths_chart(scenarios: list) -> go.Figure:
    """Overlay the median projected path of several scenarios on one chart.

    Only median paths are shown. Drawing percentile bands for every scenario would
    produce overlapping shading that is impossible to read.
    """
    figure = go.Figure()

    for index, scenario in enumerate(scenarios):
        results = scenario.results
        color = SCENARIO_COLORS[index % len(SCENARIO_COLORS)]
        medians = results.percentile_paths(percentiles=(50,))["p50"]

        figure.add_trace(
            go.Scatter(
                x=results.ages,
                y=medians,
                mode="lines",
                name=scenario.name,
                line=dict(color=color, width=2.4),
                hovertemplate=f"{scenario.name}<br>Age %{{x}}<br>%{{y:$,.0f}}<extra></extra>",
            )
        )
        # Mark each scenario's own retirement age, since they may differ.
        figure.add_vline(
            x=results.inputs.retirement_age,
            line=dict(color=color, width=1.1, dash="dot"),
            opacity=0.55,
        )

    basis = (
        "today's dollars"
        if scenarios and scenarios[0].results.inputs.show_in_todays_dollars
        else "nominal dollars"
    )
    figure.update_layout(
        title=f"Median projected balance by scenario ({basis})",
        xaxis_title="Age",
        yaxis_title=f"Portfolio balance ({basis})",
        legend=dict(orientation="h", yanchor="bottom", y=-0.24, xanchor="left", x=0),
        height=500,
        **_LAYOUT_DEFAULTS,
    )
    figure.update_yaxes(tickprefix="$", separatethousands=True, gridcolor=COLOR_GRID)
    figure.update_xaxes(gridcolor=COLOR_GRID)
    return figure


def scenario_success_chart(scenarios: list) -> go.Figure:
    """Horizontal bar chart of success probability by scenario.

    Horizontal bars are used so long scenario names stay readable.
    """
    names = [scenario.name for scenario in scenarios]
    probabilities = [scenario.results.success_probability * 100 for scenario in scenarios]
    colors = [SCENARIO_COLORS[i % len(SCENARIO_COLORS)] for i in range(len(scenarios))]

    figure = go.Figure(
        go.Bar(
            x=probabilities,
            y=names,
            orientation="h",
            marker=dict(color=colors),
            text=[f"{value:.1f}%" for value in probabilities],
            textposition="outside",
            hovertemplate="%{y}<br>Success probability %{x:.1f}%<extra></extra>",
        )
    )
    figure.update_layout(
        title="Retirement success probability by scenario",
        xaxis_title="Success probability (%)",
        yaxis_title="",
        showlegend=False,
        height=max(260, 78 * len(scenarios)),
        **_LAYOUT_DEFAULTS,
    )
    figure.update_xaxes(range=[0, 108], ticksuffix="%", gridcolor=COLOR_GRID)
    figure.update_yaxes(autorange="reversed")
    return figure


def sensitivity_chart(sensitivity, baseline_value: float | None = None) -> go.Figure:
    """Plot success probability against the swept input value.

    A marker on the baseline value shows where the current plan sits on the curve.
    """
    probabilities = [value * 100 for value in sensitivity.success_probabilities]
    is_rate = sensitivity.field_name in {"expected_return", "volatility", "inflation_rate"}
    x_values = [v * 100 for v in sensitivity.values] if is_rate else sensitivity.values

    figure = go.Figure(
        go.Scatter(
            x=x_values,
            y=probabilities,
            mode="lines+markers",
            line=dict(color=COLOR_MEDIAN, width=2.6),
            marker=dict(size=7, color=COLOR_MEDIAN),
            name="Success probability",
            hovertemplate="%{x}<br>Success probability %{y:.1f}%<extra></extra>",
        )
    )

    if baseline_value is not None:
        marker_x = baseline_value * 100 if is_rate else baseline_value
        figure.add_vline(
            x=marker_x, line=dict(color=COLOR_MARKER, width=1.6, dash="dash")
        )
        figure.add_annotation(
            x=marker_x,
            y=1.03,
            yref="paper",
            text="Current plan",
            showarrow=False,
            font=dict(color=COLOR_MARKER, size=12),
            xanchor="left",
            xshift=6,
        )

    axis_title = f"{sensitivity.label} (%)" if is_rate else sensitivity.label
    figure.update_layout(
        title=f"Success probability versus {sensitivity.label.lower()}",
        xaxis_title=axis_title,
        yaxis_title="Success probability (%)",
        showlegend=False,
        height=430,
        **_LAYOUT_DEFAULTS,
    )
    figure.update_yaxes(range=[0, 105], ticksuffix="%", gridcolor=COLOR_GRID)
    figure.update_xaxes(gridcolor=COLOR_GRID)
    if not is_rate and sensitivity.field_name not in {"retirement_age", "life_expectancy"}:
        figure.update_xaxes(tickprefix="$", separatethousands=True)
    return figure


# ---------------------------------------------------------------------------
# Risk profile chart
# ---------------------------------------------------------------------------
def risk_gauge_chart(tolerance: float, capacity: float, overall: float) -> go.Figure:
    """Plot tolerance, capacity and overall scores on a shared 0-100 axis.

    A horizontal lollipop layout keeps the three scores directly comparable and makes
    the gap between tolerance and capacity — the point of the two-axis approach — easy
    to read at a glance.
    """
    labels = ["Risk tolerance", "Risk capacity", "Overall"]
    values = [tolerance, capacity, overall]
    colors = [COLOR_MEDIAN, "#3d7a5a", COLOR_MARKER]

    figure = go.Figure()

    # Shaded bands behind the markers, matching the four risk levels.
    band_edges = [(0, 35, "#eef1f4"), (35, 55, "#e7edf2"), (55, 75, "#dfe8ef"), (75, 100, "#d6e2ec")]
    for low, high, shade in band_edges:
        figure.add_vrect(x0=low, x1=high, fillcolor=shade, line_width=0, layer="below")

    for label, value, color in zip(labels, values, colors):
        figure.add_trace(
            go.Scatter(
                x=[0, value],
                y=[label, label],
                mode="lines",
                line=dict(color=color, width=3),
                hoverinfo="skip",
                showlegend=False,
            )
        )
        figure.add_trace(
            go.Scatter(
                x=[value],
                y=[label],
                mode="markers+text",
                marker=dict(color=color, size=16),
                text=[f"{value:.0f}"],
                textposition="middle right",
                textfont=dict(size=13, color="#33414f"),
                hovertemplate=f"{label}: {value:.0f} / 100<extra></extra>",
                showlegend=False,
            )
        )

    figure.update_layout(
        title="Risk scores on a 0-100 scale",
        xaxis_title="Score (higher = more risk-seeking)",
        yaxis_title="",
        height=300,
        **_LAYOUT_DEFAULTS,
    )
    figure.update_xaxes(range=[0, 108], gridcolor=COLOR_GRID)
    figure.update_yaxes(autorange="reversed")
    return figure
