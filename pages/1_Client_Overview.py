"""Client Overview — summary of the most recent retirement projection.

Reads the results stored in Streamlit session state by the Retirement Planner so the
latest inputs and outputs survive navigation between pages.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st  # noqa: E402

from components.metrics import render_metric_row, render_snapshot_metrics  # noqa: E402
from components.navigation import (  # noqa: E402
    configure_page,
    page_header,
    render_disclaimer,
    render_sidebar_brand,
    section_header,
)
from models.monte_carlo import SimulationResults  # noqa: E402
from services.retirement_service import (  # noqa: E402
    RESULTS_SESSION_KEY,
    build_client_snapshot,
    build_planning_status,
)
from utils.formatting import format_currency, format_percent  # noqa: E402


def render_empty_state() -> None:
    """Render instructions shown before any projection has been run."""
    st.info(
        "No projection has been run in this session yet.\n\n"
        "Open the **Retirement Planner**, enter the client's timeline, savings and "
        "assumptions in the sidebar, then select **Run simulation**. The results will "
        "appear here automatically."
    )
    st.page_link("pages/2_Retirement_Planner.py", label="Go to the Retirement Planner")


def render_overview(results: SimulationResults) -> None:
    """Render the full client summary for a completed projection."""
    inputs = results.inputs
    status_label, status_explanation = build_planning_status(results)

    section_header("Planning status")
    if status_label == "On track":
        st.success(f"**{status_label}.** {status_explanation}")
    elif status_label == "Monitor":
        st.warning(f"**{status_label}.** {status_explanation}")
    else:
        st.error(f"**{status_label}.** {status_explanation}")

    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)

    section_header("Headline figures")
    render_metric_row(
        [
            (
                "Current age",
                str(inputs.current_age),
                "Age used as the start of the projection.",
            ),
            (
                "Retirement age",
                str(inputs.retirement_age),
                "Age at which withdrawals begin.",
            ),
            (
                "Current savings",
                format_currency(inputs.current_savings),
                "Starting portfolio balance.",
            ),
            (
                "Success probability",
                format_percent(results.success_probability),
                f"Share of simulations still funded at age {inputs.life_expectancy}.",
            ),
        ]
    )
    render_metric_row(
        [
            (
                f"Median balance at age {inputs.retirement_age}",
                format_currency(results.median_balance_at_retirement),
                "Middle outcome at retirement.",
            ),
            (
                f"Median balance at age {inputs.life_expectancy}",
                format_currency(results.median_ending_balance),
                "Middle outcome at life expectancy.",
            ),
            (
                "10th percentile ending balance",
                format_currency(results.ending_balance_percentile(10)),
                "A poor-market outcome, not a worst case.",
            ),
            (
                "Simulations run",
                f"{results.n_simulations:,}",
                f"Random seed {inputs.random_seed}.",
            ),
        ]
    )

    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)

    section_header("Plan detail")
    render_snapshot_metrics(build_client_snapshot(results), per_row=3)

    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)
    basis = (
        "today's dollars." if inputs.show_in_todays_dollars else "nominal future dollars."
    )
    st.caption(
        f"Figures are shown in {basis} Return to the Retirement Planner to change "
        "assumptions and re-run the projection."
    )
    st.page_link("pages/2_Retirement_Planner.py", label="Adjust assumptions and re-run")


configure_page("Client Overview")
render_sidebar_brand()

page_header(
    "Client Overview",
    "A single-page snapshot of the client's plan and the most recent projection.",
)

stored_results = st.session_state.get(RESULTS_SESSION_KEY)

if stored_results is None:
    render_empty_state()
else:
    render_overview(stored_results)

st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)
render_disclaimer()
