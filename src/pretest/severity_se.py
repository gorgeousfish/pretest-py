"""Delta Method standard error for severity S_pre.

Implements SE(S_pre) via the Delta Method following the gradient computation
in Mikhaeil & Harshaw (2026), consistent with Stata's _pretest_severity_se().

Formula:
    SE(S_pre) = sqrt(grad_g' * Sigma_nu * grad_g)

    where the gradient vector is:
    dg/dnu_t = |nu_t|^{p-1} * sign(nu_t) / [(T_pre-1) * S_pre^{p-1}]

Special cases:
    p = 2: dg/dnu_t = nu_t / [(T_pre-1) * S_pre]
    p = 1: dg/dnu_t = sign(nu_t) / (T_pre-1)
    p = infinity: not differentiable, returns None
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from .severity import compute_severity, normalize_mode, normalize_p_norm


def _sign(x: float) -> float:
    """Signum function."""
    if x > 0:
        return 1.0
    elif x < 0:
        return -1.0
    return 0.0


def compute_severity_gradient(
    nu_vector: Sequence[float],
    p_norm: float | str = 2.0,
    *,
    mode: str = "iterative",
) -> tuple[float, ...] | None:
    """Compute the gradient of the severity function with respect to nu.

    Parameters
    ----------
    nu_vector : sequence of float
        Pre-treatment iterative violations (T_pre - 1 elements).
    p_norm : float or str
        Severity norm p >= 1. Use math.inf or 'inf' for L-infinity.
    mode : str
        Either 'iterative' or 'overall'.

    Returns
    -------
    tuple of float or None
        Gradient vector of same dimension as nu_vector.
        Returns None for p = infinity (non-differentiable).
    """
    normalized_p = normalize_p_norm(p_norm)

    # p = infinity: max function is non-differentiable
    if math.isinf(normalized_p):
        return None

    n_pre = len(nu_vector)
    if n_pre == 0:
        return ()

    # Compute severity
    s_pre = compute_severity(
        nu_vector=nu_vector,
        p_norm=normalized_p,
        mode=mode,
    )

    # Handle near-zero severity (numerically unstable gradient)
    if s_pre < 1e-10:
        return tuple(0.0 for _ in nu_vector)

    # General gradient formula:
    # dg/dnu_t = |nu_t|^{p-1} * sign(nu_t) / [n_pre * S_pre^{p-1}]
    grad: list[float] = []
    for nu_t in nu_vector:
        abs_nu = abs(nu_t)
        if abs_nu < 1e-300:
            grad.append(0.0)
        else:
            numerator = abs_nu ** (normalized_p - 1) * _sign(nu_t)
            denominator = n_pre * s_pre ** (normalized_p - 1)
            grad.append(numerator / denominator)

    return tuple(grad)


def compute_severity_se(
    nu_vector: Sequence[float],
    covariance_nu: Sequence[Sequence[float]],
    p_norm: float | str = 2.0,
    *,
    mode: str = "iterative",
) -> float | None:
    """Compute the Delta Method standard error of S_pre.

    Formula:
        SE(S_pre) = sqrt(grad_g' * Sigma_nu * grad_g)

    Parameters
    ----------
    nu_vector : sequence of float
        Pre-treatment iterative violations (T_pre - 1 elements).
    covariance_nu : nested sequence of float
        Covariance matrix of nu (T_pre-1 x T_pre-1).
    p_norm : float or str
        Severity norm p >= 1.
    mode : str
        Either 'iterative' or 'overall'.

    Returns
    -------
    float or None
        Standard error SE(S_pre), or None if p = infinity.
    """
    normalized_p = normalize_p_norm(p_norm)

    # p = infinity: Delta Method not applicable
    if math.isinf(normalized_p):
        return None

    n_pre = len(nu_vector)
    if n_pre == 0:
        return 0.0

    # Validate covariance dimensions
    if len(covariance_nu) != n_pre:
        raise ValueError(
            f"covariance_nu dimension mismatch: expected {n_pre}x{n_pre}"
        )

    # Compute gradient
    grad = compute_severity_gradient(nu_vector, p_norm=normalized_p, mode=mode)
    if grad is None:
        return None

    # Delta Method: Var(g(theta)) = grad' * Sigma * grad
    variance = 0.0
    for i in range(n_pre):
        for j in range(n_pre):
            variance += grad[i] * covariance_nu[i][j] * grad[j]

    # Handle numerical issues
    if variance < 0:
        return 0.0

    return math.sqrt(variance)
