"""Tests for the risk profiling engine.

Run from the project root with:
    pytest
"""

from __future__ import annotations

import pytest

from models.monte_carlo import RetirementInputs
from models.risk_profile import (
    RiskProfile,
    apply_profile_to_inputs,
    default_answers,
    score_questionnaire,
)
from services.risk_service import (
    build_all_profiles_table,
    build_contribution_table,
    build_profile_narrative,
    build_score_table,
)
from utils.assumptions import PORTFOLIO_PRESETS, RISK_BANDS, RISK_QUESTIONS


def all_answers(score: int) -> dict[str, int]:
    """Return an answer set where every question is answered with the same score."""
    return {question["id"]: score for question in RISK_QUESTIONS}


def make_inputs(**overrides) -> RetirementInputs:
    """A valid baseline for testing the planner hand-off."""
    base = dict(
        current_age=35,
        retirement_age=65,
        life_expectancy=90,
        current_savings=150_000.0,
        annual_contribution=20_000.0,
        contribution_growth_rate=0.02,
        expected_return=0.07,
        volatility=0.15,
        inflation_rate=0.025,
        annual_spending=70_000.0,
        annual_other_income=25_000.0,
        withdrawal_timing="beginning",
        n_simulations=1_000,
        random_seed=42,
        show_in_todays_dollars=False,
    )
    base.update(overrides)
    return RetirementInputs(**base)


# ---------------------------------------------------------------------------
# Configuration sanity
# ---------------------------------------------------------------------------
def test_questionnaire_has_both_categories() -> None:
    """The questionnaire must measure both tolerance and capacity."""
    categories = {question["category"] for question in RISK_QUESTIONS}
    assert categories == {"tolerance", "capacity"}


def test_every_option_scores_one_to_five() -> None:
    """All option scores must sit on the documented 1-5 scale."""
    for question in RISK_QUESTIONS:
        scores = [score for _, score in question["options"]]
        assert scores == [1, 2, 3, 4, 5]


def test_risk_bands_cover_the_full_range_without_gaps() -> None:
    """Bands must tile 0-100 with no gap or overlap."""
    ordered = sorted(RISK_BANDS, key=lambda band: band["min"])
    assert ordered[0]["min"] == 0.0
    for earlier, later in zip(ordered, ordered[1:]):
        assert earlier["max"] == later["min"]
    assert ordered[-1]["max"] >= 100.0


def test_every_band_maps_to_a_real_preset() -> None:
    """Each band's portfolio must exist in the preset table."""
    for band in RISK_BANDS:
        assert band["preset"] in PORTFOLIO_PRESETS
        assert "expected_return" in PORTFOLIO_PRESETS[band["preset"]]


# ---------------------------------------------------------------------------
# Scoring behaviour
# ---------------------------------------------------------------------------
def test_all_lowest_answers_produce_the_most_conservative_profile() -> None:
    """Answering everything at score 1 must yield the conservative profile."""
    profile = score_questionnaire(all_answers(1))
    assert profile.level == "Conservative"
    assert profile.tolerance_score == 0.0
    assert profile.capacity_score == 0.0
    assert profile.overall_score == 0.0


def test_all_highest_answers_produce_the_most_aggressive_profile() -> None:
    """Answering everything at score 5 must yield the aggressive profile."""
    profile = score_questionnaire(all_answers(5))
    assert profile.level == "Aggressive"
    assert profile.tolerance_score == 100.0
    assert profile.capacity_score == 100.0


def test_middle_answers_produce_a_mid_scale_score() -> None:
    """Answering everything at the middle option must score 50 on each axis."""
    profile = score_questionnaire(default_answers())
    assert profile.tolerance_score == pytest.approx(50.0)
    assert profile.capacity_score == pytest.approx(50.0)


def test_score_rises_monotonically_with_answer_level() -> None:
    """Higher answers must never produce a lower overall score."""
    scores = [score_questionnaire(all_answers(level)).overall_score for level in (1, 2, 3, 4, 5)]
    assert scores == sorted(scores)


def test_overall_is_the_minimum_not_the_average() -> None:
    """Overall score must follow the weaker axis, not the mean of the two.

    A client who is willing (high tolerance) but unable (low capacity) must be scored
    down to their capacity, so the recommendation stays suitable.
    """
    answers = {}
    for question in RISK_QUESTIONS:
        # Max out tolerance, minimise capacity.
        answers[question["id"]] = 5 if question["category"] == "tolerance" else 1

    profile = score_questionnaire(answers)
    assert profile.tolerance_score == 100.0
    assert profile.capacity_score == 0.0
    assert profile.overall_score == 0.0  # the minimum, not 50
    assert profile.level == "Conservative"


