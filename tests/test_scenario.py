"""Tests for the scenario comparison and sensitivity engine.

Run from the project root with:
    pytest
"""

from __future__ import annotations

import numpy as np
import pytest

from models.comparison import (
    SENSITIVITY_FIELDS,
    Scenario,
    analyse_levers,
    build_variant,
    compare_scenarios,
    describe_differences,
    run_scenario,
    run_sensitivity,
    suggested_sweep_values,
)
from models.monte_carlo import RetirementInputs
from services.scenario_service import (
    build_comparison_narrative,
    build_comparison_table,
    build_difference_notes,
    build_lever_table,
)


def make_inputs(**overrides) -> RetirementInputs:
    """Build a valid baseline, applying any overrides. Small sim count for speed."""
    base = dict(
        current_age=35,
        retirement_age=65,
        life_expectancy=90,
        current_savings=150_000.0,
        annual_contribution=20_000.0,
        contribution_growth_rate=0.02,
        expected_return=0.07,
        volatility=0.15,
        inflation_rate=0.025,
        annual_spending=70_000.0,
        annual_other_income=25_000.0,
        withdrawal_timing="beginning",
        n_simulations=1_000,
        random_seed=42,
        show_in_todays_dollars=False,
    )
    base.update(overrides)
    return RetirementInputs(**base)


# ---------------------------------------------------------------------------
# Variant construction
# ---------------------------------------------------------------------------
def test_build_variant_does_not_mutate_the_base() -> None:
    """Variants must be copies; the baseline is reused for every comparison."""
    base = make_inputs()
    variant = build_variant(base, retirement_age=70)

    assert variant.retirement_age == 70
    assert base.retirement_age == 65
    assert variant is not base


def test_build_variant_preserves_untouched_fields() -> None:
    """Only the named fields change; everything else is held constant."""
    base = make_inputs()
    variant = build_variant(base, annual_spending=50_000.0)

    assert variant.annual_spending == 50_000.0
    assert variant.annual_contribution == base.annual_contribution
    assert variant.expected_return == base.expected_return
    assert variant.random_seed == base.random_seed


def test_invalid_variant_is_still_rejected() -> None:
    """Validation must survive the variant path, not just direct construction."""
    from utils.validation import ValidationError

    base = make_inputs()
    with pytest.raises(ValidationError):
        run_scenario("Impossible", build_variant(base, retirement_age=95))


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------
def test_run_scenario_returns_named_results() -> None:
    """A scenario carries its name, its inputs and its results together."""
    scenario = run_scenario("Baseline", make_inputs())

    assert scenario.name == "Baseline"
    assert scenario.inputs.retirement_age == 65
    assert 0.0 <= scenario.results.success_probability <= 1.0


def test_scenario_requires_a_name() -> None:
    """An unnamed scenario cannot be identified in a comparison."""
    with pytest.raises(ValueError):
        run_scenario("   ", make_inputs())


def test_identical_scenarios_produce_identical_results() -> None:
    """Reproducibility must hold through the scenario wrapper."""
    first = run_scenario("A", make_inputs())
    second = run_scenario("B", make_inputs())

    assert first.results.success_probability == second.results.success_probability
    np.testing.assert_array_equal(first.results.balances, second.results.balances)


def test_later_retirement_improves_success_probability() -> None:
    """Directional sanity: working longer cannot hurt the plan."""
    early = run_scenario("Retire 62", build_variant(make_inputs(), retirement_age=62))
    late = run_scenario("Retire 70", build_variant(make_inputs(), retirement_age=70))

    assert late.results.success_probability > early.results.success_probability


# ---------------------------------------------------------------------------
# Comparison tables
# ---------------------------------------------------------------------------
def test_compare_scenarios_has_one_row_per_scenario() -> None:
    """The raw comparison frame must line up with the scenarios supplied."""
    scenarios = [
        run_scenario("Baseline", make_inputs()),
        run_scenario("Retire later", build_variant(make_inputs(), retirement_age=68)),
    ]
    frame = compare_scenarios(scenarios)

    assert len(frame) == 2
    assert list(frame["Scenario"]) == ["Baseline", "Retire later"]
    assert "Success probability" in frame.columns


def test_compare_scenarios_handles_an_empty_list() -> None:
    """An empty comparison must return an empty frame, not raise."""
    assert compare_scenarios([]).empty


def test_display_table_is_transposed_with_scenarios_as_columns() -> None:
    """The display table puts scenarios in columns for easier metric scanning."""
    scenarios = [
        run_scenario("A", make_inputs()),
        run_scenario("B", build_variant(make_inputs(), retirement_age=68)),
    ]
    table = build_comparison_table(scenarios)

    assert list(table.columns) == ["A", "B"]
    assert "Success probability" in table.index
    # Assert on actual cell contents. An earlier version of this function returned the
    # correct labels with every value silently NaN, because pandas aligned Series on
    # their index instead of by position.
    assert not table.isna().any().any()
    assert table.loc["Retirement age", "A"] == "65"
    assert table.loc["Retirement age", "B"] == "68"
    assert table.loc["Success probability", "A"].endswith("%")


def test_describe_differences_reports_only_changed_fields() -> None:
    """Difference notes must not list assumptions that stayed the same."""
    base = run_scenario("Base", make_inputs())
    variant = run_scenario(
        "Variant", build_variant(make_inputs(), retirement_age=68, annual_spending=60_000.0)
    )
    differences = describe_differences(base, variant)

    assert any("Retirement age" in note for note in differences)
    assert any("Annual spending" in note for note in differences)
    assert not any("Inflation" in note for note in differences)


