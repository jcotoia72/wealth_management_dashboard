"""Service layer for the Scenario Comparison module.

Mirrors :mod:`services.retirement_service`: no Streamlit, no Plotly. It formats the
raw comparison output for display and writes the plain-English commentary.
"""

from __future__ import annotations

import pandas as pd

from models.comparison import (
    LeverImpact,
    Scenario,
    SensitivityResult,
    compare_scenarios,
    describe_differences,
)
from utils.formatting import format_age, format_currency, format_percent

# Session-state key holding the list of saved scenarios. Defined here so the page and
# any future module refer to the same string.
SCENARIOS_SESSION_KEY = "comparison_scenarios"

# Holding full balance grids for many scenarios is memory-hungry (roughly 5 MB per
# 10,000-path scenario), so the page caps how many can be stored at once.
MAX_SCENARIOS = 6


def build_comparison_table(scenarios: list[Scenario]) -> pd.DataFrame:
    """Return a display-ready comparison table, one column per scenario.

    Scenarios are shown as columns rather than rows because a reader comparing plans
    scans down a single metric far more often than across a single plan.
    """
    raw = compare_scenarios(scenarios)
    if raw.empty:
        return raw

    # Build from plain lists rather than Series. Passing Series alongside a different
    # `index=` makes pandas align on labels rather than position, which silently
    # produces a table of NaN.
    formatted = pd.DataFrame(
        {
            "Retirement age": raw["Retirement age"].map(str).tolist(),
            "Annual contribution": raw["Annual contribution"].map(format_currency).tolist(),
            "Annual spending": raw["Annual spending"].map(format_currency).tolist(),
            "Success probability": raw["Success probability"].map(format_percent).tolist(),
            "Median balance at retirement": raw["Median balance at retirement"]
            .map(format_currency)
            .tolist(),
            "Median ending balance": raw["Median ending balance"]
            .map(format_currency)
            .tolist(),
            "10th percentile ending": raw["10th percentile ending"]
            .map(format_currency)
            .tolist(),
            "90th percentile ending": raw["90th percentile ending"]
            .map(format_currency)
            .tolist(),
            "Median depletion age": raw["Median depletion age"].map(format_age).tolist(),
        },
        index=raw["Scenario"].tolist(),
    )
    return formatted.transpose()


def build_difference_notes(scenarios: list[Scenario]) -> list[str]:
    """Describe how each scenario differs from the first one in the list."""
    if len(scenarios) < 2:
        return []
    base = scenarios[0]
    notes: list[str] = []
    for scenario in scenarios[1:]:
        differences = describe_differences(base, scenario)
        if differences:
            notes.append(f"**{scenario.name}** — {'; '.join(differences)}.")
        else:
            notes.append(
                f"**{scenario.name}** — identical assumptions to {base.name}; any "
                "difference in results is simulation noise."
            )
    return notes


def build_sensitivity_table(sensitivity: SensitivityResult) -> pd.DataFrame:
    """Return a display-ready version of a sensitivity sweep."""
    frame = sensitivity.to_frame()
    if frame.empty:
        return frame

    kind_is_rate = sensitivity.field_name in {
        "expected_return",
        "volatility",
        "inflation_rate",
    }
    kind_is_age = sensitivity.field_name in {"retirement_age", "life_expectancy"}

    if kind_is_rate:
        frame[sensitivity.label] = frame[sensitivity.label].map(format_percent)
    elif kind_is_age:
        frame[sensitivity.label] = frame[sensitivity.label].map(lambda v: f"{v:.0f}")
    else:
        frame[sensitivity.label] = frame[sensitivity.label].map(format_currency)

    frame["Success probability"] = frame["Success probability"].map(format_percent)
    frame["Median balance at retirement"] = frame["Median balance at retirement"].map(
        format_currency
    )
    frame["Median ending balance"] = frame["Median ending balance"].map(format_currency)
    return frame


def build_lever_table(levers: list[LeverImpact]) -> pd.DataFrame:
    """Return a table ranking each standardised change by its effect."""
    if not levers:
        return pd.DataFrame()
    rows = [
        {
            "Change": lever.name,
            "New success probability": format_percent(lever.new_probability),
            "Change vs baseline": f"{lever.change * 100:+.1f} pts",
            "Detail": lever.description,
        }
        for lever in levers
    ]
    return pd.DataFrame(rows)


def build_comparison_narrative(scenarios: list[Scenario]) -> str:
    """Write a short plain-English comparison of the saved scenarios."""
    if len(scenarios) < 2:
        return (
            "Save at least two scenarios to see a comparison. Each scenario is a full "
            "projection under a different set of assumptions."
        )

    ranked = sorted(scenarios, key=lambda s: s.results.success_probability, reverse=True)
    best, worst = ranked[0], ranked[-1]
    spread = best.results.success_probability - worst.results.success_probability

    sentences = [
        f"Of the {len(scenarios)} scenarios compared, **{best.name}** had the highest "
        f"success probability at {format_percent(best.results.success_probability)}, and "
        f"**{worst.name}** the lowest at "
        f"{format_percent(worst.results.success_probability)}.",
        f"That is a spread of {spread * 100:.1f} percentage points between the strongest "
        "and weakest plan.",
    ]

    if best.results.median_ending_balance > worst.results.median_ending_balance:
        sentences.append(
            f"The median balance at life expectancy ranged from "
            f"{format_currency(worst.results.median_ending_balance)} to "
            f"{format_currency(best.results.median_ending_balance)}."
        )

    sentences.append(
        "A higher success probability does not make a plan the right choice — retiring "
        "later or spending less improves the numbers but has real costs that the model "
        "does not measure. These figures are illustrative projections that depend "
        "entirely on the assumptions behind each scenario."
    )
    return " ".join(sentences)


def build_lever_narrative(levers: list[LeverImpact]) -> str:
    """Write a short summary of which single change helped most."""
    if not levers:
        return "No valid changes could be tested against this plan."

    best = levers[0]
    if best.change <= 0.001:
        return (
            "None of the standard changes meaningfully improved this plan. When the "
            "baseline already succeeds in nearly every simulation, there is little room "
            "left to improve."
        )

    lines = [
        f"The single most effective change tested was **{best.name.lower()}**, which "
        f"moved the success probability from "
        f"{format_percent(best.baseline_probability)} to "
        f"{format_percent(best.new_probability)}, a gain of "
        f"{best.change * 100:.1f} percentage points."
    ]
    if len(levers) > 1:
        weakest = levers[-1]
        lines.append(
            f"The least effective was {weakest.name.lower()}, at "
            f"{weakest.change * 100:+.1f} points."
        )
    lines.append(
        "Each change was applied on its own to the same baseline, so the effects are "
        "directly comparable but are not additive."
    )
    return " ".join(lines)
