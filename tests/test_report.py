"""Tests for the client report generator.

These assert the report is produced as valid PDF bytes and degrades gracefully, without
inspecting pixel content. Run from the project root with:
    pytest
"""

from __future__ import annotations

from models.monte_carlo import RetirementInputs, run_retirement_simulation
from services.report_service import build_client_report


def make_results(**overrides):
    """Run a small projection for use in report tests."""
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
        show_in_todays_dollars=True,
    )
    base.update(overrides)
    return run_retirement_simulation(RetirementInputs(**base))


def test_report_returns_valid_pdf_bytes() -> None:
    """The report must be non-empty bytes beginning with the PDF magic number."""
    pdf = build_client_report(make_results())
    assert isinstance(pdf, bytes)
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 1_000


def test_report_includes_the_chart_image() -> None:
    """With matplotlib available, the embedded chart should make the file sizeable."""
    pdf = build_client_report(make_results())
    # A PDF with an embedded chart is far larger than a text-only one.
    assert len(pdf) > 50_000


def test_report_accepts_a_client_name() -> None:
    """Passing a client name must not change the validity of the output."""
    pdf = build_client_report(make_results(), client_name="Jordan Sample")
    assert pdf[:5] == b"%PDF-"


def test_report_handles_an_all_failure_projection() -> None:
    """A projection where every path fails must still produce a report.

    The interpretation and depletion metrics take a different branch when there are
    failures, so this exercises that path through the report.
    """
    results = make_results(
        current_savings=0.0, annual_contribution=0.0, annual_spending=60_000.0
    )
    assert results.success_probability == 0.0
    pdf = build_client_report(results)
    assert pdf[:5] == b"%PDF-"


def test_report_handles_an_all_success_projection() -> None:
    """A projection where nothing fails (no depletion age) must still render."""
    results = make_results(
        current_savings=20_000_000.0, annual_spending=0.0, annual_other_income=0.0
    )
    assert results.success_probability == 1.0
    assert results.median_depletion_age is None
    pdf = build_client_report(results)
    assert pdf[:5] == b"%PDF-"


def test_report_works_in_nominal_dollars() -> None:
    """The nominal-dollars basis must render as readily as today's dollars."""
    pdf = build_client_report(make_results(show_in_todays_dollars=False))
    assert pdf[:5] == b"%PDF-"
