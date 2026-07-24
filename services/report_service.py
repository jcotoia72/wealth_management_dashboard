"""Client report generation.

Builds a one-page, client-facing PDF summary of a retirement projection using
reportlab. This is deliberately separate from the Streamlit page: the page hands over a
:class:`SimulationResults` and receives PDF bytes, so the report logic stays testable and
free of UI code.

The projection chart is embedded as a static image when the optional export path works.
On some hosted environments static image export is unavailable, so a failure there is
caught and the report is produced without the image rather than erroring.
"""

from __future__ import annotations

import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from models.monte_carlo import SimulationResults
from services.retirement_service import (
    build_assumptions_table,
    build_interpretation,
)
from utils.formatting import format_currency, format_percent

# Palette matched to the on-screen dashboard so the report looks of a piece with it.
_NAVY = colors.HexColor("#14304a")
_BLUE = colors.HexColor("#1f5a8c")
_GREY = colors.HexColor("#5a6b7b")
_LIGHT = colors.HexColor("#f5f7f9")
_RULE = colors.HexColor("#e3e8ee")


def _styles() -> dict[str, ParagraphStyle]:
    """Return the paragraph styles used throughout the report."""
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            textColor=_NAVY,
            fontSize=20,
            spaceAfter=2,
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle",
            parent=base["Normal"],
            textColor=_GREY,
            fontSize=10,
            spaceAfter=12,
        ),
        "h2": ParagraphStyle(
            "ReportH2",
            parent=base["Heading2"],
            textColor=_NAVY,
            fontSize=13,
            spaceBefore=14,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "ReportBody",
            parent=base["Normal"],
            fontSize=10,
            leading=15,
            textColor=colors.HexColor("#33414f"),
        ),
        "disclaimer": ParagraphStyle(
            "ReportDisclaimer",
            parent=base["Normal"],
            fontSize=8,
            leading=11,
            textColor=_GREY,
        ),
    }


def _headline_metrics_table(results: SimulationResults, styles) -> Table:
    """Build the four-cell headline metrics band."""
    basis = "today's dollars" if results.inputs.show_in_todays_dollars else "future dollars"
    cells = [
        ("Success probability", format_percent(results.success_probability)),
        (
            f"Median balance at {results.inputs.retirement_age}",
            format_currency(results.median_balance_at_retirement),
        ),
        (
            f"Median balance at {results.inputs.life_expectancy}",
            format_currency(results.median_ending_balance),
        ),
        (
            "10th percentile ending",
            format_currency(results.ending_balance_percentile(10)),
        ),
    ]

    label_style = ParagraphStyle("mlabel", fontSize=8, textColor=_GREY, leading=10)
    value_style = ParagraphStyle("mvalue", fontSize=15, textColor=_NAVY, leading=18, spaceBefore=2)

    row = [
        [Paragraph(label, label_style), Paragraph(value, value_style)]
        for label, value in cells
    ]
    # Each metric becomes its own mini stacked cell in a single row.
    table = Table(
        [[_stack(label, value, label_style, value_style) for label, value in cells]],
        colWidths=[1.72 * inch] * 4,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _LIGHT),
                ("BOX", (0, 0), (-1, -1), 0.5, _RULE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, _RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def _stack(label: str, value: str, label_style, value_style):
    """Return a small flowable stacking a label above a value inside a table cell."""
    inner = Table(
        [[Paragraph(label, label_style)], [Paragraph(value, value_style)]],
        colWidths=[1.5 * inch],
    )
    inner.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )
    return inner


