# Wealth Management Planning Dashboard

A modular retirement and portfolio planning workspace built with Python and Streamlit.
The first release contains a complete two-phase **Monte Carlo Retirement Planner** and
an expandable dashboard framework with labelled placeholders for future modules.

> **Educational tool — not financial advice.** This is a portfolio project. Projections
> are hypothetical, depend entirely on the assumptions entered, and do not reflect any
> actual investment. Nothing here is a recommendation to buy, sell or hold a security.

---

## Table of contents

1. [What this application does](#1-what-this-application-does)
2. [Main features](#2-main-features)
3. [Technology stack](#3-technology-stack)
4. [Folder structure](#4-folder-structure)
5. [Setup for absolute beginners](#5-setup-for-absolute-beginners)
6. [Running the application](#6-running-the-application)
7. [Running the tests](#7-running-the-tests)
8. [Everyday commands cheat sheet](#8-everyday-commands-cheat-sheet)
9. [How to use the dashboard](#9-how-to-use-the-dashboard)
10. [Monte Carlo methodology](#10-monte-carlo-methodology)
11. [Modelling assumptions](#11-modelling-assumptions)
12. [Known limitations](#12-known-limitations)
13. [How to verify the simulation is working](#13-how-to-verify-the-simulation-is-working)
14. [Planned future modules and where to add them](#14-planned-future-modules-and-where-to-add-them)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. What this application does

Traditional retirement calculators project a single average return and produce one
number. That single number hides the most important question a client actually has:
*how likely is this plan to work?*

This dashboard answers that question with **Monte Carlo simulation**. It runs thousands
of independent market scenarios, each with its own randomly drawn sequence of annual
returns, and reports the full range of outcomes plus the probability that the portfolio
lasts through life expectancy.

The projection has two phases:

- **Accumulation** — from today until retirement, the portfolio grows and receives
  annual contributions.
- **Decumulation** — from retirement until life expectancy, the portfolio funds the gap
  between desired spending and guaranteed income such as Social Security or a pension.

---

## 2. Main features

**Retirement Planner (fully functional)**

- Two-phase Monte Carlo projection, vectorised with NumPy
- User-controlled random seed for fully reproducible results
- Contribution growth, inflation-adjusted spending, and a Social Security / pension offset
- Selectable withdrawal timing (beginning or end of year)
- Results shown in today's dollars or nominal future dollars
- Full input validation that blocks the calculation when inputs are impossible
- Headline metric cards: success probability, median balance at retirement, median
  ending balance, 10th percentile ending balance
- Portfolio projection chart with sampled paths, a shaded 10th–90th percentile band,
  the median path, and a retirement-age marker
- Ending-balance distribution histogram
- Percentile-by-age table with CSV download
- Success and failure analysis including median depletion age
- Plain-English client summary generated only from calculated results
- Complete assumptions table with methodology notes

**Dashboard framework**

- Professional landing page with module cards and status indicators
- Client Overview page that reads the latest projection from session state
- Four clearly labelled "Coming Soon" modules with their planned capabilities
- Consistent styling, formatting and disclaimer across every page

**Engineering**

- Financial model completely separated from the interface (no Streamlit in the engine)
- Dataclasses `RetirementInputs` and `SimulationResults`
- Type hints and docstrings throughout
- 35 pytest tests covering reproducibility, validation, financial logic and edge cases

---

## 3. Technology stack

| Component | Purpose |
|---|---|
| Python 3.11+ | Language |
| Streamlit | Web interface and multipage navigation |
| NumPy | Vectorised simulation mathematics |
| pandas | Result tables and percentile summaries |
| Plotly | Interactive charts |
| pytest | Automated testing |

No database, authentication, paid service or external market-data API is used.

---

## 4. Folder structure

```
wealth_management_dashboard/
│
├── app.py                          Landing page and application entry point
│
├── pages/                          One file per module; Streamlit builds the sidebar from these
│   ├── 1_Client_Overview.py        Summary of the latest projection (functional)
│   ├── 2_Retirement_Planner.py     The Monte Carlo planner (fully functional)
│   ├── 3_Scenario_Comparison.py    Placeholder
│   ├── 4_Portfolio_Analysis.py     Placeholder
│   ├── 5_Portfolio_Optimizer.py    Placeholder
│   └── 6_Risk_Profile.py           Placeholder
│
├── models/
│   ├── __init__.py
│   └── monte_carlo.py              Simulation engine, RetirementInputs, SimulationResults
│
├── services/
│   ├── __init__.py
│   └── retirement_service.py       Builds inputs, tables and the client narrative
│
├── components/
│   ├── __init__.py
│   ├── navigation.py               Page config, headers, module list, disclaimer
│   ├── metrics.py                  Metric-card components
│   └── charts.py                   Plotly figure builders
│
├── utils/
│   ├── __init__.py
│   ├── formatting.py               Dollar and percentage formatting
│   ├── validation.py               Input rules and ValidationError
│   └── assumptions.py              Default values and accepted bounds
│
├── tests/
│   ├── __init__.py
│   └── test_monte_carlo.py         35 pytest tests
│
├── .streamlit/config.toml          Shared visual theme
├── requirements.txt
├── pytest.ini
├── README.md
└── .gitignore
```

**The architectural rule:** dependencies only point downward.
`pages` → `components` / `services` → `models` → `utils`.
Nothing in `models/` or `utils/` imports Streamlit, which is why the engine can be
tested and reused anywhere.

---

## 5. Setup for absolute beginners

Follow these steps in order. If you have never used a terminal before, that is fine —
each command is one line that you copy, paste and press Enter.

### Step 1 — Install Python 3.11 or newer

Check whether you already have it. Open a terminal:

- **Windows:** press the Start key, type `powershell`, press Enter.
- **macOS:** press Cmd+Space, type `terminal`, press Enter.

Then type:

```bash
python --version
```

If you see `Python 3.11.x` or higher, skip to Step 2. If you see an error or a version
below 3.11, download Python from <https://www.python.org/downloads/>.

> **Windows users:** on the first installer screen, tick the box that says
> **"Add python.exe to PATH"** before clicking Install. Missing this box is the single
> most common setup problem. On macOS, `python3` may be the correct command instead of
> `python`.

### Step 2 — Open the project folder in the terminal

The `cd` command means "change directory". Type `cd `, then drag the project folder from
your file explorer onto the terminal window and press Enter. It will look like:

```bash
cd path/to/wealth_management_dashboard
```

Confirm you are in the right place — this should list `app.py`:

```bash
ls          # macOS / Linux
dir         # Windows
```

### Step 3 — Create a virtual environment

A virtual environment is a private folder of libraries for this project only, so it
cannot break anything else on your computer.

```bash
python -m venv .venv
```

This creates a hidden `.venv` folder. You only ever do this once.

### Step 4 — Activate the virtual environment

**macOS / Linux:**

```bash
source .venv/bin/activate
```

**Windows (PowerShell or Command Prompt):**

```bash
.venv\Scripts\activate
```

Your prompt should now start with `(.venv)`. That is how you know it worked.

> **Windows PowerShell error about scripts being disabled?** Run this once, then repeat
> the activation command:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```

**You must activate the environment every time you open a new terminal window.** It is
not permanent.

### Step 5 — Install the libraries

```bash
pip install -r requirements.txt
```

This downloads Streamlit, NumPy, pandas, Plotly and pytest. It takes a minute or two.

---

## 6. Running the application

With the virtual environment active and your terminal in the project folder:

```bash
streamlit run app.py
```

Your browser opens automatically at <http://localhost:8501>. If it does not, copy that
address into your browser yourself.

To stop the application, click the terminal window and press **Ctrl+C**.

---

## 7. Running the tests

The tests prove the financial engine behaves correctly. Run them from the project root:

```bash
pytest
```

Expected output:

```
35 passed
```

Useful variations:

```bash
pytest -v                                    # show every test name
pytest tests/test_monte_carlo.py -v          # run one file
pytest -k "percentile" -v                    # run only tests matching a word
```

If you ever change the simulation logic, run `pytest` before anything else. A failing
test is telling you the change altered the financial results.

---

## 8. Everyday commands cheat sheet

Copy this block; it is the full lifecycle from a fresh clone.

**macOS / Linux**

```bash
cd path/to/wealth_management_dashboard
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
streamlit run app.py
```

**Windows**

```bash
cd path\to\wealth_management_dashboard
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pytest
streamlit run app.py
```

Every day after the first, you only need:

```bash
source .venv/bin/activate    # or .venv\Scripts\activate on Windows
streamlit run app.py
```

---

## 9. How to use the dashboard

1. Start the app; the landing page opens with the module overview.
2. Click **Retirement Planner** in the left sidebar.
3. Fill in the sidebar sections: personal timeline, current finances, investment
   assumptions, retirement assumptions, and (optionally) simulation settings.
4. Click **Run simulation**. Ten thousand scenarios take roughly a second.
5. Read the results top to bottom: headline metrics, projection chart, distribution,
   percentile table, failure analysis, client summary, assumptions.
6. Open **Client Overview** to see the condensed summary. The results follow you
   between pages because they are held in Streamlit's session state.

Changing any input and clicking **Run simulation** again replaces the stored results.

---

## 10. Monte Carlo methodology

### The core idea

Instead of assuming the portfolio earns exactly 7% every year, the model draws a
different random return for each year of each scenario. One scenario might see
+22%, −11%, +6%, …; another sees an entirely different sequence. Running thousands of
these produces a distribution of outcomes rather than a single false-precision answer.

This also captures **sequence-of-returns risk**: two retirees with identical average
returns can end up in very different positions depending on *when* the bad years land.
Poor returns early in retirement, while withdrawals are being taken, do far more damage
than the same returns later. A single-average-return calculator cannot show this.

### The return model

Each annual return is an independent draw from a normal distribution with the mean and
standard deviation you enter:

```
return(simulation, year) ~ Normal(expected_return, volatility)
growth_factor            = max(1 + return, 0)
```

The growth factor is floored at zero because a portfolio cannot lose more than 100% in a
single year.

### Order of operations each year

This is documented explicitly because it materially changes the results.

**Accumulation year (age < retirement age)**

1. The starting balance is multiplied by that year's growth factor.
2. The annual contribution is added at the **end** of the year, so it earns no return in
   the year it is made. This is slightly conservative.
3. The contribution amount for year *t* is `annual_contribution × (1 + growth_rate)^t`.

**Retirement year, withdrawal timing = "beginning"** (the default, conservative)

1. The net withdrawal is taken from the starting balance.
2. The remaining balance is multiplied by that year's growth factor.

**Retirement year, withdrawal timing = "end"**

1. The starting balance is multiplied by that year's growth factor.
2. The net withdrawal is taken afterwards.

### The withdrawal amount

```
net_need_today = max(0, desired_spending − guaranteed_income)      # today's dollars
withdrawal(t)  = net_need_today × (1 + inflation)^t                # nominal dollars
```

Both spending and guaranteed income are entered in today's dollars and inflated
together. If income exceeds spending, the withdrawal is zero — the surplus is assumed to
be consumed, not reinvested.

### Depletion and success

Balances are floored at zero every year, so they can never go negative. Once a balance
reaches zero it stays there permanently. The engine records the first year each path
hit zero, reported as the **depletion age**.

**Success is defined as: the portfolio balance is still greater than zero at life
expectancy.** The success probability is simply the share of paths meeting that test.

### Today's dollars versus nominal dollars

The simulation always runs in nominal dollars internally. When you choose "today's
dollars", every balance is divided by `(1 + inflation)^t` at the end. This is a display
transformation only — it never changes the success probability, and there is a test
asserting exactly that.

### Why a loop over years is still "vectorised"

Each year's balance depends on the previous year's balance, so the years cannot be
computed all at once. The engine therefore loops over years (typically 40–70 iterations)
while every operation *inside* the loop applies to all 10,000 simulations
simultaneously as NumPy array arithmetic. That is the practical vectorisation for a
path-dependent model, and it runs a 10,000-path projection in roughly one second.

---

## 11. Modelling assumptions

| Assumption | Treatment | Why it matters |
|---|---|---|
| Return distribution | Independent normal draws | Real markets have fatter tails; extreme outcomes are understated |
| Inflation | Fixed deterministic rate | Real inflation is itself uncertain and correlates with returns |
| Asset allocation | One static portfolio for life | No glidepath or de-risking at retirement is modelled |
| Contributions | Added at end of each working year | Slightly conservative versus monthly contributions |
| Withdrawals | Constant real amount each year | Real retirees adjust spending in bad markets |
| Taxes | Not modelled | Enter spending on an after-tax basis |
| Fees | Not modelled | Subtract expected fees from the return assumption instead |
| Guaranteed income | Grows with inflation, never stops | Ignores survivor-benefit reductions and policy changes |
| Longevity | Fixed planning age | Real life expectancy is a distribution |
| Rebalancing | Implicit and costless | No transaction costs or tracking error |

Defaults live in `utils/assumptions.py`. Nothing is hard-coded inside the simulation.

---

## 12. Known limitations

- **Normal returns understate tail risk.** A Student-t distribution or historical
  bootstrap would produce more realistic crashes. This is the highest-value upgrade.
- **No taxes.** Tax treatment differs sharply between traditional, Roth and taxable
  accounts and would change withdrawal sequencing.
- **No required minimum distributions.**
- **Constant real spending.** Actual retirement spending tends to decline in real terms
  through the middle of retirement and rise again with healthcare costs.
- **Annual time steps.** Monthly steps would model contribution and withdrawal timing
  more precisely.
- **Single portfolio.** No multi-account modelling and no asset-location logic.
- **No spousal modelling.** One timeline, one life expectancy.
- **Results are not persisted.** Session state clears when the browser tab closes; there
  is no database in this version.

None of these are hidden — the assumptions table in the application lists them for the
end user too.

---

## 13. How to verify the simulation is working

Do not take the engine on trust. Each of these checks can be performed in the running
application in under a minute.

**Check 1 — Reproducibility.** Run a projection, note the success probability, change
nothing, and run it again. The result must be identical. Now change the random seed from
42 to 43 and re-run: the number should move slightly (sampling noise) but stay in the
same neighbourhood.

**Check 2 — Turn off randomness.** Set volatility to **0%**. Every simulated path
becomes identical, the projection chart collapses to a single line, the histogram becomes
one bar, and success probability is exactly 0% or 100%. If anything else happens, the
random draws are being applied incorrectly.

**Check 3 — Hand-check the compounding.** With volatility at 0%, set current age 60,
retirement age 63, life expectancy 64, savings $100,000, contribution $10,000,
contribution increase 0%, return 5%. The balance at 65 should equal:

```
Year 1: 100,000 × 1.05 + 10,000 = 115,000
Year 2: 115,000 × 1.05 + 10,000 = 130,750
Year 3: 130,750 × 1.05 + 10,000 = 147,287.50
```

The percentile table should show $147,288 at age 63. This exact calculation is asserted
in `test_zero_volatility_matches_hand_calculated_accumulation`.

**Check 4 — Force guaranteed failure.** Set savings to $0, contribution to $0 and
spending to $50,000. Success probability must be 0% and the median depletion age must
equal current age + 1.

**Check 5 — Force guaranteed success.** Set savings to $25,000,000 and spending to $0.
Success probability must be 100%, and the median depletion age must display "N/A"
rather than an error.

**Check 6 — Guaranteed income covers spending.** Set spending and Social Security to the
same figure. Net withdrawals become zero, so the portfolio should keep growing after
retirement rather than declining.

**Check 7 — Directional sanity.** Each of these must move success probability in the
expected direction: raising contributions (up), raising spending (down), retiring later
(up), raising volatility while holding the mean constant (down, because volatility drag
reduces compound growth).

**Check 8 — Dollar basis.** Switch between today's dollars and nominal dollars. Balances
should change, but the success probability must not move by even one path.

**Check 9 — Non-negative balances.** No chart, table or metric should ever display a
negative balance under any inputs, including 95% volatility.

**Check 10 — The automated suite.** Run `pytest`. All 35 tests assert the behaviours
above programmatically.

### Reference output

With the shipped defaults (age 30 → 65 → 92, $75,000 saved, $20,000/yr growing 2%,
7% return, 15% volatility, 2.5% inflation, $70,000 spending, $24,000 Social Security,
beginning-of-year withdrawals, 10,000 simulations, seed 42, today's dollars):

| Metric | Value |
|---|---|
| Success probability | 77.4% |
| Median balance at age 65 | $1,472,743 |
| Median balance at age 92 | $1,415,157 |
| 10th percentile ending balance | $0 |
| Median depletion age | 84 |

If you reproduce those numbers exactly, your installation is correct.

---

## 14. Planned future modules and where to add them

The framework is deliberately built so that a new module is an additive change, not a
refactor.

| Module | Planned capability |
|---|---|
| Scenario Comparison | Save several projections and compare success probability, percentile balances and median paths side by side; sensitivity analysis on retirement age, savings rate and spending |
| Portfolio Analysis | Upload holdings from CSV; allocation, concentration, historical return, volatility, drawdown and Sharpe ratio |
| Portfolio Optimizer | Mean-variance optimisation, efficient frontier, maximum-Sharpe and minimum-variance portfolios, weight constraints |
| Risk Profile | Risk questionnaire scored to a model portfolio, then handed back to the planner as return and volatility assumptions |

### How to add a new module

1. **Write the calculation engine** in `models/`, for example
   `models/optimizer.py`. It must not import Streamlit. Give it a dataclass for inputs
   and a dataclass for results, mirroring `RetirementInputs` / `SimulationResults`.
2. **Add its defaults and bounds** to `utils/assumptions.py` and its rules to
   `utils/validation.py`. Never hard-code an assumption in the model.
3. **Add a service** in `services/` that turns widget values into the input dataclass and
   turns results into tables and plain-English text.
4. **Add chart builders** to `components/charts.py` and any new cards to
   `components/metrics.py`, so the new page reuses the existing visual language.
5. **Replace the placeholder page** in `pages/`. Keep the numeric prefix — it controls
   the sidebar order. Copy the structure of `2_Retirement_Planner.py`: configure the page,
   collect inputs, validate, run, render.
6. **Update the module list** in `components/navigation.py`. Change that module's
   `"status"` from `"planned"` to `"active"`, and update the counter on the landing page.
7. **Write tests** in `tests/`, following the patterns in `test_monte_carlo.py`:
   reproducibility, validation, a hand-calculable case, and edge cases.

Because `SimulationResults` already exposes the full balance grid, percentile helpers
and a flat `summary()` dictionary, Scenario Comparison in particular needs almost no new
financial logic — it mainly stores a list of results objects and charts them together.

---

## 15. Troubleshooting

| Problem | Fix |
|---|---|
| `python: command not found` | Try `python3`. On Windows, reinstall Python with "Add to PATH" ticked. |
| `streamlit: command not found` | The virtual environment is not active. Re-run the activation command from Step 4. |
| `ModuleNotFoundError: No module named 'models'` | You are not in the project root. `cd` into the folder containing `app.py` and run `streamlit run app.py` from there. |
| PowerShell blocks activation | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then activate again. |
| Port 8501 already in use | `streamlit run app.py --server.port 8502` |
| Browser does not open | Open <http://localhost:8501> manually. |
| Changes not appearing | Streamlit reloads on save; if not, press **R** in the browser or restart the server. |
| Simulation feels slow | Reduce the simulation count to 5,000 in the sidebar. 10,000 should take about a second. |
| `pytest` collects nothing | Run it from the project root, where `pytest.ini` lives. |

---

## Licence and use

Built as an educational portfolio project. Not for use in providing financial advice.
