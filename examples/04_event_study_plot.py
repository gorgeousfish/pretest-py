"""04_event_study_plot.py - Event study plot customization showcase.

This script demonstrates the full range of plotting capabilities in
pretest, including:
    1. Basic usage with minimal arguments
    2. Custom colors and marker styles
    3. Toggling reference lines
    4. Custom titles and labels
    5. Subplot layouts (iterative vs. overall comparison)
    6. Multi-format export (PNG, PDF)
    7. Integration with matplotlib (annotations, axis adjustments)

Requirements:
    pip install pretest-did[data] matplotlib
"""

from __future__ import annotations

import sys
from pathlib import Path

print("=" * 70)
print("  Event Study Plot Customization Showcase")
print("=" * 70)

try:
    import pandas as pd
except ImportError:
    print("\nERROR: pandas required. Install with: pip install pretest-did[data]")
    sys.exit(1)

try:
    import matplotlib
    matplotlib.use("Agg")  # non-interactive backend for script use
    import matplotlib.pyplot as plt
except ImportError:
    print("\nERROR: matplotlib required. Install with: pip install matplotlib")
    sys.exit(1)

import pretest
from pretest import (
    compute_pretest_snapshot_from_records,
    load_prop99_window_iter_records_from_csv,
)
from pretest.plotting import extract_plot_data, plot_event_study
from pretest.covariance import compute_influence_matrix, compute_standard_covariance

print(f"\nUsing pretest version: {pretest.__version__}")

output_dir = Path(__file__).parent / "output"
output_dir.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Load Prop99 data and prepare vectors for plotting
# ---------------------------------------------------------------------------

csv_path = (
    Path(pretest.__file__).parent
    / "data" / "prop99_replay"
    / "prop99_window_1985_1995_m5_iter_records.csv"
)
records = load_prop99_window_iter_records_from_csv(str(csv_path))

# Compute vectors
years_sorted = sorted({int(r["year"]) for r in records})
time_to_index = {y: i + 1 for i, y in enumerate(years_sorted)}
T = len(years_sorted)
treat_time_index = time_to_index[1989]

outcomes = [r["cigsale"] for r in records]
treatments = [int(r["treated"]) for r in records]
time_indices = [time_to_index[int(r["year"])] for r in records]
n = len(records)

grouped: dict[tuple[int, int], list[float]] = {}
for i in range(n):
    key = (time_indices[i], treatments[i])
    grouped.setdefault(key, []).append(outcomes[i])
means = {k: sum(v) / len(v) for k, v in grouped.items()}

nu_vector = [(means[(t, 1)] - means[(t-1, 1)]) - (means[(t, 0)] - means[(t-1, 0)])
             for t in range(2, treat_time_index)]
delta_vector = [((means[(t, 1)] - means[(treat_time_index, 1)])
                 - (means[(t, 0)] - means[(treat_time_index, 0)]))
                for t in range(treat_time_index, T + 1)]

influence_mat = compute_influence_matrix(
    outcomes, treatments, time_indices,
    treatment_time_index=treat_time_index,
    time_period_count=T,
)
cov_matrix = compute_standard_covariance(influence_mat)

# Compute snapshots
snapshot_iter = compute_pretest_snapshot_from_records(
    records, outcome="cigsale", treatment="treated", time="year",
    treat_time=1989, threshold_m=5, p_norm=2, mode="iterative",
    alpha=0.05, simulations=5000, seed=12345,
)
snapshot_overall = compute_pretest_snapshot_from_records(
    records, outcome="cigsale", treatment="treated", time="year",
    treat_time=1989, threshold_m=5, p_norm=2, mode="overall",
    alpha=0.05, simulations=5000, seed=12345,
)

print("\nData prepared. Generating plots...\n")

# ===========================================================================
# Plot 1: Basic usage (minimal arguments)
# ===========================================================================
print("1. Basic event study plot...")

ax = plot_event_study(
    snapshot_iter, nu_vector, delta_vector, cov_matrix, n,
    save_path=str(output_dir / "04_basic.png"),
)
plt.close()
print(f"   Saved: {output_dir / '04_basic.png'}")

# ===========================================================================
# Plot 2: Custom colors and marker styles
# ===========================================================================
print("2. Custom colors and markers...")

ax = plot_event_study(
    snapshot_iter, nu_vector, delta_vector, cov_matrix, n,
    title="Custom Styling Example",
    pre_color="darkgreen",
    post_color_pass="darkred",
    threshold_color="purple",
    marker_pre="s",          # square markers for pre-treatment
    marker_post_pass="D",    # diamond markers for post-treatment
    marker_size=10,
    ci_linewidth=2.5,
    ci_capsize=6.0,
    save_path=str(output_dir / "04_custom_style.png"),
)
plt.close()
print(f"   Saved: {output_dir / '04_custom_style.png'}")

