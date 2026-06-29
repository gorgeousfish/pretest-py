"""01_quickstart.py - Minimal working example of the pretest package.

This script demonstrates the simplest possible usage of the conditional
extrapolation pre-test framework (Mikhaeil & Harshaw, 2026). It creates
a synthetic DID dataset, runs the pre-test, and interprets the results.

Requirements:
    pip install pretest[data] matplotlib
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Step 1: Create a simple synthetic DID dataset
# ---------------------------------------------------------------------------
# We simulate a panel with:
#   - 5 time periods (t=1,...,5), treatment occurs at t=4
#   - 20 units in each group (treated and control)
#   - Parallel trends hold in pre-treatment periods (small random noise)
#   - A positive treatment effect of +3 units in post-treatment
# ---------------------------------------------------------------------------

print("=" * 70)
print("  pretest Quickstart: Conditional Extrapolation Pre-Test")
print("=" * 70)

try:
    import pandas as pd
except ImportError:
    print("\nERROR: pandas is required. Install with: pip install pretest[data]")
    sys.exit(1)

import pretest

print(f"\nUsing pretest version: {pretest.__version__}")

# Build synthetic data: 5 periods, treatment at period 4
# Pre-treatment: Y_control grows by +1 per period, Y_treated grows by +1 per period
# (parallel trends satisfied). Post-treatment: treated jumps by +3 (the ATT).
rows = []
n_per_group = 20
base_control = [10, 11, 12, 13, 14]    # control group trend
base_treated = [15, 16, 17, 21, 22]    # treated: same trend pre, +3 ATT post

for unit_id in range(n_per_group):
    for t, (yc, yt) in enumerate(zip(base_control, base_treated), start=1):
        # Add small unit-level noise (deterministic for reproducibility)
        noise_c = 0.1 * ((unit_id * 7 + t * 3) % 5 - 2)
        noise_t = 0.1 * ((unit_id * 11 + t * 5) % 5 - 2)
        rows.append({"unit": unit_id, "year": 2000 + t, "y": yc + noise_c, "treated": 0})
        rows.append({"unit": unit_id + n_per_group, "year": 2000 + t,
                     "y": yt + noise_t, "treated": 1})

df = pd.DataFrame(rows)
print(f"\nDataset: {len(df)} observations, "
      f"{df['year'].nunique()} periods, "
      f"treatment at year 2004")
print(f"  Periods: {sorted(df['year'].unique())}")
print(f"  Groups: control={len(df[df['treated']==0])//5} units, "
      f"treated={len(df[df['treated']==1])//5} units")

# ---------------------------------------------------------------------------
# Step 2: Run the pre-test using pretest_from_dataframe()
# ---------------------------------------------------------------------------
# Key parameters:
#   - threshold (M): acceptable violation bound. Larger M = more tolerant.
#   - p: norm for aggregating violations (p=2 = Euclidean mean)
#   - alpha: significance level for the conditional CI
#   - mode: 'iterative' (default) or 'overall'
# ---------------------------------------------------------------------------

print("\n" + "-" * 70)
print("Running pre-test with threshold M = 5.0, alpha = 0.05, p = 2")
print("-" * 70)

snapshot = pretest.pretest_from_dataframe(
    df,
    outcome="y",
    treatment="treated",
    time="year",
    threshold=5.0,
    treat_time=2004,
    p=2.0,
    alpha=0.05,
    mode="iterative",
    simulations=5000,
    seed=12345,
)

# ---------------------------------------------------------------------------
# Step 3: Interpret the results
# ---------------------------------------------------------------------------
summary = snapshot.reporting_summary()

print(f"\n{'Result Field':<28} {'Value'}")
print("-" * 50)
print(f"{'Decision':<28} {summary['decision']}")
print(f"{'S_pre (severity)':<28} {summary['S_pre']:.6f}")
print(f"{'Threshold M':<28} {summary['threshold']:.6f}")
print(f"{'delta_bar (avg ATT)':<28} {summary['delta_bar']:.6f}")
print(f"{'f_alpha (critical value)':<28} {summary['f_alpha']:.6f}")
print(f"{'Conditional CI':<28} {summary['conditional_interval']}")
print(f"{'Conventional CI':<28} {summary['conventional_interval']}")

print("\n" + "-" * 70)
print("Interpretation:")
print("-" * 70)
if summary["decision"] == "PASS":
    print("  The pre-test PASSES: S_pre <= M, so parallel trends violations")
    print("  are within the acceptable bound. The conditional confidence interval")
    print("  is valid and accounts for the pre-testing step.")
    print(f"  Estimated average ATT = {summary['delta_bar']:.4f}")
    ci = summary["conditional_interval"]
    if ci and ci[0] is not None:
        print(f"  Conditional 95% CI: [{ci[0]:.4f}, {ci[1]:.4f}]")
else:
    print("  The pre-test FAILS: S_pre > M, violations exceed the threshold.")
    print("  The conditional CI is not available; consider using a larger M")
    print("  or investigating the source of pre-trend violations.")

# ---------------------------------------------------------------------------
# Step 4: Generate an event study plot
# ---------------------------------------------------------------------------
print("\n" + "-" * 70)
print("Generating event study plot...")
print("-" * 70)

output_dir = Path(__file__).parent / "output"
output_dir.mkdir(exist_ok=True)

try:
    from pretest.plotting import plot_event_study_from_dataframe

    ax = plot_event_study_from_dataframe(
        df,
        outcome="y",
        treatment="treated",
        time="year",
        threshold=5.0,
        treat_time=2004,
        title="Quickstart: Synthetic DID Event Study",
        save_path=str(output_dir / "01_quickstart_event_study.png"),
        dpi=150,
    )
    print(f"  Saved: {output_dir / '01_quickstart_event_study.png'}")
except ImportError:
    print("  matplotlib not available; skipping plot generation.")
    print("  Install with: pip install matplotlib")
except Exception as e:
    print(f"  Plot generation failed: {e}")

print("\n" + "=" * 70)
print("  Quickstart complete!")
print("=" * 70)
