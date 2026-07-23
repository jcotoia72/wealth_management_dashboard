"""Monte Carlo retirement simulation engine.

This module is deliberately free of any Streamlit, Plotly or presentation code so
that it can be imported, unit tested and reused from anywhere (notebooks, scripts,
future scenario-comparison modules, etc.).

Public entry point
------------------
    results = run_retirement_simulation(inputs)

Modelling overview
------------------
The simulation projects a household portfolio one year at a time, from the client's
current age through their assumed life expectancy, across many independent random
return paths.

Phase 1 (accumulation) runs while ``age < retirement_age``.
Phase 2 (decumulation) runs from ``retirement_age`` onward.

Order of annual operations (documented explicitly because it materially affects results):

Accumulation year
    1. The starting balance is multiplied by that year's random growth factor.
    2. The annual contribution is added at the END of the year.
       Contributions therefore earn no return in the year they are made, which is a
       slightly conservative convention.

Retirement year, ``withdrawal_timing == "beginning"``
    1. The net withdrawal is taken from the starting balance.
    2. The remaining balance is multiplied by that year's growth factor.
    (Conservative: withdrawn money is not invested during the year.)

Retirement year, ``withdrawal_timing == "end"``
    1. The starting balance is multiplied by that year's growth factor.
    2. The net withdrawal is taken from the grown balance.
    (Optimistic: the full balance stays invested for the whole year.)

Key simplifying assumptions
---------------------------
* Annual returns are independent draws from a normal distribution. Real markets show
  fat tails, serial correlation and volatility clustering, so this understates the
  frequency of extreme outcomes. It is the standard first-version assumption.
* Growth factors are floored at 0.0, i.e. a single year cannot lose more than 100%.
* Inflation is a fixed, deterministic rate rather than a random variable.
* Taxes, fees, required minimum distributions, healthcare shocks, and portfolio
  rebalancing/glidepath changes are not modelled.
* Retirement spending and other income are entered in TODAY'S dollars and inflated by
  ``(1 + inflation_rate) ** t`` where ``t`` is the number of years from today.
* If guaranteed income exceeds spending in a given year, the surplus is assumed to be
  consumed rather than reinvested (net portfolio withdrawal is floored at zero).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

from utils.validation import validate_retirement_inputs

WithdrawalTiming = Literal["beginning", "end"]

# Balances below this dollar amount are treated as fully depleted. Guards against
# floating-point dust (e.g. 1e-12) being counted as a "successful" plan.
DEPLETION_TOLERANCE: float = 1.0


@dataclass(frozen=True)
class RetirementInputs:
    """All client and assumption inputs required to run one retirement projection.

    Rates are expressed as decimals (0.06 means 6%), and all dollar amounts for
    spending and income are stated in TODAY'S dollars.
    """

    # Personal timeline
    current_age: int
    retirement_age: int
    life_expectancy: int

    # Current finances
    current_savings: float
    annual_contribution: float
    contribution_growth_rate: float = 0.02

    # Investment assumptions (nominal)
    expected_return: float = 0.07
    volatility: float = 0.15
    inflation_rate: float = 0.025

    # Retirement assumptions (today's dollars)
    annual_spending: float = 60_000.0
    annual_other_income: float = 24_000.0
    withdrawal_timing: WithdrawalTiming = "beginning"

    # Simulation settings
    n_simulations: int = 10_000
    random_seed: int = 42
    show_in_todays_dollars: bool = True

    @property
    def years_to_retirement(self) -> int:
        """Number of accumulation years before retirement begins."""
        return self.retirement_age - self.current_age

    @property
    def years_in_retirement(self) -> int:
        """Number of retirement years modelled."""
        return self.life_expectancy - self.retirement_age

    @property
    def total_years(self) -> int:
        """Total number of projection years from today through life expectancy."""
        return self.life_expectancy - self.current_age


@dataclass
class SimulationResults:
    """Structured output of a Monte Carlo retirement projection.

    Attributes
    ----------
    inputs:
        The exact inputs used to produce these results.
    ages:
        1-D array of length ``total_years + 1``. ``ages[0]`` is the current age and
        each element labels the corresponding column of ``balances``.
    balances:
        2-D array of shape ``(n_simulations, total_years + 1)`` holding end-of-year
        portfolio balances in the DISPLAY basis (nominal or today's dollars,
        controlled by ``inputs.show_in_todays_dollars``). Column 0 is today's balance.
    balances_nominal:
        The same grid, always in nominal (future) dollars.
    annual_returns:
        2-D array of shape ``(n_simulations, total_years)`` of simulated annual returns.
    depletion_ages:
        1-D float array of length ``n_simulations``. The age at which the portfolio
        first reached zero, or ``np.nan`` for paths that never ran out of money.
    success_mask:
        1-D boolean array; ``True`` where the portfolio survived through life expectancy.
    retirement_index:
        Column index in ``balances`` corresponding to the retirement age.
    """

    inputs: RetirementInputs
    ages: np.ndarray
    balances: np.ndarray
    balances_nominal: np.ndarray
    annual_returns: np.ndarray
    depletion_ages: np.ndarray
    success_mask: np.ndarray
    retirement_index: int = field(default=0)

    # ------------------------------------------------------------------
    # Headline probabilities
    # ------------------------------------------------------------------
    @property
    def n_simulations(self) -> int:
        """Total number of simulated paths."""
        return int(self.balances.shape[0])

    @property
    def success_probability(self) -> float:
        """Share of paths whose balance stayed above zero through life expectancy."""
        return float(np.mean(self.success_mask))

    @property
    def failure_probability(self) -> float:
        """Share of paths that ran out of money before life expectancy."""
        return 1.0 - self.success_probability

    @property
    def n_successes(self) -> int:
        """Count of successful paths."""
        return int(np.sum(self.success_mask))

    @property
    def n_failures(self) -> int:
        """Count of failed (depleted) paths."""
        return self.n_simulations - self.n_successes

    @property
    def pct_depleted_before_life_expectancy(self) -> float:
        """Percentage (0-100) of paths depleted before life expectancy."""
        return self.failure_probability * 100.0

    # ------------------------------------------------------------------
    # Balance statistics
    # ------------------------------------------------------------------
    @property
    def balances_at_retirement(self) -> np.ndarray:
        """Portfolio balances at the retirement age, across all paths."""
        return self.balances[:, self.retirement_index]

    @property
    def ending_balances(self) -> np.ndarray:
        """Portfolio balances at life expectancy, across all paths."""
        return self.balances[:, -1]

    @property
    def median_balance_at_retirement(self) -> float:
        """Median portfolio balance at the retirement age."""
        return float(np.median(self.balances_at_retirement))

    @property
    def median_ending_balance(self) -> float:
        """Median portfolio balance at life expectancy."""
        return float(np.median(self.ending_balances))

    def ending_balance_percentile(self, percentile: float) -> float:
        """Return the ending balance at a given percentile (0-100)."""
        return float(np.percentile(self.ending_balances, percentile))

    @property
    def ending_percentiles(self) -> dict[int, float]:
        """Ending balances at the 10th, 25th, 50th, 75th and 90th percentiles."""
        return {p: self.ending_balance_percentile(p) for p in (10, 25, 50, 75, 90)}

    @property
    def median_depletion_age(self) -> float | None:
        """Median age at which failed paths ran out of money.

        Returns ``None`` when no simulation failed, so callers can display a
        graceful message instead of a NaN.
        """
        failed = self.depletion_ages[~np.isnan(self.depletion_ages)]
        if failed.size == 0:
            return None
        return float(np.median(failed))

    # ------------------------------------------------------------------
    # Derived tables (pandas, still presentation-agnostic)
    # ------------------------------------------------------------------
    def percentile_paths(
        self, percentiles: tuple[int, ...] = (10, 25, 50, 75, 90)
    ) -> pd.DataFrame:
        """Return a DataFrame of balance percentiles for every projected age.

        Index is age; one column per requested percentile, named e.g. ``"p10"``.
        """
        data = {
            f"p{p}": np.percentile(self.balances, p, axis=0) for p in percentiles
        }
        return pd.DataFrame(data, index=pd.Index(self.ages, name="Age"))

    def percentile_table(self, step: int = 5) -> pd.DataFrame:
        """Return balance percentiles at selected ages (retirement age, then every
        ``step`` years, always including life expectancy).
        """
        paths = self.percentile_paths()
        selected = list(range(self.inputs.retirement_age, self.inputs.life_expectancy + 1, step))
        if self.inputs.life_expectancy not in selected:
            selected.append(self.inputs.life_expectancy)
        return paths.loc[[age for age in selected if age in paths.index]]

    def summary(self) -> dict[str, float | int | None]:
        """Return a flat dictionary of headline statistics.

        Useful for the Client Overview page, logging, and future scenario comparison.
        """
        percentiles = self.ending_percentiles
        return {
            "success_probability": self.success_probability,
            "failure_probability": self.failure_probability,
            "n_simulations": self.n_simulations,
            "n_successes": self.n_successes,
            "n_failures": self.n_failures,
            "median_balance_at_retirement": self.median_balance_at_retirement,
            "median_ending_balance": self.median_ending_balance,
            "p10_ending_balance": percentiles[10],
            "p25_ending_balance": percentiles[25],
            "p50_ending_balance": percentiles[50],
            "p75_ending_balance": percentiles[75],
            "p90_ending_balance": percentiles[90],
            "median_depletion_age": self.median_depletion_age,
            "pct_depleted_before_life_expectancy": self.pct_depleted_before_life_expectancy,
        }


def _simulate_annual_returns(inputs: RetirementInputs) -> np.ndarray:
    """Draw independent normally distributed annual returns for every path and year.

    Shape is ``(n_simulations, total_years)``. A zero-volatility input produces
    perfectly deterministic returns equal to ``expected_return``.
    """
    rng = np.random.default_rng(inputs.random_seed)
    return rng.normal(
        loc=inputs.expected_return,
        scale=inputs.volatility,
        size=(inputs.n_simulations, inputs.total_years),
    )


def run_retirement_simulation(inputs: RetirementInputs) -> SimulationResults:
    """Run the two-phase Monte Carlo retirement projection.

    Parameters
    ----------
    inputs:
        A validated :class:`RetirementInputs` instance.

    Returns
    -------
    SimulationResults
        Structured results containing the full balance grid, simulated returns,
        depletion ages and a success mask.

    Raises
    ------
    ValidationError
        If any input fails the rules in :mod:`utils.validation`.
    """
    validate_retirement_inputs(inputs, raise_on_error=True)

    n_sims = inputs.n_simulations
    n_years = inputs.total_years

    returns = _simulate_annual_returns(inputs)
    # A single year cannot destroy more than 100% of the portfolio, so the growth
    # factor is floored at zero. Without this, a large negative draw from the normal
    # distribution could push a balance negative.
    growth_factors = np.maximum(1.0 + returns, 0.0)

    balances = np.zeros((n_sims, n_years + 1), dtype=float)
    balances[:, 0] = inputs.current_savings

    # -1 marks "never depleted"; converted to NaN ages at the end.
    depletion_year = np.full(n_sims, -1, dtype=int)

    # The loop runs once per YEAR (typically 40-70 iterations) while every operation
    # inside it is vectorised across all simulations at once. A fully vectorised
    # alternative is not possible because each year's balance depends on the previous
    # year's balance (path dependency).
    for t in range(n_years):
        age = inputs.current_age + t
        inflation_factor = (1.0 + inputs.inflation_rate) ** t
        balance = balances[:, t]

        if age < inputs.retirement_age:
            # --- Accumulation: grow the balance, then add the year's contribution.
            contribution = inputs.annual_contribution * (
                (1.0 + inputs.contribution_growth_rate) ** t
            )
            balance = balance * growth_factors[:, t] + contribution
        else:
            # --- Decumulation: the portfolio only funds spending not already covered
            # by Social Security or pension income.
            net_need_today = max(
                0.0, inputs.annual_spending - inputs.annual_other_income
            )
            withdrawal = net_need_today * inflation_factor

            if inputs.withdrawal_timing == "beginning":
                balance = np.maximum(balance - withdrawal, 0.0)
                balance = balance * growth_factors[:, t]
            else:
                balance = balance * growth_factors[:, t]
                balance = np.maximum(balance - withdrawal, 0.0)

        balance = np.maximum(balance, 0.0)
        balances[:, t + 1] = balance

        # Record the first year each path hits zero. A depleted portfolio can never
        # recover (0 * growth - withdrawal, floored at 0), so this is permanent.
        newly_depleted = (balance <= DEPLETION_TOLERANCE) & (depletion_year < 0)
        depletion_year[newly_depleted] = t + 1

    # Zero out floating-point dust so "greater than zero" is meaningful.
    balances[balances <= DEPLETION_TOLERANCE] = 0.0

    depletion_ages = np.where(
        depletion_year >= 0,
        inputs.current_age + depletion_year.astype(float),
        np.nan,
    )
    success_mask = balances[:, -1] > 0.0

    balances_nominal = balances
    if inputs.show_in_todays_dollars:
        # Deflate every column back to today's purchasing power.
        deflator = (1.0 + inputs.inflation_rate) ** np.arange(n_years + 1)
        display_balances = balances_nominal / deflator
    else:
        display_balances = balances_nominal

    return SimulationResults(
        inputs=inputs,
        ages=np.arange(inputs.current_age, inputs.life_expectancy + 1),
        balances=display_balances,
        balances_nominal=balances_nominal,
        annual_returns=returns,
        depletion_ages=depletion_ages,
        success_mask=success_mask,
        retirement_index=inputs.years_to_retirement,
    )
