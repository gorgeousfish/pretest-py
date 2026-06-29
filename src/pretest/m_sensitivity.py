"""M-sensitivity analysis for the conditional extrapolation pre-test framework."""
from __future__ import annotations

import math
import warnings
from collections.abc import Sequence
from typing import Optional, Tuple

from ._compat import frozen_slots_dataclass
from ._display import m_sensitivity_html, m_sensitivity_str


@frozen_slots_dataclass
class MSensitivityResult:
    """Result of M-sensitivity analysis.

    Attributes
    ----------
    s_pre_hat : float
        Observed severity measure.
    s_pre_se : float or None
        Standard error of severity (if available).
    n : int
        Sample size.
    delta_bar : float
        Weighted average of post-treatment effects.
    kappa : float
        Bias-correction scaling parameter.
    f_alpha : float
        Critical value for confidence interval construction.
    alpha : float
        Significance level.
    m_values : tuple of float
        Evaluated threshold values.
    phi_values : tuple of int
        Decision function values: 1 if S_pre > M, else 0.
    can_report : tuple of bool
        Whether CI can be reported at each M (True when phi=0).
    breakdown_point : float
        The M* = S_pre value at which the decision flips.
    validity_separations : tuple of float or None
        ``|S_pre - M|`` for each M value (if validity check enabled).
    separation_threshold : float
        Threshold for omega(n^{-1/2}) validity condition.
    ci_lower : float
        Lower bound of the confidence interval.
    ci_upper : float
        Upper bound of the confidence interval.
    ci_half_width : float
        Half-width of the confidence interval.
    """

    s_pre_hat: float
    s_pre_se: Optional[float]
    n: int
    delta_bar: float
    kappa: float
    f_alpha: float
    alpha: float
    m_values: Tuple[float, ...]
    phi_values: Tuple[int, ...]
    can_report: Tuple[bool, ...]
    breakdown_point: float
    validity_separations: Optional[Tuple[float, ...]]
    separation_threshold: float
    ci_lower: float
    ci_upper: float
    ci_half_width: float

    def __str__(self) -> str:
        return m_sensitivity_str(self)

    def _repr_html_(self) -> str:
        return m_sensitivity_html(self)


def compute_m_sensitivity(
    snapshot,
    m_values: Sequence[float],
    *,
    include_validity_check: bool = True,
    separation_threshold: Optional[float] = None,
) -> MSensitivityResult:
    """Compute M-sensitivity analysis from a pretest result snapshot.

    Evaluates the pre-test decision function phi(M) = 1{S_pre > M} across a
    grid of threshold values, identifying the breakdown point and reporting
    regions where confidence intervals remain valid.

    Parameters
    ----------
    snapshot : PretestResultSnapshot
        Result from compute_pretest_snapshot() or pretest_from_dataframe().
        Must have S_pre, delta_bar, kappa, f_alpha, n in
        canonical["scalars"].
    m_values : sequence of float
        Threshold values M to evaluate. Recommended: linspace(0,
        1.5*s_pre_hat, 100). Should include values both below and above
        the breakdown point M* = s_pre_hat.
    include_validity_check : bool, default True
        If True, compute ``|S_pre - M|`` to check theoretical separation
        condition omega(n^{-1/2}).
    separation_threshold : float, optional
        Estimate of omega(n^{-1/2}) for validity region. If None,
        use heuristic: 2 / sqrt(n).

    Returns
    -------
    MSensitivityResult
        Complete sensitivity analysis including breakdown point,
        reporting table, CI bounds, and validity regions.

    Raises
    ------
    ValueError
        If snapshot does not contain required fields or m_values is empty.

    References
    ----------
    Mikhaeil & Harshaw (2026), Theorem 2, Section 5.1.
    """
    # Extract required scalars from the snapshot
    scalars = snapshot.canonical.get("scalars", {})

    required_fields = ("S_pre", "delta_bar", "kappa", "f_alpha", "n")
    missing = [f for f in required_fields if f not in scalars]
    if missing:
        available = sorted(scalars.keys())
        raise ValueError(
            f"snapshot.canonical['scalars'] is missing required fields: "
            f"{missing}. Available fields: {available}"
        )

    try:
        s_pre_hat = float(scalars["S_pre"])
        delta_bar = float(scalars["delta_bar"])
        kappa = float(scalars["kappa"])
        f_alpha = float(scalars["f_alpha"])
        n = int(scalars["n"])
    except (ValueError, TypeError) as exc:
        available = sorted(scalars.keys())
        raise ValueError(
            f"Could not convert scalar fields to numeric types. "
            f"Available fields: {available}"
        ) from exc

    # Optional: severity standard error
    s_pre_se = scalars.get("S_pre_se")
    if s_pre_se is not None:
        try:
            s_pre_se = float(s_pre_se)
        except (ValueError, TypeError):
            s_pre_se = None

    # Get alpha from simulation diagnostics
    diagnostics = snapshot.diagnostics.get("simulation", {})
    alpha = float(diagnostics.get("alpha", 0.05))
    if not (0 < alpha < 1):
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")

    # Validate m_values
    m_list = list(m_values)
    if not m_list:
        raise ValueError("m_values must be non-empty")

    m_sorted = sorted(m_list)
    m_tuple = tuple(float(m) for m in m_sorted)

    # Compute phi(M) for each M
    phi_list: list[int] = []
    can_report_list: list[bool] = []

    for m in m_tuple:
        if not math.isfinite(m) or m <= 0:
            raise ValueError(f"M values must be positive and finite; got {m}")

        if s_pre_hat > 0 and (m < s_pre_hat / 1000 or m > 1000 * s_pre_hat):
            warnings.warn(
                f"M={m:.6g} is far from S_pre_hat={s_pre_hat:.6g}. "
                f"Consider using M values in "
                f"[{s_pre_hat * 0.1:.4g}, {s_pre_hat * 3:.4g}] "
                f"for informative sensitivity analysis.",
                stacklevel=2,
            )

        # phi = 1{S_pre > M}
        phi_m = 1 if s_pre_hat > m else 0
        phi_list.append(phi_m)

        # CI can be reported when phi = 0 (pre-test passes)
        can_report_list.append(phi_m == 0)

    phi_tuple = tuple(phi_list)
    can_report_tuple = tuple(can_report_list)

    # Breakdown point
    breakdown_point = s_pre_hat

    # CI computation (independent of M)
    ci_half_width = kappa * s_pre_hat + f_alpha / math.sqrt(n)
    ci_lower = delta_bar - ci_half_width
    ci_upper = delta_bar + ci_half_width

    # Validity check (optional)
    validity_separations = None
    sep_threshold: float
    if separation_threshold is not None:
        sep_threshold = separation_threshold
    else:
        sep_threshold = 2.0 / math.sqrt(n)

    if include_validity_check:
        separations = []
        for m in m_tuple:
            sep = abs(s_pre_hat - m)
            separations.append(sep)
        validity_separations = tuple(separations)

    return MSensitivityResult(
        s_pre_hat=s_pre_hat,
        s_pre_se=s_pre_se,
        n=n,
        delta_bar=delta_bar,
        kappa=kappa,
        f_alpha=f_alpha,
        alpha=alpha,
        m_values=m_tuple,
        phi_values=phi_tuple,
        can_report=can_report_tuple,
        breakdown_point=breakdown_point,
        validity_separations=validity_separations,
        separation_threshold=sep_threshold,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        ci_half_width=ci_half_width,
    )
