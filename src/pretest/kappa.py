from __future__ import annotations

import math

from .severity import _power_mean, normalize_mode, normalize_p_norm


def _ensure_finite_output(name: str, value: float) -> float:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def _normalize_t_post(t_post: int | float) -> int:
    if isinstance(t_post, (str, bytes, bytearray, bool)):
        raise ValueError("t_post must be a positive integer")
    try:
        periods = float(t_post)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError("t_post must be a positive integer") from exc
    if periods < 1 or not periods.is_integer():
        raise ValueError("t_post must be a positive integer")
    return int(periods)


def compute_kappa(
    *,
    t_post: int | float,
    p_norm: float | str,
    mode: str = "iterative",
) -> float:
    """Compute the kappa extrapolation constant.

    Calculates the multiplier that converts pre-treatment severity into
    a post-treatment bias bound, following Mikhaeil & Harshaw (2026),
    Section 5, below Theorem 2.

    Parameters
    ----------
    t_post : int
        Number of post-treatment periods T_post >= 1.
    p_norm : float or str
        The norm exponent p >= 1. Accepts numeric values or ``"inf"`` /
        ``"infinity"`` for the supremum norm.
    mode : {'iterative', 'overall'}, default 'iterative'
        Aggregation mode. In 'overall' mode, kappa is always 1.

    Returns
    -------
    float
        Positive kappa constant.

    Raises
    ------
    ValueError
        If t_post < 1, p_norm < 1, or mode is invalid.

    Examples
    --------
    >>> from pretest.kappa import compute_kappa
    >>> compute_kappa(t_post=3, p_norm=2)
    2.160...

    Notes
    -----
    Mathematical reference: Mikhaeil & Harshaw (2026), Section 5.

    In iterative mode with finite p:

    .. math::
        \\kappa = \\left(\\frac{1}{T_{\\text{post}}}
        \\sum_{j=1}^{T_{\\text{post}}} j^q\\right)^{1/q}

    where q = p/(p-1) is the dual exponent. For p = 1, kappa = T_post.
    For p = infinity, kappa = (T_post + 1) / 2. In overall mode, kappa = 1.
    """
    normalized_mode = normalize_mode(mode)
    horizon = _normalize_t_post(t_post)

    normalized_p = normalize_p_norm(p_norm)
    if normalized_mode == "overall":
        return 1.0
    if normalized_p == 1:
        return float(horizon)
    if math.isinf(normalized_p):
        return (horizon + 1) / 2.0

    dual_p = normalized_p / (normalized_p - 1.0)
    return _ensure_finite_output(
        "computed kappa",
        _power_mean(
            tuple(float(step) for step in range(1, horizon + 1)),
            dual_p,
            name="computed kappa",
        ),
    )
