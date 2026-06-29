from __future__ import annotations

from collections.abc import Sequence
import math

from ._compat import frozen_slots_dataclass
from .critical_value import compute_bias_bound, normalize_critical_value
from .validation import ValidationState

_CONDITIONAL_FIELDS = ("e(ci_lower)", "e(ci_upper)")
_CONVENTIONAL_FIELDS = ("e(ci_conv_lower)", "e(ci_conv_upper)")


@frozen_slots_dataclass
class ConfidenceIntervalAvailability:
    """Describes which confidence interval categories are reportable.

    Encapsulates the joint availability logic for conditional (pre-test
    gated) and conventional (variance-based) confidence intervals.

    Parameters
    ----------
    conditional_available : bool
        True when data is valid and the pre-test passes (phi = 0).
    conventional_available : bool
        True when data is valid and variance information is available.
    variance_available : bool
        Whether a standard-error estimate was supplied.
    conditional_display_rounded : tuple of str
        Field names reported when conditional CI is available.
    conditional_exact_absence : tuple of str
        Field names confirmed absent when conditional CI is unavailable.
    conventional_display_rounded : tuple of str
        Field names reported when conventional CI is available.
    conventional_exact_absence : tuple of str
        Field names confirmed absent when conventional CI is unavailable.
    """

    conditional_available: bool
    conventional_available: bool
    variance_available: bool
    conditional_display_rounded: tuple[str, ...]
    conditional_exact_absence: tuple[str, ...]
    conventional_display_rounded: tuple[str, ...]
    conventional_exact_absence: tuple[str, ...]

    def __post_init__(self) -> None:
        conditional_available = _normalize_boolean_flag(
            "conditional_available",
            self.conditional_available,
        )
        conventional_available = _normalize_boolean_flag(
            "conventional_available",
            self.conventional_available,
        )
        variance_available = _normalize_boolean_flag(
            "variance_available",
            self.variance_available,
        )
        conditional_display_rounded = _normalize_ci_category_fields(
            "conditional_display_rounded",
            self.conditional_display_rounded,
        )
        conditional_exact_absence = _normalize_ci_category_fields(
            "conditional_exact_absence",
            self.conditional_exact_absence,
        )
        conventional_display_rounded = _normalize_ci_category_fields(
            "conventional_display_rounded",
            self.conventional_display_rounded,
        )
        conventional_exact_absence = _normalize_ci_category_fields(
            "conventional_exact_absence",
            self.conventional_exact_absence,
        )
        if conditional_available:
            if (
                conditional_display_rounded != _CONDITIONAL_FIELDS
                or conditional_exact_absence
            ):
                raise ValueError(
                    "conditional CI category fields must match conditional_available"
                )
        elif (
            conditional_display_rounded
            or conditional_exact_absence != _CONDITIONAL_FIELDS
        ):
            raise ValueError(
                "conditional CI category fields must match conditional_available"
            )
        if conventional_available:
            if not variance_available:
                raise ValueError(
                    "conventional availability requires variance_available = True"
                )
            if (
                conventional_display_rounded != _CONVENTIONAL_FIELDS
                or conventional_exact_absence
            ):
                raise ValueError(
                    "conventional CI category fields must match conventional_available"
                )
        elif (
            conventional_display_rounded
            or conventional_exact_absence != _CONVENTIONAL_FIELDS
        ):
            raise ValueError(
                "conventional CI category fields must match conventional_available"
            )
        object.__setattr__(self, "conditional_available", conditional_available)
        object.__setattr__(self, "conventional_available", conventional_available)
        object.__setattr__(self, "variance_available", variance_available)
        object.__setattr__(
            self,
            "conditional_display_rounded",
            conditional_display_rounded,
        )
        object.__setattr__(
            self,
            "conditional_exact_absence",
            conditional_exact_absence,
        )
        object.__setattr__(
            self,
            "conventional_display_rounded",
            conventional_display_rounded,
        )
        object.__setattr__(
            self,
            "conventional_exact_absence",
            conventional_exact_absence,
        )


