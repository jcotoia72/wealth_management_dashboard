"""Retirement Planner — the fully functional module of this dashboard.

This page is responsible for input collection, validation feedback and layout only.
All financial calculations happen in :mod:`models.monte_carlo`, and all preparation of
tables and narrative text happens in :mod:`services.retirement_service`.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Streamlit runs page files directly, so the project root is added to the import path
# here as well. Without this, `from models...` would fail on some setups.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st  # noqa: E402

from components.charts import (  # noqa: E402
    ending_balance_histogram,
    percentile_band_chart,
    portfolio_paths_chart,
)
from components.metrics import (  # noqa: E402
    render_failure_metrics,
    render_headline_metrics,
)
from components.navigation import (  # noqa: E402
    configure_page,
    page_header,
    render_disclaimer,
    render_sidebar_brand,
    section_header,
)
from services.retirement_service import (  # noqa: E402
    RESULTS_SESSION_KEY,
    build_assumptions_table,
    build_inputs,
    build_interpretation,
    build_methodology_notes,
    build_percentile_table,
    build_success_summary_table,
    run_projection,
    validate,
)
from utils.assumptions import BOUNDS, DEFAULTS, PORTFOLIO_PRESETS  # noqa: E402

configure_page("Retirement Planner")
render_sidebar_brand()

page_header(
    "Monte Carlo Retirement Planner",
    "Projects a client's portfolio through accumulation and retirement across "
    "thousands of simulated market paths.",
)

# Session-state key holding assumptions handed over from the Risk Profile module.
# Defined here (not imported) so this page has no dependency on the risk page.
PLANNER_PREFILL_KEY = "planner_prefill_assumptions"

# If the Risk Profile module sent portfolio assumptions here, point the user to the
# toggle in the sidebar that applies them automatically.
_prefill = st.session_state.get(PLANNER_PREFILL_KEY)
if _prefill is not None:
    st.info(
        f"**Risk Profile assumptions available.** The {_prefill['source']} profile "
        f"recommends {_prefill['expected_return'] * 100:.1f}% return and "
        f"{_prefill['volatility'] * 100:.1f}% volatility. Use the "
        "**Use Risk Profile assumptions** toggle in the Investment assumptions section "
        "of the sidebar to apply them automatically."
    )


def _collect_inputs() -> dict[str, object]:
    """Render every sidebar widget and return the raw input values.

    Widget minimums and maximums come from :data:`utils.assumptions.BOUNDS` so the UI
    and the validation layer can never disagree.
    """
    st.sidebar.markdown("### Plan inputs")

    with st.sidebar.expander("Personal timeline", expanded=True):
        current_age = st.number_input(
            "Current age",
            min_value=int(BOUNDS["current_age"][0]),
            max_value=int(BOUNDS["current_age"][1]),
            value=int(DEFAULTS["current_age"]),
            step=1,
            help="The client's age today.",
            key="in_current_age",
        )
        retirement_age = st.number_input(
            "Retirement age",
            min_value=int(BOUNDS["retirement_age"][0]),
            max_value=int(BOUNDS["retirement_age"][1]),
            value=int(DEFAULTS["retirement_age"]),
            step=1,
            help="The age at which contributions stop and withdrawals begin.",
            key="in_retirement_age",
        )
        life_expectancy = st.number_input(
            "Life expectancy (planning age)",
            min_value=int(BOUNDS["life_expectancy"][0]),
            max_value=int(BOUNDS["life_expectancy"][1]),
            value=int(DEFAULTS["life_expectancy"]),
            step=1,
            help="Planning horizon. A conservative planning age is common practice.",
            key="in_life_expectancy",
        )

    with st.sidebar.expander("Current finances", expanded=True):
        current_savings = st.number_input(
            "Current retirement savings ($)",
            min_value=0.0,
            max_value=float(BOUNDS["current_savings"][1]),
            value=float(DEFAULTS["current_savings"]),
            step=5_000.0,
            format="%.2f",
            key="in_current_savings",
        )
        annual_contribution = st.number_input(
            "Annual contribution ($)",
            min_value=0.0,
            max_value=float(BOUNDS["annual_contribution"][1]),
            value=float(DEFAULTS["annual_contribution"]),
            step=1_000.0,
            format="%.2f",
            help="Total annual savings including any employer match.",
            key="in_annual_contribution",
        )
        contribution_growth_rate = (
            st.slider(
                "Annual contribution increase (%)",
                min_value=BOUNDS["contribution_growth_rate"][0] * 100,
                max_value=BOUNDS["contribution_growth_rate"][1] * 100,
                value=float(DEFAULTS["contribution_growth_rate"]) * 100,
                step=0.25,
                help="Rate at which the contribution grows each year, e.g. with salary.",
                key="in_contribution_growth",
            )
            / 100
        )

    with st.sidebar.expander("Investment assumptions", expanded=True):
        # If the Risk Profile module sent assumptions here, offer a toggle that drives
        # the return and volatility sliders from the profile and locks them. Streamlit
        # widget values are only set at creation time, so the reliable way to "push"
        # values into a slider is to supply them as the value AND disable the slider —
        # a live slider would let the user's manual drag win on the next rerun.
        profile_prefill = st.session_state.get(PLANNER_PREFILL_KEY)
        use_profile = False
        if profile_prefill is not None:
            use_profile = st.toggle(
                f"Use Risk Profile assumptions "
                f"({profile_prefill['source']}: "
                f"{profile_prefill['expected_return'] * 100:.1f}% / "
                f"{profile_prefill['volatility'] * 100:.1f}%)",
                value=True,
                help="When on, the return and volatility below are set by the Risk "
                "Profile result and cannot be edited here. Turn off to adjust them "
                "manually.",
            )

        preset_name = st.selectbox(
            "Portfolio preset",
            options=list(PORTFOLIO_PRESETS.keys()),
            index=list(PORTFOLIO_PRESETS.keys()).index("Custom"),
            help="Selecting a preset fills the return and volatility assumptions below.",
            disabled=use_profile,
        )
        preset = PORTFOLIO_PRESETS.get(preset_name, {})
        default_return = preset.get("expected_return", DEFAULTS["expected_return"])
        default_volatility = preset.get("volatility", DEFAULTS["volatility"])

        # When the profile toggle is on, its values take precedence over any preset.
        # Because these two sliders are keyed (for persistence), a plain value= argument
        # is ignored once the key exists in session state. To make the toggle actually
        # drive them, write the profile value straight into their session-state slot
        # before the widget renders.
        if use_profile and profile_prefill is not None:
            st.session_state["in_expected_return"] = profile_prefill["expected_return"] * 100
            st.session_state["in_volatility"] = profile_prefill["volatility"] * 100
        elif preset_name != "Custom":
            # Selecting a named preset likewise fills the two sliders.
            st.session_state["in_expected_return"] = default_return * 100
            st.session_state["in_volatility"] = default_volatility * 100

        expected_return = (
            st.slider(
                "Expected annual return, nominal (%)",
                min_value=BOUNDS["expected_return"][0] * 100,
                max_value=BOUNDS["expected_return"][1] * 100,
                value=float(default_return) * 100,
                step=0.25,
                help="Average annual return before inflation.",
                disabled=use_profile,
                key="in_expected_return",
            )
            / 100
        )
        volatility = (
            st.slider(
                "Annual volatility, standard deviation (%)",
                min_value=BOUNDS["volatility"][0] * 100,
                max_value=BOUNDS["volatility"][1] * 100,
                value=float(default_volatility) * 100,
                step=0.5,
                help="Year-to-year variability of returns. Zero removes all randomness.",
                disabled=use_profile,
                key="in_volatility",
            )
            / 100
        )
        if use_profile:
            st.caption(
                "Return and volatility are set by the Risk Profile. Turn off the toggle "
                "above to edit them."
            )
        inflation_rate = (
            st.slider(
                "Annual inflation (%)",
                min_value=BOUNDS["inflation_rate"][0] * 100,
                max_value=BOUNDS["inflation_rate"][1] * 100,
                value=float(DEFAULTS["inflation_rate"]) * 100,
                step=0.25,
                key="in_inflation",
            )
            / 100
        )

    with st.sidebar.expander("Retirement assumptions", expanded=True):
        annual_spending = st.number_input(
            "Desired annual spending, today's dollars ($)",
            min_value=0.0,
            max_value=float(BOUNDS["annual_spending"][1]),
            value=float(DEFAULTS["annual_spending"]),
            step=2_500.0,
            format="%.2f",
            help="After-tax spending target in today's purchasing power.",
            key="in_annual_spending",
        )
        annual_other_income = st.number_input(
            "Social Security / pension, today's dollars ($)",
            min_value=0.0,
            max_value=float(BOUNDS["annual_other_income"][1]),
            value=float(DEFAULTS["annual_other_income"]),
            step=1_000.0,
            format="%.2f",
            help="Guaranteed income that reduces what the portfolio must provide.",
            key="in_annual_other_income",
        )
        withdrawal_timing = st.radio(
            "Withdrawal timing",
            options=["beginning", "end"],
            index=0 if DEFAULTS["withdrawal_timing"] == "beginning" else 1,
            format_func=lambda value: (
                "Beginning of year (conservative)"
                if value == "beginning"
                else "End of year"
            ),
            help="Beginning-of-year withdrawals are removed before that year's return "
            "is applied, which produces slightly lower outcomes.",
            key="in_withdrawal_timing",
        )

    with st.sidebar.expander("Simulation settings", expanded=False):
        n_simulations = st.select_slider(
            "Number of simulations",
            options=[1_000, 2_500, 5_000, 10_000, 25_000, 50_000, 100_000],
            value=int(DEFAULTS["n_simulations"]),
            help="More simulations give a smoother distribution but take longer.",
            key="in_n_simulations",
        )
        random_seed = st.number_input(
            "Random seed",
            min_value=0,
            max_value=1_000_000,
            value=int(DEFAULTS["random_seed"]),
            step=1,
            help="The same seed and inputs always reproduce exactly the same results.",
            key="in_random_seed",
        )
        dollar_basis = st.radio(
            "Display results in",
            options=["Today's dollars", "Nominal (future) dollars"],
            index=0 if DEFAULTS["show_in_todays_dollars"] else 1,
            help="Today's dollars removes inflation so figures are comparable to "
            "current purchasing power.",
            key="in_dollar_basis",
        )

    return {
        "current_age": current_age,
        "retirement_age": retirement_age,
        "life_expectancy": life_expectancy,
        "current_savings": current_savings,
        "annual_contribution": annual_contribution,
        "contribution_growth_rate": contribution_growth_rate,
        "expected_return": expected_return,
        "volatility": volatility,
        "inflation_rate": inflation_rate,
        "annual_spending": annual_spending,
        "annual_other_income": annual_other_income,
        "withdrawal_timing": withdrawal_timing,
        "n_simulations": n_simulations,
        "random_seed": random_seed,
        "show_in_todays_dollars": dollar_basis == "Today's dollars",
    }


def _render_results(results) -> None:
    """Render every results section for a completed projection."""
    section_header(
        "Headline results",
        f"Based on {results.n_simulations:,} simulated market paths.",
    )
    render_headline_metrics(results)

    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)
    section_header(
        "Portfolio projection",
        "A sample of individual paths, the shaded 10th-to-90th percentile range, and "
        "the median outcome.",
    )
    st.plotly_chart(portfolio_paths_chart(results), use_container_width=True)

    with st.expander("Show percentile-only view (cleaner for client handouts)"):
        st.plotly_chart(percentile_band_chart(results), use_container_width=True)

    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)
    section_header(
        "Distribution of ending balances",
        f"Portfolio balance at age {results.inputs.life_expectancy} across all "
        "simulations. The top 1% of outcomes are grouped into the final bin so the "
        "main distribution stays readable.",
    )
    st.plotly_chart(ending_balance_histogram(results), use_container_width=True)

    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)
    section_header(
        "Balances by age and percentile",
        "Read across a row for the range of outcomes at that age.",
    )
    st.dataframe(build_percentile_table(results), use_container_width=True)

    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)
    section_header("Success and failure analysis")
    render_failure_metrics(results)
    st.dataframe(
        build_success_summary_table(results), use_container_width=True, hide_index=True
    )
    if results.n_failures == 0:
        st.success(
            "No simulation depleted the portfolio before life expectancy under these "
            "assumptions."
        )

    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)
    section_header("Client summary")
    st.markdown(build_interpretation(results))

    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)
    section_header("Assumptions used")
    with st.expander("View all assumptions and methodology notes", expanded=False):
        st.dataframe(
            build_assumptions_table(results.inputs),
            use_container_width=True,
            hide_index=True,
        )
        st.markdown("**Modelling notes**")
        for note in build_methodology_notes():
            st.markdown(f"- {note}")

    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)
    section_header(
        "Downloads",
        "Export the numbers for your own analysis, or a client-ready PDF summary.",
    )
    client_name = st.text_input(
        "Client name for the report (optional)",
        placeholder="e.g. Jordan Sample",
        key="report_client_name",
    )

    download_columns = st.columns(2, gap="medium")
    with download_columns[0]:
        csv = build_percentile_table(results).to_csv().encode("utf-8")
        st.download_button(
            "Download percentile table (CSV)",
            data=csv,
            file_name="retirement_percentiles.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with download_columns[1]:
        # The report is only built when requested — generating the chart image and PDF
        # takes a moment, so it should not run on every rerun.
        if st.button("Prepare client report (PDF)", use_container_width=True):
            with st.spinner("Building report..."):
                from services.report_service import build_client_report

                st.session_state["client_report_pdf"] = build_client_report(
                    results, client_name=client_name
                )
        report_bytes = st.session_state.get("client_report_pdf")
        if report_bytes:
            st.download_button(
                "Download client report (PDF)",
                data=report_bytes,
                file_name="retirement_summary.pdf",
                mime="application/pdf",
                use_container_width=True,
            )


# ---------------------------------------------------------------------------
# Page flow
# ---------------------------------------------------------------------------
raw_inputs = _collect_inputs()
st.sidebar.markdown("---")

_run_col, _reset_col = st.sidebar.columns([2, 1])
with _run_col:
    run_clicked = st.button("Run simulation", type="primary", use_container_width=True)
with _reset_col:
    reset_clicked = st.button("Reset", use_container_width=True, help="Clear inputs and results.")

if reset_clicked:
    # Clear every keyed input plus the stored projection, then rerun so the widgets
    # rebuild at their defaults. Keys are removed rather than reassigned because a
    # widget's value cannot be set both by session state and a value= argument.
    for state_key in list(st.session_state.keys()):
        if state_key.startswith("in_"):
            del st.session_state[state_key]
    st.session_state.pop(RESULTS_SESSION_KEY, None)
    st.session_state.pop(PLANNER_PREFILL_KEY, None)
    st.rerun()

inputs = build_inputs(raw_inputs)
errors = validate(inputs)

if errors:
    st.error("Please correct the following before running the projection:")
    for message in errors:
        st.markdown(f"- {message}")
    st.stop()

st.caption(
    f"Ready to project ages {inputs.current_age} to {inputs.life_expectancy}: "
    f"{inputs.years_to_retirement} years of saving followed by "
    f"{inputs.years_in_retirement} years of withdrawals."
)

if run_clicked:
    with st.spinner(f"Running {inputs.n_simulations:,} simulations..."):
        st.session_state[RESULTS_SESSION_KEY] = run_projection(inputs)

stored_results = st.session_state.get(RESULTS_SESSION_KEY)

if stored_results is None:
    st.info(
        "Set the plan inputs in the sidebar, then select **Run simulation**. Results "
        "stay available on the Client Overview page as you move between modules."
    )
else:
    _render_results(stored_results)

st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)
render_disclaimer()