def test_difference_notes_flag_identical_scenarios() -> None:
    """Two identical scenarios should be called out as identical."""
    scenarios = [run_scenario("A", make_inputs()), run_scenario("B", make_inputs())]
    notes = build_difference_notes(scenarios)

    assert len(notes) == 1
    assert "identical" in notes[0].lower()


def test_narrative_requires_two_scenarios() -> None:
    """The comparison narrative must degrade gracefully with one scenario."""
    single = [run_scenario("Only", make_inputs())]
    assert "at least two" in build_comparison_narrative(single).lower()


def test_narrative_names_the_best_and_worst_scenario() -> None:
    """The summary must identify the strongest and weakest plan by name."""
    scenarios = [
        run_scenario("Weak", build_variant(make_inputs(), annual_contribution=0.0)),
        run_scenario("Strong", build_variant(make_inputs(), annual_contribution=60_000.0)),
    ]
    narrative = build_comparison_narrative(scenarios)

    assert "Strong" in narrative and "Weak" in narrative


# ---------------------------------------------------------------------------
# Sensitivity sweeps
# ---------------------------------------------------------------------------
def test_sensitivity_returns_one_point_per_valid_value() -> None:
    """Every tested value must produce exactly one recorded outcome."""
    sweep = run_sensitivity(
        make_inputs(), "retirement_age", [60, 63, 66, 69], n_simulations=1_000
    )

    assert len(sweep.values) == 4
    assert len(sweep.success_probabilities) == 4
    assert len(sweep.median_ending_balances) == 4
    assert sweep.skipped_values == []


def test_sensitivity_skips_invalid_values_instead_of_raising() -> None:
    """A sweep that crosses into invalid territory must survive it."""
    # Life expectancy is 90, so a retirement age of 95 is impossible.
    sweep = run_sensitivity(
        make_inputs(), "retirement_age", [65, 95], n_simulations=1_000
    )

    assert sweep.values == [65]
    assert sweep.skipped_values == [95]


def test_sensitivity_success_rises_with_retirement_age() -> None:
    """Sweeping retirement age upward must not reduce success probability."""
    sweep = run_sensitivity(
        make_inputs(), "retirement_age", [60, 64, 68, 72], n_simulations=2_000
    )

    assert sweep.is_monotonic_increasing


def test_sensitivity_success_falls_as_spending_rises() -> None:
    """Higher spending must weaken the plan."""
    sweep = run_sensitivity(
        make_inputs(),
        "annual_spending",
        [40_000.0, 70_000.0, 100_000.0],
        n_simulations=2_000,
    )

    assert sweep.success_probabilities[0] >= sweep.success_probabilities[-1]


def test_sensitivity_rejects_unknown_fields() -> None:
    """Only whitelisted fields may be swept."""
    with pytest.raises(ValueError):
        run_sensitivity(make_inputs(), "not_a_field", [1, 2, 3])


def test_sensitivity_frame_matches_the_recorded_values() -> None:
    """The tidy frame must carry the same data as the result object."""
    sweep = run_sensitivity(
        make_inputs(), "volatility", [0.05, 0.15, 0.25], n_simulations=1_000
    )
    frame = sweep.to_frame()

    assert len(frame) == 3
    assert list(frame.columns)[0] == sweep.label
    assert frame["Success probability"].tolist() == sweep.success_probabilities


def test_sweep_values_are_centred_on_the_current_value() -> None:
    """Suggested ranges must include the baseline so it appears on the chart."""
    base = make_inputs()
    ages = suggested_sweep_values(base, "retirement_age", points=9)

    assert len(ages) == 9
    assert float(base.retirement_age) in ages


def test_every_sensitivity_field_produces_usable_defaults() -> None:
    """Each supported field must generate a valid default sweep range."""
    base = make_inputs()
    for field_name in SENSITIVITY_FIELDS:
        values = suggested_sweep_values(base, field_name, points=5)
        assert len(values) == 5
        assert all(isinstance(value, float) for value in values)


# ---------------------------------------------------------------------------
# Lever analysis
# ---------------------------------------------------------------------------
def test_levers_are_sorted_by_impact() -> None:
    """The most effective change must come first."""
    levers = analyse_levers(make_inputs(), n_simulations=1_000)
    changes = [lever.change for lever in levers]

    assert changes == sorted(changes, reverse=True)


def test_levers_share_a_common_baseline() -> None:
    """Every lever must be measured against the same starting probability."""
    levers = analyse_levers(make_inputs(), n_simulations=1_000)
    baselines = {lever.baseline_probability for lever in levers}

    assert len(baselines) == 1


def test_levers_improve_a_struggling_plan() -> None:
    """On a plan with room to improve, the best lever must be a genuine gain."""
    weak = make_inputs(annual_contribution=5_000.0, annual_spending=90_000.0)
    levers = analyse_levers(weak, n_simulations=2_000)

    assert levers[0].change > 0


def test_lever_table_has_a_row_per_lever() -> None:
    """The display table must not drop or duplicate levers."""
    levers = analyse_levers(make_inputs(), n_simulations=1_000)
    table = build_lever_table(levers)

    assert len(table) == len(levers)
    assert "Change vs baseline" in table.columns


def test_lever_table_handles_an_empty_list() -> None:
    """No levers must produce an empty frame rather than an error."""
    assert build_lever_table([]).empty
