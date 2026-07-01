"""02_prop99_replication.py - Replicate the paper's Proposition 99 case study.

This script replicates the Prop 99 (California tobacco control) results
from Mikhaeil & Harshaw (2026), demonstrating both iterative and overall
modes using the packaged dataset.

The Prop99 window case (1985-1995, M=5) is the paper's primary empirical
illustration of the conditional extrapolation pre-test framework.

Requirements:
    pip install pretest-did[data] matplotlib
"""

from __future__ import annotations

import sys
from pathlib import Path

print("=" * 70)
print("  Prop99 Replication: California Tobacco Control Program")
print("  Window 1985-1995, Threshold M = 5")
print("=" * 70)

import pretest
from pretest import (
    compute_pretest_snapshot_from_records,
    load_prop99_window_iter_records_from_csv,
)

print(f"\nUsing pretest version: {pretest.__version__}")

# ---------------------------------------------------------------------------
# Step 1: Load packaged Prop99 records
# ---------------------------------------------------------------------------
# The dataset contains per-capita cigarette sales (cigsale) for California
# (treated, state that implemented Prop99 in 1989) and 38 control states.
# Window: 1985-1995, giving T_pre=4 and T_post=7.
# ---------------------------------------------------------------------------

print("\n" + "-" * 70)
print("Loading Prop99 window records...")
print("-" * 70)

# Load from the packaged CSV shipped with pretest
csv_path = (
    Path(pretest.__file__).parent
    / "data" / "prop99_replay"
    / "prop99_window_1985_1995_m5_iter_records.csv"
)
records = load_prop99_window_iter_records_from_csv(str(csv_path))

years = sorted({r["year"] for r in records})
n_treated = sum(1 for r in records if r["treated"] == 1)
n_control = sum(1 for r in records if r["treated"] == 0)
print(f"  Records loaded: {len(records)}")
print(f"  Years: {[int(y) for y in years]}")
print(f"  Treated obs: {n_treated}, Control obs: {n_control}")
print(f"  Treatment year: 1989 (first post-treatment period)")

# ---------------------------------------------------------------------------
# Step 2: Compute iterative mode snapshot
# ---------------------------------------------------------------------------
# Iterative mode: S_pre = (mean(|nu_t|^p))^{1/p} where nu_t are period-by-
# period DID violations of parallel trends (Section 2.1).
# ---------------------------------------------------------------------------

print("\n" + "-" * 70)
print("Computing ITERATIVE mode results...")
print("-" * 70)

snapshot_iter = compute_pretest_snapshot_from_records(
    records,
    outcome="cigsale",
    treatment="treated",
    time="year",
    treat_time=1989,
    threshold_m=5,
    p_norm=2,
    mode="iterative",
    alpha=0.05,
    simulations=5000,
    seed=12345,
)

summary_iter = snapshot_iter.reporting_summary()
print(f"\n  {'Field':<28} {'Value'}")
print(f"  {'-'*48}")
print(f"  {'Decision':<28} {summary_iter['decision']}")
print(f"  {'S_pre':<28} {summary_iter['S_pre']:.6f}")
print(f"  {'Threshold M':<28} {summary_iter['threshold']:.1f}")
print(f"  {'delta_bar':<28} {summary_iter['delta_bar']:.6f}")
print(f"  {'f_alpha':<28} {summary_iter['f_alpha']:.6f}")
print(f"  {'Conditional CI':<28} {summary_iter['conditional_interval']}")
print(f"  {'Conventional CI':<28} {summary_iter['conventional_interval']}")

# ---------------------------------------------------------------------------
# Step 3: Compute overall mode snapshot
# ---------------------------------------------------------------------------
# Overall mode: S_pre = max(|nu_bar_t|) where nu_bar_t = sum_{s=2}^t nu_s
# is the cumulative violation (Appendix C). Kappa = 1 in overall mode.
# ---------------------------------------------------------------------------

print("\n" + "-" * 70)
print("Computing OVERALL mode results...")
print("-" * 70)

snapshot_overall = compute_pretest_snapshot_from_records(
    records,
    outcome="cigsale",
    treatment="treated",
    time="year",
    treat_time=1989,
    threshold_m=5,
    p_norm=2,
    mode="overall",
    alpha=0.05,
    simulations=5000,
    seed=12345,
)

summary_overall = snapshot_overall.reporting_summary()
print(f"\n  {'Field':<28} {'Value'}")
print(f"  {'-'*48}")
print(f"  {'Decision':<28} {summary_overall['decision']}")
print(f"  {'S_pre':<28} {summary_overall['S_pre']:.6f}")
print(f"  {'Threshold M':<28} {summary_overall['threshold']:.1f}")
print(f"  {'delta_bar':<28} {summary_overall['delta_bar']:.6f}")
print(f"  {'f_alpha':<28} {summary_overall['f_alpha']:.6f}")
print(f"  {'Conditional CI':<28} {summary_overall['conditional_interval']}")
print(f"  {'Conventional CI':<28} {summary_overall['conventional_interval']}")

