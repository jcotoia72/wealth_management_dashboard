"""Tests for the Monte Carlo retirement engine and its validation rules.

Run from the project root with:
    pytest
"""

from __future__ import annotations

import numpy as np
import pytest

from models.monte_carlo import (
    RetirementInputs,
    SimulationResults,
    run_retirement_simulation,
)
from utils.validation import ValidationError, validate_retirement_inputs


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------
def make_inputs(**overrides) -> RetirementInputs:
    """Build a valid baseline :class:`RetirementInputs`, applying any overrides.

    A small simulation count keeps the suite fast; tests that depend on
    distributional accuracy override it explicitly.
    """
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
        n_simulations=2_000,
        random_seed=42,
        show_in_todays_dollars=False,
    )
    base.update(overrides)
    return RetirementInputs(**base)


@pytest.fixture(scope="module")
def baseline_results() -> SimulationResults:
    """A single baseline projection reused across several tests."""
    return run_retirement_simulation(make_inputs())


# ---------------------------------------------------------------------------
# 1. Reproducibility
# ---------------------------------------------------------------------------
def test_same_seed_produces_identical_results() -> None:
    """The same seed and inputs must reproduce results exactly."""
    first = run_retirement_simulation(make_inputs(random_seed=123))
    second = run_retirement_simulation(make_inputs(random_seed=123))

    np.testing.assert_array_equal(first.balances, second.balances)
    np.testing.assert_array_equal(first.annual_returns, second.annual_returns)
    assert first.success_probability == second.success_probability


def test_different_seeds_produce_different_results() -> None:
    """A different seed should produce a different set of random paths."""
    first = run_retirement_simulation(make_inputs(random_seed=1))
    second = run_retirement_simulation(make_inputs(random_seed=2))
    assert not np.array_equal(first.balances, second.balances)


# ---------------------------------------------------------------------------
# 2. Age validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "overrides",
    [
        {"current_age": 0},
        {"current_age": 65, "retirement_age": 65},
        {"current_age": 70, "retirement_age": 65},
        {"retirement_age": 65, "life_expectancy": 65},
        {"retirement_age": 70, "life_expectancy": 68},
    ],
)
def test_invalid_ages_are_rejected(overrides: dict) -> None:
    """Impossible age combinations must raise before any calculation runs."""
    inputs = make_inputs(**overrides)
    assert validate_retirement_inputs(inputs), "expected at least one validation error"
    with pytest.raises(ValidationError):
        run_retirement_simulation(inputs)


# ---------------------------------------------------------------------------
# 3. Negative financial inputs
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "field",
    [
        "current_savings",
        "annual_contribution",
        "annual_spending",
        "annual_other_income",
    ],
)
def test_negative_financial_inputs_are_rejected(field: str) -> None:
    """Negative dollar amounts must be rejected for every money field."""
    inputs = make_inputs(**{field: -1.0})
    errors = validate_retirement_inputs(inputs)
    assert any("cannot be negative" in message for message in errors)
    with pytest.raises(ValidationError):
        run_retirement_simulation(inputs)


def test_negative_volatility_is_rejected() -> None:
    """Volatility is a standard deviation and cannot be negative."""
    inputs = make_inputs(volatility=-0.05)
    with pytest.raises(ValidationError):
        run_retirement_simulation(inputs)


def test_simulation_count_bounds_are_enforced() -> None:
    """Simulation counts outside the accepted range must be rejected."""
    with pytest.raises(ValidationError):
        run_retirement_simulation(make_inputs(n_simulations=100))
    with pytest.raises(ValidationError):
        run_retirement_simulation(make_inputs(n_simulations=500_000))


def test_out_of_bounds_rates_are_rejected() -> None:
    """Return and inflation assumptions must stay within sensible bounds."""
    with pytest.raises(ValidationError):
        run_retirement_simulation(make_inputs(expected_return=0.95))
    with pytest.raises(ValidationError):
        run_retirement_simulation(make_inputs(inflation_rate=0.75))


# ---------------------------------------------------------------------------
# 4. Zero volatility is deterministic
# ---------------------------------------------------------------------------
def test_zero_volatility_produces_deterministic_returns() -> None:
    """With no volatility, every simulated return equals the expected return."""
    inputs = make_inputs(volatility=0.0, expected_return=0.06, n_simulations=1_000)
    results = run_retirement_simulation(inputs)

    assert np.allclose(results.annual_returns, 0.06)
    # Every path is then identical, so the spread of ending balances is zero.
    assert np.allclose(results.ending_balances, results.ending_balances[0])
    assert results.success_probability in (0.0, 1.0)


