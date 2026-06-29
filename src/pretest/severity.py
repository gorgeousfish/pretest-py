from __future__ import annotations

from collections.abc import Sequence
import math
import sys

from ._compat import frozen_slots_dataclass

_LOG_SPACE_POWER_THRESHOLD = 3.0
_LOG_FLOAT_MAX = math.log(sys.float_info.max)


def _coerce_float(name: str, value: float | int | str, *, message: str | None = None) -> float:
    if isinstance(value, bool):
        raise ValueError(message or f"{name} must be finite")
    try:
        return float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError(message or f"{name} must be finite") from exc


def _normalize_finite_float(name: str, value: float | int | str) -> float:
    normalized = _coerce_float(name, value)
    if not math.isfinite(normalized):
        raise ValueError(f"{name} must be finite")
    return normalized


def _normalize_nonnegative_finite_float(name: str, value: float | int | str) -> float:
    normalized = _normalize_finite_float(name, value)
    if normalized < 0:
        raise ValueError(f"{name} must be nonnegative")
    return normalized


def _ensure_finite_output(name: str, value: float) -> float:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def _log_mean_exp(log_values: Sequence[float]) -> float:
    max_log = max(log_values)
    return max_log + math.log(
        sum(math.exp(value - max_log) for value in log_values) / len(log_values)
    )


def _power_mean(values: Sequence[float], exponent: float, *, name: str) -> float:
    max_value = max(values)
    if max_value == 0.0:
        return 0.0
    use_log_space = (
        exponent >= _LOG_SPACE_POWER_THRESHOLD
        or exponent * math.log(max_value) > _LOG_FLOAT_MAX
    )
    if use_log_space:
        log_mean_power = _log_mean_exp(
            [
                exponent * math.log(value)
                for value in values
                if value > 0.0
            ]
            + [-math.inf] * sum(value == 0.0 for value in values)
        )
        return math.exp(log_mean_power / exponent)

    try:
        mean_power = sum(value**exponent for value in values) / len(values)
    except OverflowError as exc:
        raise ValueError(f"{name} must be finite") from exc
    return mean_power ** (1.0 / exponent)


def _normalize_decision_surface_float(name: str, value: object) -> float:
    if isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{name} must be finite")
    return _normalize_finite_float(name, value)


def _normalize_binary_decision_flag(value: object) -> int:
    if isinstance(value, (bool, str, bytes, bytearray)):
        raise ValueError("phi and pretest_pass must be binary")
    try:
        normalized = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError("phi and pretest_pass must be binary") from exc
    if not normalized.is_integer() or int(normalized) not in {0, 1}:
        raise ValueError("phi and pretest_pass must be binary")
    return int(normalized)


def normalize_mode(mode: str) -> str:
    if not isinstance(mode, str):
        raise ValueError("mode must be either 'iterative' or 'overall'")
    normalized = mode.strip().lower()
    if normalized not in {"iterative", "overall"}:
        raise ValueError("mode must be either 'iterative' or 'overall'")
    return normalized


def normalize_p_norm(p_norm: float | str) -> float:
    if isinstance(p_norm, (bytes, bytearray)):
        raise ValueError("p_norm must not be a string-backed numeric")
    if isinstance(p_norm, str):
        normalized = p_norm.strip().lower()
        if normalized in {"inf", "infinity"}:
            return math.inf
        if normalized:
            try:
                parsed = float(normalized)
            except (OverflowError, TypeError, ValueError):
                parsed = None
            else:
                if math.isfinite(parsed):
                    raise ValueError("p_norm must not be a string-backed numeric")
        value = _coerce_float(
            "p_norm",
            normalized,
            message="p_norm must be finite or infinity",
        )
        if math.isinf(value):
            raise ValueError("p_norm must be finite or infinity")
    else:
        value = _coerce_float(
            "p_norm",
            p_norm,
            message="p_norm must be finite or infinity",
        )

    if math.isnan(value):
        raise ValueError("p_norm must be finite or infinity")
    if value < 1:
        raise ValueError("p_norm must be >= 1")
    if value >= 1e10:
        return math.inf
    return value


def _cumulative_violations(nu_vector: Sequence[float]) -> list[float]:
    cumulative: list[float] = []
    running_total = 0.0
    for index, value in enumerate(nu_vector):
        running_total += _normalize_finite_float(f"nu_vector[{index}]", value)
        cumulative.append(running_total)
    return cumulative


