# pretest

**Conditional extrapolation pre-testing for Difference-in-Differences in Python**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)
[![Version: 0.1.0](https://img.shields.io/badge/Version-0.1.0-green.svg)](CHANGELOG.md)

<p align="center">
  <img src="image/README/image.png" alt="pretest" width="100%">
</p>

## Overview

`pretest` implements the conditional extrapolation pre-test and
interval-reporting rule of Mikhaeil and Harshaw as a typed Python API and CLI.
It starts after a DID or event-study workflow has supplied compatible
pre-treatment violations, covariance or critical-value information, timing,
sample size, an interval center, and an analyst threshold. The main returned
object is a `PretestResultSnapshot` that keeps validation state, severity,
threshold, pass decision, simulation settings, and conditional/conventional
interval fields together.

Under the **conditional extrapolation assumption**, if pre-treatment violations
do not exceed an acceptable threshold *M*, the conditional interval becomes
reportable:

> **Assumption 3 (Conditional Extrapolation):** If *S* <sub>pre </sub> ≤ *M*, then *S* <sub>post </sub> ≤ *S* <sub>pre </sub>.

The package provides:

- Pre-test, severity calculation, and conditional interval reporting rule
- A `PretestResultSnapshot` API exposing decision state, conditional interval,
  conventional comparison interval, diagnostics, and simulation settings
- Record-backed Proposition 99 and upstream-estimator handoff examples
- **Conditional confidence-interval fields** centered on the paper's average DID estimand (`delta_bar`), with ATT-labeled compatibility surfaces documented as aliases rather than canonical ATT-level outputs

## Requirements

| Requirement                         | Description                                                                                                                                                                 |
| :---------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Minimum 3 time periods**    | *T* <sub>pre </sub> ≥ 2. At least two pre-treatment periods are required because iterative violations ν̂<sub>t </sub> are only defined for *t* ≥ 2. |
| **Block adoption design**     | All treated units must receive treatment at the same time *t* <sub>0 </sub>. Staggered adoption designs are **not** supported.                               |
| **Severity norm *p***         | Severity norm *p* must be at least 1 when supplied through the command surface or Python API.                                                             |
| **Binary treatment**          | Treatment indicator must be coded as 0 (control) or 1 (treated).                                                                                                            |
| **Complete time-group cells** | Each time period must contain observations in both treatment and control groups.                                                                                            |

### Data Completeness

When some time periods lack observations for either group, the covariance matrix
cannot be computed. The Python API returns an invalid `PretestResultSnapshot`:

- `snapshot.reporting_summary()["decision"]` is `"INVALID"`
- `snapshot.reporting_summary()["data_valid"]` is `0`
- `snapshot.reporting_summary()["phi"]`, `S_pre`, and `f_alpha` are `None`
- `snapshot.conditional_interval()` and the summary's `conditional_interval`
  field are `None`

The Stata-compatible `e(...)` aliases for those states are documented in the
stored-results section; Python reporting code should read `reporting_summary()`,
`conditional_interval()`, and `conventional_interval()`.

### Two-Period Designs

This command **cannot be used** for canonical 2×2 DID designs with only two time
periods.

## Installation

### Python Package

From the Python package directory:

```bash
python -m pip install .
```

For source-based reproduction with test and paper extras:

```bash
python -m pip install -e ".[test,paper]"
```

The article build also requires a TeX distribution with `pdflatex` and `bibtex`
on `PATH`.

From the public repository URL:

```bash
python -m pip install "git+https://github.com/gorgeousfish/pretest.git#subdirectory=pretest-py"
```

After installation, check the command-line entry point:

```bash
python -m pretest --version
python -m pretest prop99-python-handoff-summary \
  --records-csv PATH/TO/prop99_window_1985_1995.csv \
  --format text
```

The handoff command reads a CSV with columns `cigsale`, `treated`, and `year`,
computes kernel inputs and the Python critical value, and prints the result
snapshot. Pass any CSV regenerated from the documented CRAN `tidysynth` route,
or caller-supplied records with the same columns.

## Quick Start

The Python package exposes a typed API and CLI helpers. It does not read
arbitrary Stata `.dta` files; use the Stata companion for that workflow.

```bash
python -m pretest --version
python -m pretest prop99-python-handoff-summary --records-csv PATH --format text
```

The shortest Python path from Proposition 99 records to a reporting snapshot:

```python
import pretest

records = pretest.load_prop99_window_iter_records_from_csv(
    "PATH/TO/prop99_window_1985_1995.csv"
)
snapshot = pretest.compute_pretest_snapshot_from_records(
    records,
    outcome="cigsale",
    treatment="treated",
    time="year",
    treat_time=1989,
    threshold_m=5,
    p_norm=2,
    mode="overall",
    simulations=5000,
    seed=12345,
)

summary = snapshot.reporting_summary()
summary["decision"]              # "PASS"
summary["conditional_interval"]  # conditional interval bounds
summary["conventional_interval"] # comparison interval bounds
```

For a snapshot from already-computed inputs:

```python
import pretest

profile = pretest.DatasetProfile(
    time_periods=(1985, 1986, 1987, 1988, 1989, 1990, 1991),
    treatment_values=(0, 1),
)
snapshot = pretest.compute_pretest_snapshot(
    "pretest cigsale, treatment(treated) time(year) treat_time(1989) threshold(5)",
    profile,
    nu_vector=(1.0, 2.0, 3.0),
    f_alpha=2.5,
    delta_bar=1.5,
    sample_size=100,
)

summary = snapshot.reporting_summary()
summary["decision"]
summary["conditional_interval"]
summary["conventional_interval"]
```

## High-Level Snapshot API

`pretest.compute_pretest_snapshot(...)` assembles the full package snapshot in
one call from the validated command surface and kernel inputs:

```python
import pretest

profile = pretest.DatasetProfile(
    time_periods=(1985, 1986, 1987, 1988, 1989, 1990, 1991),
    treatment_values=(0, 1),
)
snapshot = pretest.compute_pretest_snapshot(
    "pretest cigsale, treatment(treated) time(year) treat_time(1989) threshold(5)",
    profile,
    nu_vector=(1.0, 2.0, 3.0),
    f_alpha=2.5,
    delta_bar=1.5,
    sample_size=100,
)
```

When `profile` contains `time_periods` and the command specifies
`treat_time(...)`, the helper infers `T_post` automatically. When validation
fails, it returns an invalid-result snapshot immediately without requiring
kernel inputs.

When an upstream Python DID or event-study workflow has already produced
coefficient and covariance output, `pretest` starts at the reporting handoff:

```python
import numpy as np
import pretest

# The manuscript replication script estimates these event-time coefficients
# from a small fixed-effects event-study design before calling pretest.
relative_terms = (-2, -1, 0, 1, 2)
event_coefficients = np.array([0.125195, -0.075836, -0.270610, -0.311162, -0.239842])
event_covariance = np.array([
    [0.00162765, 0.00081383, 0.00081383, 0.00081383, 0.00081383],
    [0.00081383, 0.00162765, 0.00081383, 0.00081383, 0.00081383],
    [0.00081383, 0.00081383, 0.00162765, 0.00081383, 0.00081383],
    [0.00081383, 0.00081383, 0.00081383, 0.00162765, 0.00081383],
    [0.00081383, 0.00081383, 0.00081383, 0.00081383, 0.00162765],
])
pre_indices = [index for index, relative_time in enumerate(relative_terms) if relative_time < 0]
post_indices = [index for index, relative_time in enumerate(relative_terms) if relative_time >= 0]
ordered_indices = pre_indices + post_indices
post_weights = np.ones(len(post_indices)) / len(post_indices)
nu_vector = tuple(float(event_coefficients[index]) for index in pre_indices)
covariance_matrix = tuple(
    tuple(float(event_covariance[row, col]) for col in ordered_indices)
    for row in ordered_indices
)
delta_bar = float(post_weights @ event_coefficients[post_indices])
se_delta_bar = float(np.sqrt(post_weights @ event_covariance[np.ix_(post_indices, post_indices)] @ post_weights))
snapshot = pretest.compute_pretest_snapshot(
    "pretest outcome, treatment(treated) time(year) treat_time(2019) threshold(0.3)",
    pretest.DatasetProfile(
        time_periods=(2016, 2017, 2018, 2019, 2020, 2021),
        treatment_values=(0, 1),
    ),
    nu_vector=nu_vector,
    covariance_matrix=covariance_matrix,
    delta_bar=delta_bar,
    se_delta_bar=se_delta_bar,
    sample_size=240,
    simulations=1000,
    seed=20260608,
)
```

The covariance dimension must match `(T_pre - 1) + T_post` after the time
profile and treatment time are resolved.

The snapshot exposes a compact reporting view:

```python
summary = snapshot.reporting_summary()
summary["decision"]              # "PASS", "FAIL", "INVALID", or "UNKNOWN"
summary["S_pre"]                 # pre-treatment severity
summary["threshold"]             # analyst threshold M
summary["conditional_interval"]  # None when the pre-test does not pass
summary["conventional_interval"] # comparison interval when SE input is supplied

snapshot.conditional_interval()
snapshot.conventional_interval()
```

A compact report table should include `mode`, `data_valid`, `S_pre`,
`threshold`, `decision`, `f_alpha`, `simulations`, `seed`,
`conditional_interval`, and `conventional_interval`. If `decision` is `FAIL` or
`INVALID`, report the conditional interval as unavailable; the conventional
interval is a separate comparison family.

The Stata-style command parser keeps the severity option explicit:

| Option | Default | Description |
| :----- | :------ | :---------- |
| `p(#)` | 2 | Severity norm *p* >= 1; use `p(.)` or `p(1e10)` for L-infinity |

`pretest.compute_critical_value(...)` and `pretest.compute_psi(...)` expose the
simulation kernel directly. The critical-value path is deterministic for a fixed
seed and follows the dimension convention `(T_pre - 1) + T_post`. In
`mode="overall"`, the helper applies the Appendix C bridge internally before
simulating `f^Delta(alpha, Sigma^Delta)`. Callers holding cumulative-coordinate
`Sigma^Delta` should pass `covariance_form="overall"` to skip the bridge.

```python
import pretest

f_alpha = pretest.compute_critical_value(
    covariance_matrix=((1.0, 0.2), (0.2, 1.0)),
    alpha=0.2,
    simulations=100,
    t_pre=2,
    t_post=1,
    p_norm=2,
    mode="overall",
    seed=7,
)
```

Snapshot callers can omit `f_alpha` when they provide `covariance_matrix`,
`simulations`, and `seed`; the snapshot diagnostics record the simulation
settings used. The same overall-mode bridge is applied inside
`compute_pretest_snapshot(...)`.

```python
import pretest

snapshot = pretest.compute_pretest_snapshot(
    "pretest cigsale, treatment(treated) time(year) treat_time(1990) threshold(5) alpha(0.2)",
    pretest.DatasetProfile(time_periods=(1988, 1989, 1990), treatment_values=(0, 1)),
    nu_vector=(1.0,),
    covariance_matrix=((1.0, 0.0), (0.0, 1.0)),
    simulations=100,
    seed=7,
    delta_bar=1.5,
    sample_size=100,
)
```

For overall-mode snapshots, set `pre_violations_form="overall"` when
`nu_vector` already carries cumulative `nu_bar` coordinates. The `nu_vector`
length must match `T_pre - 1`. Use `covariance_form="iterative"` for raw
iterative covariance targets; the snapshot records covariance targets
`theta = (nu, delta)`. The records estimator is a repeated-cross-section
surface: it does not accept panel identifiers or cluster variables, reports
`e(is_panel)=0`, and uses the Stata/Mata `n / n_td` weighting convention with
`n - 1` divisor. Cluster covariance is not implemented.

`pretest.simulate_coverage(...)` turns draw-level `delta_bar` / `S_pre`
sequences into a deterministic `SimulationCoverageResult`. The summary reports
total replications, pretest pass rate, `conditional_coverage` among passing
draws, `valid_reporting_rate` as unconditional coverage over all draws, and
`mean_ci_width_when_passed`.

```python
import pretest

coverage = pretest.simulate_coverage(
    true_effect=1.0,
    delta_bar_draws=(0.95, 1.10, 1.30),
    s_pre_draws=(0.1, 0.2, 2.0),
    f_alpha=1.0,
    sample_size=100,
    threshold_m=1.0,
    kappa=2.0,
    mode="iterative",
)

coverage.conditional_coverage
coverage.valid_reporting_rate
coverage.mean_ci_width_when_passed
```

`pretest.simulate_coverage_from_covariance(...)` adds the covariance-level
coverage summary. The `simulations` argument controls the critical-value Monte
Carlo order statistic; use `coverage_replications` when the coverage draw count
should differ. `delta_bar` draws are centered at
`tau_bar - true_post_violation_mean`, with `true_post_violation_mean=0` as the
no-post-violation case. The Section 6 reference violation path is
`pretest.compute_section6_violation_path(...)`, using
`log(T) * (sin(t) + cos(t/2))` scaled to target normalized severity.

In overall mode, `simulate_coverage(...)` uses the Appendix C kappa-free
half-width; `simulate_coverage_from_covariance(...)` derives the paper kappa for
iterative coordinates. When `pre_violations_form="overall"`, inputs are already
the cumulative `nu_bar` / `Delta` coordinate. Overall simulation helpers require
`kappa=1`. Degenerate PSD covariance inputs keep their exact Gaussian law and
may produce `f_alpha = 0.0`. For L-infinity behavior, `p_norm >= 1e10` is the
finite numeric sentinel: both `p(.)` and `p(1e10)` select the L-infinity path.

`SimulationCoverageResult.to_dict()` returns a JSON-ready mapping including
proposed and conventional coverage rates with standard error keys:
`conditional_coverage_standard_error`, `valid_reporting_rate_standard_error`,
`conventional_conditional_coverage`,
`conventional_conditional_coverage_standard_error`,
`conventional_valid_reporting_rate`, and
`conventional_valid_reporting_rate_standard_error`. If
`conventional_half_width` is omitted, the legacy fallback is not the pretest
critical value `f_alpha`. After the critical-value simulation, the coverage
helper uses the same deterministic random stream's subsequent draws for coverage
replications.

```python
import pretest

pre_path = pretest.compute_section6_violation_path(
    t_start=2,
    t_end=3,
    total_periods=5,
    target_severity=1.0,
    p_norm=2,
)
post_path = pretest.compute_section6_violation_path(
    t_start=4,
    t_end=5,
    total_periods=5,
    target_severity=0.2,
    p_norm=2,
)
section6_coverage = pretest.simulate_coverage_from_covariance(
    true_effect=1.0,
    true_pre_violations=pre_path,
    true_post_violations=post_path,
    covariance_matrix=(
        (0.0, 0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0, 0.0),
    ),
    alpha=0.05,
    simulations=100,
    coverage_replications=100,
    sample_size=100,
    threshold_m=2.0,
    t_pre=3,
    t_post=2,
    p_norm=2,
    mode="iterative",
    seed=7,
)

section6_coverage.valid_reporting_rate
section6_coverage.conventional_conditional_coverage
section6_coverage.conventional_valid_reporting_rate
section6_coverage.conventional_conditional_coverage_standard_error
section6_coverage.conventional_valid_reporting_rate_standard_error
section6_coverage.critical_value
section6_coverage.to_dict()
```

### Selected Stable Python API

For package identity, use `__version__`.

For command parsing and validation, use `PretestCommandSpec`,
`parse_stata_command(...)`, `DatasetProfile`, `run_validation(...)`, `validate_option_domain(...)`,
`ConfidenceIntervalAvailability`, `resolve_ci_availability(...)`,
`ValidationContractError`, and `PretestValidationError`.

For the paper formulas, use `compute_severity(...)`, `classify_pretest(...)`,
`compute_kappa(...)`, `compute_kappa_weighted(...)`, `compute_bias_bound(...)`,
`compute_ci_half_width(...)`, `compute_severity_gradient(...)`,
`compute_severity_se(...)`, `compute_critical_value(...)`,
`compute_psi(...)`, `normalize_critical_value(...)`, and `SeverityDecision`.

For simple group-time data and covariance handoffs, use
`pretest_from_dataframe(...)`, `compute_influence_matrix(...)`,
`compute_standard_covariance(...)`, `compute_cluster_robust_covariance(...)`,
and `extract_nu_covariance(...)`.

For assembled outputs, use `compute_pretest_snapshot(...)`,
`PretestResultSnapshot`,
`load_prop99_window_iter_records_from_csv(...)`,
`compute_pretest_snapshot_from_records(...)`, and
`compute_pretest_kernel_inputs_from_records(...)`. For simulation summaries, use
`simulate_coverage(...)`, `simulate_coverage_from_covariance(...)`,
`SimulationCoverageResult`, and `compute_section6_violation_path(...)`.

For M-sensitivity analysis, use `compute_m_sensitivity(...)` and
`MSensitivityResult`.

For data generating processes and Monte Carlo coverage experiments, use
`DGPConfig`, `generate_did_data(...)`, `generate_did_data_from_preset(...)`,
`compute_true_covariance(...)`, `run_monte_carlo_coverage(...)`, and
`MonteCarloResult`.

The stable root namespace is intentionally smaller than the local reproduction
surface. Packaged Prop99 summaries and reference checks remain available through
submodules and CLI commands:
`pretest.data_estimators.load_prop99_window_iter_records(...)`,
`pretest.data_estimators.build_prop99_python_handoff_summary(...)`,
`pretest.data_estimators.build_prop99_window_iter_parity_summary(...)`,
`pretest.data_estimators.build_prop99_window_overall_deterministic_split_capture_evidence(...)`,
`pretest.replay_summary.materialize_prop99_replay_summary(...)`,
`pretest.replay_summary.load_prop99_nonoverall_split_capture_inventory(...)`,
and `pretest.plotting.render_event_study_svg(...)`.

## Prop99 Public Example And Reference Helpers

The Proposition 99 handoff command reads reduced records from an explicit CSV,
derives the DID quantities, computes the Python Monte Carlo critical value, and
prints the snapshot fields:

```bash
python -m pretest prop99-python-handoff-summary --records-csv PATH --format text
```

The CSV must have columns `cigsale`, `treated`, and `year`.

Additional local reference helpers inspect Stata stored results and graph
preview material when fixed-reference files are available, reached through
`pretest.replay_summary` and `pretest.plotting` submodules. These are local
reproduction aids, not part of the public wheel interface.

For user-facing analysis, prefer the record-backed API path: load group-time
records, compute kernel inputs, and call `compute_pretest_snapshot(...)`.

## Distribution And Public Release Checks

To install the companion Stata files from a local copy:

```stata
cd "/path/to/pretest"
net install pretest, from("`c(pwd)'/pretest-stata") replace
net get pretest, from("`c(pwd)'/pretest-stata") replace
```

Before a public tag, run Python distribution checks from a clean repository
copy. The GitHub Actions workflow `.github/workflows/python-release-gates.yml`
builds the wheel and source distribution, validates metadata, and makes checked
files downloadable as `pretest-0.1.0-distributions`. The local equivalent:

```bash
python -m build
twine check dist/*
python -m pip install dist/pretest-0.1.0-py3-none-any.whl
python -m pretest --version
python -m pretest prop99-python-handoff-summary --records-csv PATH --format text
```

The public wheel command surface uses regenerated or caller-supplied records for
the Prop99 handoff. Use `prop99-replay-summary` only as a local reference
command when fixed-reference files are present and
`PRETEST_ENABLE_SOURCE_TREE_HELPERS=1` is set.

## Companion Stata Reference Outputs

The companion Stata command supplies the reference outputs used by the packaged
replay cases. Its syntax, graph options, stored results, and installation notes
are documented in `pretest-stata/README.md` and `pretest-stata/pretest.sthlp`.
The Python CLI does not execute arbitrary `.dta` files and does not accept Stata
graph options such as `ci_opt_pass()` or `line_opt_m()`; use the Python API and
module commands above for the Python package surface.

## Key Formulas

### Pre-test (Theorem 1)

The pre-test indicator is defined as:

> φ = 𝟙{*Ŝ* <sub>pre </sub> > *M*}

where φ = 0 indicates **PASS** (the conditional interval is reportable under
the stated restriction) and φ = 1 indicates **FAIL** (the conditional interval
is not reported).

### Average DID Estimate

**Important:** The δ̄̂ reported by this package is **not** the traditional ATT.

The DID estimand at time *t* is defined relative to the treatment time *t* <sub>0 </sub>:

> δ̂<sub>t </sub> = (Ȳ <sub>t,D=1 </sub> − Ȳ <sub>t₀,D=1 </sub>) − (Ȳ <sub>t,D=0 </sub> − Ȳ <sub>t₀,D=0 </sub>)

where Ȳ <sub>t,D=d </sub> denotes the sample mean of outcomes for group *D* = *d* at time *t*.

The average DID estimand across post-treatment periods is:

> δ̄̂ = (1/*T*<sub>post</sub>) × Σ<sub>t=t₀</sub><sup>T</sup> δ̂<sub>t</sub>

**Key differences from traditional DID:**

| Aspect                     | Paper's δ̄̂                                     | Traditional ATT        |
| :------------------------- | :------------------------------------------------- | :--------------------- |
| Reference point            | Treatment time *t* <sub>0 </sub>          | Pre-treatment average  |
| δ̂<sub>t₀</sub> | Always 0 (by construction)                         | N/A                    |
| Interpretation             | Incremental change from*t* <sub>0 </sub> | Total treatment effect |

**Example:** If treatment effect is constant at 2.0 per period:

- Traditional ATT ≈ 2.0 (total effect)
- Paper's δ̄̂ ≈ 0 (no incremental change after t₀)

**Why this definition?** The paper's δ̄̂ is designed for the conditional extrapolation framework, where:

1. The CI bounds account for potential bias via κ · Ŝ_pre
2. The interpretation is: "treatment effect relative to treatment onset"

For a conventional comparison interval on the same δ̄ center, read
`e(ci_conv_lower)` and `e(ci_conv_upper)` or the Python snapshot's
`conventional_interval()` method. These fields are not a traditional ATT-level
interval.

### Conditional Confidence Interval (Theorem 2)

 **1. Iterative mode (Default):**

> *I* = δ̄̂ ± {κ · *Ŝ* <sub>pre </sub> + *f*(α, Σ̂) / √*n*}

 Bias bound includes the multiplier κ ≥ 1.

 **2. Overall mode:**

> *I*<sup>Δ</sup> = δ̄̂ ± {*Ŝ*<sup>Δ</sup><sub>pre</sub> + *f*<sup>Δ</sup>(α, Σ̂<sup>Δ</sup>) / √*n*}

 Bias bound uses *no multiplier* (κ = 1).

### κ Constant (Iterative Mode Only)

> κ = ((1/*T*<sub>post</sub>) · Σ<sub>t=1</sub><sup>T<sub>post</sub></sup> *t*<sup>q</sup>)<sup>1/q</sup>

 where *q* is the Hölder conjugate of *p*. κ captures the worst-case accumulation of iterative violations over time.

- For *T* <sub>post </sub> > 1, κ > 1.
- For *p* = 2 and large *T* <sub>post </sub>, κ grows with √*T* <sub>post </sub>.
- **Overall Mode:** κ is not used (effectively κ = 1); interval width follows the Appendix C kappa-free formula.

## Stored Results

The `e(...)` names below document the Stata companion and fixed-reference result
surface. Python code should read `reporting_summary()`,
`conditional_interval()`, and `conventional_interval()` unless intentionally
inspecting Stata-compatible reference outputs.

### Scalars

| Result              | Description                                                     |
| :------------------ | :-------------------------------------------------------------- |
| `e(S_pre)`        | Estimated pre-treatment severity                                |
| `e(S_pre_se)`     | Standard error of S_pre (Delta method)                          |
| `e(kappa)`        | Bias bound constant κ (iterative mode; equals 1 in overall mode) |
| `e(phi)`          | Pre-test result (0 = pass, 1 = fail, . = data issue or invalid) |
| `e(data_valid)`   | Data validity indicator                                         |
| `e(pretest_pass)` | Pre-test pass indicator                                         |
| `e(delta_bar)`    | Average DID estimate                                            |
| `e(ATT)`          | Compatibility-only alias for `e(delta_bar)` (δ̄ relative to t0; not τ̄ / ATT level) |
| `e(se_delta_bar)` | Standard error of average DID estimate                          |
| `e(ci_lower)`     | Conditional CI lower bound                                      |
| `e(ci_upper)`     | Conditional CI upper bound                                      |
| `e(T)`            | Total time periods                                              |
| `e(T_pre)`        | Pre-treatment periods                                           |
| `e(T_post)`       | Post-treatment periods                                          |
| `e(N)`            | Number of observations                                          |

### Matrices

| Result       | Description                                                  |
| :----------- | :----------------------------------------------------------- |
| `e(nu)`    | Iterative violations (*T* <sub>pre </sub>−1 × 1) |
| `e(delta)` | DID estimates (*T* <sub>post </sub> × 1)          |
| `e(theta)` | Full parameter vector θ̂                                   |
| `e(Sigma)` | Asymptotic covariance matrix                                 |
| `e(b)`     | Compatibility-only coefficient vector for the ATT-labeled `delta_bar` alias |
| `e(V)`     | Compatibility-only variance matrix for the ATT-labeled `delta_bar` alias |

All ATT-labeled compatibility surfaces carry δ̄, not τ̄.
In overall mode, `e(theta)` and `e(S_pre_se)` stay diagnostic-only because
current Stata auxiliaries follow the iterative path; authoritative overall replay
targets stay on the primary scalar bridge.

## Mode Selection: Iterative vs. Overall

| Feature               | Iterative Mode (Default)                                        | Overall Mode (`overall`)                               |
| :-------------------- | :-------------------------------------------------------------- | :------------------------------------------------------- |
| **Assumption**  | Violations accumulate period-to-period                          | Violations are bounded by cumulative total               |
| **Sensitivity** | Sensitive to **volatility/noise** (sharp changes)          | Sensitive to **drift/trend** (long-term divergence) |
| **Blind Spot**  | May pass smooth linear trends (constant small changes)          | May fail even if period-to-period changes are small      |
| **Bias Bound**  | Scaled by κ (proportional to √*T* <sub>post </sub>) | **No multiplier** (κ = 1)                         |
| **CI Width**    | Includes the iterative κ multiplier          | Uses the Appendix C kappa-free half-width         |

In iterative mode, the conditional CI is centered at δ̄ and adjusted by κ · Ŝ_pre.
In overall mode, the Appendix C half-width stays κ-free: δ̄ ± {Ŝ_pre^Δ + f^Δ(α, Σ̂^Δ) / √n}.

**Reporting guidance:**

1. Choose the mode before reading the conditional interval and report it with
   `S_pre`, `threshold`, `decision`, `f_alpha`, `simulations`, and `seed`.
2. Use iterative mode when bounding period-to-period violations; overall mode
   when bounding cumulative divergence from the treatment-time baseline.
3. If the two modes disagree, treat the result as a diagnostic contrast. Inspect
   the pre-treatment path, state which violation coordinate the threshold *M*
   bounds, and report a conditional interval only for the selected mode.

## Stata Companion Example

The following local example uses the companion Stata command. The
Python package itself exposes API and packaged-reference commands rather than a
general `.dta` estimation command.

```stata
* Simulated panel data
clear
set seed 12345
set obs 500
gen id = ceil(_n/10)
gen time = mod(_n-1, 10) + 1
gen treat = (id <= 25)
gen y = rnormal() + treat*(time >= 6)*0.5
```

## Not Implemented In 0.1.0

The items below are outside version 0.1.0's documented public interface:

- Triple difference-in-differences designs with an additional grouping dimension
- Staggered treatment adoption designs
- Covariate-adjusted estimation inside the Python package
- Threshold-sensitivity plots over a continuous range of *M* values

## References

Mikhaeil, J. M., & Harshaw, C. (2026). Valid Inference when Testing Violations of Parallel Trends for Difference-in-Differences. *arXiv preprint arXiv:2510.26470v3*. Available at: https://arxiv.org/abs/2510.26470

Rambachan, A., & Roth, J. (2023). A More Credible Approach to Parallel Trends. *Review of Economic Studies*, 90(5), 2555–2591. https://doi.org/10.1093/restud/rdad018

Roth, J. (2022). Pretest with Caution: Event-Study Estimates after Testing for Parallel Trends. *American Economic Review: Insights*, 4(3), 305–322. https://doi.org/10.1257/aeri.20210236

## Authors

**Python package authors and maintainers:**

- **Xuanyu Cai**, City University of Macau
  Email: [xuanyuCAI@outlook.com](mailto:xuanyuCAI@outlook.com)
- **Wenli Xu**, City University of Macau
  Email: [wlxu@cityu.edu.mo](mailto:wlxu@cityu.edu.mo)

**Methodology:**

- **Jonas M. Mikhaeil**, Department of Statistics, Columbia University
- **Christopher Harshaw**, Department of Statistics, Columbia University

## License

AGPL-3.0. See [LICENSE](LICENSE) for details.

## Citation

If you use this Python package in your research, please cite the package and the
methodology paper. Until version 0.1.0 has a public DOI, tagged release URL, or
package page, cite the software version and note that the source and
reproduction files are pending a persistent public identifier.

**APA Format:**

> Cai, X., & Xu, W. (2025). *pretest: Software for conditional extrapolation pre-testing in Python* (Version 0.1.0) [Computer software]. Source and reproduction files pending persistent DOI, versioned release URL, or public package page.
>
> Mikhaeil, J. M., & Harshaw, C. (2026). Valid Inference when Testing Violations of Parallel Trends for Difference-in-Differences. *arXiv preprint arXiv:2510.26470v3*. https://arxiv.org/abs/2510.26470

**BibTeX:**

```bibtex
@software{pretestpy2025,
      title={pretest: Software for conditional extrapolation pre-testing in Python}
      author={Xuanyu Cai and Wenli Xu},
      year={2025},
      version={0.1.0},
      note={Source and reproduction files pending persistent DOI, versioned release URL, or public package page}
}

@misc{mikhaeil2026valid,
      title={Valid Inference when Testing Violations of Parallel Trends
             for Difference-in-Differences},
      author={Jonas M. Mikhaeil and Christopher Harshaw},
      year={2026},
      eprint={2510.26470},
      archivePrefix={arXiv},
      primaryClass={stat.ME},
      note={arXiv:2510.26470v3},
      url={https://arxiv.org/abs/2510.26470}
}
```