# ---------------------------------------------------------------------------
# Step 4: Side-by-side comparison
# ---------------------------------------------------------------------------

print("\n" + "-" * 70)
print("COMPARISON: Iterative vs. Overall")
print("-" * 70)
print(f"\n  {'Metric':<24} {'Iterative':<18} {'Overall'}")
print(f"  {'-'*60}")
print(f"  {'Decision':<24} {summary_iter['decision']:<18} {summary_overall['decision']}")
print(f"  {'S_pre':<24} {summary_iter['S_pre']:<18.6f} {summary_overall['S_pre']:.6f}")
print(f"  {'f_alpha':<24} {summary_iter['f_alpha']:<18.6f} {summary_overall['f_alpha']:.6f}")
print(f"  {'delta_bar':<24} {summary_iter['delta_bar']:<18.6f} {summary_overall['delta_bar']:.6f}")

# Extract kappa from stored scalars
kappa_iter = snapshot_iter.canonical["scalars"].get("kappa", "N/A")
kappa_overall = snapshot_overall.canonical["scalars"].get("kappa", "N/A")
print(f"  {'kappa':<24} {kappa_iter:<18} {kappa_overall}")

# ---------------------------------------------------------------------------
# Step 5: Print stored results table
# ---------------------------------------------------------------------------

print("\n" + "-" * 70)
print("Complete Stored Results (Iterative)")
print("-" * 70)
scalars = snapshot_iter.canonical["scalars"]
macros = snapshot_iter.canonical["macros"]
print(f"\n  {'Scalar':<20} {'Value'}")
print(f"  {'-'*40}")
for key in sorted(scalars.keys()):
    val = scalars[key]
    if isinstance(val, float):
        print(f"  {key:<20} {val:.6f}")
    else:
        print(f"  {key:<20} {val}")

print(f"\n  {'Macro':<20} {'Value'}")
print(f"  {'-'*40}")
for key in sorted(macros.keys()):
    print(f"  {key:<20} {macros[key]}")

# ---------------------------------------------------------------------------
# Step 6: Generate event study plots for both modes
# ---------------------------------------------------------------------------

print("\n" + "-" * 70)
print("Generating event study plots...")
print("-" * 70)

output_dir = Path(__file__).parent / "output"
output_dir.mkdir(exist_ok=True)

try:
    from pretest.plotting import extract_plot_data, plot_event_study
    from pretest.covariance import (
        compute_influence_matrix,
        compute_standard_covariance,
    )

    # Re-derive vectors needed for plotting
    years_sorted = sorted({int(r["year"]) for r in records})
    time_to_index = {y: i + 1 for i, y in enumerate(years_sorted)}
    T = len(years_sorted)
    treat_time_index = time_to_index[1989]

    outcomes = [r["cigsale"] for r in records]
    treatments = [int(r["treated"]) for r in records]
    time_indices = [time_to_index[int(r["year"])] for r in records]
    n = len(records)

    # Group means
    grouped: dict[tuple[int, int], list[float]] = {}
    for i in range(n):
        key = (time_indices[i], treatments[i])
        grouped.setdefault(key, []).append(outcomes[i])
    means = {k: sum(v) / len(v) for k, v in grouped.items()}

    # nu_vector (iterative violations)
    nu_vector = []
    for t in range(2, treat_time_index):
        nu_t = (means[(t, 1)] - means[(t-1, 1)]) - (means[(t, 0)] - means[(t-1, 0)])
        nu_vector.append(nu_t)

    # delta_vector (DID estimates)
    delta_vector = []
    for t in range(treat_time_index, T + 1):
        delta_t = (
            (means[(t, 1)] - means[(treat_time_index, 1)])
            - (means[(t, 0)] - means[(treat_time_index, 0)])
        )
        delta_vector.append(delta_t)

    # Covariance matrix
    influence_mat = compute_influence_matrix(
        outcomes, treatments, time_indices,
        treatment_time_index=treat_time_index,
        time_period_count=T,
    )
    cov_matrix = compute_standard_covariance(influence_mat)

    import matplotlib.pyplot as plt

    # Plot iterative mode
    fig, axes = plt.subplots(2, 1, figsize=(10, 10))

    plot_event_study(
        snapshot_iter, nu_vector, delta_vector, cov_matrix, n,
        title="Prop99 Event Study — Iterative Mode (M=5)",
        ax=axes[0],
    )

    plot_event_study(
        snapshot_overall, nu_vector, delta_vector, cov_matrix, n,
        title="Prop99 Event Study — Overall Mode (M=5)",
        ax=axes[1],
    )

    fig.tight_layout()
    save_path = output_dir / "02_prop99_event_study.png"
    fig.savefig(str(save_path), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {save_path}")

except ImportError:
    print("  matplotlib not available; skipping plot generation.")
    print("  Install with: pip install matplotlib")
except Exception as e:
    print(f"  Plot generation failed: {e}")

print("\n" + "=" * 70)
print("  Prop99 replication complete!")
print("=" * 70)
