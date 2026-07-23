"""Shared page chrome: styling, headers, sidebar branding and the disclaimer.

Every page calls :func:`configure_page` first so the layout, title and CSS stay
identical across the application.
"""

from __future__ import annotations

import streamlit as st

APP_TITLE = "Wealth Management Planning Dashboard"

# Neutral, financial-services palette. Kept small and consistent on purpose.
_CUSTOM_CSS = """
<style>
    .block-container {padding-top: 2.5rem; padding-bottom: 3rem; max-width: 1400px;}
    h1, h2, h3 {color: #14304a; letter-spacing: -0.01em;}
    .app-subtitle {color: #5a6b7b; font-size: 1.02rem; margin-top: -0.6rem;}
    .section-rule {border: none; border-top: 1px solid #e3e8ee; margin: 1.6rem 0 1.2rem 0;}
    .module-card {
        border: 1px solid #e3e8ee; border-radius: 6px; padding: 1.1rem 1.2rem;
        background-color: #fbfcfd; height: 100%;
    }
    .module-card h4 {margin: 0 0 0.35rem 0; color: #14304a; font-size: 1.02rem;}
    .module-card p {margin: 0; color: #5a6b7b; font-size: 0.88rem; line-height: 1.45;}
    .status-badge {
        display: inline-block; padding: 0.14rem 0.55rem; border-radius: 3px;
        font-size: 0.72rem; font-weight: 600; letter-spacing: 0.04em;
        text-transform: uppercase; margin-bottom: 0.55rem;
    }
    .status-active {background-color: #e4f1e8; color: #1d6b3a; border: 1px solid #b9dcc6;}
    .status-planned {background-color: #eef1f4; color: #5a6b7b; border: 1px solid #dbe1e8;}
    .disclaimer {
        border-left: 3px solid #b0bcc8; background-color: #f7f9fb;
        padding: 0.85rem 1.1rem; color: #4a5a6a; font-size: 0.85rem; line-height: 1.5;
    }
    div[data-testid="stMetric"] {
        background-color: #fbfcfd; border: 1px solid #e3e8ee;
        border-radius: 6px; padding: 0.9rem 1rem;
    }
    div[data-testid="stMetricLabel"] p {
        color: #5a6b7b; font-size: 0.82rem; font-weight: 500;
    }
</style>
"""

# Single source of truth for the module list. Adding a future module means adding one
# entry here and one file in pages/.
MODULES: list[dict[str, str]] = [
    {
        "name": "Client Overview",
        "path": "pages/1_Client_Overview.py",
        "status": "active",
        "description": "Snapshot of the client's timeline, savings and latest projection results.",
    },
    {
        "name": "Retirement Planner",
        "path": "pages/2_Retirement_Planner.py",
        "status": "active",
        "description": "Two-phase Monte Carlo projection of accumulation and retirement withdrawals.",
    },
    {
        "name": "Scenario Comparison",
        "path": "pages/3_Scenario_Comparison.py",
        "status": "planned",
        "description": "Run several plans side by side to compare retirement ages, savings rates and spending levels.",
    },
    {
        "name": "Portfolio Analysis",
        "path": "pages/4_Portfolio_Analysis.py",
        "status": "planned",
        "description": "Holdings, allocation, historical performance and risk statistics for a client portfolio.",
    },
    {
        "name": "Portfolio Optimizer",
        "path": "pages/5_Portfolio_Optimizer.py",
        "status": "planned",
        "description": "Mean-variance optimisation and efficient frontier construction under client constraints.",
    },
    {
        "name": "Risk Profile",
        "path": "pages/6_Risk_Profile.py",
        "status": "planned",
        "description": "Risk-tolerance questionnaire mapped to a recommended target allocation.",
    },
]


def configure_page(page_title: str) -> None:
    """Apply the shared page configuration and stylesheet.

    Must be the first Streamlit call on every page.
    """
    st.set_page_config(
        page_title=f"{page_title} | {APP_TITLE}",
        page_icon=":chart_with_upwards_trend:",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "") -> None:
    """Render a consistent page title, optional subtitle and a horizontal rule."""
    st.title(title)
    if subtitle:
        st.markdown(f"<p class='app-subtitle'>{subtitle}</p>", unsafe_allow_html=True)
    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)


def section_header(title: str, description: str = "") -> None:
    """Render a second-level section heading with optional supporting text."""
    st.subheader(title)
    if description:
        st.caption(description)


def render_disclaimer() -> None:
    """Render the educational-use disclaimer shown on every page."""
    st.markdown(
        "<div class='disclaimer'><strong>Educational tool — not financial advice.</strong> "
        "This dashboard is a portfolio project built to illustrate planning concepts. "
        "Projections are hypothetical, depend entirely on the assumptions entered, and "
        "do not reflect the performance of any actual investment. Nothing here is a "
        "recommendation to buy, sell or hold any security, and it should not be used to "
        "make financial decisions. Consult a qualified financial professional."
        "</div>",
        unsafe_allow_html=True,
    )


def render_sidebar_brand() -> None:
    """Render the consistent sidebar heading shown on every page."""
    st.sidebar.markdown(f"### {APP_TITLE}")
    st.sidebar.caption("Educational planning tool · v1.0")
    st.sidebar.markdown("---")


def render_module_navigation(columns: int = 3) -> None:
    """Render module cards with links, used on the landing page."""
    for row_start in range(0, len(MODULES), columns):
        row = MODULES[row_start : row_start + columns]
        cols = st.columns(columns, gap="medium")
        for col, module in zip(cols, row):
            with col:
                badge_class = (
                    "status-active" if module["status"] == "active" else "status-planned"
                )
                badge_text = "Active" if module["status"] == "active" else "Coming soon"
                st.markdown(
                    f"<div class='module-card'>"
                    f"<span class='status-badge {badge_class}'>{badge_text}</span>"
                    f"<h4>{module['name']}</h4>"
                    f"<p>{module['description']}</p>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                st.page_link(module["path"], label=f"Open {module['name']}")


def render_coming_soon(
    module_name: str, summary: str, planned_features: list[str]
) -> None:
    """Render a standard placeholder body for a module that is not built yet."""
    st.info(
        f"**Coming soon.** The {module_name} module is not yet implemented. "
        "The Retirement Planner is the fully functional module in this version."
    )
    st.write(summary)
    st.markdown("**Planned capabilities**")
    for feature in planned_features:
        st.markdown(f"- {feature}")
    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)
    st.page_link("pages/2_Retirement_Planner.py", label="Go to the Retirement Planner")
    st.page_link("app.py", label="Back to the dashboard home")
