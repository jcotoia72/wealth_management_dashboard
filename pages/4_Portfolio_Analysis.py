"""Portfolio Analysis — placeholder page for a future module."""

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

configure_page("Portfolio Analysis")
render_sidebar_brand()

page_header(
    "Portfolio Analysis",
    "Examine an existing client portfolio: allocation, concentration and realised risk.",
)

render_coming_soon(
    module_name="Portfolio Analysis",
    summary=(
        "This module will accept a holdings file and describe what the client actually owns today, in contrast to the Retirement Planner, which works from summary assumptions rather than individual positions."
    ),
    planned_features=[
        "Upload holdings from a CSV file",
        "Asset-class and sector allocation breakdown",
        "Concentration and single-position risk flags",
        "Historical return, volatility, drawdown and Sharpe ratio statistics",
        "Comparison of the current allocation against a target allocation",
    ],
)

render_disclaimer()
