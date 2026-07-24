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
from utils.formatting import format_percent


def all_answers(score: int) -> dict[str, int]:
    """Return an answer set where every question is answered with the same score."""
    return {question["id"]: score for question in RISK_QUESTIONS}


def _scores_for_overall(target: float) -> dict[str, int]:
    """Return answers whose overall score is closest to ``target`` (0-100).

    Overall is the minimum of the two category axes, and equal answers across every
    question produce equal tolerance and capacity, so a single uniform answer level
    maps directly onto a score. This searches the achievable uniform-level scores and
    the fractional mixes between adjacent levels to get close to the target.
    """
    from models.risk_profile import score_questionnaire

    best_answers = all_answers(3)
    best_gap = abs(score_questionnaire(best_answers).overall_score - target)

    # Try uniform levels and simple mixes (some questions one level, rest the next).
    question_ids = [q["id"] for q in RISK_QUESTIONS]
    for base_level in range(1, 5):
        for n_upgraded in range(len(question_ids) + 1):
            answers = {qid: base_level for qid in question_ids}
            for qid in question_ids[:n_upgraded]:
                answers[qid] = base_level + 1
            gap = abs(score_questionnaire(answers).overall_score - target)
            if gap < best_gap:
                best_gap, best_answers = gap, dict(answers)
    return best_answers


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
# Interpolation: the core of the continuous mapping
# ---------------------------------------------------------------------------
def test_interpolation_hits_the_spectrum_endpoints() -> None:
    """Score 0 and 100 must land on the configured floor and ceiling (rounded)."""
    from models.risk_profile import interpolate_assumptions
    from utils.assumptions import RISK_SPECTRUM

    ret_lo, vol_lo = interpolate_assumptions(0.0)
    ret_hi, vol_hi = interpolate_assumptions(100.0)

    increment = RISK_SPECTRUM["rounding"]
    assert ret_lo == pytest.approx(RISK_SPECTRUM["return_floor"], abs=increment)
    assert vol_lo == pytest.approx(RISK_SPECTRUM["volatility_floor"], abs=increment)
    assert ret_hi == pytest.approx(RISK_SPECTRUM["return_ceiling"], abs=increment)
    assert vol_hi == pytest.approx(RISK_SPECTRUM["volatility_ceiling"], abs=increment)


def test_interpolation_is_monotonic_across_the_range() -> None:
    """Higher scores must never produce lower return or volatility."""
    from models.risk_profile import interpolate_assumptions

    returns, vols = [], []
    for score in range(0, 101, 5):
        r, v = interpolate_assumptions(float(score))
        returns.append(r)
        vols.append(v)
    assert returns == sorted(returns)
    assert vols == sorted(vols)


def test_interpolation_is_rounded_to_the_configured_increment() -> None:
    """Every interpolated rate must be a clean multiple of the rounding increment."""
    from models.risk_profile import interpolate_assumptions
    from utils.assumptions import RISK_SPECTRUM

    increment = RISK_SPECTRUM["rounding"]
    for score in (12.0, 37.5, 58.3, 81.9, 99.0):
        r, v = interpolate_assumptions(score)
        # A value that is a multiple of the increment leaves ~0 remainder.
        assert r / increment == pytest.approx(round(r / increment), abs=1e-6)
        assert v / increment == pytest.approx(round(v / increment), abs=1e-6)


def test_two_scores_in_the_same_band_can_differ() -> None:
    """The whole point: two scores in one band need not share assumptions.

    Snapping to a preset would give these identical numbers; interpolation should not.
    """
    lower = score_questionnaire(_scores_for_overall(58))
    higher = score_questionnaire(_scores_for_overall(68))

    # The higher score must carry higher-or-equal assumptions, and across this gap
    # they should genuinely differ — which snapping to a single preset would prevent.
    assert higher.expected_return >= lower.expected_return
    assert higher.volatility >= lower.volatility
    assert (
        higher.expected_return != lower.expected_return
        or higher.volatility != lower.volatility
    )


def test_volatility_rises_faster_than_return() -> None:
    """Volatility should accelerate relative to return as risk increases.

    Comparing the low half and high half of the spectrum, volatility should gain a
    larger share of its total range than return does — the diminishing risk-adjusted
    reward the curve shapes are meant to capture.
    """
    from models.risk_profile import interpolate_assumptions
    from utils.assumptions import RISK_SPECTRUM

    r_mid, v_mid = interpolate_assumptions(50.0)

    return_range = RISK_SPECTRUM["return_ceiling"] - RISK_SPECTRUM["return_floor"]
    vol_range = RISK_SPECTRUM["volatility_ceiling"] - RISK_SPECTRUM["volatility_floor"]
    return_progress = (r_mid - RISK_SPECTRUM["return_floor"]) / return_range
    vol_progress = (v_mid - RISK_SPECTRUM["volatility_floor"]) / vol_range

    # At the midpoint, return should be further along its range than volatility,
    # because return front-loads (curve < 1) and volatility back-loads (curve > 1).
    assert return_progress > vol_progress


def test_nearest_preset_is_a_real_preset() -> None:
    """The label's nearest preset must exist and never be 'Custom'."""
    for level in (1, 2, 3, 4, 5):
        profile = score_questionnaire(all_answers(level))
        assert profile.nearest_preset in PORTFOLIO_PRESETS
        assert profile.nearest_preset != "Custom"


def test_descriptive_label_reflects_within_band_position() -> None:
    """Scores at different positions must produce different descriptive labels.

    The label encodes where in a band the score sits (cautious / solidly / leaning),
    so two clearly different scores should not share a label.
    """
    low = score_questionnaire(_scores_for_overall(40))
    high = score_questionnaire(_scores_for_overall(70))
    assert low.descriptive_label != high.descriptive_label
    # The label vocabulary should be one of the three within-band descriptors.
    for profile in (low, high):
        assert any(
            word in profile.descriptive_label.lower()
            for word in ("cautious", "solidly", "leaning")
        )


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
    """The narrative must state the descriptive label and the interpolated figures."""
    profile = score_questionnaire(all_answers(5))
    narrative = build_profile_narrative(profile)
    assert profile.descriptive_label in narrative
    assert format_percent(profile.expected_return) in narrative


def test_default_answers_covers_all_questions() -> None:
    """The default answer set must answer every question exactly once."""
    defaults = default_answers()
    assert set(defaults.keys()) == {question["id"] for question in RISK_QUESTIONS}
