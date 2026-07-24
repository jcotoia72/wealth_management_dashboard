"""Service layer for the Risk Profile module.

No Streamlit, no Plotly. Formats the scoring output and writes the plain-English
explanation of the recommendation.
"""

from __future__ import annotations

import pandas as pd

from models.risk_profile import RiskProfile
from utils.assumptions import PORTFOLIO_PRESETS, RISK_BANDS
from utils.formatting import format_percent

# Session-state key holding the most recent risk profile, so the Retirement Planner can
# offer to adopt it.
RISK_PROFILE_SESSION_KEY = "latest_risk_profile"


def build_score_table(profile: RiskProfile) -> pd.DataFrame:
    """Return a small table of the three headline scores."""
    rows = [
        ("Risk tolerance (willingness)", f"{profile.tolerance_score:.0f} / 100"),
        ("Risk capacity (ability)", f"{profile.capacity_score:.0f} / 100"),
        ("Overall (lower of the two)", f"{profile.overall_score:.0f} / 100"),
    ]
    return pd.DataFrame(rows, columns=["Measure", "Score"])


def build_contribution_table(profile: RiskProfile) -> pd.DataFrame:
    """Return a transparent breakdown of how each answer fed the score."""
    rows = [
        {
            "Question": contribution.question_text,
            "Category": contribution.category.capitalize(),
            "Answer": contribution.option_label,
            "Score (1-5)": contribution.option_score,
            "Weight": f"{contribution.weight:.1f}",
        }
        for contribution in profile.contributions
    ]
    return pd.DataFrame(rows)


def build_recommendation_table(profile: RiskProfile) -> pd.DataFrame:
    """Return the recommended portfolio's assumptions."""
    rows = [
        ("Recommended profile", profile.level),
        ("Model portfolio", profile.recommended_preset),
        ("Expected annual return", format_percent(profile.expected_return)),
        ("Annual volatility", format_percent(profile.volatility)),
    ]
    return pd.DataFrame(rows, columns=["Item", "Value"])


def build_all_profiles_table() -> pd.DataFrame:
    """Return every risk band and its portfolio, for context under the recommendation."""
    rows = []
    for band in RISK_BANDS:
        preset = PORTFOLIO_PRESETS[band["preset"]]
        rows.append(
            {
                "Profile": band["level"],
                "Score range": f"{band['min']:.0f} – {min(band['max'], 100):.0f}",
                "Model portfolio": band["preset"],
                "Expected return": format_percent(preset["expected_return"]),
                "Volatility": format_percent(preset["volatility"]),
            }
        )
    return pd.DataFrame(rows)


def build_profile_narrative(profile: RiskProfile) -> str:
    """Write a short plain-English explanation of the recommendation."""
    sentences = [
        f"Based on the questionnaire, this client's risk profile is **{profile.level}**, "
        f"which maps to a {profile.recommended_preset} model portfolio with an assumed "
        f"return of {format_percent(profile.expected_return)} and volatility of "
        f"{format_percent(profile.volatility)}.",
        f"The profile reflects a risk tolerance score of "
        f"{profile.tolerance_score:.0f} and a risk capacity score of "
        f"{profile.capacity_score:.0f} out of 100.",
    ]

    if profile.is_mismatched:
        sentences.append(profile.mismatch)
    else:
        sentences.append(
            "Tolerance and capacity are broadly consistent, so the recommendation is "
            "straightforward."
        )

    sentences.append(
        "This is a starting point for a conversation, not a directive. A questionnaire "
        "cannot capture everything about a client's circumstances, and the final "
        "allocation should reflect a fuller discussion."
    )
    return " ".join(sentences)


def build_planner_handoff_note(profile: RiskProfile) -> str:
    """Return the note shown when offering to send the profile to the planner."""
    return (
        f"Apply the {profile.level} portfolio "
        f"({format_percent(profile.expected_return)} return, "
        f"{format_percent(profile.volatility)} volatility) to the Retirement Planner "
        "as its investment assumptions."
    )
