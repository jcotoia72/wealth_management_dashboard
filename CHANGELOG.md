# Changelog

All notable changes to the Wealth Management Planning Dashboard are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/), and the project
is an educational portfolio piece rather than a released product, so versions are
development milestones.

## [0.8.0] — Quality-of-life & Client Report
*Tests: 97*

### Added
- **Downloadable client report (PDF)** — a one-page, client-facing summary with headline
  metrics, the projection chart, the plain-English interpretation, percentile and
  assumptions tables, and the disclaimer. Optional client name.
- **Reset buttons** on the Retirement Planner, Risk Profile, and Scenario Comparison
  pages to clear inputs and results.
- **Input persistence** — planner inputs are remembered when navigating between pages.

### Changed
- The report chart renders with matplotlib rather than Plotly's static export, removing a
  headless-browser dependency so it works reliably when deployed.

## [0.7.0] — Risk Profile UI cleanup

### Changed
- Moved the recommended-profile label to a clean headline instead of a cramped metric card.

### Removed
- The redundant "Closest model" field, which was implied by the profile name.

## [0.6.0] — Continuous risk mapping
*Tests: 91*

### Changed
- Replaced the four fixed risk buckets with smooth interpolation across the full risk
  spectrum, so two clients in the same band receive genuinely different assumptions.
- Volatility rises faster than return across the curve, reflecting diminishing
  risk-adjusted reward.
- Added finer descriptive labels (e.g. "Cautious Growth" vs "Growth-leaning"); interpolated
  assumptions are rounded to 0.25%.

## [0.5.0] — Profile auto-apply toggle

### Added
- A toggle on the Retirement Planner that applies the Risk Profile's return and volatility
  automatically, locking the sliders while active so no manual re-entry is needed.

## [0.4.0] — Risk Profile module
*Tests: 84*

### Added
- The **Risk Profile** module (fully active): an eight-question assessment scoring risk
  tolerance and risk capacity separately.
- Overall score uses the lower of the two axes, so a plan is never rated above what the
  client can actually absorb.
- A mismatch flag when willingness and ability diverge sharply.
- Mapping from the result to a model portfolio, handed to the Retirement Planner to close
  the loop between modules.
- A transparent score breakdown showing each answer's contribution.

## [0.3.0] — Scenario Comparison module
*Tests: 62*

### Added
- The **Scenario Comparison** module (fully active): save up to six named projections and
  compare them side by side.
- Quick presets and a full custom variant builder.
- Success-probability bar chart and overlaid median-path chart across scenarios.
- One-variable sensitivity analysis that charts the success curve for any assumption.
- Lever ranking that measures which single change most improves the plan.

### Fixed
- A table-rendering bug that displayed all comparison values as blank.

## [0.2.0] — Deployment fixes

### Fixed
- A configuration error that prevented the app from launching on Streamlit Community Cloud.
- Corrected the performance figures in the documentation (10,000 paths run in ~0.03s).

## [0.1.0] — Foundation & Retirement Planner
*Tests: 35*

### Added
- The modular dashboard framework: landing page, sidebar navigation, and a six-module
  structure with clearly labelled "Coming Soon" placeholders.
- The **Monte Carlo Retirement Planner**: a two-phase simulation (accumulation and
  withdrawals) running 10,000 vectorized NumPy paths.
- Contribution growth, inflation-adjusted spending, a Social Security / pension offset, and
  a beginning/end-of-year withdrawal-timing option.
- Results dashboard: success-probability and balance metric cards, a projection chart with
  a 10th–90th percentile band, an ending-balance histogram, a percentile-by-age table, and
  failure analysis.
- A plain-English client interpretation generated from the results, plus a full assumptions
  table.
- A Client Overview page reading the latest projection from session state.
- Reproducibility via a user-controlled random seed, and a today's-dollars / nominal toggle.
- Full input validation that blocks impossible inputs before any calculation runs.
- A README with beginner setup instructions, methodology, and verification steps.

---

**Current modules:** Client Overview, Retirement Planner, Scenario Comparison and Risk
Profile are active. Portfolio Analysis and Portfolio Optimizer are planned.
