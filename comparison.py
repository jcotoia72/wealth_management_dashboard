"""Scenario comparison and sensitivity analysis engine.

Like :mod:`models.monte_carlo`, this module contains no Streamlit and no Plotly code.
It builds on the existing simulation engine rather than duplicating any financial
logic: a scenario is simply a named set of inputs plus the results they produced.

Public entry points
-------------------
    scenario   = run_scenario("Retire at 67", inputs)
    frame      = compare_scenarios([scenario_a, scenario_b])
    sweep      = run_sensitivity(inputs, "retirement_age", [62, 65, 68])
    levers     = analyse_levers(inputs)
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd

from models.monte_carlo import (
    RetirementInputs,
    SimulationResults,
    run_retirement_simulation,
)
from utils.validation import ValidationError, validate_retirement_inputs

# Fields a user may vary in a sensitivity sweep, mapped to a display label and whether
# the value is a rate (shown as a percentage) or a plain number.
SENSITIVITY_FIELDS: dict[str, dict[str, Any]] = {
    "retirement_age": {"label": "Retirement age", "kind": "age"},
    "annual_contribution": {"label": "Annual contribution", "kind": "currency"},
    "annual_spending": {"label": "Annual retirement spending", "kind": "currency"},
    "current_savings": {"label": "Current savings", "kind": "currency"},
    "annual_other_income": {"label": "Social Security / pension", "kind": "currency"},
    "expected_return": {"label": "Expected annual return", "kind": "rate"},
    "volatility": {"label": "Annual volatility", "kind": "rate"},
    "inflation_rate": {"label": "Annual inflation", "kind": "rate"},
    "life_expectancy": {"label": "Life expectancy", "kind": "age"},
}


@dataclass
class Scenario:
    """A named projection: the inputs used and the results they produced."""

    name: str
    inputs: RetirementInputs
    results: SimulationResults

    def summary_row(self) -> dict[str, Any]:
        """Return one flat row of headline statistics for a comparison table."""
        summary = self.results.summary()
        return {
            "Scenario": self.name,
            "Retirement age": self.inputs.retirement_age,
            "Annual contribution": self.inputs.annual_contribution,
            "Annual spending": self.inputs.annual_spending,
            "Success probability": summary["success_probability"],
            "Median balance at retirement": summary["median_balance_at_retirement"],
            "Median ending balance": summary["median_ending_balance"],
            "10th percentile ending": summary["p10_ending_balance"],
            "90th percentile ending": summary["p90_ending_balance"],
            "Median depletion age": summary["median_depletion_age"],
        }


@dataclass
class SensitivityResult:
    """Outcome of varying one input across a range of values.

    Only summary statistics are retained, not the full balance grids, so a sweep of
    twenty values stays cheap to hold in memory.
    """

    field_name: str
    label: str
    values: list[float]
    success_probabilities: list[float]
    median_ending_balances: list[float]
    median_retirement_balances: list[float]
    skipped_values: list[float] = field(default_factory=list)

    def to_frame(self) -> pd.DataFrame:
        """Return the sweep as a tidy DataFrame indexed by the varied value."""
        return pd.DataFrame(
            {
                self.label: self.values,
                "Success probability": self.success_probabilities,
                "Median balance at retirement": self.median_retirement_balances,
                "Median ending balance": self.median_ending_balances,
            }
        )

    @property
    def is_monotonic_increasing(self) -> bool:
        """Whether success probability rose consistently across the sweep."""
        values = np.asarray(self.success_probabilities)
        return bool(np.all(np.diff(values) >= -1e-9))


@dataclass
class LeverImpact:
    """The effect of one standardised change applied to a base plan."""

    name: str
    description: str
    baseline_probability: float
    new_probability: float

    @property
    def change(self) -> float:
        """Change in success probability, in decimal terms."""
        return self.new_probability - self.baseline_probability


def build_variant(base: RetirementInputs, **overrides: Any) -> RetirementInputs:
    """Return a copy of ``base`` with the supplied fields replaced.

    ``RetirementInputs`` is frozen, so this never mutates the original — which matters
    when several variants are derived from one baseline.
    """
    return replace(base, **overrides)


def run_scenario(name: str, inputs: RetirementInputs) -> Scenario:
    """Run a projection and wrap it as a named :class:`Scenario`."""
    if not name or not name.strip():
        raise ValueError("A scenario must have a non-empty name.")
    results = run_retirement_simulation(inputs)
    return Scenario(name=name.strip(), inputs=inputs, results=results)


def compare_scenarios(scenarios: Sequence[Scenario]) -> pd.DataFrame:
    """Return a raw numeric comparison table, one row per scenario.

    Values are left unformatted so the caller can decide how to display them; use
    :func:`services.scenario_service.build_comparison_table` for a display-ready version.
    """
    if not scenarios:
        return pd.DataFrame()
    return pd.DataFrame([scenario.summary_row() for scenario in scenarios])


def describe_differences(base: Scenario, other: Scenario) -> list[str]:
    """Describe, in plain terms, how ``other`` differs from ``base``.

    Only fields that actually changed are reported, which keeps the comparison honest
    when two scenarios differ in several ways at once.
    """
    differences: list[str] = []
    watched = {
        "retirement_age": "Retirement age",
        "current_age": "Current age",
        "life_expectancy": "Life expectancy",
        "current_savings": "Current savings",
        "annual_contribution": "Annual contribution",
        "contribution_growth_rate": "Contribution increase",
        "expected_return": "Expected return",
        "volatility": "Volatility",
        "inflation_rate": "Inflation",
        "annual_spending": "Annual spending",
        "annual_other_income": "Other income",
        "withdrawal_timing": "Withdrawal timing",
    }
    for attribute, label in watched.items():
        base_value = getattr(base.inputs, attribute)
        other_value = getattr(other.inputs, attribute)
        if base_value != other_value:
            differences.append(f"{label}: {base_value} to {other_value}")
    return differences


def run_sensitivity(
    base: RetirementInputs,
    field_name: str,
    values: Iterable[float],
    n_simulations: int | None = None,
) -> SensitivityResult:
    """Vary one input across ``values`` and record how the outcome responds.

    Parameters
    ----------
    base:
        The baseline inputs; every other assumption is held constant.
    field_name:
        Name of the field to vary. Must be a key of :data:`SENSITIVITY_FIELDS`.
    values:
        The values to test.
    n_simulations:
        Optional smaller simulation count for the sweep. A sweep runs one full
        projection per value, so reducing this keeps an interactive sweep responsive.

    Notes
    -----
    Values that produce an invalid plan (for example a retirement age above life
    expectancy) are skipped and reported in ``skipped_values`` rather than raising, so
    one bad point does not discard an otherwise useful sweep.
    """
    if field_name not in SENSITIVITY_FIELDS:
        raise ValueError(
            f"'{field_name}' is not a supported sensitivity field. "
            f"Choose one of: {', '.join(SENSITIVITY_FIELDS)}."
        )

    label = SENSITIVITY_FIELDS[field_name]["label"]
    tested: list[float] = []
    success: list[float] = []
    ending: list[float] = []
    at_retirement: list[float] = []
    skipped: list[float] = []

    for value in values:
        overrides: dict[str, Any] = {field_name: value}
        if n_simulations is not None:
            overrides["n_simulations"] = n_simulations
        candidate = build_variant(base, **overrides)

        # Skip rather than raise: a sweep across retirement ages will naturally cross
        # into invalid territory at the top end for a short life expectancy.
        if validate_retirement_inputs(candidate):
            skipped.append(value)
            continue

        results = run_retirement_simulation(candidate)
        tested.append(value)
        success.append(results.success_probability)
        ending.append(results.median_ending_balance)
        at_retirement.append(results.median_balance_at_retirement)

    return SensitivityResult(
        field_name=field_name,
        label=label,
        values=tested,
        success_probabilities=success,
        median_ending_balances=ending,
        median_retirement_balances=at_retirement,
        skipped_values=skipped,
    )


def analyse_levers(
    base: RetirementInputs,
    extra_years: int = 3,
    extra_contribution: float = 5_000.0,
    spending_reduction: float = 5_000.0,
    n_simulations: int | None = None,
) -> list[LeverImpact]:
    """Measure which single standardised change most improves the plan.

    Each lever is applied on its own to the same baseline, so the results are directly
    comparable. Returned sorted from largest improvement to smallest.
    """
    overrides: dict[str, Any] = {}
    if n_simulations is not None:
        overrides["n_simulations"] = n_simulations
    baseline_inputs = build_variant(base, **overrides) if overrides else base
    baseline = run_retirement_simulation(baseline_inputs).success_probability

    candidates: list[tuple[str, str, dict[str, Any]]] = [
        (
            f"Work {extra_years} more years",
            f"Retire at {base.retirement_age + extra_years} instead of {base.retirement_age}.",
            {"retirement_age": base.retirement_age + extra_years},
        ),
        (
            f"Save ${extra_contribution:,.0f} more per year",
            f"Contribute ${base.annual_contribution + extra_contribution:,.0f} annually.",
            {"annual_contribution": base.annual_contribution + extra_contribution},
        ),
        (
            f"Spend ${spending_reduction:,.0f} less per year",
            f"Target ${max(0.0, base.annual_spending - spending_reduction):,.0f} of annual spending.",
            {"annual_spending": max(0.0, base.annual_spending - spending_reduction)},
        ),
        (
            "Reduce portfolio volatility by 3 points",
            "Hold a less volatile allocation, with the expected return unchanged.",
            {"volatility": max(0.0, base.volatility - 0.03)},
        ),
    ]

    impacts: list[LeverImpact] = []
    for name, description, changes in candidates:
        changes.update(overrides)
        variant = build_variant(base, **changes)
        if validate_retirement_inputs(variant):
            continue
        probability = run_retirement_simulation(variant).success_probability
        impacts.append(
            LeverImpact(
                name=name,
                description=description,
                baseline_probability=baseline,
                new_probability=probability,
            )
        )

    return sorted(impacts, key=lambda impact: impact.change, reverse=True)


def suggested_sweep_values(base: RetirementInputs, field_name: str, points: int = 9) -> list[float]:
    """Return a sensible default range of values to sweep for a given field.

    The range is centred on the current value so the baseline is always visible in the
    resulting chart.
    """
    if field_name not in SENSITIVITY_FIELDS:
        raise ValueError(f"'{field_name}' is not a supported sensitivity field.")

    current = getattr(base, field_name)
    kind = SENSITIVITY_FIELDS[field_name]["kind"]

    if kind == "age":
        span = points // 2
        return [float(current - span + offset) for offset in range(points)]
    if kind == "rate":
        step = 0.01
        span = points // 2
        return [
            round(max(0.0, current + (offset - span) * step), 4) for offset in range(points)
        ]
    # Currency: sweep from half to one and a half times the current value.
    if current <= 0:
        return [float(step * 5_000) for step in range(points)]
    low, high = current * 0.5, current * 1.5
    return [round(value, 2) for value in np.linspace(low, high, points).tolist()]
