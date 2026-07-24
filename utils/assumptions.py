"""Central store for default assumptions and validation bounds.

Nothing in the simulation engine hard-codes a financial assumption. Every default a
user sees in the sidebar comes from this module, so assumptions can be reviewed,
documented and changed in one place — which is exactly what a compliance or
investment-committee review of a planning tool would ask for.
"""

from __future__ import annotations

from typing import Any, Final

# ---------------------------------------------------------------------------
# Default input values shown in the sidebar
# ---------------------------------------------------------------------------
DEFAULTS: Final[dict[str, float | int | str | bool]] = {
    # Personal timeline
    "current_age": 30,
    "retirement_age": 65,
    "life_expectancy": 92,
    # Current finances
    "current_savings": 75_000.0,
    "annual_contribution": 20_000.0,
    "contribution_growth_rate": 0.02,
    # Investment assumptions (nominal, annual)
    "expected_return": 0.07,
    "volatility": 0.15,
    "inflation_rate": 0.025,
    # Retirement assumptions (today's dollars)
    "annual_spending": 70_000.0,
    "annual_other_income": 24_000.0,
    "withdrawal_timing": "beginning",
    # Simulation settings
    "n_simulations": 10_000,
    "random_seed": 42,
    "show_in_todays_dollars": True,
}

# ---------------------------------------------------------------------------
# Accepted ranges. (low, high) inclusive. Used by utils.validation and to bound
# the Streamlit widgets so most bad input is impossible to enter in the first place.
# ---------------------------------------------------------------------------
BOUNDS: Final[dict[str, tuple[float, float]]] = {
    "current_age": (18, 100),
    "retirement_age": (30, 100),
    "life_expectancy": (40, 120),
    "current_savings": (0.0, 100_000_000.0),
    "annual_contribution": (0.0, 5_000_000.0),
    "contribution_growth_rate": (-0.10, 0.20),
    "expected_return": (-0.20, 0.30),
    "volatility": (0.0, 1.00),
    "inflation_rate": (-0.05, 0.20),
    "annual_spending": (0.0, 10_000_000.0),
    "annual_other_income": (0.0, 10_000_000.0),
    "n_simulations": (1_000, 100_000),
}

# ---------------------------------------------------------------------------
# Notes shown to the user alongside the assumptions table. Keeping the wording here
# means the methodology text and the numbers can never drift apart.
# ---------------------------------------------------------------------------
ASSUMPTION_NOTES: Final[dict[str, str]] = {
    "return_model": (
        "Annual returns are drawn independently from a normal distribution. Real "
        "markets have fatter tails than a normal distribution, so extreme outcomes "
        "are likely understated."
    ),
    "inflation": (
        "Inflation is applied as a fixed annual rate. Retirement spending and "
        "guaranteed income are entered in today's dollars and grown at this rate."
    ),
    "taxes": (
        "Taxes, advisory fees, fund expenses and required minimum distributions are "
        "not modelled. Spending should be entered on an after-tax basis."
    ),
    "sequence": (
        "Contributions are added at the end of each working year. Retirement "
        "withdrawals are taken at the timing selected in the sidebar."
    ),
    "allocation": (
        "A single static portfolio is assumed for life. No glidepath, rebalancing "
        "drift or allocation change at retirement is modelled."
    ),
}

# Risk-profile presets an advisor might use as a starting point.
PORTFOLIO_PRESETS: Final[dict[str, dict[str, float]]] = {
    "Conservative (30/70)": {"expected_return": 0.050, "volatility": 0.070},
    "Moderate (60/40)": {"expected_return": 0.065, "volatility": 0.110},
    "Growth (80/20)": {"expected_return": 0.075, "volatility": 0.140},
    "Aggressive (100/0)": {"expected_return": 0.085, "volatility": 0.170},
    "Custom": {},
}

# ---------------------------------------------------------------------------
# Risk Profile questionnaire configuration
# ---------------------------------------------------------------------------
# The questionnaire separates two distinct ideas that are easy to conflate:
#   * Risk TOLERANCE  — how a client feels about volatility (psychological).
#   * Risk CAPACITY   — how much risk their financial situation can absorb
#                       (objective: time horizon, income stability, reserves).
# A client can be willing but unable, or able but unwilling. Scoring them
# separately and then reconciling the two is standard suitability practice and
# is more defensible than a single blended number.
#
# Each question carries a weight. Each option carries a score from 1 (most
# conservative) to 5 (most aggressive). The category score is the weighted
# average of answered options, rescaled to 0-100.

