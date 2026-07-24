"""Scenario Comparison — compare several retirement plans side by side.

Like the Retirement Planner, this page handles input collection, session state and
layout only. Scenario logic lives in :mod:`models.comparison` and formatting in
:mod:`services.scenario_service`.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st  # noqa: E402

from components.charts import (  # noqa: E402
    scenario_median_paths_chart,
    scenario_success_chart,
    sensitivity_chart,
)
from components.metrics import render_metric_row  # noqa: E402
from components.navigation import (  # noqa: E402
    configure_page,
    page_header,
    render_disclaimer,
    render_sidebar_brand,
    section_header,
)
from models.comparison import (  # noqa: E402
    SENSITIVITY_FIELDS,
    Scenario,
    analyse_levers,
    build_variant,
    run_scenario,
    run_sensitivity,
    suggested_sweep_values,
)
from services.retirement_service import RESULTS_SESSION_KEY  # noqa: E402
from services.scenario_service import (  # noqa: E402
    MAX_SCENARIOS,
    SCENARIOS_SESSION_KEY,
    build_comparison_narrative,
    build_comparison_table,
    build_difference_notes,
    build_lever_narrative,
    build_lever_table,
    build_sensitivity_table,
)
from utils.assumptions import BOUNDS  # noqa: E402
from utils.formatting import format_currency, format_percent  # noqa: E402

configure_page("Scenario Comparison")
render_sidebar_brand()

page_header(
    "Scenario Comparison",
    "Run several plans side by side to see which assumptions actually move the outcome.",
)


def get_scenarios() -> list[Scenario]:
    """Return the saved scenarios held in session state."""
    return st.session_state.setdefault(SCENARIOS_SESSION_KEY, [])


def add_scenario(scenario: Scenario) -> tuple[bool, str]:
    """Add a scenario to the library, enforcing the cap and unique names."""
    scenarios = get_scenarios()
    if len(scenarios) >= MAX_SCENARIOS:
        return False, (
            f"The comparison holds a maximum of {MAX_SCENARIOS} scenarios. "
            "Remove one before adding another."
        )
    if any(existing.name == scenario.name for existing in scenarios):
        return False, f"A scenario named '{scenario.name}' already exists."
    scenarios.append(scenario)
    return True, f"Added '{scenario.name}'."


def render_empty_state() -> None:
    """Explain the dependency on the Retirement Planner."""
    st.info(
        "This module compares variations on a baseline plan, so it needs a projection "
        "to start from.\n\n"
        "Open the **Retirement Planner**, set the client's assumptions, and select "
        "**Run simulation**. Then come back here to build variations on it."
    )
    st.page_link("pages/2_Retirement_Planner.py", label="Go to the Retirement Planner")


def render_library(scenarios: list[Scenario]) -> None:
    """Render the saved-scenario list with remove controls."""
    if not scenarios:
        st.caption("No scenarios saved yet. Add the baseline below to begin.")
        return

    for index, scenario in enumerate(scenarios):
        columns = st.columns([4, 2, 2, 1])
        with columns[0]:
            st.markdown(f"**{scenario.name}**")
            st.caption(
                f"Retire at {scenario.inputs.retirement_age} · "
                f"{format_currency(scenario.inputs.annual_contribution)}/yr saved · "
                f"{format_currency(scenario.inputs.annual_spending)}/yr spending"
            )
        with columns[1]:
            st.metric("Success", format_percent(scenario.results.success_probability))
        with columns[2]:
            st.metric(
                "Median ending",
                format_currency(scenario.results.median_ending_balance),
            )
        with columns[3]:
            if st.button("Remove", key=f"remove_{index}", use_container_width=True):
                scenarios.pop(index)
                st.rerun()


def render_variant_builder(base_scenario: Scenario) -> None:
    """Render the form used to create a new variant of the baseline."""
    base = base_scenario.inputs

    with st.form("variant_form"):
        st.markdown("**Create a variant**")
        st.caption(
            "Every field starts at the baseline value. Change only what you want to "
            "test — anything left alone is held constant."
        )

        name = st.text_input("Scenario name", placeholder="e.g. Retire at 67")

        left, right = st.columns(2)
        with left:
            retirement_age = st.number_input(
                "Retirement age",
                min_value=int(BOUNDS["retirement_age"][0]),
                max_value=int(BOUNDS["retirement_age"][1]),
                value=int(base.retirement_age),
                step=1,
            )
            annual_contribution = st.number_input(
                "Annual contribution ($)",
                min_value=0.0,
                max_value=float(BOUNDS["annual_contribution"][1]),
                value=float(base.annual_contribution),
                step=1_000.0,
            )
            current_savings = st.number_input(
                "Current savings ($)",
                min_value=0.0,
                max_value=float(BOUNDS["current_savings"][1]),
                value=float(base.current_savings),
                step=5_000.0,
            )
        with right:
            annual_spending = st.number_input(
                "Annual spending ($, today's dollars)",
                min_value=0.0,
                max_value=float(BOUNDS["annual_spending"][1]),
                value=float(base.annual_spending),
                step=2_500.0,
            )
            expected_return = (
                st.slider(
                    "Expected annual return (%)",
                    min_value=BOUNDS["expected_return"][0] * 100,
                    max_value=BOUNDS["expected_return"][1] * 100,
                    value=float(base.expected_return) * 100,
                    step=0.25,
                )
                / 100
            )
            volatility = (
                st.slider(
                    "Annual volatility (%)",
                    min_value=BOUNDS["volatility"][0] * 100,
                    max_value=BOUNDS["volatility"][1] * 100,
                    value=float(base.volatility) * 100,
                    step=0.5,
                )
                / 100
            )

        submitted = st.form_submit_button("Run and add scenario", type="primary")

    if submitted:
        if not name.strip():
            st.error("Give the scenario a name so it can be identified in the comparison.")
            return
        variant = build_variant(
            base,
            retirement_age=int(retirement_age),
            annual_contribution=float(annual_contribution),
            current_savings=float(current_savings),
            annual_spending=float(annual_spending),
            expected_return=float(expected_return),
            volatility=float(volatility),
        )
        try:
            with st.spinner(f"Running '{name}'..."):
                scenario = run_scenario(name, variant)
        except Exception as error:  # noqa: BLE001 - surfaced to the user directly
            st.error(f"That scenario could not be run: {error}")
            return
        added, message = add_scenario(scenario)
        if added:
            st.success(message)
            st.rerun()
        else:
            st.warning(message)


def render_quick_presets(base_scenario: Scenario) -> None:
    """Offer one-click standard variants an advisor would commonly test."""
    base = base_scenario.inputs
    presets = [
        (
            f"Retire at {base.retirement_age + 3}",
            {"retirement_age": base.retirement_age + 3},
        ),
        (
            "Save $5,000 more",
            {"annual_contribution": base.annual_contribution + 5_000.0},
        ),
        (
            "Spend $10,000 less",
            {"annual_spending": max(0.0, base.annual_spending - 10_000.0)},
        ),
    ]

    columns = st.columns(len(presets))
    for column, (label, overrides) in zip(columns, presets):
        with column:
            if st.button(label, key=f"preset_{label}", use_container_width=True):
                variant = build_variant(base, **overrides)
                try:
                    scenario = run_scenario(label, variant)
                except Exception as error:  # noqa: BLE001
                    st.error(f"Could not run that preset: {error}")
                    return
                added, message = add_scenario(scenario)
                if added:
                    st.success(message)
                    st.rerun()
                else:
                    st.warning(message)


def render_comparison(scenarios: list[Scenario]) -> None:
    """Render the comparison table, charts and narrative."""
    section_header(
        "Side-by-side comparison",
        "Each column is one complete projection. Read across a row to compare a single "
        "metric.",
    )
    st.dataframe(build_comparison_table(scenarios), use_container_width=True)

    notes = build_difference_notes(scenarios)
    if notes:
        with st.expander("What differs between these scenarios"):
            st.caption(f"Compared against **{scenarios[0].name}**:")
            for note in notes:
                st.markdown(f"- {note}")

    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)
    section_header("Success probability")
    st.plotly_chart(scenario_success_chart(scenarios), use_container_width=True)

    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)
    section_header(
        "Median paths",
        "Only the median path of each scenario is drawn. Dotted vertical lines mark "
        "each scenario's own retirement age.",
    )
    st.plotly_chart(scenario_median_paths_chart(scenarios), use_container_width=True)

    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)
    section_header("Comparison summary")
    st.markdown(build_comparison_narrative(scenarios))

    csv = build_comparison_table(scenarios).to_csv().encode("utf-8")
    st.download_button(
        "Download comparison (CSV)",
        data=csv,
        file_name="scenario_comparison.csv",
        mime="text/csv",
    )


def render_sensitivity_section(base_scenario: Scenario) -> None:
    """Render the one-variable sensitivity sweep."""
    base = base_scenario.inputs

    section_header(
        "Sensitivity analysis",
        "Vary one assumption across a range while holding everything else constant.",
    )

    left, right = st.columns([2, 1])
    with left:
        field_name = st.selectbox(
            "Assumption to vary",
            options=list(SENSITIVITY_FIELDS.keys()),
            format_func=lambda key: SENSITIVITY_FIELDS[key]["label"],
        )
    with right:
        sweep_simulations = st.select_slider(
            "Simulations per point",
            options=[1_000, 2_000, 5_000, 10_000],
            value=2_000,
            help="A sweep runs one full projection per point, so a lower count keeps "
            "it responsive. Raise it if the curve looks noisy.",
        )

    if st.button("Run sensitivity analysis", type="primary"):
        values = suggested_sweep_values(base, field_name)
        with st.spinner("Running sweep..."):
            st.session_state["latest_sweep"] = run_sensitivity(
                base, field_name, values, n_simulations=int(sweep_simulations)
            )

    sweep = st.session_state.get("latest_sweep")
    if sweep is None:
        st.caption("Select an assumption and run the sweep to see the curve.")
        return

    if not sweep.values:
        st.warning(
            "No valid values could be tested for that assumption. Every point in the "
            "range produced an invalid plan."
        )
        return

    baseline_value = getattr(base, sweep.field_name)
    st.plotly_chart(
        sensitivity_chart(sweep, baseline_value=baseline_value), use_container_width=True
    )
    st.dataframe(
        build_sensitivity_table(sweep), use_container_width=True, hide_index=True
    )

    if sweep.skipped_values:
        st.caption(
            f"{len(sweep.skipped_values)} value(s) were skipped because they produced "
            "an invalid plan, for example a retirement age above life expectancy."
        )


def render_lever_section(base_scenario: Scenario) -> None:
    """Render the 'which single change helps most' analysis."""
    section_header(
        "Which single change helps most",
        "Each change is applied on its own to the baseline, so the effects are "
        "comparable but not additive.",
    )

    if st.button("Analyse improvement levers"):
        with st.spinner("Testing changes..."):
            st.session_state["latest_levers"] = analyse_levers(
                base_scenario.inputs, n_simulations=2_000
            )

    levers = st.session_state.get("latest_levers")
    if levers is None:
        st.caption("Run the analysis to rank the standard changes by their effect.")
        return

    st.dataframe(build_lever_table(levers), use_container_width=True, hide_index=True)
    st.markdown(build_lever_narrative(levers))


# ---------------------------------------------------------------------------
# Page flow
# ---------------------------------------------------------------------------
planner_results = st.session_state.get(RESULTS_SESSION_KEY)

if planner_results is None:
    render_empty_state()
    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)
    render_disclaimer()
else:
    base_scenario = Scenario(
        name="Baseline (from planner)",
        inputs=planner_results.inputs,
        results=planner_results,
    )

    section_header("Baseline plan")
    render_metric_row(
        [
            (
                "Success probability",
                format_percent(planner_results.success_probability),
                "From the most recent Retirement Planner run.",
            ),
            ("Retirement age", str(planner_results.inputs.retirement_age), ""),
            (
                "Annual contribution",
                format_currency(planner_results.inputs.annual_contribution),
                "",
            ),
            (
                "Annual spending",
                format_currency(planner_results.inputs.annual_spending),
                "Today's dollars.",
            ),
        ]
    )

    saved_scenarios = get_scenarios()
    if not any(s.name == base_scenario.name for s in saved_scenarios):
        if st.button("Add baseline to comparison", type="primary"):
            added, message = add_scenario(base_scenario)
            if added:
                st.success(message)
                st.rerun()
            else:
                st.warning(message)

    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)

    section_header(
        "Saved scenarios",
        f"Holds up to {MAX_SCENARIOS} scenarios at a time.",
    )
    render_library(saved_scenarios)

    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)
    section_header("Add a scenario")
    st.markdown("**Quick presets**")
    render_quick_presets(base_scenario)
    st.markdown("")
    render_variant_builder(base_scenario)

    if len(saved_scenarios) >= 2:
        st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)
        render_comparison(saved_scenarios)
    elif saved_scenarios:
        st.info("Add one more scenario to see the side-by-side comparison.")

    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)
    render_sensitivity_section(base_scenario)

    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)
    render_lever_section(base_scenario)

    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)
    render_disclaimer()
