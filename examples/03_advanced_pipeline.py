"""03_advanced_pipeline.py - Step-by-step low-level API demonstration.

This script demonstrates the full internal pipeline of the conditional
extrapolation pre-test framework, exposing each computational step.
Intended for advanced users and researchers who want to understand
the inner mechanics or integrate external DID estimators.

Steps covered:
    1. Data creation and group mean computation
    2. Manual nu_vector and delta_vector construction
    3. Influence function matrix construction
    4. Standard vs. cluster-robust covariance estimation
    5. Severity S_pre computation
    6. Delta Method SE for severity
    7. Pre-test decision (classify_pretest)
    8. Kappa factor computation
    9. Monte Carlo critical value simulation
    10. Conditional CI half-width
    11. Integration with external DID tools (e.g., PyFixest)

Requirements:
    pip install pretest[data]
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

print("=" * 70)
print("  Advanced Pipeline: Step-by-Step Low-Level API")
print("=" * 70)

try:
    import pandas as pd
except ImportError:
    print("\nERROR: pandas required. Install with: pip install pretest[data]")
    sys.exit(1)

import pretest
from pretest import (
    classify_pretest,
    compute_ci_half_width,
    compute_cluster_robust_covariance,
    compute_critical_value,
    compute_influence_matrix,
    compute_kappa,
    compute_severity,
    compute_severity_se,
    compute_standard_covariance,
    extract_nu_covariance,
)

print(f"\nUsing pretest version: {pretest.__version__}")

# ===========================================================================
# Step 1: Create data and compute group means
# ===========================================================================
print("\n" + "=" * 70)
print("STEP 1: Create panel data and compute group-time means")
print("=" * 70)

# 4 pre-treatment periods + 3 post-treatment periods = 7 total
# Treatment at period 5 (index). 30 units per group.
n_per_group = 30
T = 7
treat_time_index = 5  # 1-indexed: periods 1-4 are pre, 5-7 are post
T_pre = treat_time_index - 1  # = 4
T_post = T - T_pre  # = 3

rows = []
for unit in range(n_per_group):
    for t in range(1, T + 1):
        # Control: linear trend with noise
        yc = 5.0 + 2.0 * t + 0.3 * ((unit * 7 + t) % 5 - 2)
        # Treated: same trend pre-treatment + ATT=4 post-treatment
        att = 4.0 if t >= treat_time_index else 0.0
        yt = 8.0 + 2.0 * t + att + 0.3 * ((unit * 11 + t * 3) % 5 - 2)
        rows.append({"y": yc, "treated": 0, "time": t, "cluster": unit})
        rows.append({"y": yt, "treated": 1, "time": t, "cluster": unit + n_per_group})

df = pd.DataFrame(rows)
n = len(df)
print(f"  Dataset: n={n}, T={T}, T_pre={T_pre}, T_post={T_post}")

# Compute group means manually
outcomes_arr = list(df["y"])
treatments_arr = [int(x) for x in df["treated"]]
time_indices_arr = list(df["time"])

grouped: dict[tuple[int, int], list[float]] = {}
for i in range(n):
    key = (time_indices_arr[i], treatments_arr[i])
    grouped.setdefault(key, []).append(outcomes_arr[i])

means = {k: sum(v) / len(v) for k, v in grouped.items()}
print("  Group-time means (period, group) -> mean:")
for t in range(1, T + 1):
    print(f"    t={t}: control={means[(t,0)]:.4f}, treated={means[(t,1)]:.4f}")

# ===========================================================================
# Step 2: Compute nu_vector and delta_vector
# ===========================================================================
print("\n" + "=" * 70)
print("STEP 2: Compute iterative violations nu_t and DID estimates delta_t")
print("=" * 70)

# nu_t = (Y_bar_{t,1} - Y_bar_{t-1,1}) - (Y_bar_{t,0} - Y_bar_{t-1,0})
# for t = 2, ..., t0-1 (pre-treatment differencing violations)
nu_vector: list[float] = []
for t in range(2, treat_time_index):
    nu_t = (means[(t, 1)] - means[(t-1, 1)]) - (means[(t, 0)] - means[(t-1, 0)])
    nu_vector.append(nu_t)
    print(f"  nu_{t} = {nu_t:.6f}")

# delta_t = (Y_bar_{t,1} - Y_bar_{t0,1}) - (Y_bar_{t,0} - Y_bar_{t0,0})
# for t = t0, ..., T (post-treatment DID estimates)
delta_vector: list[float] = []
for t in range(treat_time_index, T + 1):
    delta_t = (
        (means[(t, 1)] - means[(treat_time_index, 1)])
        - (means[(t, 0)] - means[(treat_time_index, 0)])
    )
    delta_vector.append(delta_t)
    print(f"  delta_{t} = {delta_t:.6f}")

delta_bar = sum(delta_vector) / len(delta_vector)
print(f"\n  delta_bar (average ATT) = {delta_bar:.6f}")

# ===========================================================================
# Step 3: Compute influence function matrix
# ===========================================================================
print("\n" + "=" * 70)
print("STEP 3: Build influence function matrix (n x (T-1))")
print("=" * 70)

influence_mat = compute_influence_matrix(
    outcomes_arr,
    treatments_arr,
    time_indices_arr,
    treatment_time_index=treat_time_index,
    time_period_count=T,
)
print(f"  Influence matrix dimension: {len(influence_mat)} x {len(influence_mat[0])}")
print(f"  (n={len(influence_mat)}, T-1={len(influence_mat[0])})")

# ===========================================================================
# Step 4: Covariance estimation (standard vs. cluster-robust)
# ===========================================================================
print("\n" + "=" * 70)
print("STEP 4: Covariance estimation")
print("=" * 70)

# Standard (iid) covariance: Sigma = (1/(n-1)) * Psi' * Psi
cov_standard = compute_standard_covariance(influence_mat)
print(f"\n  Standard covariance (diagonal):")
for i in range(len(cov_standard)):
    print(f"    Sigma[{i},{i}] = {cov_standard[i][i]:.6f}")

# Cluster-robust covariance
cluster_ids = list(df["cluster"])
cov_cluster = compute_cluster_robust_covariance(influence_mat, cluster_ids)
print(f"\n  Cluster-robust covariance (diagonal):")
for i in range(len(cov_cluster)):
    print(f"    Sigma_cl[{i},{i}] = {cov_cluster[i][i]:.6f}")

# ===========================================================================
# Step 5: Extract nu-block and compute severity
# ===========================================================================
print("\n" + "=" * 70)
print("STEP 5: Extract Sigma_nu and compute severity S_pre")
print("=" * 70)

pre_term_count = T_pre - 1  # number of nu terms
sigma_nu = extract_nu_covariance(cov_standard, pre_term_count)
print(f"  Sigma_nu dimension: {len(sigma_nu)} x {len(sigma_nu[0])}")

# Severity: S_pre = (mean(|nu_t|^p))^{1/p} with p=2
s_pre = compute_severity(nu_vector=tuple(nu_vector), p_norm=2.0, mode="iterative")
print(f"  S_pre (p=2, iterative) = {s_pre:.6f}")

# Compare with other p-norms
s_pre_p1 = compute_severity(nu_vector=tuple(nu_vector), p_norm=1.0, mode="iterative")
s_pre_pinf = compute_severity(nu_vector=tuple(nu_vector), p_norm=math.inf, mode="iterative")
print(f"  S_pre (p=1, mean abs) = {s_pre_p1:.6f}")
print(f"  S_pre (p=inf, max abs) = {s_pre_pinf:.6f}")

# ===========================================================================
# Step 6: Delta Method SE for severity
# ===========================================================================
print("\n" + "=" * 70)
print("STEP 6: Compute SE(S_pre) via Delta Method")
print("=" * 70)

s_pre_se = compute_severity_se(
    tuple(nu_vector),
    sigma_nu,
    p_norm=2.0,
    mode="iterative",
)
print(f"  SE(S_pre) = {s_pre_se:.6f}" if s_pre_se is not None else "  SE(S_pre) = None (p=inf)")

# ===========================================================================
# Step 7: Pre-test decision
# ===========================================================================
print("\n" + "=" * 70)
print("STEP 7: Classify pre-test decision (phi = 1{S_pre > M})")
print("=" * 70)

M = 5.0  # threshold
decision = classify_pretest(s_pre_hat=s_pre, threshold_m=M)
print(f"  S_pre = {decision.s_pre_hat:.6f}")
print(f"  M     = {decision.threshold_m:.6f}")
print(f"  phi   = {decision.phi}  (1 = reject parallel trends)")
print(f"  pass  = {decision.pretest_pass}  (1 = trends acceptable)")

# ===========================================================================
# Step 8: Kappa factor
# ===========================================================================
print("\n" + "=" * 70)
print("STEP 8: Compute kappa factor")
print("=" * 70)

kappa = compute_kappa(t_post=T_post, p_norm=2.0, mode="iterative")
print(f"  kappa (T_post={T_post}, p=2, iterative) = {kappa:.6f}")

kappa_overall = compute_kappa(t_post=T_post, p_norm=2.0, mode="overall")
print(f"  kappa (T_post={T_post}, p=2, overall)   = {kappa_overall:.6f}")
print("  Note: kappa = 1 in overall mode by construction.")

# ===========================================================================
# Step 9: Monte Carlo critical value
# ===========================================================================
print("\n" + "=" * 70)
print("STEP 9: Monte Carlo critical value f(alpha, Sigma)")
print("=" * 70)

f_alpha = compute_critical_value(
    cov_standard,
    alpha=0.05,
    simulations=5000,
    t_pre=T_pre,
    t_post=T_post,
    p_norm=2.0,
    mode="iterative",
    kappa=kappa,
    seed=12345,
    covariance_form="iterative",
)
print(f"  f_alpha (alpha=0.05, sims=5000) = {f_alpha:.6f}")
print("  This is the conditional critical value from Theorem 2.")

# ===========================================================================
# Step 10: Confidence interval half-width
# ===========================================================================
print("\n" + "=" * 70)
print("STEP 10: Conditional CI half-width")
print("=" * 70)

ci_half = compute_ci_half_width(
    mode="iterative",
    s_pre_hat=s_pre,
    kappa=kappa,
    f_alpha=f_alpha,
    n=n,
)
print(f"  CI half-width = {ci_half:.6f}")
print(f"  Conditional CI = [{delta_bar - ci_half:.4f}, {delta_bar + ci_half:.4f}]")
print(f"  (Centered on delta_bar = {delta_bar:.4f})")

# ===========================================================================
# Step 11: Integration with external DID tools
# ===========================================================================
print("\n" + "=" * 70)
print("STEP 11: External DID tool integration (concept)")
print("=" * 70)
print("""
  If you have coefficient estimates from PyFixest, linearmodels, or other
  DID tools, you can feed them directly into the pretest pipeline:

  Example with PyFixest (pseudo-code):
  -------------------------------------
  import pyfixest as pf

  # Estimate event-study model
  model = pf.feols("y ~ i(time, treated, ref=4) | unit + time", data=df)
  coefficients = model.coef()     # event-study coefficients
  vcov_matrix = model.vcov()      # variance-covariance matrix

  # Split into pre/post
  nu_vector = coefficients[:T_pre-1]   # pre-treatment coefficients
  delta_vector = coefficients[T_pre-1:]  # post-treatment coefficients

  # Feed into pretest severity and decision
  s_pre = compute_severity(nu_vector=nu_vector, p_norm=2.0, mode="iterative")
  decision = classify_pretest(s_pre_hat=s_pre, threshold_m=M)

  # Then compute conditional CI as above (Steps 8-10)
""")

print("=" * 70)
print("  Advanced pipeline demo complete!")
print("=" * 70)
