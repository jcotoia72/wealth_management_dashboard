"""Input validation for the retirement planner.

Validation lives outside both the simulation engine and the Streamlit pages so that
the same rules protect the model no matter how it is called. The Streamlit page uses
:func:`validate_retirement_inputs` to collect readable messages; the engine uses the
same function with ``raise_on_error=True`` to refuse to run on bad data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from utils.assumptions import BOUNDS

if TYPE_CHECKING:  # pragma: no cover - import only for type checkers
    from models.monte_carlo import RetirementInputs


class ValidationError(ValueError):
    """Raised when retirement inputs fail validation.

    The ``errors`` attribute holds every problem found, not just the first one, so a
    user can fix all of them at once.
    """

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def _check_range(
    value: float,
    low: float,
    high: float,
    label: str,
    as_percent: bool = False,
) -> str | None:
    """Return an error message if ``value`` falls outside ``[low, high]``."""
    if low <= value <= high:
        return None
    if as_percent:
        return f"{label} must be between {low:.0%} and {high:.0%}."
    return f"{label} must be between {low:,.0f} and {high:,.0f}."


def validate_retirement_inputs(
    inputs: "RetirementInputs", raise_on_error: bool = False
) -> list[str]:
    """Validate a :class:`RetirementInputs` instance.

    Parameters
    ----------
    inputs:
        The inputs to check.
    raise_on_error:
        When ``True``, raise :class:`ValidationError` instead of returning messages.

    Returns
    -------
    list[str]
        Human-readable error messages. Empty when the inputs are valid.
    """
    errors: list[str] = []

    # --- Timeline ---------------------------------------------------------
    if inputs.current_age <= 0:
        errors.append("Current age must be greater than zero.")
    if inputs.retirement_age <= inputs.current_age:
        errors.append("Retirement age must be greater than current age.")
    if inputs.life_expectancy <= inputs.retirement_age:
        errors.append("Life expectancy must be greater than retirement age.")

    age_error = _check_range(
        inputs.current_age, BOUNDS["current_age"][0], BOUNDS["current_age"][1], "Current age"
    )
    if age_error:
        errors.append(age_error)
    life_error = _check_range(
        inputs.life_expectancy,
        BOUNDS["life_expectancy"][0],
        BOUNDS["life_expectancy"][1],
        "Life expectancy",
    )
    if life_error:
        errors.append(life_error)

    # --- Dollar amounts ---------------------------------------------------
    non_negative_fields = {
        "Current retirement savings": inputs.current_savings,
        "Annual contribution": inputs.annual_contribution,
        "Desired annual retirement spending": inputs.annual_spending,
        "Social Security / pension income": inputs.annual_other_income,
    }
    for label, value in non_negative_fields.items():
        if value < 0:
            errors.append(f"{label} cannot be negative.")

    # --- Rate assumptions -------------------------------------------------
    if inputs.volatility < 0:
        errors.append("Annual volatility cannot be negative.")

    rate_checks = [
        (inputs.expected_return, "expected_return", "Expected annual return"),
        (inputs.volatility, "volatility", "Annual volatility"),
        (inputs.inflation_rate, "inflation_rate", "Annual inflation rate"),
        (
            inputs.contribution_growth_rate,
            "contribution_growth_rate",
            "Annual contribution increase rate",
        ),
    ]
    for value, key, label in rate_checks:
        message = _check_range(value, BOUNDS[key][0], BOUNDS[key][1], label, as_percent=True)
        if message:
            errors.append(message)

    # --- Simulation settings ---------------------------------------------
    low, high = BOUNDS["n_simulations"]
    if not (low <= inputs.n_simulations <= high):
        errors.append(
            f"Number of simulations must be between {low:,} and {high:,}."
        )
    if inputs.withdrawal_timing not in ("beginning", "end"):
        errors.append("Withdrawal timing must be either 'beginning' or 'end'.")
    if int(inputs.random_seed) != inputs.random_seed or inputs.random_seed < 0:
        errors.append("Random seed must be a non-negative whole number.")

    if errors and raise_on_error:
        raise ValidationError(errors)
    return errors