def _normalize_boolean_flag(name: str, value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _normalize_ci_category_fields(
    name: str,
    value: object,
) -> tuple[str, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise ValueError(f"{name} must be a non-string sequence of strings")
    normalized: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise ValueError(f"{name}[{index}] must be a string")
        normalized.append(item)
    return tuple(normalized)


def _validate_pretest_state_consistency(state: ValidationState) -> None:
    if not isinstance(state, ValidationState):
        raise ValueError("state must be a ValidationState")
    if isinstance(state.data_valid, bool) or state.data_valid not in {0, 1}:
        raise ValueError("data_valid must be 0 or 1")
    if state.phi is not None and (
        isinstance(state.phi, bool) or state.phi not in {0, 1}
    ):
        raise ValueError("phi and pretest_pass must be binary")
    if state.pretest_pass is not None and (
        isinstance(state.pretest_pass, bool) or state.pretest_pass not in {0, 1}
    ):
        raise ValueError("phi and pretest_pass must be binary")
    if state.data_valid == 0:
        if state.phi is not None or state.pretest_pass != 0:
            raise ValueError(
                "invalid data state must keep phi unset and pretest_pass at 0"
            )
        return
    if (state.phi is None) != (state.pretest_pass is None):
        raise ValueError(
            "phi and pretest_pass must either both be set or both be unset"
        )
    if state.phi is None:
        return
    if state.pretest_pass != 1 - state.phi:
        raise ValueError("phi and pretest_pass must remain complementary")


def compute_ci_half_width(
    *,
    mode: str,
    s_pre_hat: float,
    f_alpha: float,
    n: int | float,
    kappa: float | None = None,
) -> float:
    """Compute the confidence interval half-width.

    Combines the bias bound and the scaled critical value to produce
    the half-width of the conditional confidence interval, following
    Mikhaeil & Harshaw (2026), Section 5, Equation below Theorem 2.

    Parameters
    ----------
    mode : {'iterative', 'overall'}
        Aggregation mode.
    s_pre_hat : float
        Estimated pre-treatment severity (nonnegative).
    f_alpha : float
        Critical value from Monte Carlo simulation (nonnegative).
    n : int or float
        Sample size (positive).
    kappa : float or None, optional
        Extrapolation constant. Required in iterative mode.

    Returns
    -------
    float
        Nonnegative half-width of the conditional confidence interval.

    Raises
    ------
    ValueError
        If n <= 0, f_alpha < 0, or computed half-width is non-finite.

    Notes
    -----
    .. math::
        \\text{half-width} = \\kappa \\cdot \\hat{S}_{\\text{pre}}
        + \\frac{f_\\alpha}{\\sqrt{n}}
    """
    if isinstance(n, (str, bytes, bytearray, bool)):
        raise ValueError("n must be finite and positive")
    try:
        sample_size = float(n)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError("n must be finite and positive") from exc
    if not math.isfinite(sample_size) or sample_size <= 0:
        raise ValueError("n must be finite and positive")

    bias_bound = compute_bias_bound(
        mode=mode,
        s_pre_hat=s_pre_hat,
        kappa=kappa,
    )
    critical_value = normalize_critical_value(f_alpha) / math.sqrt(sample_size)
    half_width = bias_bound + critical_value
    if not math.isfinite(half_width):
        raise ValueError("computed CI half-width must be finite")
    return half_width


def resolve_ci_availability(
    state: ValidationState,
    *,
    variance_available: bool = True,
) -> ConfidenceIntervalAvailability:
    """Determine confidence interval availability from validation state.

    Resolves which CI categories (conditional and conventional) may be
    reported given the pre-test classification and data validity.

    Parameters
    ----------
    state : ValidationState
        Current validation state carrying data_valid, phi, and
        pretest_pass indicators.
    variance_available : bool, default True
        Whether a variance/standard-error estimate is available for
        the conventional interval.

    Returns
    -------
    ConfidenceIntervalAvailability
        Frozen dataclass describing which intervals are reportable.

    Raises
    ------
    ValueError
        If the validation state is internally inconsistent.
    """
    _validate_pretest_state_consistency(state)
    variance_ready = _normalize_boolean_flag("variance_available", variance_available)
    conditional_available = state.data_valid == 1 and state.pretest_pass == 1
    conventional_available = state.data_valid == 1 and variance_ready

    return ConfidenceIntervalAvailability(
        conditional_available=conditional_available,
        conventional_available=conventional_available,
        variance_available=variance_ready,
        conditional_display_rounded=_CONDITIONAL_FIELDS if conditional_available else (),
        conditional_exact_absence=_CONDITIONAL_FIELDS if not conditional_available else (),
        conventional_display_rounded=_CONVENTIONAL_FIELDS if conventional_available else (),
        conventional_exact_absence=_CONVENTIONAL_FIELDS if not conventional_available else (),
    )
