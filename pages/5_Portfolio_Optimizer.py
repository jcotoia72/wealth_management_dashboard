"""Portfolio Optimizer — placeholder page for a future module."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from components.navigation import (  # noqa: E402
    configure_page,
    page_header,
    render_coming_soon,
    render_disclaimer,
    render_sidebar_brand,
)

configure_page("Portfolio Optimizer")
render_sidebar_brand()

page_header(
    "Portfolio Optimizer",
    "Construct efficient portfolios under client-specific constraints.",
)

render_coming_soon(
    module_name="Portfolio Optimizer",
    summary=(
        "This module will apply mean-variance optimisation to a set of candidate assets and show the trade-off between expected return and risk, then feed the chosen portfolio's return and volatility back into the Retirement Planner."
    ),
    planned_features=[
        "Efficient frontier construction from expected returns and a covariance matrix",
        "Maximum Sharpe ratio and minimum variance portfolios",
        "Weight constraints, including long-only and per-asset limits",
        "Comparison of the optimised portfolio against the current allocation",
        "One-click export of the resulting return and volatility into the Retirement Planner",
    ],
)

render_disclaimer()