def test_zero_volatility_matches_hand_calculated_accumulation() -> None:
    """A no-volatility accumulation must match a closed-form compounding calculation.

    Convention being verified: the balance grows first, then the contribution is
    added at the end of the year.
    """
    inputs = make_inputs(
        current_age=60,
        retirement_age=63,
        life_expectancy=64,
        current_savings=100_000.0,
        annual_contribution=10_000.0,
        contribution_growth_rate=0.0,
        expected_return=0.05,
        volatility=0.0,
        n_simulations=1_000,
        show_in_todays_dollars=False,
    )
    results = run_retirement_simulation(inputs)

    expected = 100_000.0
    for _ in range(3):
        expected = expected * 1.05 + 10_000.0

    assert results.balances_at_retirement[0] == pytest.approx(expected, rel=1e-9)


# ---------------------------------------------------------------------------
# 5 & 6. Guaranteed success and guaranteed failure
# ---------------------------------------------------------------------------
def test_large_savings_and_no_spending_always_succeeds() -> None:
    """A very large portfolio with no spending need must never fail."""
    inputs = make_inputs(
        current_savings=25_000_000.0,
        annual_contribution=0.0,
        annual_spending=0.0,
        annual_other_income=0.0,
        n_simulations=1_000,
    )
    results = run_retirement_simulation(inputs)
    assert results.success_probability == 1.0
    assert results.n_failures == 0
    assert results.median_depletion_age is None


def test_no_savings_with_spending_always_fails() -> None:
    """With nothing saved and a real spending need, every path must fail."""
    inputs = make_inputs(
        current_savings=0.0,
        annual_contribution=0.0,
        annual_spending=50_000.0,
        annual_other_income=0.0,
        n_simulations=1_000,
    )
    results = run_retirement_simulation(inputs)
    assert results.success_probability == 0.0
    assert results.median_depletion_age is not None
    # The portfolio is empty from the start, so depletion is recorded in year one.
    assert results.median_depletion_age == pytest.approx(inputs.current_age + 1)


def test_guaranteed_income_covering_spending_preserves_the_portfolio() -> None:
    """When guaranteed income meets spending, no withdrawal should be taken."""
    inputs = make_inputs(
        annual_spending=40_000.0,
        annual_other_income=40_000.0,
        volatility=0.0,
        expected_return=0.04,
        n_simulations=1_000,
    )
    results = run_retirement_simulation(inputs)
    assert results.success_probability == 1.0
    # With no withdrawals the balance must keep compounding after retirement.
    assert results.ending_balances[0] > results.balances_at_retirement[0]


# ---------------------------------------------------------------------------
# 7. Balances never go negative
# ---------------------------------------------------------------------------
def test_balances_are_never_negative(baseline_results: SimulationResults) -> None:
    """No cell of the balance grid may be negative under any path."""
    assert np.all(baseline_results.balances >= 0.0)
    assert np.all(baseline_results.balances_nominal >= 0.0)


def test_balances_never_negative_under_extreme_volatility() -> None:
    """Even with implausible volatility, the floor at zero must hold."""
    inputs = make_inputs(volatility=0.95, expected_return=-0.15, n_simulations=1_000)
    results = run_retirement_simulation(inputs)
    assert np.all(results.balances >= 0.0)


def test_depleted_paths_stay_depleted() -> None:
    """Once a path reaches zero it must remain at zero for every later year."""
    inputs = make_inputs(
        current_savings=10_000.0,
        annual_contribution=0.0,
        annual_spending=80_000.0,
        annual_other_income=0.0,
        n_simulations=1_000,
    )
    results = run_retirement_simulation(inputs)
    zeroed = results.balances == 0.0
    # A cumulative maximum of the zero flag can never decrease along a row.
    assert np.all(np.maximum.accumulate(zeroed, axis=1) == zeroed)


# ---------------------------------------------------------------------------
# 8. Array dimensions
# ---------------------------------------------------------------------------
def test_result_arrays_have_expected_dimensions(baseline_results: SimulationResults) -> None:
    """Balance, return, age and mask arrays must all line up."""
    inputs = baseline_results.inputs
    n_years = inputs.life_expectancy - inputs.current_age

    assert baseline_results.balances.shape == (inputs.n_simulations, n_years + 1)
    assert baseline_results.balances_nominal.shape == (inputs.n_simulations, n_years + 1)
    assert baseline_results.annual_returns.shape == (inputs.n_simulations, n_years)
    assert baseline_results.ages.shape == (n_years + 1,)
    assert baseline_results.depletion_ages.shape == (inputs.n_simulations,)
    assert baseline_results.success_mask.shape == (inputs.n_simulations,)
    assert baseline_results.ages[0] == inputs.current_age
    assert baseline_results.ages[-1] == inputs.life_expectancy


def test_first_column_equals_current_savings(baseline_results: SimulationResults) -> None:
    """Column zero of the balance grid is today's balance for every path."""
    assert np.all(
        baseline_results.balances_nominal[:, 0] == baseline_results.inputs.current_savings
    )


