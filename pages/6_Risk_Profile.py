"""Risk Profile — a questionnaire that maps a client to a model portfolio.

This module closes the loop with the Retirement Planner: the recommended portfolio's
return and volatility can be sent straight to the planner as its investment
assumptions. Scoring lives in :mod:`models.risk_profile`; this page handles the form,
session state and layout only.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st  # noqa: E402

from components.charts import risk_gauge_chart  # noqa: E402
from components.metrics import render_metric_row  # noqa: E402
from components.navigation import (  # noqa: E402
    configure_page,
    page_header,
    render_disclaimer,
    render_sidebar_brand,
    section_header,
)
from models.risk_profile import score_questionnaire  # noqa: E402
from services.retirement_service import RESULTS_SESSION_KEY  # noqa: E402
from services.risk_service import (  # noqa: E402
    RISK_PROFILE_SESSION_KEY,
    build_all_profiles_table,
    build_contribution_table,
    build_planner_handoff_note,
    build_profile_narrative,
    build_recommendation_table,
    build_score_table,
)
from utils.assumptions import RISK_QUESTIONS  # noqa: E402
from utils.formatting import format_percent  # noqa: E402

# Key holding return/volatility to prefill the planner with, read by the planner page.
PLANNER_PREFILL_KEY = "planner_prefill_assumptions"

configure_page("Risk Profile")
render_sidebar_brand()

page_header(
    "Risk Profile",
    "A short questionnaire that scores risk tolerance and capacity, then maps the "
    "client to a model portfolio.",
)


def render_questionnaire() -> dict[str, int]:
    """Render the questionnaire and return the chosen option score for each question.

    Tolerance and capacity questions are grouped under their own headings so the two
    ideas stay visibly distinct.
    """
    answers: dict[str, int] = {}

    st.markdown(
        "Each question offers five choices, from most cautious to most risk-seeking. "
        "There are no right answers — the goal is to describe the client accurately."
    )

    for category, heading, blurb in [
        (
            "tolerance",
            "Part 1 — Risk tolerance (willingness)",
            "How the client feels about risk and volatility.",
        ),
        (
            "capacity",
            "Part 2 — Risk capacity (ability)",
            "How much risk the client's financial situation can absorb.",
        ),
    ]:
        section_header(heading, blurb)
        for question in [q for q in RISK_QUESTIONS if q["category"] == category]:
            labels = [label for label, _ in question["options"]]
            choice = st.radio(
                question["text"],
                options=labels,
                index=2,  # default to the middle option
                key=f"risk_{question['id']}",
            )
            # Map the chosen label back to its 1-5 score.
            answers[question["id"]] = next(
                score for label, score in question["options"] if label == choice
            )
        st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)

    return answers


def render_results(profile) -> None:
    """Render the scored profile, breakdown and planner hand-off."""
    section_header("Recommended profile")

    # The descriptive label can be two words ("Cautious Aggressive"), which looks
    # cramped in a metric card. Present it as a headline line instead, with the three
    # numeric results in metric cards below where the large-number styling suits them.
    st.markdown(
        f"<p style='font-size:1.35rem; font-weight:600; color:#14304a; "
        f"margin-bottom:0.2rem;'>{profile.descriptive_label}</p>"
        f"<p class='app-subtitle' style='margin-top:0;'>Overall risk score "
        f"{profile.overall_score:.0f} / 100</p>",
        unsafe_allow_html=True,
    )

    render_metric_row(
        [
            (
                "Overall score",
                f"{profile.overall_score:.0f} / 100",
                "The lower of the tolerance and capacity scores.",
            ),
            (
                "Expected return",
                format_percent(profile.expected_return),
                "Interpolated nominal annual return for this score.",
            ),
            (
                "Volatility",
                format_percent(profile.volatility),
                "Interpolated annual standard deviation for this score.",
            ),
        ]
    )

    if profile.is_mismatched:
        st.warning(profile.mismatch)

    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)
    section_header(
        "Tolerance versus capacity",
        "The recommendation follows the lower of the two scores.",
    )
    st.plotly_chart(
        risk_gauge_chart(
            profile.tolerance_score, profile.capacity_score, profile.overall_score
        ),
        use_container_width=True,
    )
    st.dataframe(build_score_table(profile), use_container_width=True, hide_index=True)

    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)
    section_header("Recommendation summary")
    st.markdown(build_profile_narrative(profile))

    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)
    section_header("Send to the Retirement Planner")
    st.caption(build_planner_handoff_note(profile))
    if st.button("Apply this portfolio to the planner", type="primary"):
        st.session_state[PLANNER_PREFILL_KEY] = {
            "expected_return": profile.expected_return,
            "volatility": profile.volatility,
            "source": profile.descriptive_label,
        }
        st.success(
            "Saved. Open the Retirement Planner and switch on the **Use Risk Profile "
            "assumptions** toggle in the sidebar to apply these values automatically."
        )
        st.page_link("pages/2_Retirement_Planner.py", label="Go to the Retirement Planner")

    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)
    with st.expander("How this score was calculated"):
        st.caption(
            "Each answer scores 1 (most cautious) to 5 (most risk-seeking). Category "
            "scores are the weighted average of answers, rescaled to 0-100."
        )
        st.dataframe(
            build_contribution_table(profile), use_container_width=True, hide_index=True
        )

    with st.expander("All risk profiles for reference"):
        st.dataframe(
            build_all_profiles_table(), use_container_width=True, hide_index=True
        )


# ---------------------------------------------------------------------------
# Page flow
# ---------------------------------------------------------------------------
answers = render_questionnaire()

_score_col, _reset_col = st.columns([2, 1])
with _score_col:
    score_clicked = st.button("Score questionnaire", type="primary", use_container_width=True)
with _reset_col:
    if st.button("Reset answers", use_container_width=True, help="Clear the questionnaire and result."):
        for state_key in list(st.session_state.keys()):
            if state_key.startswith("risk_"):
                del st.session_state[state_key]
        st.session_state.pop(RISK_PROFILE_SESSION_KEY, None)
        st.rerun()

if score_clicked:
    profile = score_questionnaire(answers)
    st.session_state[RISK_PROFILE_SESSION_KEY] = profile

stored_profile = st.session_state.get(RISK_PROFILE_SESSION_KEY)

if stored_profile is None:
    st.info(
        "Answer the questions above and select **Score questionnaire** to see the "
        "recommended profile."
    )
else:
    render_results(stored_profile)

st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)
render_disclaimer()