# ===========================================================================
# Plot 3: Toggle reference lines on/off
# ===========================================================================
print("3. Toggling reference lines...")

ax = plot_event_study(
    snapshot_iter, nu_vector, delta_vector, cov_matrix, n,
    title="No Reference Lines",
    show_zero_line=False,
    show_treatment_line=False,
    show_threshold=False,
    show_att_comparison=False,
    show_note=False,
    save_path=str(output_dir / "04_no_reflines.png"),
)
plt.close()
print(f"   Saved: {output_dir / '04_no_reflines.png'}")

# ===========================================================================
# Plot 4: Custom title and labels
# ===========================================================================
print("4. Custom title and axis labels...")

ax = plot_event_study(
    snapshot_iter, nu_vector, delta_vector, cov_matrix, n,
    title="California Prop 99: Cigarette Sales",
    xlabel="Year relative to 1989",
    ylabel="Per-capita sales difference",
    figsize=(12, 7),
    dpi=200,
    save_path=str(output_dir / "04_custom_labels.png"),
)
plt.close()
print(f"   Saved: {output_dir / '04_custom_labels.png'}")

# ===========================================================================
# Plot 5: Subplot layout (iterative vs. overall)
# ===========================================================================
print("5. Subplot layout: Iterative vs. Overall...")

fig, axes = plt.subplots(2, 1, figsize=(10, 10))

# Iterative mode in top panel
plot_event_study(
    snapshot_iter, nu_vector, delta_vector, cov_matrix, n,
    title="Iterative Mode (period-by-period violations)",
    ax=axes[0],
)

# Overall mode in bottom panel
plot_event_study(
    snapshot_overall, nu_vector, delta_vector, cov_matrix, n,
    title="Overall Mode (cumulative violations)",
    ax=axes[1],
    pre_color="darkgreen",
    post_color_pass="darkblue",
    threshold_color="red",
)

fig.suptitle("Prop99: Iterative vs. Overall Comparison", fontsize=14, y=1.01)
fig.tight_layout()
save_path = output_dir / "04_subplot_comparison.png"
fig.savefig(str(save_path), dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"   Saved: {save_path}")

# ===========================================================================
# Plot 6: Multi-format export (PNG + PDF)
# ===========================================================================
print("6. Multi-format export (PNG + PDF)...")

# PNG export
ax = plot_event_study(
    snapshot_iter, nu_vector, delta_vector, cov_matrix, n,
    title="Publication-Quality Export",
    save_path=str(output_dir / "04_export.png"),
    dpi=300,
)
plt.close()
print(f"   Saved: {output_dir / '04_export.png'} (300 DPI)")

# PDF export
fig, ax = plt.subplots(figsize=(10, 6))
plot_event_study(
    snapshot_iter, nu_vector, delta_vector, cov_matrix, n,
    title="Publication-Quality Export (PDF)",
    ax=ax,
)
fig.savefig(str(output_dir / "04_export.pdf"), bbox_inches="tight")
plt.close(fig)
print(f"   Saved: {output_dir / '04_export.pdf'}")

# ===========================================================================
# Plot 7: Custom annotations and axis adjustments
# ===========================================================================
print("7. Custom matplotlib annotations...")

fig, ax = plt.subplots(figsize=(11, 6.5))
plot_event_study(
    snapshot_iter, nu_vector, delta_vector, cov_matrix, n,
    title="Annotated Event Study",
    ax=ax,
    show_note=False,  # We'll add our own annotations
)

# Add custom annotation: highlight treatment period
ax.axvspan(-0.5, max(range(T - treat_time_index + 1)) + 0.5,
           alpha=0.05, color="blue", label="Post-treatment")

# Add text annotation
summary = snapshot_iter.reporting_summary()
ax.annotate(
    f"Pre-test: {summary['decision']}\n"
    f"S_pre = {summary['S_pre']:.3f}\n"
    f"ATT = {summary['delta_bar']:.2f}",
    xy=(0.02, 0.98),
    xycoords="axes fraction",
    verticalalignment="top",
    fontsize=10,
    bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", alpha=0.8),
)

# Adjust axis limits for better readability
ax.set_xlim(-4.5, 8.5)
ax.legend(loc="lower right", fontsize=9)

fig.tight_layout()
save_path = output_dir / "04_annotated.png"
fig.savefig(str(save_path), dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"   Saved: {save_path}")

# ===========================================================================
# Summary
# ===========================================================================
print("\n" + "=" * 70)
print("  Plot customization showcase complete!")
print(f"  All figures saved to: {output_dir}")
print("=" * 70)
