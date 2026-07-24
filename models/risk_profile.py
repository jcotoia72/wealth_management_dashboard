"""Risk profiling engine: scores a questionnaire into a recommended portfolio.

Streamlit-free and Plotly-free, like the other engines. The scoring is fully
transparent — every weight and option score comes from
:data:`utils.assumptions.RISK_QUESTIONS`, and the intermediate contribution of each
answer is returned so the interface can show its work rather than presenting a black-box
number.

Public entry points
-------------------
    profile = score_questionnaire(answers)
    inputs  = apply_profile_to_inputs(base_inputs, profile)
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from models.monte_carlo import RetirementInputs
from utils.assumptions import (
    PORTFOLIO_PRESETS,
    RISK_BANDS,
    RISK_QUESTIONS,
    RISK_SPECTRUM,
)

# Option scores run 1 (most conservative) to 5 (most aggressive). These bounds are used
# to rescale a weighted average onto a 0-100 axis.
_MIN_OPTION_SCORE = 1
_MAX_OPTION_SCORE = 5


def _interpolate(score: float, floor: float, ceiling: float, curve: float) -> float:
    """Map a 0-100 score onto ``[floor, ceiling]`` along a power curve.

    ``curve`` shapes the mapping: 1.0 is linear, below 1.0 front-loads the gains
    (rises quickly then tapers), above 1.0 back-loads them (rises slowly then
    accelerates). The normalised score is clamped to [0, 1] for safety.
    """
    normalised = max(0.0, min(1.0, score / 100.0))
    shaped = normalised ** curve
    return floor + shaped * (ceiling - floor)


def _round_rate(value: float) -> float:
    """Round a rate to the spectrum's configured increment (default 0.25%)."""
    increment = RISK_SPECTRUM["rounding"]
    return round(value / increment) * increment


def interpolate_assumptions(score: float) -> tuple[float, float]:
    """Return ``(expected_return, volatility)`` for a 0-100 overall score.

    Both are interpolated along the risk spectrum and rounded, so that scores between
    band boundaries produce genuinely different assumptions rather than snapping to a
    preset.
    """
    spectrum = RISK_SPECTRUM
    expected_return = _interpolate(
        score,
        spectrum["return_floor"],
        spectrum["return_ceiling"],
        spectrum["return_curve"],
    )
    volatility = _interpolate(
        score,
        spectrum["volatility_floor"],
        spectrum["volatility_ceiling"],
        spectrum["volatility_curve"],
    )
    return _round_rate(expected_return), _round_rate(volatility)


@dataclass
class AnswerContribution:
    """One answered question and how it fed into the score."""

    question_id: str
    question_text: str
    category: str
    weight: float
    option_label: str
    option_score: int


@dataclass
class RiskProfile:
    """The outcome of scoring a completed questionnaire.

    Attributes
    ----------
    tolerance_score, capacity_score, overall_score:
        Scores on a 0-100 scale. Overall is the lower of the two category axes, not
        their average — see :func:`score_questionnaire` for why.
    level:
        The risk band label, e.g. ``"Moderate"``, taken from the overall score.
    descriptive_label:
        A finer label reflecting position within the band, e.g. ``"Growth-leaning"``.
    nearest_preset:
        The name of the closest reference portfolio in :data:`PORTFOLIO_PRESETS`. Used
        for context only; the actual assumptions are interpolated, not taken from it.
    expected_return, volatility:
        Interpolated assumptions for this specific score, ready to feed the planner.
    mismatch:
        A note when tolerance and capacity diverge sharply, or ``None``.
    contributions:
        Per-answer breakdown supporting a transparent display of the score.
    """

    tolerance_score: float
    capacity_score: float
    overall_score: float
    level: str
    descriptive_label: str
    nearest_preset: str
    expected_return: float
    volatility: float
    mismatch: str | None = None
    contributions: list[AnswerContribution] = field(default_factory=list)

    @property
    def is_mismatched(self) -> bool:
        """Whether tolerance and capacity diverge enough to warrant a caveat."""
        return self.mismatch is not None


def _category_score(
    answers: dict[str, int], category: str
) -> tuple[float, list[AnswerContribution]]:
    """Return the 0-100 weighted score for one category and its contributions.

    Only answered questions count toward the weighted average, so a partially completed
    questionnaire still produces a meaningful score for the questions that were answered.
    """
    questions = [q for q in RISK_QUESTIONS if q["category"] == category]

    weighted_sum = 0.0
    weight_total = 0.0
    contributions: list[AnswerContribution] = []

    for question in questions:
        if question["id"] not in answers:
            continue
        option_score = answers[question["id"]]
        weight = float(question["weight"])
        weighted_sum += option_score * weight
        weight_total += weight

        option_label = next(
            (label for label, score in question["options"] if score == option_score),
            "",
        )
        contributions.append(
            AnswerContribution(
                question_id=question["id"],
                question_text=question["text"],
                category=category,
                weight=weight,
                option_label=option_label,
                option_score=option_score,
            )
        )

    if weight_total == 0.0:
        return 0.0, contributions

    weighted_average = weighted_sum / weight_total
    # Rescale from the 1-5 option range onto 0-100.
    scaled = (weighted_average - _MIN_OPTION_SCORE) / (
        _MAX_OPTION_SCORE - _MIN_OPTION_SCORE
    )
    return scaled * 100.0, contributions


