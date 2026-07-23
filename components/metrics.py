"""Reusable metric-card components.

Pages pass already-computed values here; these functions never calculate anything.
"""

from __future__ import annotations

from typing import Sequence

import streamlit as st

from models.monte_carlo import SimulationResults
from utils.formatting import format_age, format_currency, format_percent


def render_metric_row(metrics: Sequence[tuple[str, str, str]]) -> None:
    """Render a row of metric cards.

    Parameters
    ----------
    metrics:
        Sequence of ``(label, value, help_text)`` tuples. ``help_text`` may be empty.
    """
    columns = st.columns(len(metrics), gap="medium")
    for column, (label, value, help_text) in zip(columns, metrics):
        with column:
            st.metric(label=label, value=value, help=help_text or None)


def render_headline_metrics(results: SimulationResults) -> None:
    """Render the four headline metric cards for a completed projection."""
    basis = "today's dollars" if results.inputs.show_in_todays_dollars else "future dollars"
    render_metric_row(
        [
            (
                "Retirement success probability",
                format_percent(results.success_probability),
                "Share of simulations where the portfolio still had a positive balance "
                f"at age {results.inputs.life_expectancy}.",
            ),
            (
                f"Median balance at age {results.inputs.retirement_age}",
                format_currency(results.median_balance_at_retirement),
                f"Middle outcome of all simulations at retirement, in {basis}.",
            ),
            (
                f"Median balance at age {results.inputs.life_expectancy}",
                format_currency(results.median_ending_balance),
                f"Middle outcome of all simulations at life expectancy, in {basis}.",
            ),
            (
                "10th percentile ending balance",
                format_currency(results.ending_balance_percentile(10)),
                "90% of simulations ended above this figure; it represents a poor-market "
                "outcome rather than a worst case.",
            ),
        ]
    )


def render_failure_metrics(results: SimulationResults) -> None:
    """Render the success/failure breakdown metric cards."""
    depletion_age = results.median_depletion_age
    render_metric_row(
        [
            (
                "Successful simulations",
                f"{results.n_successes:,} of {results.n_simulations:,}",
                "Paths that never ran out of money.",
            ),
            (
                "Failed simulations",
                f"{results.n_failures:,} of {results.n_simulations:,}",
                "Paths where the portfolio reached zero before life expectancy.",
            ),
            (
                "Depleted before life expectancy",
                format_percent(results.failure_probability),
                "Percentage of all simulations that ran out of money.",
            ),
            (
                "Median depletion age",
                format_age(depletion_age) if depletion_age is not None else "None",
                "Median age at which money ran out, among failed simulations only.",
            ),
        ]
    )


def render_snapshot_metrics(snapshot: Sequence[tuple[str, str]], per_row: int = 4) -> None:
    """Render arbitrary label/value pairs as metric cards, wrapped across rows."""
    items = list(snapshot)
    for start in range(0, len(items), per_row):
        chunk = items[start : start + per_row]
        columns = st.columns(per_row, gap="medium")
        for column, (label, value) in zip(columns, chunk):
            with column:
                st.metric(label=label, value=value)