def test_retirement_index_points_at_the_retirement_age(
    baseline_results: SimulationResults,
) -> None:
    """The retirement index must select the retirement-age column."""
    index = baseline_results.retirement_index
    assert baseline_results.ages[index] == baseline_results.inputs.retirement_age


# ---------------------------------------------------------------------------
# 9. Probability bounds
# ---------------------------------------------------------------------------
def test_success_probability_stays_between_zero_and_one(
    baseline_results: SimulationResults,
) -> None:
    """Probabilities must be valid and complementary."""
    assert 0.0 <= baseline_results.success_probability <= 1.0
    assert 0.0 <= baseline_results.failure_probability <= 1.0
    assert baseline_results.success_probability + baseline_results.failure_probability == pytest.approx(1.0)
    assert baseline_results.n_successes + baseline_results.n_failures == baseline_results.n_simulations


# ---------------------------------------------------------------------------
# 10. Percentiles
# ---------------------------------------------------------------------------
def test_percentiles_match_numpy(baseline_results: SimulationResults) -> None:
    """Reported percentiles must equal a direct NumPy calculation."""
    ending = baseline_results.ending_balances
    for percentile in (10, 25, 50, 75, 90):
        assert baseline_results.ending_balance_percentile(percentile) == pytest.approx(
            float(np.percentile(ending, percentile))
        )


def test_percentiles_are_monotonically_increasing(
    baseline_results: SimulationResults,
) -> None:
    """Higher percentiles must never report lower balances."""
    values = [baseline_results.ending_balance_percentile(p) for p in (10, 25, 50, 75, 90)]
    assert values == sorted(values)


def test_median_ending_balance_matches_fiftieth_percentile(
    baseline_results: SimulationResults,
) -> None:
    """The median convenience property must agree with the 50th percentile."""
    assert baseline_results.median_ending_balance == pytest.approx(
        baseline_results.ending_balance_percentile(50)
    )


def test_percentile_paths_shape_and_ordering(baseline_results: SimulationResults) -> None:
    """The percentile path table must cover every age and stay correctly ordered."""
    paths = baseline_results.percentile_paths()
    assert len(paths) == len(baseline_results.ages)
    assert list(paths.columns) == ["p10", "p25", "p50", "p75", "p90"]
    assert np.all(paths["p10"].to_numpy() <= paths["p50"].to_numpy() + 1e-9)
    assert np.all(paths["p50"].to_numpy() <= paths["p90"].to_numpy() + 1e-9)


def test_percentile_table_includes_retirement_and_life_expectancy(
    baseline_results: SimulationResults,
) -> None:
    """The displayed age table must span retirement through life expectancy."""
    table = baseline_results.percentile_table(step=5)
    assert table.index[0] == baseline_results.inputs.retirement_age
    assert table.index[-1] == baseline_results.inputs.life_expectancy


# ---------------------------------------------------------------------------
# Additional behaviour: dollar basis and summary payload
# ---------------------------------------------------------------------------
def test_todays_dollars_are_deflated_versions_of_nominal() -> None:
    """Selecting today's dollars must deflate, not re-simulate."""
    nominal = run_retirement_simulation(make_inputs(show_in_todays_dollars=False))
    real = run_retirement_simulation(make_inputs(show_in_todays_dollars=True))

    deflator = (1 + real.inputs.inflation_rate) ** np.arange(real.balances.shape[1])
    np.testing.assert_allclose(real.balances, nominal.balances / deflator, rtol=1e-9)
    # Deflating cannot change whether a path ended above zero.
    assert real.success_probability == nominal.success_probability


def test_summary_contains_every_required_metric(baseline_results: SimulationResults) -> None:
    """The summary payload must expose all metrics the dashboard displays."""
    summary = baseline_results.summary()
    required = {
        "success_probability",
        "failure_probability",
        "median_balance_at_retirement",
        "median_ending_balance",
        "p10_ending_balance",
        "p25_ending_balance",
        "p50_ending_balance",
        "p75_ending_balance",
        "p90_ending_balance",
        "median_depletion_age",
        "pct_depleted_before_life_expectancy",
    }
    assert required.issubset(summary.keys())


def test_higher_contributions_improve_the_plan() -> None:
    """A directional sanity check: saving more must not reduce success probability."""
    low = run_retirement_simulation(make_inputs(annual_contribution=5_000.0))
    high = run_retirement_simulation(make_inputs(annual_contribution=40_000.0))
    assert high.success_probability >= low.success_probability


def test_beginning_of_year_withdrawals_are_more_conservative() -> None:
    """Withdrawing before returns are applied cannot beat withdrawing after."""
    beginning = run_retirement_simulation(make_inputs(withdrawal_timing="beginning"))
    end = run_retirement_simulation(make_inputs(withdrawal_timing="end"))
    assert beginning.median_ending_balance <= end.median_ending_balance