def _percentile_table(results: SimulationResults, styles) -> Table:
    """Build a compact percentile-by-age table for the report."""
    frame = results.percentile_table(step=max(5, (results.inputs.life_expectancy - results.inputs.retirement_age) // 5))
    header = ["Age", "10th", "25th", "Median", "75th", "90th"]
    data = [header]
    for age, row in frame.iterrows():
        data.append(
            [
                str(age),
                format_currency(row["p10"]),
                format_currency(row["p25"]),
                format_currency(row["p50"]),
                format_currency(row["p75"]),
                format_currency(row["p90"]),
            ]
        )

    table = Table(data, colWidths=[0.7 * inch] + [1.32 * inch] * 5)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT]),
                ("GRID", (0, 0), (-1, -1), 0.4, _RULE),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _assumptions_table(results: SimulationResults) -> Table:
    """Build a two-column assumptions table for the report."""
    frame = build_assumptions_table(results.inputs)
    data = [["Assumption", "Value"]] + frame.values.tolist()
    table = Table(data, colWidths=[3.6 * inch] + [3.2 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT]),
                ("GRID", (0, 0), (-1, -1), 0.4, _RULE),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def _chart_image(results: SimulationResults) -> Image | None:
    """Return the projection chart as a reportlab Image, or None if rendering fails.

    The chart is drawn with matplotlib rather than exported from Plotly. Plotly's static
    export needs a headless browser (kaleido/Chrome) that is often unavailable on hosted
    environments, whereas matplotlib renders straight to PNG with no such dependency.
    Any failure is swallowed so the report is still produced without the chart.
    """
    try:
        import matplotlib

        matplotlib.use("Agg")  # non-interactive backend, no display needed
        import matplotlib.pyplot as plt
        import numpy as np

        ages = results.ages
        percentiles = results.percentile_paths(percentiles=(10, 50, 90))

        fig, ax = plt.subplots(figsize=(7.6, 3.4), dpi=150)

        # A light sample of individual paths for texture.
        rng = np.random.default_rng(results.inputs.random_seed)
        sample_n = min(60, results.n_simulations)
        for index in rng.choice(results.n_simulations, size=sample_n, replace=False):
            ax.plot(ages, results.balances[index], color="#c3cdd6", linewidth=0.4, zorder=1)

        # 10th-90th percentile band and median.
        ax.fill_between(
            ages, percentiles["p10"], percentiles["p90"],
            color="#1f5a8c", alpha=0.15, zorder=2, label="10th–90th percentile",
        )
        ax.plot(ages, percentiles["p50"], color="#1f5a8c", linewidth=2.2, zorder=3, label="Median")
        ax.axvline(
            results.inputs.retirement_age, color="#8c5a1f", linewidth=1.3,
            linestyle="--", zorder=4, label=f"Retirement ({results.inputs.retirement_age})",
        )

        basis = "today's dollars" if results.inputs.show_in_todays_dollars else "future dollars"
        ax.set_xlabel("Age", fontsize=9)
        ax.set_ylabel(f"Portfolio balance ({basis})", fontsize=9)
        ax.set_title("Projected portfolio balance by age", fontsize=11, color="#14304a")
        ax.legend(fontsize=7.5, loc="upper left", framealpha=0.9)
        ax.tick_params(labelsize=8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda value, _: f"${value/1_000_000:.1f}M" if value >= 1_000_000 else f"${value/1_000:.0f}K")
        )
        ax.grid(True, color="#e3e8ee", linewidth=0.5)
        fig.tight_layout()

        image_buffer = io.BytesIO()
        fig.savefig(image_buffer, format="png", bbox_inches="tight")
        plt.close(fig)
        image_buffer.seek(0)
        return Image(image_buffer, width=6.8 * inch, height=3.05 * inch)
    except Exception:
        return None


def build_client_report(results: SimulationResults, client_name: str = "") -> bytes:
    """Build a one-page client report PDF and return it as bytes.

    Parameters
    ----------
    results:
        The projection to summarise.
    client_name:
        Optional name shown in the report header.

    Returns
    -------
    bytes
        The PDF file contents, ready for a Streamlit download button.
    """
    styles = _styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.6 * inch,
        title="Retirement Projection Summary",
    )

    story: list = []

    # Header
    heading = "Retirement Projection Summary"
    if client_name.strip():
        heading = f"Retirement Projection Summary — {client_name.strip()}"
    story.append(Paragraph(heading, styles["title"]))
    story.append(
        Paragraph(
            f"Prepared {date.today().strftime('%B %d, %Y')} · "
            f"{results.n_simulations:,} Monte Carlo simulations",
            styles["subtitle"],
        )
    )

    # Headline metrics
    story.append(_headline_metrics_table(results, styles))
    story.append(Spacer(1, 6))

    # Chart (optional)
    chart = _chart_image(results)
    if chart is not None:
        story.append(Spacer(1, 6))
        story.append(chart)

    # Interpretation
    story.append(Paragraph("What this means", styles["h2"]))
    interpretation = build_interpretation(results).replace("**", "")
    story.append(Paragraph(interpretation, styles["body"]))

    # Percentile table
    story.append(Paragraph("Projected balances by age", styles["h2"]))
    story.append(_percentile_table(results, styles))

    # Assumptions
    story.append(Paragraph("Assumptions used", styles["h2"]))
    story.append(_assumptions_table(results))

    # Disclaimer
    story.append(Spacer(1, 10))
    story.append(
        Paragraph(
            "Educational tool — not financial advice. This summary is a hypothetical "
            "projection produced by a portfolio-project planning tool. Results depend "
            "entirely on the assumptions listed above and do not reflect the performance "
            "of any actual investment. Nothing here is a recommendation to buy, sell or "
            "hold any security. Consult a qualified financial professional before making "
            "financial decisions.",
            styles["disclaimer"],
        )
    )

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