def test_empty_answers_are_rejected() -> None:
    """An empty questionnaire cannot produce a profile."""
    with pytest.raises(ValueError):
        score_questionnaire({})


# ---------------------------------------------------------------------------
# Mismatch detection
# ---------------------------------------------------------------------------
def test_large_tolerance_capacity_gap_is_flagged() -> None:
    """A wide gap between the two axes must produce a mismatch note."""
    answers = {}
    for question in RISK_QUESTIONS:
        answers[question["id"]] = 5 if question["category"] == "tolerance" else 1
    profile = score_questionnaire(answers)
    assert profile.is_mismatched
    assert profile.mismatch is not None


def test_consistent_answers_are_not_flagged() -> None:
    """When both axes agree, there must be no mismatch note."""
    profile = score_questionnaire(all_answers(3))
    assert not profile.is_mismatched
    assert profile.mismatch is None


def test_mismatch_direction_is_described_correctly() -> None:
    """The willing-but-constrained case must mention capacity as the limiter."""
    answers = {}
    for question in RISK_QUESTIONS:
        answers[question["id"]] = 5 if question["category"] == "tolerance" else 1
    profile = score_questionnaire(answers)
    assert "capacity" in profile.mismatch.lower()


# ---------------------------------------------------------------------------
# Planner hand-off
# ---------------------------------------------------------------------------
def test_apply_profile_sets_return_and_volatility() -> None:
    """Applying a profile must overwrite exactly the two investment assumptions."""
    base = make_inputs()
    profile = score_questionnaire(all_answers(5))
    updated = apply_profile_to_inputs(base, profile)

    assert updated.expected_return == profile.expected_return
    assert updated.volatility == profile.volatility
    # Everything else must be untouched.
    assert updated.current_savings == base.current_savings
    assert updated.retirement_age == base.retirement_age


def test_apply_profile_does_not_mutate_the_base() -> None:
    """The frozen base inputs must not change when a profile is applied."""
    base = make_inputs(expected_return=0.07, volatility=0.15)
    profile = score_questionnaire(all_answers(1))
    apply_profile_to_inputs(base, profile)
    assert base.expected_return == 0.07
    assert base.volatility == 0.15


def test_applied_profile_produces_a_runnable_projection() -> None:
    """The whole loop must work: score, apply, and the result must simulate."""
    from models.monte_carlo import run_retirement_simulation

    base = make_inputs()
    profile = score_questionnaire(all_answers(4))
    updated = apply_profile_to_inputs(base, profile)
    results = run_retirement_simulation(updated)
    assert 0.0 <= results.success_probability <= 1.0


# ---------------------------------------------------------------------------
# Recommended assumptions are ordered sensibly
# ---------------------------------------------------------------------------
def test_more_aggressive_profiles_have_higher_return_and_volatility() -> None:
    """Across the profiles, both return and volatility must increase together."""
    profiles = [score_questionnaire(all_answers(level)) for level in (1, 3, 4, 5)]
    returns = [p.expected_return for p in profiles]
    vols = [p.volatility for p in profiles]
    assert returns == sorted(returns)
    assert vols == sorted(vols)


# ---------------------------------------------------------------------------
# Service formatting
# ---------------------------------------------------------------------------
def test_score_table_has_three_measures() -> None:
    """The score table must show tolerance, capacity and overall."""
    profile = score_questionnaire(default_answers())
    table = build_score_table(profile)
    assert len(table) == 3


def test_contribution_table_has_a_row_per_answer() -> None:
    """The breakdown must account for every answered question."""
    answers = all_answers(3)
    profile = score_questionnaire(answers)
    table = build_contribution_table(profile)
    assert len(table) == len(answers)


def test_all_profiles_table_lists_every_band() -> None:
    """The reference table must show all four risk levels."""
    table = build_all_profiles_table()
    assert len(table) == len(RISK_BANDS)


def test_narrative_names_the_level_and_portfolio() -> None:
    """The narrative must state the recommended level and portfolio."""
    profile = score_questionnaire(all_answers(5))
    narrative = build_profile_narrative(profile)
    assert profile.level in narrative
    assert profile.recommended_preset in narrative


def test_default_answers_covers_all_questions() -> None:
    """The default answer set must answer every question exactly once."""
    defaults = default_answers()
    assert set(defaults.keys()) == {question["id"] for question in RISK_QUESTIONS}
