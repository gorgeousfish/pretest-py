"""05_monte_carlo_simulation.py - Monte Carlo Simulation with the pretest DGP Generator.

This tutorial demonstrates:
1. Generating DID data from built-in DGP presets
2. Running a single pretest analysis on generated data
3. Conducting Monte Carlo coverage experiments
4. Comparing pass rates across different violation magnitudes
5. Customizing DGP configurations

Requirements:
    pip install pretest[data]
"""

from __future__ import annotations

import sys
import time

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas is required. Install with: pip install pretest[data]")
    sys.exit(1)

import pretest

print("=" * 70)
print("  pretest: Monte Carlo Simulation with Built-in DGP")
print("=" * 70)
print(f"\nUsing pretest version: {pretest.__version__}")

# ---------------------------------------------------------------------------
# Step 1: Generate DID data from a built-in preset
# ---------------------------------------------------------------------------
print("\n" + "-" * 70)
print("Step 1: Generate DID data from 'section6_baseline' preset")
print("-" * 70)

df, config = pretest.generate_did_data_from_preset(
    "section6_baseline", n_units=200, seed=42
)

print(f"  Preset: section6_baseline")
print(f"  n_units={config.n_units}, t_pre={config.t_pre}, t_post={config.t_post}")
print(f"  true_effect={config.true_effect}, sigma_epsilon={config.sigma_epsilon}")
print(f"  violation_path={tuple(round(v, 4) for v in config.violation_path)}")
print(f"  true_severity (L2)={config.true_severity:.4f}")
print(f"  Generated DataFrame: {len(df)} rows, columns={list(df.columns)}")

# ---------------------------------------------------------------------------
# Step 2: Run a single pretest analysis on the generated data
# ---------------------------------------------------------------------------
print("\n" + "-" * 70)
print("Step 2: Run pretest_from_dataframe() on generated data")
print("-" * 70)

treat_time = float(config.t_pre + 1)
snapshot = pretest.pretest_from_dataframe(
    df,
    outcome="outcome",
    treatment="treatment",
    time="time",
    threshold=0.5,
    treat_time=treat_time,
    p=2.0,
    alpha=0.05,
    mode="iterative",
    simulations=1000,
    seed=12345,
)

summary = snapshot.reporting_summary()
print(f"  Decision: {summary['decision']}")
print(f"  S_pre: {summary['S_pre']:.4f}")
print(f"  Threshold M: {summary['threshold']}")
print(f"  Conditional CI: {summary['conditional_interval']}")

# ---------------------------------------------------------------------------
# Step 3: Run a Monte Carlo coverage experiment
# ---------------------------------------------------------------------------
print("\n" + "-" * 70)
print("Step 3: Monte Carlo coverage experiment (50 replications)")
print("-" * 70)

start = time.time()
mc_result = pretest.run_monte_carlo_coverage(
    config,
    threshold_m=0.5,
    replications=50,
    alpha=0.05,
    p_norm=2.0,
    mode="iterative",
    simulations=500,
    seed=42,
)
elapsed = time.time() - start

print(f"  Replications: {mc_result.replications}")
print(f"  Pass rate: {mc_result.pass_rate:.2%}")
print(f"  Pass count: {mc_result.pass_count}/{mc_result.replications}")
print(f"  Conditional coverage: {mc_result.conditional_coverage}")
print(f"  Valid reporting rate: {mc_result.valid_reporting_rate:.4f}")
print(f"  Mean CI width (passed): {mc_result.mean_ci_width}")
print(f"  Mean S_pre: {mc_result.mean_s_pre:.4f} (std={mc_result.std_s_pre:.4f})")
print(f"  Elapsed: {elapsed:.1f}s")

# ---------------------------------------------------------------------------
# Step 4: Compare pass rates across violation magnitudes
# ---------------------------------------------------------------------------
print("\n" + "-" * 70)
print("Step 4: Compare presets — no_violation vs small vs large")
print("-" * 70)

presets = ["no_violation", "small_violation", "large_violation"]
results: dict[str, pretest.MonteCarloResult] = {}

for preset_name in presets:
    _, preset_config = pretest.generate_did_data_from_preset(
        preset_name, n_units=200, seed=99
    )
    mc = pretest.run_monte_carlo_coverage(
        preset_config,
        threshold_m=0.5,
        replications=30,
        simulations=500,
        seed=99,
    )
    results[preset_name] = mc

print(f"\n  {'Preset':<20} {'Pass Rate':>10} {'Cond. Coverage':>16} {'Mean S_pre':>12}")
print("  " + "-" * 60)
for name, mc in results.items():
    cov = f"{mc.conditional_coverage:.2%}" if mc.conditional_coverage is not None else "N/A"
    print(f"  {name:<20} {mc.pass_rate:>10.2%} {cov:>16} {mc.mean_s_pre:>12.4f}")

# ---------------------------------------------------------------------------
# Step 5: Custom DGP configuration
# ---------------------------------------------------------------------------
print("\n" + "-" * 70)
print("Step 5: Custom DGP with user-specified violation path")
print("-" * 70)

custom_config = pretest.DGPConfig(
    n_units=100,
    t_pre=4,
    t_post=2,
    true_effect=2.0,
    violation_path=(0.1, -0.05, 0.2),
    sigma_epsilon=0.8,
    seed=777,
)

print(f"  n_units={custom_config.n_units}, t_pre={custom_config.t_pre}")
print(f"  true_effect={custom_config.true_effect}")
print(f"  violation_path={custom_config.violation_path}")
print(f"  true_severity={custom_config.true_severity:.4f}")

cov_matrix = pretest.compute_true_covariance(custom_config)
dim = len(cov_matrix)
print(f"  True covariance: {dim}x{dim} diagonal, value={cov_matrix[0][0]:.4f}")

print("\n" + "=" * 70)
print("  Monte Carlo simulation tutorial complete!")
print("=" * 70)


if __name__ == "__main__":
    pass
