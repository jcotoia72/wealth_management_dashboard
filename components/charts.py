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
