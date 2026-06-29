from __future__ import annotations

import math

from .severity import normalize_mode


def _coerce_float(name: str, value: float | int) -> float:
    if isinstance(value, (str, bytes, bytearray, bool)):
        raise ValueError(f"{name} must be finite")
    try:
        return float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be finite") from exc


def _normalize_finite_float(name: str, value: float | int) -> float:
    normalized = _coerce_float(name, value)
    if not math.isfinite(normalized):
        raise ValueError(f"{name} must be finite")
    return normalized


def _normalize_positive_finite_float(name: str, value: float | int) -> float:
    normalized = _normalize_finite_float(name, value)
    if normalized <= 0:
        raise ValueError(f"{name} must be positive")
    return normalized


def _normalize_nonnegative_finite_float(name: str, value: float | int) -> float:
    normalized = _normalize_finite_float(name, value)
    if normalized < 0:
        raise ValueError(f"{name} must be nonnegative")
    return normalized


def _ensure_finite_output(name: str, value: float) -> float:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def normalize_critical_value(f_alpha: float | int) -> float:
    """Validate and normalize the critical value f_alpha.

    Ensures the critical value is a nonnegative finite float suitable for
    use in confidence interval calculations.

    Parameters
    ----------
    f_alpha : float or int
        Raw critical value from Monte Carlo simulation or user input.

    Returns
    -------
    float
        Normalized nonnegative critical value.

    Raises
    ------
    ValueError
        If f_alpha is negative, non-finite, or not numeric.
    """
    return _normalize_nonnegative_finite_float("f_alpha", f_alpha)


def compute_bias_bound(
    *,
    mode: str,
    s_pre_hat: float,
    kappa: float | None = None,
) -> float:
    """Compute the bias bound kappa * S_pre.

    Calculates the worst-case extrapolation bias bound that enters the
    confidence interval half-width formula, following Mikhaeil & Harshaw
    (2026), Section 5, Theorem 2.

    Parameters
    ----------
    mode : {'iterative', 'overall'}
        Aggregation mode. In 'overall' mode the bias bound equals S_pre
        directly (kappa = 1).
    s_pre_hat : float
        Estimated pre-treatment severity (nonnegative, finite).
    kappa : float or None, optional
        Extrapolation constant. Required in iterative mode; must equal 1
        (within tolerance) or be None in overall mode.

    Returns
    -------
    float
        Nonnegative bias bound.

    Raises
    ------
    ValueError
        If kappa is missing in iterative mode, or kappa != 1 in overall
        mode, or inputs are non-finite.

    Notes
    -----
    .. math::
        \\text{bias bound} = \\kappa \\cdot \\hat{S}_{\\text{pre}}
    """
    normalized_mode = normalize_mode(mode)
    severity = _normalize_nonnegative_finite_float("s_pre_hat", s_pre_hat)

    if normalized_mode == "overall":
        if kappa is not None:
            normalized_kappa = _normalize_finite_float("kappa", kappa)
            if not math.isclose(
                normalized_kappa,
                1.0,
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise ValueError("overall mode requires kappa = 1")
        return severity

    if kappa is None:
        raise ValueError("iterative mode requires a kappa multiplier")
    return _ensure_finite_output(
        "computed bias bound",
        _normalize_positive_finite_float("kappa", kappa) * severity,
    )
