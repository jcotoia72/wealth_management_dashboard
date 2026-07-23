"""Service layer between the Monte Carlo engine and the Streamlit pages.

This module contains no Streamlit and no Plotly code. It turns raw widget values into
a validated :class:`RetirementInputs`, runs the model, and prepares plain tables and
sentences that any interface could render.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from models.monte_carlo import (
    RetirementInputs,
    SimulationResults,
    run_retirement_simulation,
)
from utils.assumptions import ASSUMPTION_NOTES
from utils.formatting import (
    format_age,
    format_currency,
    format_percent,
    round_to_nearest,
)
from utils.validation import validate_retirement_inputs

# Key used to store the latest results in Streamlit's session state. Defined here so
# every page refers to the same string.
RESULTS_SESSION_KEY = "latest_retirement_results"


def build_inputs(raw: dict[str, Any]) -> RetirementInputs:
    """Build a :class:`RetirementInputs` from a dictionary of widget values.

    Values are coerced to the correct types so that, for example, a Streamlit
    number_input returning ``65.0`` becomes a proper integer age.
    """
    return RetirementInputs(
        current_age=int(raw["current_age"]),
        retirement_age=int(raw["retirement_age"]),
        life_expectancy=int(raw["life_expectancy"]),
        current_savings=float(raw["current_savings"]),
        annual_contribution=float(raw["annual_contribution"]),
        contribution_growth_rate=float(raw["contribution_growth_rate"]),
        expected_return=float(raw["expected_return"]),
        volatility=float(raw["volatility"]),
        inflation_rate=float(raw["inflation_rate"]),
        annual_spending=float(raw["annual_spending"]),
        annual_other_income=float(raw["annual_other_income"]),
        withdrawal_timing=str(raw["withdrawal_timing"]),
        n_simulations=int(raw["n_simulations"]),
        random_seed=int(raw["random_seed"]),
        show_in_todays_dollars=bool(raw["show_in_todays_dollars"]),
    )


def validate(inputs: RetirementInputs) -> list[str]:
    """Return a list of validation errors (empty when the inputs are valid)."""
    return validate_retirement_inputs(inputs)


def run_projection(inputs: RetirementInputs) -> SimulationResults:
    """Run the Monte Carlo projection for the supplied inputs."""
    return run_retirement_simulation(inputs)


def build_assumptions_table(inputs: RetirementInputs) -> pd.DataFrame:
    """Return a two-column table of every assumption used in the projection."""
    dollar_basis = (
        "Today's dollars (inflation-adjusted)"
        if inputs.show_in_todays_dollars
        else "Nominal (future) dollars"
    )
    timing_label = (
        "Beginning of year (withdrawal taken before returns)"
        if inputs.withdrawal_timing == "beginning"
        else "End of year (withdrawal taken after returns)"
    )

    rows: list[tuple[str, str]] = [
        ("Current age", str(inputs.current_age)),
        ("Retirement age", str(inputs.retirement_age)),
        ("Life expectancy", str(inputs.life_expectancy)),
        ("Years until retirement", f"{inputs.years_to_retirement} years"),
        ("Years in retirement", f"{inputs.years_in_retirement} years"),
        ("Current retirement savings", format_currency(inputs.current_savings)),
        ("Annual contribution", format_currency(inputs.annual_contribution)),
        ("Annual contribution increase", format_percent(inputs.contribution_growth_rate)),
        ("Expected annual return (nominal)", format_percent(inputs.expected_return)),
        ("Annual volatility (standard deviation)", format_percent(inputs.volatility)),
        ("Annual inflation", format_percent(inputs.inflation_rate)),
        (
            "Desired retirement spending (today's dollars)",
            format_currency(inputs.annual_spending),
        ),
        (
            "Social Security / pension income (today's dollars)",
            format_currency(inputs.annual_other_income),
        ),
        (
            "Net first-year withdrawal need (today's dollars)",
            format_currency(max(0.0, inputs.annual_spending - inputs.annual_other_income)),
        ),
        ("Withdrawal timing", timing_label),
        ("Number of simulations", f"{inputs.n_simulations:,}"),
        ("Random seed", str(inputs.random_seed)),
        ("Results displayed in", dollar_basis),
        ("Return distribution", "Normal (independent annual draws)"),
    ]
    return pd.DataFrame(rows, columns=["Assumption", "Value"])


def build_methodology_notes() -> list[str]:
    """Return the plain-English modelling caveats shown under the assumptions."""
    return list(ASSUMPTION_NOTES.values())


def build_percentile_table(results: SimulationResults, step: int = 5) -> pd.DataFrame:
    """Return a formatted percentile-by-age table ready for display."""
    table = results.percentile_table(step=step)
    formatted = table.map(format_currency)
    formatted.columns = [
        "10th percentile",
        "25th percentile",
        "50th percentile (median)",
        "75th percentile",
        "90th percentile",
    ]
    formatted.index = [f"Age {age}" for age in table.index]
    formatted.index.name = "Age"
    return formatted


def build_success_summary_table(results: SimulationResults) -> pd.DataFrame:
    """Return a small success-versus-failure count table."""
    rows = [
        (
            "Successful simulations",
            f"{results.n_successes:,}",
            format_percent(results.success_probability),
        ),
        (
            "Failed simulations (money ran out)",
            f"{results.n_failures:,}",
            format_percent(results.failure_probability),
        ),
    ]
    return pd.DataFrame(rows, columns=["Outcome", "Simulations", "Share of total"])


def build_interpretation(results: SimulationResults) -> str:
    """Generate a short, plain-English summary based only on calculated results.

    The wording never promises an outcome; it describes what the simulations showed
    and reminds the reader that results follow directly from the assumptions.
    """
    inputs = results.inputs
    basis = "in today's dollars" if inputs.show_in_todays_dollars else "in future dollars"
    success_pct = format_percent(results.success_probability, decimals=0)
    median_end = format_currency(round_to_nearest(results.median_ending_balance))
    median_retire = format_currency(round_to_nearest(results.median_balance_at_retirement))
    p10_end = format_currency(round_to_nearest(results.ending_balance_percentile(10)))

    sentences = [
        f"Under the selected assumptions, the plan succeeded in {success_pct} of "
        f"{results.n_simulations:,} simulations, meaning the portfolio still held a "
        f"positive balance at age {inputs.life_expectancy}.",
        f"The median projected balance at retirement (age {inputs.retirement_age}) was "
        f"{median_retire}, and the median balance at age {inputs.life_expectancy} was "
        f"{median_end} {basis}.",
        f"In the weakest 10% of outcomes, the balance at age {inputs.life_expectancy} was "
        f"{p10_end} or less.",
    ]

    if results.n_failures > 0:
        sentences.append(
            f"Across the {results.n_failures:,} simulations that ran out of money, the "
            f"median depletion age was {results.median_depletion_age:.0f}."
        )
    else:
        sentences.append(
            "No simulation ran out of money before life expectancy under these assumptions."
        )

    sentences.append(
        "These figures are illustrative projections, not predictions. They depend "
        "heavily on the return, volatility, inflation and spending assumptions "
        "selected above, and small changes to those assumptions can move the results "
        "meaningfully."
    )
    return " ".join(sentences)


def build_planning_status(results: SimulationResults) -> tuple[str, str]:
    """Return a ``(status_label, explanation)`` pair for the Client Overview page.

    The thresholds below are a common planning convention: roughly 85%+ is treated as
    on track, 70-85% as worth monitoring, and below 70% as needing attention. They are
    a presentation choice, not a regulatory standard.
    """
    probability = results.success_probability
    if probability >= 0.85:
        return (
            "On track",
            "The plan succeeded in the large majority of simulations under the "
            "current assumptions.",
        )
    if probability >= 0.70:
        return (
            "Monitor",
            "The plan succeeded in most simulations, but the margin is thin enough "
            "that changes in spending, savings or market returns would matter.",
        )
    return (
        "Needs attention",
        "A meaningful share of simulations ran out of money before life expectancy. "
        "Reviewing the savings rate, retirement age or spending target would be "
        "a reasonable next step.",
    )


def build_client_snapshot(results: SimulationResults) -> list[tuple[str, str]]:
    """Return label/value pairs summarising the latest projection for a client view."""
    inputs = results.inputs
    return [
        ("Current age", str(inputs.current_age)),
        ("Retirement age", str(inputs.retirement_age)),
        ("Life expectancy", str(inputs.life_expectancy)),
        ("Current retirement savings", format_currency(inputs.current_savings)),
        ("Annual contribution", format_currency(inputs.annual_contribution)),
        ("Retirement success probability", format_percent(results.success_probability)),
        (
            "Median balance at retirement",
            format_currency(results.median_balance_at_retirement),
        ),
        ("Median ending balance", format_currency(results.median_ending_balance)),
        (
            "Median depletion age (failed simulations)",
            format_age(results.median_depletion_age),
        ),
    ]
