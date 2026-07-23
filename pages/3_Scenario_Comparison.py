"""Scenario Comparison — placeholder page for a future module."""

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

configure_page("Scenario Comparison")
render_sidebar_brand()

page_header(
    "Scenario Comparison",
    "Compare several retirement plans side by side to see which assumptions matter most.",
)

render_coming_soon(
    module_name="Scenario Comparison",
    summary=(
        "This module will let an advisor save multiple projections and compare them directly, which is the natural next step once a baseline plan exists. Because the simulation engine already returns a structured results object, comparing scenarios mainly requires storing several of them and charting them together."
    ),
    planned_features=[
        "Save and name multiple projections within a session",
        "Side-by-side table of success probability and percentile balances",
        "Overlaid median paths for two or more scenarios on one chart",
        "Sensitivity view showing how success probability changes with retirement age, savings rate or spending",
        "Plain-English summary of which single change improves the plan the most",
    ],
)

render_disclaimer()
