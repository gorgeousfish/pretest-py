# Changelog

All notable changes to `pretest` will be documented in this file.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

## [0.1.0] - 2025-12-22

### Added

**Core functionality**

- DID estimators for δ̂ₜ and ν̂ₜ (Section 2.1)
- Severity measurement with *p*-norm, *p* ∈ [1, ∞] (Section 3.1)
- κ constant with closed-form solutions (Section 3.2, Proposition 1)
- ψ function for Monte Carlo critical values (Section 5.1)
- Conditionally valid confidence intervals (Section 5.1, Theorem 2)

**Stata interface**

- Complete command syntax with required and optional arguments
- Formatted output display following Stata conventions
- Comprehensive return values in `e()`
- Event study visualization
- SMCL help documentation (`help pretest`)

**Python package**

- Releasable `pretest` package with a typed public API and console script
- Stata-style command parser, dataset validation, severity, kappa, confidence
  interval, and high-level `compute_pretest_snapshot(...)` helpers
- Monte Carlo simulation APIs including `compute_psi(...)`,
  `compute_critical_value(...)`, `simulate_coverage(...)`, and
  `simulate_coverage_from_covariance(...)`
- Public Prop99 records-to-snapshot handoff plus local fixed-reference CLI
  helpers for inspecting bounded same-case comparison metadata
- Prop99 overall reference metadata now keeps `capture_ready: true`,
  `graph-exported`, and `numeric_fields_promoted` attached to the captured
  same-case metadata. The bundled Python split documents are record-backed:
  deterministic estimator fields match the companion Stata capture, while
  conditional interval bounds remain stream-specific because the Monte Carlo
  critical value is computed by the Python RNG stream.

**Two violation modes**

- Iterative (default): CI = δ̄̂ ± {κ · Ŝₚᵣₑ + f(α, Σ̂) / √n}
- Overall (Appendix C): CI = δ̄̂ ± {Ŝᐩₚᵣₑ + fᐩ(α, Σ̂ᐩ) / √n}

**Additional features**

- Stata command support for cluster-robust standard errors; the Python records
  helper does not implement cluster covariance
- Monte Carlo critical-value simulation support via the `simulate()` option

### Requirements

- Stata 17.0 or later
- Python 3.11 or later for the `pretest` package
