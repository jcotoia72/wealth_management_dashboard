"""Wealth Management Planning Dashboard — application entry point.

Run with:
    streamlit run app.py

Streamlit automatically discovers the files in ``pages/`` and builds the sidebar
navigation from them; this file is the home page of that multipage application.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root is importable no matter where Streamlit is launched from.
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st  # noqa: E402

from components.navigation import (  # noqa: E402
    APP_TITLE,
    configure_page,
    page_header,
    render_disclaimer,
    render_module_navigation,
    render_sidebar_brand,
    section_header,
)
from services.retirement_service import RESULTS_SESSION_KEY  # noqa: E402
from utils.formatting import format_currency, format_percent  # noqa: E402

configure_page("Home")
render_sidebar_brand()
st.sidebar.markdown("**Modules**")
st.sidebar.caption(
    "Use the page list above to move between modules. The Retirement Planner is the "
    "fully functional module in this version."
)

page_header(
    APP_TITLE,
    "A modular retirement and portfolio planning workspace for illustrating "
    "long-horizon client outcomes.",
)

st.markdown(
    "This dashboard models how a client's savings could evolve from today through "
    "retirement using Monte Carlo simulation. Rather than projecting a single average "
    "return, it runs thousands of independent market scenarios and reports the "
    "**range** of outcomes and the **probability** that the plan lasts through life "
    "expectancy. Every assumption behind the projection is displayed alongside the "
    "results, and the calculation engine is separated from the interface so it can be "
    "tested and reused."
)

st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Status strip: reflects whether a projection has been run in this session.
# ---------------------------------------------------------------------------
results = st.session_state.get(RESULTS_SESSION_KEY)

section_header("Dashboard status")
status_columns = st.columns(4, gap="medium")
with status_columns[0]:
    st.metric("Retirement Planner", "Active", help="Fully implemented in this version.")
with status_columns[1]:
    st.metric(
        "Modules available",
        "4 of 6",
        help="Client Overview, Retirement Planner, Scenario Comparison and Risk Profile.",
    )
with status_columns[2]:
    if results is None:
        st.metric("Latest projection", "Not run")
    else:
        st.metric(
            "Latest projection",
            format_percent(results.success_probability),
            help="Retirement success probability from the most recent simulation.",
        )
with status_columns[3]:
    if results is None:
        st.metric("Median ending balance", "—")
    else:
        st.metric(
            "Median ending balance",
            format_currency(results.median_ending_balance),
            help=f"Median balance at age {results.inputs.life_expectancy}.",
        )

if results is None:
    st.info(
        "No projection has been run yet in this session. Open the **Retirement Planner** "
        "to run one; results will then appear here and on the Client Overview page."
    )
else:
    st.success(
        f"A projection is loaded: {results.n_simulations:,} simulations, ages "
        f"{results.inputs.current_age} to {results.inputs.life_expectancy}. "
        "Open Client Overview for the summary."
    )

st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)

section_header(
    "Modules",
    "Each module is a separate page. Planned modules are listed so the structure of "
    "the finished application is visible.",
)
render_module_navigation()

st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)

section_header("How the projection works")
st.markdown(
    """
1. **Accumulation.** From the current age to the retirement age, the portfolio earns a
   randomly drawn return each year and the annual contribution is added at year end.
   Contributions can grow each year to reflect rising income.
2. **Decumulation.** From retirement to life expectancy, the portfolio funds the
   difference between desired spending and guaranteed income such as Social Security or
   a pension. Both figures are entered in today's dollars and grown with inflation.
3. **Repetition.** Steps 1 and 2 are repeated across thousands of independent return
   paths, producing a distribution of outcomes instead of a single answer.
4. **Success measurement.** A path counts as successful when the balance is still above
   zero at life expectancy. The success probability is simply the share of paths that
   met that test.
"""
)

st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)
render_disclaimer()
