"""Covariance estimation for the conditional extrapolation pre-test framework.

Implements influence-function-based asymptotic covariance estimation for the
parameter vector theta = (nu_2, ..., nu_{t0-1}, delta_{t0}, ..., delta_T)
following Mikhaeil & Harshaw (2026), Section 2.3, Assumptions 1-2.

Supports:

- Standard (iid) covariance: Sigma_hat = (1/(n-1)) * Psi' * Psi
- Cluster-robust covariance (Cameron & Miller 2015):
  Sigma_hat = (G/(G-1)) * (1/n) * sum_{g=1}^G u_g * u_g'
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any


def compute_influence_matrix(
    outcomes: Sequence[float],
    treatments: Sequence[int],
    time_indices: Sequence[int],
    *,
    treatment_time_index: int,
    time_period_count: int,
) -> list[list[float]]:
    """Construct the n x (T-1) influence function matrix for theta.

    The influence function for a group-time mean Y_bar_{t,d} is:
        psi_i(Y_bar_{t,d}) = (n / n_{td}) * 1{D_i=d, t_i=t} * (Y_i - Y_bar_{t,d})

    Parameters
    ----------
    outcomes : sequence of float
        Outcome values Y_i for each observation.
    treatments : sequence of int
        Treatment indicators D_i in {0, 1}.
    time_indices : sequence of int
        Time period indices (1-indexed).
    treatment_time_index : int
        Treatment time t0 (1-indexed).
    time_period_count : int
        Total number of time periods T.

    Returns
    -------
    list[list[float]]
        Influence matrix of dimension n x (T-1).
    """
    n = len(outcomes)
    dim = time_period_count - 1
    matrix = [[0.0] * dim for _ in range(n)]

    # Pre-compute group means and counts
    grouped: dict[tuple[int, int], list[float]] = {}
    for i in range(n):
        key = (time_indices[i], treatments[i])
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(outcomes[i])

    means: dict[tuple[int, int], float] = {}
    counts: dict[tuple[int, int], int] = {}
    for key, values in grouped.items():
        means[key] = sum(values) / len(values)
        counts[key] = len(values)

    # Part 1: Influence for iterative violations nu_t (t = 2, ..., t0-1)
    col = 0
    for t in range(2, treatment_time_index):
        for i in range(n):
            d = treatments[i]
            ti = time_indices[i]
            if d == 1:
                if ti == t:
                    matrix[i][col] += (outcomes[i] - means[(t, 1)]) * n / counts[(t, 1)]
                if ti == t - 1:
                    matrix[i][col] -= (outcomes[i] - means[(t - 1, 1)]) * n / counts[(t - 1, 1)]
            else:
                if ti == t:
                    matrix[i][col] -= (outcomes[i] - means[(t, 0)]) * n / counts[(t, 0)]
                if ti == t - 1:
                    matrix[i][col] += (outcomes[i] - means[(t - 1, 0)]) * n / counts[(t - 1, 0)]
        col += 1

    # Part 2: Influence for DID estimands delta_t (t = t0, ..., T)
    ref_mean_1 = means.get((treatment_time_index, 1), 0.0)
    ref_mean_0 = means.get((treatment_time_index, 0), 0.0)
    ref_count_1 = counts.get((treatment_time_index, 1), 1)
    ref_count_0 = counts.get((treatment_time_index, 0), 1)

    for t in range(treatment_time_index, time_period_count + 1):
        mean_t_1 = means.get((t, 1), 0.0)
        mean_t_0 = means.get((t, 0), 0.0)
        count_t_1 = counts.get((t, 1), 1)
        count_t_0 = counts.get((t, 0), 1)

        for i in range(n):
            d = treatments[i]
            ti = time_indices[i]
            if d == 1:
                if ti == t:
                    matrix[i][col] += (outcomes[i] - mean_t_1) * n / count_t_1
                if ti == treatment_time_index:
                    matrix[i][col] -= (outcomes[i] - ref_mean_1) * n / ref_count_1
            else:
                if ti == t:
                    matrix[i][col] -= (outcomes[i] - mean_t_0) * n / count_t_0
                if ti == treatment_time_index:
                    matrix[i][col] += (outcomes[i] - ref_mean_0) * n / ref_count_0
        col += 1

    return matrix


def compute_standard_covariance(
    influence_matrix: list[list[float]],
) -> tuple[tuple[float, ...], ...]:
    """Compute standard (iid) covariance from influence matrix.

    Formula: Sigma_hat = (1/(n-1)) * Psi' * Psi

    Parameters
    ----------
    influence_matrix : list of list of float
        n x dim influence matrix.

    Returns
    -------
    tuple of tuple of float
        dim x dim covariance matrix.
    """
    n = len(influence_matrix)
    if n < 2:
        raise ValueError("at least two observations required for covariance estimation")
    dim = len(influence_matrix[0])
    rows: list[tuple[float, ...]] = []
    for i in range(dim):
        row: list[float] = []
        for j in range(dim):
            val = sum(influence_matrix[k][i] * influence_matrix[k][j] for k in range(n))
            row.append(val / (n - 1))
        rows.append(tuple(row))
    return tuple(rows)


def compute_cluster_robust_covariance(
    influence_matrix: list[list[float]],
    cluster_ids: Sequence[Any],
) -> tuple[tuple[float, ...], ...]:
    """Compute cluster-robust covariance (Cameron & Miller 2015).

    Formula:
        Sigma_hat = (G/(G-1)) * (1/n) * sum_{g=1}^G u_g * u_g'
        where u_g = sum_{i in cluster g} psi_i

    Parameters
    ----------
    influence_matrix : list of list of float
        n x dim influence matrix.
    cluster_ids : sequence
        Cluster identifier for each observation.

    Returns
    -------
    tuple of tuple of float
        dim x dim cluster-robust covariance matrix.
    """
    n = len(influence_matrix)
    if n < 2:
        raise ValueError("at least two observations required for covariance estimation")
    dim = len(influence_matrix[0])

    # Aggregate influence by cluster
    cluster_sums: dict[Any, list[float]] = {}
    for i in range(n):
        cid = cluster_ids[i]
        if cid not in cluster_sums:
            cluster_sums[cid] = [0.0] * dim
        for j in range(dim):
            cluster_sums[cid][j] += influence_matrix[i][j]

    G = len(cluster_sums)
    if G < 2:
        raise ValueError("at least two clusters required for cluster-robust covariance")

    # Compute outer product sum: sum_{g=1}^G u_g * u_g'
    sigma = [[0.0] * dim for _ in range(dim)]
    for u_g in cluster_sums.values():
        for i in range(dim):
            for j in range(dim):
                sigma[i][j] += u_g[i] * u_g[j]

    # Apply scaling: (G/(G-1)) * (1/n)
    scale = G / ((G - 1) * n)
    rows: list[tuple[float, ...]] = []
    for i in range(dim):
        rows.append(tuple(sigma[i][j] * scale for j in range(dim)))
    return tuple(rows)


def extract_nu_covariance(
    covariance_matrix: Sequence[Sequence[float]],
    pre_term_count: int,
) -> tuple[tuple[float, ...], ...]:
    """Extract the upper-left block Sigma_nu from the full covariance.

    Parameters
    ----------
    covariance_matrix : nested sequence of float
        Full (T-1) x (T-1) covariance matrix.
    pre_term_count : int
        Number of pre-treatment violation parameters (T_pre - 1).

    Returns
    -------
    tuple of tuple of float
        pre_term_count x pre_term_count covariance of violations.
    """
    rows: list[tuple[float, ...]] = []
    for i in range(pre_term_count):
        rows.append(tuple(covariance_matrix[i][j] for j in range(pre_term_count)))
    return tuple(rows)


def compute_delta_bar_se(
    covariance_matrix: Sequence[Sequence[float]],
    *,
    sample_size: int,
    pre_term_count: int,
    post_period_count: int,
) -> float:
    """Compute the standard error of delta_bar.

    Formula: SE(delta_bar) = sqrt(sum(Sigma_delta) / (T_post^2 * n))
    where Sigma_delta is the post-treatment block of the covariance matrix.

    Parameters
    ----------
    covariance_matrix : nested sequence of float
        Full (T-1) x (T-1) covariance matrix.
    sample_size : int
        Total number of observations n.
    pre_term_count : int
        Number of pre-treatment violation parameters (T_pre - 1).
    post_period_count : int
        Number of post-treatment periods T_post.

    Returns
    -------
    float
        Standard error of delta_bar.
    """
    dim = len(covariance_matrix)
    post_start = pre_term_count
    variance = sum(
        covariance_matrix[i][j]
        for i in range(post_start, dim)
        for j in range(post_start, dim)
    ) / (post_period_count * post_period_count * sample_size)
    if variance < -1e-12:
        raise ValueError("delta_bar variance must be nonnegative")
    return math.sqrt(max(variance, 0.0))
