# pretest

**Conditional Extrapolation Pre-Testing for Difference-in-Differences**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)
[![Version: 0.1.0](https://img.shields.io/badge/Version-0.1.0-green.svg)](CHANGELOG.md)

<p align="center">
  <img src="image/README/image.png" alt="pretest" width="100%">
</p>

## Overview

`pretest` implements the conditional extrapolation pre-test and interval-reporting
rule of Mikhaeil and Harshaw (2026) as a typed Python API. Given pre-treatment
violations, a covariance structure, and an analyst threshold *M*, it returns a
`PretestResultSnapshot` containing the pass/fail decision, conditional confidence
interval, conventional comparison interval, and all diagnostic scalars.

Under the **conditional extrapolation assumption**, if pre-treatment violations
do not exceed *M*, the conditional interval becomes reportable:

> **Assumption 3 (Conditional Extrapolation):** If *S*<sub>pre</sub> ≤ *M*, then *S*<sub>post</sub> ≤ *S*<sub>pre</sub>.

**First Run:**

```python
import pretest

df, dgp = pretest.generate_did_data_from_preset("small_violation", n_units=200, seed=42)
snapshot = pretest.pretest_from_dataframe(
    df, outcome="y", treatment="treat", time="time",
    threshold=1.0, treat_time=6, mode="iterative", seed=42,
)
print(snapshot.reporting_summary()["decision"])  # "PASS" or "FAIL"
```

## Requirements

| Requirement | Description |
| :--- | :--- |
| **Python** | 3.11 or higher |
| **Minimum 3 time periods** | *T*<sub>pre</sub> ≥ 2. Iterative violations ν̂<sub>t</sub> are defined for *t* ≥ 2. |
| **Block adoption design** | All treated units share a single treatment time *t*<sub>0</sub>. Staggered adoption is **not** supported. |
| **Binary treatment** | Coded as 0 (control) or 1 (treated). |
| **Complete time-group cells** | Each period must have observations in both groups. |

### Data Completeness

When some time periods lack observations for either group, the covariance matrix
cannot be computed. The API returns an invalid `PretestResultSnapshot`:

- `snapshot.reporting_summary()["decision"]` → `"INVALID"`
- `snapshot.reporting_summary()["data_valid"]` → `0`
- `snapshot.conditional_interval()` → `None`

### Two-Period Designs

This package **cannot be used** for canonical 2×2 DID designs with only two time
periods (*T*<sub>pre</sub> < 2).

## Installation

```bash
pip install pretest
```

From GitHub:

```bash
pip install "git+https://github.com/gorgeousfish/pretest-py.git#subdirectory=pretest-py"
```

Verify:

```bash
python -m pretest --version
```

## Quick Start

```python
import pretest

# Generate a DID dataset with a small pre-treatment violation
df, dgp = pretest.generate_did_data_from_preset("small_violation", n_units=200, seed=42)

# Run the full pre-test pipeline
snapshot = pretest.pretest_from_dataframe(
    df,
    outcome="y",
    treatment="treat",
    time="time",
    threshold=1.0,
    treat_time=6,
    p=2.0,
    alpha=0.05,
    mode="iterative",
    simulations=5000,
    seed=42,
)

# Inspect the result
summary = snapshot.reporting_summary()
summary["decision"]              # "PASS", "FAIL", "INVALID", or "UNKNOWN"
summary["S_pre"]                 # pre-treatment severity
summary["threshold"]             # analyst threshold M
summary["conditional_interval"]  # conditional CI bounds (None if FAIL)
summary["conventional_interval"] # comparison interval bounds
```

## API Reference

### Core Functions

| Function | Description | Reference |
| :--- | :--- | :--- |
| `pretest_from_dataframe(...)` | End-to-end pre-test from a DataFrame | Theorems 1–2 |
| `compute_pretest_snapshot(...)` | Snapshot from pre-computed kernel inputs | Theorems 1–2 |
| `compute_severity(...)` | Compute *Ŝ*<sub>pre</sub> from violations | §2.1 |
| `classify_pretest(...)` | Decision φ = 𝟙{Ŝ<sub>pre</sub> > M} | Theorem 1 |
| `compute_kappa(...)` | Bias-bound constant κ | Theorem 2 |
| `compute_ci_half_width(...)` | Conditional CI half-width | Theorem 2 |
| `compute_critical_value(...)` | Monte Carlo critical value *f*(α, Σ̂) | §3 |

### Pipeline

| Function | Description |
| :--- | :--- |
| `compute_pretest_snapshot_from_records(...)` | Snapshot from group-time CSV records |
| `compute_pretest_kernel_inputs_from_records(...)` | Extract kernel inputs from records |
| `load_prop99_window_iter_records_from_csv(...)` | Load Proposition 99 example records |

### Simulation

| Function | Description |
| :--- | :--- |
| `simulate_coverage(...)` | Coverage from draw-level sequences |
| `simulate_coverage_from_covariance(...)` | Coverage from covariance specification |
| `compute_section6_violation_path(...)` | Section 6 violation path generator |
| `run_monte_carlo_coverage(...)` | Full Monte Carlo coverage experiment |

### Sensitivity

| Function | Description |
| :--- | :--- |
| `compute_m_sensitivity(...)` | M-sensitivity analysis over a threshold grid |

### Data Generating Processes

| Function | Description |
| :--- | :--- |
| `generate_did_data(...)` | Generate DID data from a `DGPConfig` |
| `generate_did_data_from_preset(...)` | Generate data from named presets |
| `compute_true_covariance(...)` | Population covariance for a DGP |

### Options

| Option | Default | Description |
| :--- | :--- | :--- |
| `threshold` | — | Acceptable violation threshold *M* > 0 (required) |
| `p` | 2 | Severity norm *p* ≥ 1 |
| `alpha` | 0.05 | Significance level |
| `mode` | `"iterative"` | `"iterative"` or `"overall"` |
| `simulations` | 5000 | Monte Carlo draws for critical value |
| `seed` | 12345 | Random seed |
| `cluster` | `None` | Column name for cluster-robust SE |

## Key Formulas

### Pre-test (Theorem 1)

> φ = 𝟙{*Ŝ*<sub>pre</sub> > *M*}

φ = 0 → **PASS** (conditional interval reportable); φ = 1 → **FAIL**.

### Average DID Estimand

**Important:** δ̄̂ is **not** the traditional ATT.

> δ̂<sub>t</sub> = (Ȳ<sub>t,D=1</sub> − Ȳ<sub>t₀,D=1</sub>) − (Ȳ<sub>t,D=0</sub> − Ȳ<sub>t₀,D=0</sub>)

> δ̄̂ = (1/*T*<sub>post</sub>) × Σ<sub>t=t₀</sub><sup>T</sup> δ̂<sub>t</sub>

| Aspect | Paper's δ̄̂ | Traditional ATT |
| :--- | :--- | :--- |
| Reference point | Treatment time *t*<sub>0</sub> | Pre-treatment average |
| δ̂<sub>t₀</sub> | Always 0 (by construction) | N/A |
| Interpretation | Incremental change from *t*<sub>0</sub> | Total treatment effect |

### Conditional Confidence Interval (Theorem 2)

**Iterative mode (default):**

> *I* = δ̄̂ ± {κ · *Ŝ*<sub>pre</sub> + *f*(α, Σ̂) / √*n*}

**Overall mode:**

> *I*<sup>Δ</sup> = δ̄̂ ± {*Ŝ*<sup>Δ</sup><sub>pre</sub> + *f*<sup>Δ</sup>(α, Σ̂<sup>Δ</sup>) / √*n*}

### κ Constant (Iterative Mode Only)

> κ = ((1/*T*<sub>post</sub>) · Σ<sub>t=1</sub><sup>T<sub>post</sub></sup> *t*<sup>q</sup>)<sup>1/q</sup>

where *q* is the Hölder conjugate of *p*. In overall mode κ = 1 (no multiplier).

## Result Object

`PretestResultSnapshot` fields accessible via `reporting_summary()`:

| Field | Description |
| :--- | :--- |
| `decision` | `"PASS"`, `"FAIL"`, `"INVALID"`, or `"UNKNOWN"` |
| `data_valid` | 1 if input data passed validation |
| `S_pre` | Pre-treatment severity |
| `threshold` | Analyst threshold *M* |
| `phi` | Pre-test indicator (0 = pass, 1 = fail) |
| `kappa` | Bias-bound constant κ |
| `delta_bar` | Average DID estimate δ̄̂ |
| `se_delta_bar` | Standard error of δ̄̂ |
| `f_alpha` | Simulated critical value |
| `simulations` | Number of Monte Carlo draws |
| `seed` | Random seed used |
| `conditional_interval` | `(lower, upper)` or `None` if test fails |
| `conventional_interval` | `(lower, upper)` comparison interval |
| `mode` | `"iterative"` or `"overall"` |

Additional methods:

```python
snapshot.conditional_interval()   # -> tuple[float, float] | None
snapshot.conventional_interval()  # -> tuple[float, float] | None
snapshot.reporting_summary()      # -> dict with all fields above
```

## Mode Selection: Iterative vs. Overall

| Feature | Iterative Mode (Default) | Overall Mode (`overall`) |
| :--- | :--- | :--- |
| **Assumption** | Violations accumulate period-to-period | Violations bounded by cumulative total |
| **Sensitivity** | Sensitive to **volatility/noise** | Sensitive to **drift/trend** |
| **Blind Spot** | May pass smooth linear trends | May fail even if period-to-period changes are small |
| **Bias Bound** | Scaled by κ (∝ √*T*<sub>post</sub>) | **No multiplier** (κ = 1) |
| **CI Width** | Includes iterative κ multiplier | Appendix C kappa-free half-width |

**Reporting guidance:**

1. Choose the mode before reading the conditional interval.
2. Use iterative mode when bounding period-to-period violations; overall mode when bounding cumulative divergence.
3. If the two modes disagree, treat the result as a diagnostic contrast.

## Example

```python
import numpy as np
import pretest

# Upstream event-study coefficients (e.g., from PyFixest or statsmodels)
relative_terms = (-2, -1, 0, 1, 2)
event_coefficients = np.array([0.125, -0.076, -0.271, -0.311, -0.240])
event_covariance = np.diag([0.0016] * 5) + 0.0008

# Extract pre/post indices
pre_idx = [i for i, t in enumerate(relative_terms) if t < 0]
post_idx = [i for i, t in enumerate(relative_terms) if t >= 0]
ordered = pre_idx + post_idx

# Compute kernel inputs
nu_vector = tuple(float(event_coefficients[i]) for i in pre_idx)
cov_matrix = tuple(
    tuple(float(event_covariance[r, c]) for c in ordered)
    for r in ordered
)
post_weights = np.ones(len(post_idx)) / len(post_idx)
delta_bar = float(post_weights @ event_coefficients[post_idx])
se_delta_bar = float(np.sqrt(
    post_weights @ event_covariance[np.ix_(post_idx, post_idx)] @ post_weights
))

# Run pretest
snapshot = pretest.compute_pretest_snapshot(
    "pretest outcome, treatment(treated) time(year) treat_time(2019) threshold(0.3)",
    pretest.DatasetProfile(
        time_periods=(2016, 2017, 2018, 2019, 2020, 2021),
        treatment_values=(0, 1),
    ),
    nu_vector=nu_vector,
    covariance_matrix=cov_matrix,
    delta_bar=delta_bar,
    se_delta_bar=se_delta_bar,
    sample_size=240,
    simulations=5000,
    seed=42,
)

summary = snapshot.reporting_summary()
print(f"Decision: {summary['decision']}")
print(f"S_pre: {summary['S_pre']:.4f}")
print(f"Conditional CI: {summary['conditional_interval']}")
print(f"Conventional CI: {summary['conventional_interval']}")
```

For a minimal snapshot from already-computed scalars:

```python
import pretest

snapshot = pretest.compute_pretest_snapshot(
    "pretest cigsale, treatment(treated) time(year) treat_time(1989) threshold(5)",
    pretest.DatasetProfile(
        time_periods=(1985, 1986, 1987, 1988, 1989, 1990, 1991),
        treatment_values=(0, 1),
    ),
    nu_vector=(1.0, 2.0, 3.0),
    f_alpha=2.5,
    delta_bar=1.5,
    sample_size=100,
)
snapshot.reporting_summary()["decision"]
snapshot.conditional_interval()
```

## M-Sensitivity Analysis

`compute_m_sensitivity(...)` evaluates how the pre-test decision and conditional
interval respond to a grid of threshold values:

```python
import pretest

result = pretest.compute_m_sensitivity(
    snapshot,
    m_grid=[0.5, 1.0, 2.0, 5.0, 10.0],
)
result.pass_threshold  # smallest M where the test passes
result.results          # list of per-M snapshots
```

## Not Implemented in 0.1.0

- Triple difference-in-differences designs
- Staggered treatment adoption
- Covariate-adjusted estimation
- Threshold-sensitivity plots over a continuous range of *M* values

## References

Mikhaeil, J. M., & Harshaw, C. (2026). Valid Inference when Testing Violations of Parallel Trends for Difference-in-Differences. *arXiv preprint arXiv:2510.26470v3*. Available at: https://arxiv.org/abs/2510.26470

Rambachan, A., & Roth, J. (2023). A More Credible Approach to Parallel Trends. *Review of Economic Studies*, 90(5), 2555–2591. https://doi.org/10.1093/restud/rdad018

Roth, J. (2022). Pretest with Caution: Event-Study Estimates after Testing for Parallel Trends. *American Economic Review: Insights*, 4(3), 305–322. https://doi.org/10.1257/aeri.20210236

## Authors

**Python Implementation:**

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

If you use this package in your research, please cite:

**APA Format:**

> Cai, X., & Xu, W. (2026). *pretest: Conditional Extrapolation Pre-Testing for Difference-in-Differences* (Version 0.1.0) [Computer software]. https://github.com/gorgeousfish/pretest-py
>
> Mikhaeil, J. M., & Harshaw, C. (2026). Valid Inference when Testing Violations of Parallel Trends for Difference-in-Differences. *arXiv preprint arXiv:2510.26470v3*. https://arxiv.org/abs/2510.26470

**BibTeX:**

```bibtex
@software{cai2026pretest,
  author    = {Cai, Xuanyu and Xu, Wenli},
  title     = {pretest: Conditional Extrapolation Pre-Testing for Difference-in-Differences},
  year      = {2026},
  version   = {0.1.0},
  url       = {https://github.com/gorgeousfish/pretest-py}
}

@misc{mikhaeil2026validinferencetestingviolations,
      title={Valid Inference when Testing Violations of Parallel Trends for Difference-in-Differences},
      author={Jonas M. Mikhaeil and Christopher Harshaw},
      year={2026},
      eprint={2510.26470},
      archivePrefix={arXiv},
      primaryClass={stat.ME},
      url={https://arxiv.org/abs/2510.26470},
}
```
