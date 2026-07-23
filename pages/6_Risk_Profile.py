"""Risk Profile — placeholder page for a future module."""

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

configure_page("Risk Profile")
render_sidebar_brand()

page_header(
    "Risk Profile",
    "Translate a client risk questionnaire into a suitable target allocation.",
)

render_coming_soon(
    module_name="Risk Profile",
    summary=(
        "This module will score a short risk-tolerance and risk-capacity questionnaire and map the result to a model portfolio, closing the loop between how a client feels about risk and the assumptions used in their projection."
    ),
    planned_features=[
        "Structured risk-tolerance and risk-capacity questionnaire",
        "Transparent scoring with the weighting of each question shown",
        "Mapping from score to a model portfolio and its assumed return and volatility",
        "Comparison of stated risk tolerance against the risk implied by the current plan",
        "Automatic hand-off of the recommended assumptions to the Retirement Planner",
    ],
)

render_disclaimer()