RISK_QUESTIONS: Final[list[dict[str, Any]]] = [
    {
        "id": "horizon",
        "category": "capacity",
        "weight": 2.0,
        "text": "When do you expect to start drawing on this money?",
        "options": [
            ("Within 3 years", 1),
            ("3 to 7 years", 2),
            ("8 to 15 years", 3),
            ("16 to 25 years", 4),
            ("More than 25 years", 5),
        ],
    },
    {
        "id": "income_stability",
        "category": "capacity",
        "weight": 1.5,
        "text": "How stable is your current income?",
        "options": [
            ("Very unstable or irregular", 1),
            ("Somewhat unstable", 2),
            ("Reasonably stable", 3),
            ("Stable and secure", 4),
            ("Very secure with strong growth prospects", 5),
        ],
    },
    {
        "id": "emergency_reserve",
        "category": "capacity",
        "weight": 1.0,
        "text": "If you lost your income, how long could your cash reserves cover expenses?",
        "options": [
            ("Less than 1 month", 1),
            ("1 to 3 months", 2),
            ("3 to 6 months", 3),
            ("6 to 12 months", 4),
            ("More than 12 months", 5),
        ],
    },
    {
        "id": "portfolio_share",
        "category": "capacity",
        "weight": 1.0,
        "text": "Roughly what share of your total net worth does this portfolio represent?",
        "options": [
            ("Nearly all of it", 1),
            ("More than half", 2),
            ("About half", 3),
            ("Less than half", 4),
            ("A small fraction", 5),
        ],
    },
    {
        "id": "reaction_to_loss",
        "category": "tolerance",
        "weight": 2.0,
        "text": "If this portfolio fell 20% in a year, what would you most likely do?",
        "options": [
            ("Sell everything to stop further losses", 1),
            ("Sell some to reduce risk", 2),
            ("Do nothing and wait for recovery", 3),
            ("Keep contributing as planned", 4),
            ("Invest more to buy at lower prices", 5),
        ],
    },
    {
        "id": "volatility_comfort",
        "category": "tolerance",
        "weight": 1.5,
        "text": "Which portfolio would you be most comfortable holding?",
        "options": [
            ("Small, steady gains; very rare small losses", 1),
            ("Modest gains; occasional small losses", 2),
            ("Higher gains; some moderate down years", 3),
            ("Strong gains; regular volatility", 4),
            ("Highest potential gains; large swings both ways", 5),
        ],
    },
    {
        "id": "priority",
        "category": "tolerance",
        "weight": 1.5,
        "text": "Which statement best describes your primary goal?",
        "options": [
            ("Protecting my money is far more important than growing it", 1),
            ("I lean toward protection over growth", 2),
            ("I want a balance of growth and protection", 3),
            ("I lean toward growth and accept the risk", 4),
            ("Maximising long-term growth is my clear priority", 5),
        ],
    },
    {
        "id": "experience",
        "category": "tolerance",
        "weight": 1.0,
        "text": "How would you describe your investing experience?",
        "options": [
            ("None; this is new to me", 1),
            ("A little; mostly savings accounts", 2),
            ("Some; I hold funds or a retirement account", 3),
            ("Experienced; I actively manage investments", 4),
            ("Very experienced across many asset types", 5),
        ],
    },
]

# Score bands map a 0-100 category score to a risk level. The upper bound of each
# band is exclusive except the last. These bands are a presentation convention,
# not a regulatory standard.
RISK_BANDS: Final[list[dict[str, Any]]] = [
    {"level": "Conservative", "min": 0.0, "max": 35.0, "preset": "Conservative (30/70)"},
    {"level": "Moderate", "min": 35.0, "max": 55.0, "preset": "Moderate (60/40)"},
    {"level": "Growth", "min": 55.0, "max": 75.0, "preset": "Growth (80/20)"},
    {"level": "Aggressive", "min": 75.0, "max": 100.01, "preset": "Aggressive (100/0)"},
]

# ---------------------------------------------------------------------------
# Continuous risk-to-portfolio mapping
# ---------------------------------------------------------------------------
# Rather than snapping a questionnaire score to one of the preset portfolios, the
# engine interpolates a return/volatility point along a spectrum. This preserves the
# granularity the questionnaire actually captured: two clients scoring 56 and 74 both
# sit in the "Growth" band but receive different, defensible assumptions.
#
# The spectrum is anchored on financially sensible endpoints for a diversified
# portfolio, NOT on any two presets, so score 0 and score 100 land on meaningful
# bounds. The named presets remain as reference labels only.
#
#   score 0   -> a bond-heavy conservative mix
#   score 100 -> a broadly all-equity mix
#
# Return and volatility use different curve shapes: volatility rises faster than
# return as risk increases, reflecting diminishing risk-adjusted reward (the reason
# risk tolerance matters at all). The exponents below are applied to the normalised
# 0-1 score. An exponent < 1 front-loads growth; > 1 back-loads it.
RISK_SPECTRUM: Final[dict[str, float]] = {
    "return_floor": 0.040,   # score 0: conservative real-plus-inflation return
    "return_ceiling": 0.090,  # score 100: all-equity nominal return
    "return_curve": 0.85,     # slight front-loading: return gains taper near the top
    "volatility_floor": 0.050,   # score 0: low-volatility bond-heavy mix
    "volatility_ceiling": 0.180,  # score 100: all-equity volatility
    "volatility_curve": 1.30,     # back-loaded: volatility accelerates toward the top
    "rounding": 0.0025,       # round interpolated rates to the nearest 0.25%
}
