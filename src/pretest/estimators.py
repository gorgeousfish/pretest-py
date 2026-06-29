"""High-level pandas DataFrame API for the conditional extrapolation pre-test.

Provides ``pretest_from_dataframe()`` as the primary user-facing function that
takes a pandas DataFrame and returns a ``PretestResultSnapshot`` with all
estimation, testing, and inference results.

This module implements:
- Complete DID estimation from panel or repeated cross-section data (Section 2.1-2.2)
- Influence-function covariance estimation (Section 2.3, Assumptions 1-2)
- Cluster-robust covariance (Cameron & Miller, 2015)
- Delta Method SE for severity (Stata parity)
- General linear estimands with user-supplied post-treatment weights (Appendix B)

Reference:
    Mikhaeil, J. M. and C. Harshaw (2026). Valid Inference when Testing
    Violations of Parallel Trends for Difference-in-Differences.
    arXiv:2510.26470.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from .covariance import (
    compute_cluster_robust_covariance,
    compute_delta_bar_se,
    compute_influence_matrix,
    compute_standard_covariance,
    extract_nu_covariance,
)
from .kappa import compute_kappa
from .pipeline import compute_pretest_snapshot
from .result_schema import PretestResultSnapshot
from .severity import compute_severity, normalize_mode, normalize_p_norm
from .severity_se import compute_severity_se
from .simulation import compute_critical_value
from .validation import DatasetProfile


def _validate_dataframe(df: Any) -> None:
    """Validate that df is a pandas DataFrame."""
    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError(
            "pretest_from_dataframe requires pandas. "
            "Install with: pip install pretest[data]"
        ) from exc
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")


def _validate_columns(df: Any, columns: list[str]) -> None:
    """Validate that all required columns exist in the DataFrame."""
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(f"DataFrame missing required columns: {missing}")


def compute_kappa_weighted(
    *,
    t_post: int,
    p_norm: float | str,
    weights: Sequence[float],
    mode: str = "iterative",
) -> float:
    """Compute the weighted kappa constant for general linear estimands (Appendix B).

    Formula:
        kappa_c = T_post^{1/p} * (sum((c_{T_post-t+1} * t)^q))^{1/q}

    where q is the Holder conjugate of p (1/p + 1/q = 1).

    Parameters
    ----------
    t_post : int
        Number of post-treatment periods.
    p_norm : float or str
        Severity norm p >= 1.
    weights : sequence of float
        Post-treatment weights c_t (must sum to a reasonable total;
        typically normalized so sum = 1).
    mode : str
        Either 'iterative' or 'overall'.

    Returns
    -------
    float
        Weighted kappa constant kappa_c.
    """
    normalized_mode = normalize_mode(mode)
    normalized_p = normalize_p_norm(p_norm)

    if normalized_mode == "overall":
        return 1.0

    if len(weights) != t_post:
        raise ValueError(
            f"weights length {len(weights)} must equal t_post={t_post}"
        )

    if math.isinf(normalized_p):
        # p = inf, q = 1: kappa_c = T_post * sum(|c_{T_post-t+1} * t|)
        return t_post * sum(
            abs(weights[t_post - t] * t) for t in range(1, t_post + 1)
        )

    if normalized_p == 1:
        # p = 1, q = inf: kappa_c = T_post^1 * max(|c_{T_post-t+1} * t|)
        return t_post * max(
            abs(weights[t_post - t] * t) for t in range(1, t_post + 1)
        )

    # General case: q = p / (p - 1)
    q = normalized_p / (normalized_p - 1.0)
    terms = [abs(weights[t_post - t] * t) ** q for t in range(1, t_post + 1)]
    sum_terms = sum(terms)

    return (t_post ** (1.0 / normalized_p)) * (sum_terms ** (1.0 / q))


def pretest_from_dataframe(
    df: Any,
    outcome: str,
    treatment: str,
    time: str,
    threshold: float,
    *,
    treat_time: float | None = None,
    p: float = 2.0,
    alpha: float = 0.05,
    cluster: str | None = None,
    mode: str = "iterative",
    simulations: int = 5000,
    seed: int = 12345,
    post_weights: Sequence[float] | None = None,
) -> PretestResultSnapshot:
    """Run the conditional extrapolation pre-test from a pandas DataFrame.

    This is the primary user-facing function. It performs the complete pipeline:
    1. Validate and prepare data
    2. Compute DID estimates delta_t and iterative violations nu_t (Section 2.1)
    3. Estimate asymptotic covariance matrix (Section 2.3)
    4. Calculate severity S_pre (Section 3.1)
    5. Execute pre-test phi = 1{S_pre > M} (Theorem 1, Section 4.2)
    6. Compute Monte Carlo critical value f(alpha, Sigma) (Appendix D.5)
    7. Construct conditionally valid confidence interval (Theorem 2, Section 5.1)

    Parameters
    ----------
    df : pandas.DataFrame
        Input data with outcome, treatment, time, and optional cluster columns.
    outcome : str
        Name of the outcome variable column.
    treatment : str
        Name of the binary treatment indicator column (0=control, 1=treated).
    time : str
        Name of the time period column.
    threshold : float
        Acceptable violation threshold M > 0 (Section 3.1).
    treat_time : float or None
        Treatment time t0 (first post-treatment period). If None, must be
        inferable from the data (time-varying treatment in panel).
    p : float
        Severity norm exponent p >= 1 (default: 2). Use math.inf for L-infinity.
    alpha : float
        Significance level in (0, 1) (default: 0.05).
    cluster : str or None
        Column name for cluster-robust standard errors.
    mode : str
        'iterative' (default) or 'overall' (Appendix C, kappa-free).
    simulations : int
        Number of Monte Carlo simulations for critical value (default: 5000).
    seed : int
        Random seed for reproducibility (default: 12345).
    post_weights : sequence of float or None
        Custom post-treatment weights for general linear estimands (Appendix B).
        None uses equal weights (1/T_post for each period).

    Returns
    -------
    PretestResultSnapshot
        Complete result snapshot with validation state, severity, decision,
        conditional and conventional intervals, and diagnostics.

    Raises
    ------
    ImportError
        If pandas is not installed.
    TypeError
        If df is not a pandas DataFrame.
    ValueError
        If required columns are missing, data fails validation, or parameters
        are out of range.

    Examples
    --------
    >>> import pandas as pd
    >>> import pretest
    >>> df = pd.DataFrame({
    ...     'y': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    ...     'treated': [0, 0, 1, 1] * 3,
    ...     'year': [2000]*4 + [2001]*4 + [2002]*4,
    ... })
    >>> snapshot = pretest.pretest_from_dataframe(
    ...     df, outcome='y', treatment='treated', time='year',
    ...     threshold=5.0, treat_time=2002,
    ... )
    >>> snapshot.reporting_summary()['decision']
    'PASS'
    """
    import pandas as pd

    _validate_dataframe(df)

    # Validate required columns
    required_cols = [outcome, treatment, time]
    if cluster is not None:
        required_cols.append(cluster)
    _validate_columns(df, required_cols)

    # Validate parameters
    normalized_mode = normalize_mode(mode)
    if threshold <= 0:
        raise ValueError("threshold must be positive")
    if alpha <= 0 or alpha >= 1:
        raise ValueError("alpha must be in (0, 1)")
    normalized_p = normalize_p_norm(p)

    # Drop rows with missing values in key columns
    subset_cols = list(dict.fromkeys(required_cols + [outcome]))
    working_df = df[subset_cols].dropna(
        subset=[outcome, treatment, time]
    ).copy()

    # Validate treatment is binary
    treat_values = working_df[treatment].unique()
    if not set(treat_values).issubset({0, 1, 0.0, 1.0}):
        raise ValueError(
            f"treatment column must contain only 0 and 1, got: {sorted(treat_values)}"
        )

    # Extract time structure
    observed_times = sorted(working_df[time].unique())
    time_to_index = {t: i + 1 for i, t in enumerate(observed_times)}
    T = len(observed_times)

    # Determine treatment time
    if treat_time is None:
        raise ValueError(
            "treat_time must be specified. Auto-detection from time-varying "
            "treatment is not yet supported in the DataFrame interface."
        )
    if treat_time not in observed_times:
        raise ValueError(
            f"treat_time={treat_time} not found in observed time values: {observed_times}"
        )

    treatment_time_index = time_to_index[treat_time]
    T_pre = treatment_time_index - 1
    T_post = T - T_pre

    if T_pre < 2:
        raise ValueError(
            f"treat_time must leave at least 2 pre-treatment periods, got T_pre={T_pre}"
        )
    if T_post < 1:
        raise ValueError(
            f"treat_time must leave at least 1 post-treatment period, got T_post={T_post}"
        )

    # Validate post_weights dimension
    if post_weights is not None:
        if len(post_weights) != T_post:
            raise ValueError(
                f"post_weights length {len(post_weights)} must equal T_post={T_post}"
            )

    # Convert to internal arrays
    outcomes_arr = list(working_df[outcome])
    treatments_arr = [int(x) for x in working_df[treatment]]
    time_indices_arr = [time_to_index[t] for t in working_df[time]]
    n = len(outcomes_arr)

    # Validate complete group-time support
    for t_idx in range(1, T + 1):
        for d in (0, 1):
            count = sum(
                1 for i in range(n)
                if time_indices_arr[i] == t_idx and treatments_arr[i] == d
            )
            if count == 0:
                orig_time = observed_times[t_idx - 1]
                group = "treated" if d == 1 else "control"
                raise ValueError(
                    f"No observations for time={orig_time}, group={group}. "
                    "Complete group-time support required."
                )

    # Compute group means
    grouped: dict[tuple[int, int], list[float]] = {}
    for i in range(n):
        key = (time_indices_arr[i], treatments_arr[i])
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(outcomes_arr[i])

    means: dict[tuple[int, int], float] = {
        k: sum(v) / len(v) for k, v in grouped.items()
    }

    # Compute iterative violations nu_t (Section 2.1)
    nu_vector: list[float] = []
    for t in range(2, treatment_time_index):
        nu_t = (means[(t, 1)] - means[(t - 1, 1)]) - (means[(t, 0)] - means[(t - 1, 0)])
        nu_vector.append(nu_t)

    # Compute overall violations nu_bar_t (cumulative sum)
    nu_bar_vector: list[float] = []
    cumulative = 0.0
    for nu_t in nu_vector:
        cumulative += nu_t
        nu_bar_vector.append(cumulative)

    # Compute DID estimates delta_t (Section 2.1)
    delta_vector: list[float] = []
    for t in range(treatment_time_index, T + 1):
        delta_t = (
            (means[(t, 1)] - means[(treatment_time_index, 1)])
            - (means[(t, 0)] - means[(treatment_time_index, 0)])
        )
        delta_vector.append(delta_t)

    # Compute delta_bar (average or weighted)
    if post_weights is not None:
        delta_bar = sum(w * d for w, d in zip(post_weights, delta_vector))
    else:
        delta_bar = sum(delta_vector) / len(delta_vector)

    # Compute influence matrix
    influence_mat = compute_influence_matrix(
        outcomes_arr,
        treatments_arr,
        time_indices_arr,
        treatment_time_index=treatment_time_index,
        time_period_count=T,
    )

    # Compute covariance matrix
    if cluster is not None:
        cluster_ids = working_df[cluster].tolist()
        covariance_matrix = compute_cluster_robust_covariance(
            influence_mat, cluster_ids
        )
    else:
        covariance_matrix = compute_standard_covariance(influence_mat)

    # Compute SE(delta_bar)
    pre_term_count = T_pre - 1
    if post_weights is not None:
        # Weighted SE: sqrt(c' * Sigma_delta * c / n)
        post_start = pre_term_count
        dim = len(covariance_matrix)
        variance = 0.0
        for i in range(T_post):
            for j in range(T_post):
                variance += (
                    post_weights[i]
                    * covariance_matrix[post_start + i][post_start + j]
                    * post_weights[j]
                )
        variance /= n
        se_delta_bar = math.sqrt(max(variance, 0.0))
    else:
        se_delta_bar = compute_delta_bar_se(
            covariance_matrix,
            sample_size=n,
            pre_term_count=pre_term_count,
            post_period_count=T_post,
        )

    # Compute severity SE via Delta Method
    sigma_nu = extract_nu_covariance(covariance_matrix, pre_term_count)
    s_pre_se = compute_severity_se(
        tuple(nu_vector),
        sigma_nu,
        p_norm=normalized_p,
        mode=normalized_mode,
    )

    # Compute kappa (or weighted kappa)
    if post_weights is not None:
        kappa = compute_kappa_weighted(
            t_post=T_post,
            p_norm=normalized_p,
            weights=list(post_weights),
            mode=normalized_mode,
        )
    else:
        kappa = compute_kappa(
            t_post=T_post,
            p_norm=normalized_p,
            mode=normalized_mode,
        )

    # Compute critical value
    f_alpha = compute_critical_value(
        covariance_matrix,
        alpha=alpha,
        simulations=simulations,
        t_pre=T_pre,
        t_post=T_post,
        p_norm=normalized_p,
        mode=normalized_mode,
        kappa=kappa,
        seed=seed,
        covariance_form="iterative",
    )

    # Build command string
    p_str = "." if math.isinf(normalized_p) else str(p)
    command = (
        f"pretest {outcome}, treatment({treatment}) time({time}) "
        f"treat_time({treat_time}) threshold({threshold}) "
        f"p({p_str}) alpha({alpha}) simulate({simulations}) seed({seed})"
    )
    if normalized_mode == "overall":
        command += " overall"

    # Build profile
    profile = DatasetProfile(
        time_periods=tuple(float(t) for t in observed_times),
        treatment_values=(0.0, 1.0),
    )

    # Construct snapshot via pipeline
    snapshot = compute_pretest_snapshot(
        command,
        profile,
        nu_vector=tuple(nu_vector),
        nu_bar_vector=tuple(nu_bar_vector) if normalized_mode == "overall" else None,
        f_alpha=f_alpha,
        covariance_matrix=covariance_matrix,
        covariance_form="iterative",
        delta_bar=delta_bar,
        se_delta_bar=se_delta_bar,
        sample_size=n,
        t_post=T_post,
        s_pre_se=s_pre_se,
        theta=tuple(nu_vector) + tuple(delta_vector),
    )

    # Add estimation diagnostics
    snapshot.diagnostics["estimation"] = {
        "data_source": "pandas.DataFrame",
        "sample_size": n,
        "T": T,
        "T_pre": T_pre,
        "T_post": T_post,
        "treat_time": treat_time,
        "mode": normalized_mode,
        "cluster": cluster,
        "n_clusters": len(set(working_df[cluster].tolist())) if cluster else None,
        "post_weights": list(post_weights) if post_weights is not None else None,
        "covariance_type": "cluster-robust" if cluster else "standard",
        "s_pre_se": s_pre_se,
    }

    return snapshot
