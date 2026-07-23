"""Display formatting helpers.

Every dollar and percentage shown anywhere in the dashboard goes through one of these
functions, so formatting stays consistent across pages, tables and charts.
"""

from __future__ import annotations

import math


def format_currency(value: float, decimals: int = 0) -> str:
    """Format a number as US dollars, e.g. ``1234567`` -> ``"$1,234,567"``.

    Negative values are shown in parentheses, following accounting convention.
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "N/A"
    if value < 0:
        return f"(${abs(value):,.{decimals}f})"
    return f"${value:,.{decimals}f}"


def format_currency_compact(value: float) -> str:
    """Format large dollar amounts compactly for chart axes and tight cards.

    ``2_450_000`` -> ``"$2.45M"``; ``640_000`` -> ``"$640K"``.
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "N/A"
    sign = "-" if value < 0 else ""
    magnitude = abs(value)
    if magnitude >= 1_000_000_000:
        return f"{sign}${magnitude / 1_000_000_000:.2f}B"
    if magnitude >= 1_000_000:
        return f"{sign}${magnitude / 1_000_000:.2f}M"
    if magnitude >= 1_000:
        return f"{sign}${magnitude / 1_000:.0f}K"
    return f"{sign}${magnitude:,.0f}"


def format_percent(value: float, decimals: int = 1) -> str:
    """Format a decimal rate as a percentage, e.g. ``0.072`` -> ``"7.2%"``."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "N/A"
    return f"{value * 100:.{decimals}f}%"


def format_age(value: float | None) -> str:
    """Format an age, tolerating ``None`` for metrics that may not exist."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "N/A"
    return f"Age {value:.0f}"


def round_to_nearest(value: float, nearest: int = 10_000) -> float:
    """Round a dollar figure for client-facing narrative text.

    Plain-English summaries read better with round numbers ("about $640,000") than
    with false precision ("$643,127.44").
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return 0.0
    return round(value / nearest) * nearest