def _band_for_score(score: float) -> dict[str, Any]:
    """Return the risk band a 0-100 score falls into."""
    for band in RISK_BANDS:
        if band["min"] <= score < band["max"]:
            return band
    # Defensive fallback: clamp to the nearest band if a score lands exactly on 100.
    return RISK_BANDS[0] if score < RISK_BANDS[0]["min"] else RISK_BANDS[-1]


def _descriptive_label(score: float, band: dict[str, Any]) -> str:
    """Return a finer label reflecting where in its band the score sits.

    A score near the bottom of a band is described as "cautious", near the top as
    "leaning" toward the next level up. This surfaces the granularity the continuous
    score captured without inventing a whole new set of category names.
    """
    span = band["max"] - band["min"]
    if span <= 0:
        return band["level"]
    position = (score - band["min"]) / span  # 0 at band floor, 1 at band ceiling

    if position < 0.33:
        return f"Cautious {band['level']}"
    if position > 0.67:
        return f"{band['level']}-leaning"
    return f"Solidly {band['level']}"


def _nearest_preset(expected_return: float) -> str:
    """Return the preset portfolio whose return is closest to an interpolated value.

    Used only for the human-readable label; the actual assumptions are interpolated.
    The ``Custom`` preset (which has no assumptions) is skipped.
    """
    candidates = {
        name: values
        for name, values in PORTFOLIO_PRESETS.items()
        if "expected_return" in values
    }
    return min(
        candidates,
        key=lambda name: abs(candidates[name]["expected_return"] - expected_return),
    )


def _describe_mismatch(tolerance: float, capacity: float) -> str | None:
    """Return a plain-English caveat when tolerance and capacity diverge sharply.

    A gap of roughly one full risk band (about 20 points) is the threshold. Below that,
    the two axes are treated as broadly consistent.
    """
    gap = tolerance - capacity
    if abs(gap) < 20.0:
        return None
    if gap > 0:
        return (
            "Willing but constrained: the answers show a comfort with risk that the "
            "current financial situation may not support. The recommendation follows "
            "the lower capacity score, because the ability to absorb a loss matters more "
            "than the appetite for one."
        )
    return (
        "Able but cautious: the financial situation could support more risk than the "
        "client is comfortable taking. The recommendation follows the lower tolerance "
        "score; pushing a client past their comfort tends to end in selling at the worst "
        "possible moment."
    )


def score_questionnaire(answers: dict[str, int]) -> RiskProfile:
    """Score a completed questionnaire into a recommended portfolio.

    Parameters
    ----------
    answers:
        Mapping of question id to the chosen option's score (1-5).

    Returns
    -------
    RiskProfile

    Notes
    -----
    The overall score is the **minimum** of the tolerance and capacity scores, not their
    average. Suitability is limited by the weaker of the two: a client who is emotionally
    comfortable with risk but financially unable to absorb a loss should not be placed in
    an aggressive portfolio, and vice versa. Averaging would let a high score on one axis
    mask a genuine constraint on the other.
    """
    if not answers:
        raise ValueError("At least one question must be answered to produce a profile.")

    tolerance_score, tolerance_contrib = _category_score(answers, "tolerance")
    capacity_score, capacity_contrib = _category_score(answers, "capacity")
    overall_score = min(tolerance_score, capacity_score)

    band = _band_for_score(overall_score)
    # Interpolate assumptions from the continuous score rather than snapping to a
    # preset. Two clients in the same band but with different scores get genuinely
    # different assumptions.
    expected_return, volatility = interpolate_assumptions(overall_score)
    nearest = _nearest_preset(expected_return)

    return RiskProfile(
        tolerance_score=tolerance_score,
        capacity_score=capacity_score,
        overall_score=overall_score,
        level=band["level"],
        descriptive_label=_descriptive_label(overall_score, band),
        nearest_preset=nearest,
        expected_return=expected_return,
        volatility=volatility,
        mismatch=_describe_mismatch(tolerance_score, capacity_score),
        contributions=tolerance_contrib + capacity_contrib,
    )


def apply_profile_to_inputs(
    base: RetirementInputs, profile: RiskProfile
) -> RetirementInputs:
    """Return a copy of ``base`` with the profile's return and volatility applied.

    This is the hand-off back to the Retirement Planner: the questionnaire result
    becomes the investment assumptions of the projection.
    """
    return replace(
        base,
        expected_return=profile.expected_return,
        volatility=profile.volatility,
    )


def default_answers() -> dict[str, int]:
    """Return a neutral set of answers (every question at the middle option).

    Used to seed the questionnaire so a profile can be produced before the user changes
    anything, and as a baseline in tests.
    """
    return {question["id"]: 3 for question in RISK_QUESTIONS}