def _validated_overall_cumulative_bridge(
    nu_vector: Sequence[float],
    nu_bar_vector: Sequence[float],
) -> list[float]:
    expected_cumulative = _cumulative_violations(nu_vector)
    normalized_nu_bar = [
        _normalize_finite_float(f"nu_bar_vector[{index}]", value)
        for index, value in enumerate(nu_bar_vector)
    ]
    if len(normalized_nu_bar) != len(expected_cumulative):
        raise ValueError(
            "nu_bar_vector must equal the cumulative sum of nu_vector in overall mode"
        )
    for expected, observed in zip(expected_cumulative, normalized_nu_bar):
        if not math.isclose(observed, expected, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError(
                "nu_bar_vector must equal the cumulative sum of nu_vector in overall mode"
            )
    return normalized_nu_bar


def _normalize_numeric_sequence_input(
    name: str,
    values: Sequence[float],
) -> Sequence[float]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise ValueError(f"{name} must be a non-string sequence of numerics")
    for index, value in enumerate(values):
        if isinstance(value, (str, bytes, bytearray)):
            raise ValueError(f"{name}[{index}] must not be a string-backed numeric")
        if isinstance(value, bool):
            raise ValueError(f"{name}[{index}] must not be a boolean-backed numeric")
    return values


def _select_vector(
    nu_vector: Sequence[float],
    *,
    mode: str,
    nu_bar_vector: Sequence[float] | None,
) -> list[float]:
    normalized_nu_vector = _normalize_numeric_sequence_input("nu_vector", nu_vector)
    if mode != "overall" and nu_bar_vector is not None:
        raise ValueError("nu_bar_vector is only valid in overall mode")
    if mode == "overall":
        source = (
            _validated_overall_cumulative_bridge(
                normalized_nu_vector,
                _normalize_numeric_sequence_input("nu_bar_vector", nu_bar_vector),
            )
            if nu_bar_vector is not None
            else _cumulative_violations(normalized_nu_vector)
        )
    else:
        source = normalized_nu_vector

    source_name = "nu_bar_vector" if mode == "overall" and nu_bar_vector is not None else "nu_vector"
    values = [
        abs(_normalize_finite_float(f"{source_name}[{index}]", value))
        for index, value in enumerate(source)
    ]
    if not values:
        raise ValueError("severity requires at least one violation term")
    return values


@frozen_slots_dataclass
class SeverityDecision:
    """Immutable result of the pre-test severity classification.

    Encapsulates the binary decision rule phi = 1{S_pre > M} and its
    complement pretest_pass = 1 - phi, following Mikhaeil & Harshaw (2026),
    Section 4.2, Theorem 1.

    Parameters
    ----------
    s_pre_hat : float
        Estimated pre-treatment severity statistic (nonnegative).
    threshold_m : float
        Positive classification threshold M.
    phi : int
        Binary indicator: 1 if severity exceeds threshold, 0 otherwise.
    pretest_pass : int
        Binary indicator: 1 - phi. Equals 1 when the pre-test passes.

    Notes
    -----
    The decision boundary is strict inequality:

    .. math::
        \\phi = \\mathbf{1}\\{\\hat{S}_{\\text{pre}} > M\\}
    """

    s_pre_hat: float
    threshold_m: float
    phi: int
    pretest_pass: int

    def __post_init__(self) -> None:
        severity = _normalize_decision_surface_float("s_pre_hat", self.s_pre_hat)
        if severity < 0:
            raise ValueError("s_pre_hat must be nonnegative")
        threshold = _normalize_decision_surface_float("threshold_m", self.threshold_m)
        if threshold <= 0:
            raise ValueError("threshold_m must be positive")
        phi = _normalize_binary_decision_flag(self.phi)
        pretest_pass = _normalize_binary_decision_flag(self.pretest_pass)
        if pretest_pass != 1 - phi or phi != int(severity > threshold):
            raise ValueError(
                "phi and pretest_pass must match the severity decision boundary"
            )
        object.__setattr__(self, "s_pre_hat", severity)
        object.__setattr__(self, "threshold_m", threshold)
        object.__setattr__(self, "phi", phi)
        object.__setattr__(self, "pretest_pass", pretest_pass)


def compute_severity(
    *,
    nu_vector: Sequence[float],
    p_norm: float | str,
    mode: str = "iterative",
    nu_bar_vector: Sequence[float] | None = None,
) -> float:
    """Compute the pre-treatment severity statistic S_pre.

    Implements the p-norm severity measure from Mikhaeil & Harshaw (2026),
    Section 3.1, Equations (8-9).

    Parameters
    ----------
    nu_vector : sequence of float
        Pre-treatment violation estimates (nu_2, ..., nu_{t0-1}) in iterative
        mode, or the period-level increments in overall mode.
    p_norm : float or str
        The norm exponent p >= 1. Accepts numeric values or ``"inf"`` /
        ``"infinity"`` for the supremum norm.
    mode : {'iterative', 'overall'}, default 'iterative'
        Aggregation mode. In 'iterative' mode the severity is computed from
        period-level violations; in 'overall' mode it uses cumulative sums.
    nu_bar_vector : sequence of float or None, optional
        Cumulative sum vector for overall mode validation. Must equal the
        running cumulative sum of ``nu_vector`` when provided.

    Returns
    -------
    float
        Nonnegative severity statistic.

    Raises
    ------
    ValueError
        If inputs fail validation (empty vector, invalid p_norm, mode
        mismatch, or non-finite values).

    Examples
    --------
    >>> from pretest.severity import compute_severity
    >>> compute_severity(nu_vector=[0.1, -0.2, 0.15], p_norm=2)
    0.153...

    Notes
    -----
    Mathematical reference: Mikhaeil & Harshaw (2026), Section 3.1.

    The iterative-mode formula is:

    .. math::
        \hat{S}_{\text{pre}} = \left(\frac{1}{T_0-1}
        \sum_{t=2}^{T_0} |\hat{\nu}_t|^p\right)^{1/p}

    For p = infinity, this reduces to the maximum absolute violation.
    """
    normalized_mode = normalize_mode(mode)
    normalized_p = normalize_p_norm(p_norm)
    values = _select_vector(
        nu_vector,
        mode=normalized_mode,
        nu_bar_vector=nu_bar_vector,
    )

    if math.isinf(normalized_p):
        return _ensure_finite_output("computed severity", max(values))

    return _ensure_finite_output(
        "computed severity",
        _power_mean(values, normalized_p, name="computed severity"),
    )


def classify_pretest(*, s_pre_hat: float, threshold_m: float) -> SeverityDecision:
    """Classify the pre-test outcome using the severity decision rule.

    Applies the indicator function phi = 1{S_pre > M} from Mikhaeil &
    Harshaw (2026), Section 4.2, Theorem 1.

    Parameters
    ----------
    s_pre_hat : float
        Estimated severity statistic (nonnegative, finite).
    threshold_m : float
        Positive classification threshold M.

    Returns
    -------
    SeverityDecision
        Frozen dataclass with fields ``s_pre_hat``, ``threshold_m``,
        ``phi``, and ``pretest_pass``.

    Raises
    ------
    ValueError
        If s_pre_hat is negative or threshold_m is non-positive.

    Examples
    --------
    >>> from pretest.severity import classify_pretest
    >>> decision = classify_pretest(s_pre_hat=0.05, threshold_m=0.1)
    >>> decision.pretest_pass
    1

    Notes
    -----
    .. math::
        \\phi = \\mathbf{1}\\{\\hat{S}_{\\text{pre}} > M\\}, \\quad
        \\text{pretest\\_pass} = 1 - \\phi
    """
    if isinstance(s_pre_hat, (str, bytes, bytearray)):
        raise ValueError("s_pre_hat must be finite")
    if isinstance(threshold_m, (str, bytes, bytearray)):
        raise ValueError("threshold_m must be finite")
    severity = _normalize_nonnegative_finite_float("s_pre_hat", s_pre_hat)
    threshold = _normalize_finite_float("threshold_m", threshold_m)
    if threshold <= 0:
        raise ValueError("threshold_m must be positive")
    phi = int(severity > threshold)
    return SeverityDecision(
        s_pre_hat=severity,
        threshold_m=threshold,
        phi=phi,
        pretest_pass=1 - phi,
    )
