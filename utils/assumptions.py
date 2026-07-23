"""Central store for default assumptions and validation bounds.

Nothing in the simulation engine hard-codes a financial assumption. Every default a
user sees in the sidebar comes from this module, so assumptions can be reviewed,
documented and changed in one place — which is exactly what a compliance or
investment-committee review of a planning tool would ask for.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Default input values shown in the sidebar
# ---------------------------------------------------------------------------
DEFAULTS: Final[dict[str, float | int | str | bool]] = {
    # Personal timeline
    "current_age": 30,
    "retirement_age": 65,
    "life_expectancy": 92,
    # Current finances
    "current_savings": 75_000.0,
    "annual_contribution": 20_000.0,
    "contribution_growth_rate": 0.02,
    # Investment assumptions (nominal, annual)
    "expected_return": 0.07,
    "volatility": 0.15,
    "inflation_rate": 0.025,
    # Retirement assumptions (today's dollars)
    "annual_spending": 70_000.0,
    "annual_other_income": 24_000.0,
    "withdrawal_timing": "beginning",
    # Simulation settings
    "n_simulations": 10_000,
    "random_seed": 42,
    "show_in_todays_dollars": True,
}

# ---------------------------------------------------------------------------
# Accepted ranges. (low, high) inclusive. Used by utils.validation and to bound
# the Streamlit widgets so most bad input is impossible to enter in the first place.
# ---------------------------------------------------------------------------
BOUNDS: Final[dict[str, tuple[float, float]]] = {
    "current_age": (18, 100),
    "retirement_age": (30, 100),
    "life_expectancy": (40, 120),
    "current_savings": (0.0, 100_000_000.0),
    "annual_contribution": (0.0, 5_000_000.0),
    "contribution_growth_rate": (-0.10, 0.20),
    "expected_return": (-0.20, 0.30),
    "volatility": (0.0, 1.00),
    "inflation_rate": (-0.05, 0.20),
    "annual_spending": (0.0, 10_000_000.0),
    "annual_other_income": (0.0, 10_000_000.0),
    "n_simulations": (1_000, 100_000),
}

# ---------------------------------------------------------------------------
# Notes shown to the user alongside the assumptions table. Keeping the wording here
# means the methodology text and the numbers can never drift apart.
# ---------------------------------------------------------------------------
ASSUMPTION_NOTES: Final[dict[str, str]] = {
    "return_model": (
        "Annual returns are drawn independently from a normal distribution. Real "
        "markets have fatter tails than a normal distribution, so extreme outcomes "
        "are likely understated."
    ),
    "inflation": (
        "Inflation is applied as a fixed annual rate. Retirement spending and "
        "guaranteed income are entered in today's dollars and grown at this rate."
    ),
    "taxes": (
        "Taxes, advisory fees, fund expenses and required minimum distributions are "
        "not modelled. Spending should be entered on an after-tax basis."
    ),
    "sequence": (
        "Contributions are added at the end of each working year. Retirement "
        "withdrawals are taken at the timing selected in the sidebar."
    ),
    "allocation": (
        "A single static portfolio is assumed for life. No glidepath, rebalancing "
        "drift or allocation change at retirement is modelled."
    ),
}

# Risk-profile presets an advisor might use as a starting point.
PORTFOLIO_PRESETS: Final[dict[str, dict[str, float]]] = {
    "Conservative (30/70)": {"expected_return": 0.050, "volatility": 0.070},
    "Moderate (60/40)": {"expected_return": 0.065, "volatility": 0.110},
    "Growth (80/20)": {"expected_return": 0.075, "volatility": 0.140},
    "Aggressive (100/0)": {"expected_return": 0.085, "volatility": 0.170},
    "Custom": {},
}
