from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
import random
from statistics import NormalDist

from ._compat import frozen_slots_dataclass
from ._display import simulation_coverage_html, simulation_coverage_str
from .kappa import compute_kappa
from .severity import compute_severity, normalize_mode, normalize_p_norm


_PSD_TOLERANCE = 1e-12


@frozen_slots_dataclass
class SimulationCoverageResult(Mapping[str, int | float | None]):
    """Result of a Monte Carlo coverage simulation.

    Contains coverage rates, pass rates, and CI widths from a coverage
    experiment that evaluates the finite-sample performance of the
    conditional pre-test confidence interval.

    Attributes
    ----------
    replications : int
        Total number of simulation replications.
    pass_count : int
        Number of replications where the pre-test passed.
    covered_when_passed : int
        Number of passing replications where the conditional CI covers.
    conventional_covered_when_passed : int
        Number of passing replications where the conventional CI covers.
    pass_rate : float
        Fraction of replications passing the pre-test.
    conditional_coverage : float or None
        Coverage rate conditional on passing, or None if pass_count = 0.
    conventional_conditional_coverage : float or None
        Conventional coverage conditional on passing.
    valid_reporting_rate : float
        Unconditional rate of correct reporting (covered and passed).
    conventional_valid_reporting_rate : float
        Unconditional conventional correct reporting rate.
    mean_ci_width_when_passed : float or None
        Average conditional CI width among passing replications.
    mean_conventional_ci_width_when_passed : float or None
        Average conventional CI width among passing replications.
    critical_value : float or None
        The simulated critical value used.
    conditional_coverage_standard_error : float or None
        Standard error of the conditional coverage estimate.
    conventional_conditional_coverage_standard_error : float or None
        Standard error of the conventional conditional coverage.
    valid_reporting_rate_standard_error : float or None
        Standard error of the valid reporting rate.
    conventional_valid_reporting_rate_standard_error : float or None
        Standard error of the conventional valid reporting rate.
    """

    replications: int
    pass_count: int
    covered_when_passed: int
    conventional_covered_when_passed: int
    pass_rate: float
    conditional_coverage: float | None
    conventional_conditional_coverage: float | None
    valid_reporting_rate: float
    conventional_valid_reporting_rate: float
    mean_ci_width_when_passed: float | None
    mean_conventional_ci_width_when_passed: float | None
    critical_value: float | None = None
    conditional_coverage_standard_error: float | None = None
    conventional_conditional_coverage_standard_error: float | None = None
    valid_reporting_rate_standard_error: float | None = None
    conventional_valid_reporting_rate_standard_error: float | None = None

    def __str__(self) -> str:
        return simulation_coverage_str(self)

    def _repr_html_(self) -> str:
        return simulation_coverage_html(self)

    def __getitem__(self, key: str) -> int | float | None:
        try:
            return self.to_dict()[key]
        except KeyError as exc:
            raise KeyError(f"Unknown SimulationCoverageResult field: {key}") from exc

    def __iter__(self):
        return iter(self.to_dict())

    def __len__(self) -> int:
        return len(self.to_dict())

    def keys(self):
        return self.to_dict().keys()

    def values(self):
        return self.to_dict().values()

    def items(self):
        return self.to_dict().items()

    def to_dict(self) -> dict[str, int | float | None]:
        return {
            "replications": self.replications,
            "pass_count": self.pass_count,
            "covered_when_passed": self.covered_when_passed,
            "conventional_covered_when_passed": self.conventional_covered_when_passed,
            "pass_rate": self.pass_rate,
            "conditional_coverage": self.conditional_coverage,
            "conventional_conditional_coverage": (
                self.conventional_conditional_coverage
            ),
            "valid_reporting_rate": self.valid_reporting_rate,
            "conventional_valid_reporting_rate": (
                self.conventional_valid_reporting_rate
            ),
            "mean_ci_width_when_passed": self.mean_ci_width_when_passed,
            "mean_conventional_ci_width_when_passed": (
                self.mean_conventional_ci_width_when_passed
            ),
            "critical_value": self.critical_value,
            "conditional_coverage_standard_error": (
                self.conditional_coverage_standard_error
            ),
            "conventional_conditional_coverage_standard_error": (
                self.conventional_conditional_coverage_standard_error
            ),
            "valid_reporting_rate_standard_error": (
                self.valid_reporting_rate_standard_error
            ),
            "conventional_valid_reporting_rate_standard_error": (
                self.conventional_valid_reporting_rate_standard_error
            ),
        }


def _normalize_positive_integer(name: str, value: int | float) -> int:
    if isinstance(value, (str, bytes, bytearray, bool)):
        raise ValueError(f"{name} must be a positive integer")
    try:
        normalized = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if not math.isfinite(normalized) or not normalized.is_integer() or normalized < 1:
        raise ValueError(f"{name} must be a positive integer")
    return int(normalized)


def _normalize_integer(name: str, value: int | float) -> int:
    if isinstance(value, (str, bytes, bytearray, bool)):
        raise ValueError(f"{name} must be an integer")
    try:
        normalized = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not math.isfinite(normalized) or not normalized.is_integer():
        raise ValueError(f"{name} must be an integer")
    return int(normalized)


def _normalize_simulations(value: int | float) -> int:
    simulations = _normalize_positive_integer("simulations", value)
    if simulations < 100:
        raise ValueError("simulations must be >= 100")
    return simulations


def _normalize_coverage_replications(value: int | float) -> int:
    return _normalize_positive_integer("coverage_replications", value)


def _normalize_pre_periods(value: int | float) -> int:
    pre_periods = _normalize_positive_integer("t_pre", value)
    if pre_periods < 2:
        raise ValueError("t_pre must be >= 2")
    return pre_periods


def _normalize_unit_interval(name: str, value: float | int) -> float:
    if isinstance(value, (str, bytes, bytearray, bool)):
        raise ValueError(f"{name} must be in (0, 1)")
    try:
        normalized = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be in (0, 1)") from exc
    if not math.isfinite(normalized) or normalized <= 0 or normalized >= 1:
        raise ValueError(f"{name} must be in (0, 1)")
    return normalized


def _normalize_nonnegative_float(name: str, value: float | int) -> float:
    if isinstance(value, (str, bytes, bytearray, bool)):
        raise ValueError(f"{name} must be finite and nonnegative")
    try:
        normalized = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be finite and nonnegative") from exc
    if not math.isfinite(normalized) or normalized < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return normalized


def _normalize_positive_float(name: str, value: float | int) -> float:
    if isinstance(value, (str, bytes, bytearray, bool)):
        raise ValueError(f"{name} must be positive")
    try:
        normalized = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be positive") from exc
    if not math.isfinite(normalized) or normalized <= 0:
        raise ValueError(f"{name} must be positive")
    return normalized


def _normalize_nonnegative_critical_value(name: str, value: float | int) -> float:
    normalized = _normalize_float(name, value)
    if normalized < 0:
        raise ValueError(f"{name} must be nonnegative")
    return normalized


def _normalize_optional_nonnegative_float(
    name: str,
    value: float | int | None,
) -> float | None:
    if value is None:
        return None
    normalized = _normalize_float(name, value)
    if normalized < 0:
        raise ValueError(f"{name} must be nonnegative")
    return normalized


def _binomial_standard_error(*, successes: int, trials: int) -> float | None:
    if trials < 1:
        return None
    rate = successes / trials
    return math.sqrt(rate * (1.0 - rate) / trials)


def _normalize_float(name: str, value: float | int) -> float:
    if isinstance(value, (str, bytes, bytearray, bool)):
        raise ValueError(f"{name} must be finite")
    try:
        normalized = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be finite") from exc
    if not math.isfinite(normalized):
        raise ValueError(f"{name} must be finite")
    return normalized


def _validate_overall_unit_kappa(kappa: float | int | None) -> None:
    if kappa is None:
        return
    normalized_kappa = _normalize_float("kappa", kappa)
    if not math.isclose(
        normalized_kappa,
        1.0,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError("overall mode requires kappa = 1")


def _normalize_coordinate_form(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be either 'iterative' or 'overall'")
    normalized = value.strip().lower()
    if normalized not in {"iterative", "overall"}:
        raise ValueError(f"{name} must be either 'iterative' or 'overall'")
    return normalized


def _normalize_covariance_form(value: str) -> str:
    return _normalize_coordinate_form("covariance_form", value)


def _resolve_simulation_kappa(
    *,
    mode: str,
    t_post: int,
    p_norm: float,
    kappa: float | int | None,
) -> float:
    if mode == "overall":
        _validate_overall_unit_kappa(kappa)
        return 1.0
    if kappa is None:
        return compute_kappa(t_post=t_post, p_norm=p_norm, mode=mode)
    return _normalize_positive_float("kappa", kappa)


def _normalize_numeric_sequence(name: str, values: Sequence[float]) -> tuple[float, ...]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise ValueError(f"{name} must be a non-string sequence of numerics")
    normalized: list[float] = []
    for index, value in enumerate(values):
        normalized.append(_normalize_float(f"{name}[{index}]", value))
    return tuple(normalized)


def _normalize_covariance_matrix(
    covariance_matrix: Sequence[Sequence[float]],
) -> tuple[tuple[float, ...], ...]:
    if (
        isinstance(covariance_matrix, (str, bytes, bytearray))
        or not isinstance(covariance_matrix, Sequence)
        or not covariance_matrix
    ):
        raise ValueError("covariance_matrix must be a non-empty square matrix")
    rows: list[tuple[float, ...]] = []
    for row_index, row in enumerate(covariance_matrix):
        rows.append(_normalize_numeric_sequence(f"covariance_matrix[{row_index}]", row))
    dimension = len(rows)
    if any(len(row) != dimension for row in rows):
        raise ValueError("covariance_matrix must be square")
    for row_index in range(dimension):
        for col_index in range(row_index + 1, dimension):
            if not math.isclose(
                rows[row_index][col_index],
                rows[col_index][row_index],
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise ValueError("covariance_matrix must be symmetric")
    return tuple(rows)


def _cholesky_lower_psd(matrix: tuple[tuple[float, ...], ...]) -> list[list[float]]:
    dimension = len(matrix)
    lower = [[0.0] * dimension for _ in range(dimension)]
    for row in range(dimension):
        for col in range(row + 1):
            prior = sum(lower[row][k] * lower[col][k] for k in range(col))
            residual = matrix[row][col] - prior
            if row == col:
                if residual < -_PSD_TOLERANCE or not math.isfinite(residual):
                    raise ValueError("covariance_matrix must be positive semidefinite")
                lower[row][col] = math.sqrt(max(residual, 0.0))
            elif lower[col][col] > _PSD_TOLERANCE:
                lower[row][col] = residual / lower[col][col]
            elif abs(residual) > _PSD_TOLERANCE:
                raise ValueError("covariance_matrix must be positive semidefinite")
    return lower


def _validate_positive_semidefinite_covariance(
    matrix: tuple[tuple[float, ...], ...],
) -> None:
    dimension = len(matrix)
    lower = [[0.0] * dimension for _ in range(dimension)]
    for row in range(dimension):
        for col in range(row + 1):
            prior = sum(lower[row][k] * lower[col][k] for k in range(col))
            residual = matrix[row][col] - prior
            if row == col:
                if residual < -_PSD_TOLERANCE:
                    raise ValueError("covariance_matrix must be positive semidefinite")
                lower[row][col] = math.sqrt(max(residual, 0.0))
            elif lower[col][col] > _PSD_TOLERANCE:
                lower[row][col] = residual / lower[col][col]
            elif abs(residual) > _PSD_TOLERANCE:
                raise ValueError("covariance_matrix must be positive semidefinite")


def _transform_covariance_for_overall_mode(
    covariance: tuple[tuple[float, ...], ...],
    *,
    pre_terms: int,
    post_periods: int,
) -> tuple[tuple[float, ...], ...]:
    dimension = pre_terms + post_periods
    transform = [[0.0] * dimension for _ in range(dimension)]
    for row in range(dimension):
        transform[row][row] = 1.0
    for row in range(pre_terms):
        for col in range(row):
            transform[row][col] = 1.0

    transformed: list[tuple[float, ...]] = []
    for row in range(dimension):
        transformed_row: list[float] = []
        for col in range(dimension):
            value = 0.0
            for left in range(dimension):
                left_factor = transform[row][left]
                if left_factor == 0.0:
                    continue
                for right in range(dimension):
                    right_factor = transform[col][right]
                    if right_factor == 0.0:
                        continue
                    value += left_factor * covariance[left][right] * right_factor
            transformed_row.append(value)
        transformed.append(tuple(transformed_row))
    return tuple(transformed)


def _cumulative_values(values: Sequence[float]) -> tuple[float, ...]:
    cumulative: list[float] = []
    running_total = 0.0
    for value in values:
        running_total += value
        cumulative.append(running_total)
    return tuple(cumulative)


def _iterative_values_from_cumulative(values: Sequence[float]) -> tuple[float, ...]:
    differences: list[float] = []
    previous = 0.0
    for value in values:
        differences.append(value - previous)
        previous = value
    return tuple(differences)


def _compute_pre_parameter_severity(
    values: Sequence[float],
    *,
    p_norm: float,
    mode: str,
) -> float:
    if mode == "overall":
        cumulative_values = tuple(values)
        return compute_severity(
            nu_vector=_iterative_values_from_cumulative(cumulative_values),
            nu_bar_vector=cumulative_values,
            p_norm=p_norm,
            mode="overall",
        )
    return compute_severity(
        nu_vector=values,
        p_norm=p_norm,
        mode="iterative",
    )


def _post_violation_mean_from_path(
    *,
    final_pre_overall_violation: float,
    true_post_violations: Sequence[float],
    post_violations_form: str,
    post_periods: int,
) -> float:
    normalized_post = _normalize_numeric_sequence(
        "true_post_violations",
        true_post_violations,
    )
    if len(normalized_post) != post_periods:
        raise ValueError(
            f"true_post_violations dimension mismatch: expected {post_periods} but got {len(normalized_post)}"
        )
    if post_violations_form == "overall":
        post_overall_violations = normalized_post
    else:
        post_overall_violations = tuple(
            final_pre_overall_violation + cumulative_post
            for cumulative_post in _cumulative_values(normalized_post)
        )
    return sum(post_overall_violations) / len(post_overall_violations)


def compute_section6_violation_path(
    *,
    t_start: int | float,
    t_end: int | float,
    total_periods: int | float,
    target_severity: float | int,
    p_norm: float | str,
) -> tuple[float, ...]:
    """Generate a violation path calibrated to a target severity.

    Constructs a deterministic violation path over [t_start, t_end] whose
    p-norm severity equals ``target_severity``, following the DGP
    construction in Mikhaeil & Harshaw (2026), Section 6.

    Parameters
    ----------
    t_start : int
        Start period of the violation window (>= 2).
    t_end : int
        End period of the violation window (<= total_periods).
    total_periods : int
        Total number of periods (>= 3).
    target_severity : float
        Desired severity value (nonnegative).
    p_norm : float or str
        Norm exponent p >= 1.

    Returns
    -------
    tuple of float
        Violation path of length (t_end - t_start + 1) with the
        specified severity.

    Raises
    ------
    ValueError
        If period indices are invalid or target is negative.
    """
    start = _normalize_positive_integer("t_start", t_start)
    end = _normalize_positive_integer("t_end", t_end)
    total = _normalize_positive_integer("total_periods", total_periods)
    if total < 3:
        raise ValueError("total_periods must be >= 3")
    if start < 2 or start > end or end > total:
        raise ValueError("require 2 <= t_start <= t_end <= total_periods")
    target = _normalize_nonnegative_float("target_severity", target_severity)
    normalized_p = normalize_p_norm(p_norm)
    period_count = end - start + 1
    if target == 0.0:
        return (0.0,) * period_count

    raw_path = tuple(
        math.log(total) * (math.sin(period) + math.cos(period / 2.0))
        for period in range(start, end + 1)
    )
    raw_severity = compute_severity(
        nu_vector=raw_path,
        p_norm=normalized_p,
        mode="iterative",
    )
    if raw_severity <= 0.0:
        raise ValueError("raw Section 6 severity must be positive")
    scale = target / raw_severity
    return tuple(scale * value for value in raw_path)


def _draw_gaussian_vector(
    *,
    lower_cholesky: list[list[float]],
    rng: random.Random,
) -> tuple[float, ...]:
    dimension = len(lower_cholesky)
    standard_normal = [rng.gauss(0.0, 1.0) for _ in range(dimension)]
    return tuple(
        sum(lower_cholesky[row][col] * standard_normal[col] for col in range(row + 1))
        for row in range(dimension)
    )


def _post_mean_error_variance(
    covariance: tuple[tuple[float, ...], ...],
    *,
    pre_terms: int,
) -> float:
    post_indices = range(pre_terms, len(covariance))
    post_count = len(covariance) - pre_terms
    variance = sum(
        covariance[row][col]
        for row in post_indices
        for col in post_indices
    ) / (post_count * post_count)
    if variance < -_PSD_TOLERANCE:
        raise ValueError("post-treatment mean variance must be nonnegative")
    return max(variance, 0.0)


def _compute_critical_value_from_lower(
    *,
    lower_cholesky: list[list[float]],
    rng: random.Random,
    alpha: float,
    simulations: int,
    t_pre: int,
    t_post: int,
    p_norm: float,
    mode: str,
    kappa: float | None,
) -> float:
    psi_values: list[float] = []
    for _ in range(simulations):
        draw = _draw_gaussian_vector(lower_cholesky=lower_cholesky, rng=rng)
        psi_values.append(
            compute_psi(
                error_vector=draw,
                t_pre=t_pre,
                t_post=t_post,
                p_norm=p_norm,
                mode=mode,
                kappa=kappa,
            )
    )

    psi_values.sort()
    if psi_values[-1] == 0.0:
        return 0.0
    # The paper's tail rule uses `>= c_f`, so the discrete Monte Carlo
    # estimator must step one order statistic to the right to keep the
    # empirical tail probability at or below alpha.
    quantile_index = math.ceil(simulations * (1.0 - alpha)) + 1
    if quantile_index > simulations:
        return math.nextafter(psi_values[-1], math.inf)
    quantile_index = max(1, quantile_index)
    return psi_values[quantile_index - 1]


def compute_psi(
    error_vector: Sequence[float],
    *,
    t_pre: int | float,
    t_post: int | float,
    p_norm: float | str,
    mode: str = "iterative",
    kappa: float | None = None,
) -> float:
    """Compute the psi statistic for a single Monte Carlo draw.

    Evaluates psi(e) = ``|mean(e_post)|`` + kappa * S_pre(e_pre), which is
    the test statistic whose quantile defines the critical value f_alpha.

    Parameters
    ----------
    error_vector : sequence of float
        Joint error vector of dimension (T_pre - 1) + T_post.
    t_pre : int
        Number of pre-treatment periods (>= 2).
    t_post : int
        Number of post-treatment periods (>= 1).
    p_norm : float or str
        Norm exponent p >= 1.
    mode : {'iterative', 'overall'}, default 'iterative'
        Aggregation mode.
    kappa : float or None, optional
        Extrapolation constant. Computed internally if None.

    Returns
    -------
    float
        Nonnegative psi value.

    Notes
    -----
    .. math::
        \\psi(\\mathbf{e}) = |\\bar{e}_{\\text{post}}|
        + \\kappa \\cdot S_{\\text{pre}}(\\mathbf{e}_{\\text{pre}})
    """
    normalized_mode = normalize_mode(mode)
    pre_periods = _normalize_pre_periods(t_pre)
    post_periods = _normalize_positive_integer("t_post", t_post)
    normalized_p = normalize_p_norm(p_norm)
    pre_terms = pre_periods - 1
    vector = _normalize_numeric_sequence("error_vector", error_vector)
    expected_dimension = pre_terms + post_periods
    if len(vector) != expected_dimension:
        raise ValueError(
            f"error_vector dimension mismatch: expected {expected_dimension} but got {len(vector)}"
        )

    post_vector = vector[pre_terms:]
    post_component = abs(sum(post_vector) / len(post_vector))
    if pre_terms < 1:
        return post_component

    severity = compute_severity(
        nu_vector=vector[:pre_terms],
        p_norm=normalized_p,
        mode="iterative",
    )
    if normalized_mode == "overall":
        _validate_overall_unit_kappa(kappa)
        return post_component + severity
    resolved_kappa = _resolve_simulation_kappa(
        mode=normalized_mode,
        t_post=post_periods,
        p_norm=normalized_p,
        kappa=kappa,
    )
    return post_component + resolved_kappa * severity


def compute_critical_value(
    covariance_matrix: Sequence[Sequence[float]],
    *,
    alpha: float | int = 0.05,
    simulations: int | float = 5000,
    t_pre: int | float | None = None,
    t_post: int | float = 1,
    p_norm: float | str = 2,
    mode: str = "iterative",
    kappa: float | None = None,
    seed: int | float = 12345,
    covariance_form: str = "iterative",
) -> float:
    """Compute the critical value f_alpha via Monte Carlo simulation.

    Draws from N(0, Sigma_hat) and computes the (1-alpha) quantile of
    the psi distribution, following Mikhaeil & Harshaw (2026), Section 5.

    Parameters
    ----------
    covariance_matrix : sequence of sequence of float
        Estimated covariance matrix of dimension (T_pre-1 + T_post).
    alpha : float, default 0.05
        Significance level in (0, 1).
    simulations : int, default 5000
        Number of Monte Carlo draws (>= 100).
    t_pre : int or None, optional
        Pre-treatment periods. Inferred from matrix dimension if None.
    t_post : int, default 1
        Post-treatment periods.
    p_norm : float or str, default 2
        Norm exponent p >= 1.
    mode : {'iterative', 'overall'}, default 'iterative'
        Aggregation mode.
    kappa : float or None, optional
        Extrapolation constant. Computed internally if None.
    seed : int, default 12345
        Random seed for reproducibility.
    covariance_form : {'iterative', 'overall'}, default 'iterative'
        Coordinate system of the supplied covariance matrix.

    Returns
    -------
    float
        Nonnegative critical value f_alpha.

    Raises
    ------
    ValueError
        If the covariance matrix is not positive semidefinite, or
        dimensions are inconsistent.

    Notes
    -----
    .. math::
        f_\\alpha(\\hat{\\Sigma}) = \\inf\\{c :\\;
        P(\\psi(\\mathbf{e}) \\geq c) \\leq \\alpha\\}
    """
    covariance = _normalize_covariance_matrix(covariance_matrix)
    _validate_positive_semidefinite_covariance(covariance)
    alpha_value = _normalize_unit_interval("alpha", alpha)
    simulation_count = _normalize_simulations(simulations)
    post_periods = _normalize_positive_integer("t_post", t_post)
    if t_pre is None:
        inferred_pre_periods = len(covariance) - post_periods + 1
        if inferred_pre_periods < 2:
            raise ValueError("t_pre could not be inferred from covariance_matrix and t_post")
        pre_periods = inferred_pre_periods
    else:
        pre_periods = _normalize_pre_periods(t_pre)
    normalized_mode = normalize_mode(mode)
    normalized_covariance_form = _normalize_covariance_form(covariance_form)
    if normalized_mode != "overall" and normalized_covariance_form == "overall":
        raise ValueError("covariance_form='overall' is only valid in overall mode")
    normalized_p = normalize_p_norm(p_norm)
    normalized_seed = _normalize_integer("seed", seed)
    dimension = len(covariance)
    expected_dimension = (pre_periods - 1) + post_periods
    if dimension != expected_dimension:
        raise ValueError(
            f"covariance_matrix dimension mismatch: expected {expected_dimension} but got {dimension}"
        )
    resolved_kappa = _resolve_simulation_kappa(
        mode=normalized_mode,
        t_post=post_periods,
        p_norm=normalized_p,
        kappa=kappa,
    )
    if normalized_mode == "overall" and normalized_covariance_form == "iterative":
        covariance = _transform_covariance_for_overall_mode(
            covariance,
            pre_terms=pre_periods - 1,
            post_periods=post_periods,
        )

    lower = _cholesky_lower_psd(covariance)
    return _compute_critical_value_from_lower(
        lower_cholesky=lower,
        rng=random.Random(normalized_seed),
        alpha=alpha_value,
        simulations=simulation_count,
        t_pre=pre_periods,
        t_post=post_periods,
        p_norm=normalized_p,
        mode=normalized_mode,
        kappa=resolved_kappa,
    )


def simulate_coverage(
    *,
    true_effect: float | int,
    delta_bar_draws: Sequence[float],
    s_pre_draws: Sequence[float],
    f_alpha: float | int,
    sample_size: int | float,
    threshold_m: float | int,
    mode: str = "iterative",
    kappa: float | None = None,
    conventional_half_width: float | int | None = None,
) -> SimulationCoverageResult:
    """Evaluate coverage from pre-drawn severity and effect estimates.

    Given paired draws of (delta_bar, S_pre), applies the pre-test
    classification and computes conditional and conventional coverage
    rates.

    Parameters
    ----------
    true_effect : float
        True treatment effect for coverage evaluation.
    delta_bar_draws : sequence of float
        Simulated treatment-effect estimates.
    s_pre_draws : sequence of float
        Simulated severity estimates (same length as delta_bar_draws).
    f_alpha : float
        Critical value (nonnegative).
    sample_size : int
        Sample size for CI width scaling.
    threshold_m : float
        Positive pre-test threshold M.
    mode : {'iterative', 'overall'}, default 'iterative'
        Aggregation mode.
    kappa : float or None, optional
        Extrapolation constant (required in iterative mode).
    conventional_half_width : float or None, optional
        Fixed conventional CI half-width. Computed from f_alpha if None.

    Returns
    -------
    SimulationCoverageResult
        Frozen result with coverage rates and diagnostic statistics.

    Raises
    ------
    ValueError
        If draws are empty or have mismatched lengths.
    """
    effect = _normalize_float("true_effect", true_effect)
    deltas = _normalize_numeric_sequence("delta_bar_draws", delta_bar_draws)
    severities = _normalize_numeric_sequence("s_pre_draws", s_pre_draws)
    if len(deltas) != len(severities):
        raise ValueError("delta_bar_draws and s_pre_draws must have equal length")
    if not deltas:
        raise ValueError("coverage simulation requires at least one replication")
    critical_value = _normalize_nonnegative_critical_value("f_alpha", f_alpha)
    sample = _normalize_positive_integer("sample_size", sample_size)
    threshold = _normalize_float("threshold_m", threshold_m)
    if threshold <= 0:
        raise ValueError("threshold_m must be positive")
    normalized_mode = normalize_mode(mode)
    if normalized_mode == "overall":
        multiplier = _resolve_simulation_kappa(
            mode=normalized_mode,
            t_post=1,
            p_norm=1.0,
            kappa=kappa,
        )
    else:
        multiplier = _normalize_positive_float("kappa", kappa)
    normalized_conventional_half_width = _normalize_optional_nonnegative_float(
        "conventional_half_width",
        conventional_half_width,
    )

    pass_count = 0
    covered = 0
    conventional_covered = 0
    ci_widths: list[float] = []
    conventional_ci_widths: list[float] = []
    resolved_conventional_half_width = (
        normalized_conventional_half_width
        if normalized_conventional_half_width is not None
        else critical_value / math.sqrt(sample)
    )
    for delta_bar, severity in zip(deltas, severities):
        normalized_severity = _normalize_nonnegative_float("s_pre_draw", severity)
        if normalized_severity > threshold:
            continue
        pass_count += 1
        half_width = multiplier * normalized_severity + critical_value / math.sqrt(sample)
        ci_widths.append(2.0 * half_width)
        conventional_ci_widths.append(2.0 * resolved_conventional_half_width)
        lower = delta_bar - half_width
        upper = delta_bar + half_width
        if lower <= effect <= upper:
            covered += 1
        conventional_lower = delta_bar - resolved_conventional_half_width
        conventional_upper = delta_bar + resolved_conventional_half_width
        if conventional_lower <= effect <= conventional_upper:
            conventional_covered += 1

    replications = len(deltas)
    return SimulationCoverageResult(
        replications=replications,
        pass_count=pass_count,
        covered_when_passed=covered,
        conventional_covered_when_passed=conventional_covered,
        pass_rate=pass_count / replications,
        conditional_coverage=(covered / pass_count if pass_count else None),
        conventional_conditional_coverage=(
            conventional_covered / pass_count if pass_count else None
        ),
        valid_reporting_rate=covered / replications,
        conventional_valid_reporting_rate=conventional_covered / replications,
        mean_ci_width_when_passed=(
            sum(ci_widths) / len(ci_widths) if ci_widths else None
        ),
        mean_conventional_ci_width_when_passed=(
            sum(conventional_ci_widths) / len(conventional_ci_widths)
            if conventional_ci_widths
            else None
        ),
        critical_value=critical_value,
        conditional_coverage_standard_error=_binomial_standard_error(
            successes=covered,
            trials=pass_count,
        ),
        conventional_conditional_coverage_standard_error=_binomial_standard_error(
            successes=conventional_covered,
            trials=pass_count,
        ),
        valid_reporting_rate_standard_error=_binomial_standard_error(
            successes=covered,
            trials=replications,
        ),
        conventional_valid_reporting_rate_standard_error=_binomial_standard_error(
            successes=conventional_covered,
            trials=replications,
        ),
    )


def simulate_coverage_from_covariance(
    *,
    true_effect: float | int,
    true_pre_violations: Sequence[float],
    covariance_matrix: Sequence[Sequence[float]],
    alpha: float | int,
    simulations: int | float,
    sample_size: int | float,
    threshold_m: float | int,
    t_pre: int | float,
    t_post: int | float,
    p_norm: float | str,
    mode: str = "iterative",
    kappa: float | None = None,
    seed: int | float = 12345,
    covariance_form: str = "iterative",
    pre_violations_form: str = "iterative",
    true_post_violation_mean: float | int | None = None,
    coverage_replications: int | float | None = None,
    true_post_violations: Sequence[float] | None = None,
    post_violations_form: str = "iterative",
) -> SimulationCoverageResult:
    """Run a full Monte Carlo coverage simulation from a covariance matrix.

    Combines critical-value simulation and coverage evaluation in a
    single call, generating draws from N(0, Sigma) scaled by sqrt(n).

    Parameters
    ----------
    true_effect : float
        True treatment effect.
    true_pre_violations : sequence of float
        True pre-treatment violation path.
    covariance_matrix : sequence of sequence of float
        Covariance matrix of dimension (T_pre-1 + T_post).
    alpha : float
        Significance level in (0, 1).
    simulations : int
        Number of Monte Carlo draws for the critical value (>= 100).
    sample_size : int
        Sample size for finite-sample scaling.
    threshold_m : float
        Positive pre-test threshold M.
    t_pre : int
        Number of pre-treatment periods (>= 2).
    t_post : int
        Number of post-treatment periods (>= 1).
    p_norm : float or str
        Norm exponent p >= 1.
    mode : {'iterative', 'overall'}, default 'iterative'
        Aggregation mode.
    kappa : float or None, optional
        Extrapolation constant.
    seed : int, default 12345
        Random seed.
    covariance_form : {'iterative', 'overall'}, default 'iterative'
        Coordinate system of the covariance matrix.
    pre_violations_form : {'iterative', 'overall'}, default 'iterative'
        Coordinate system of the true pre-violations.
    true_post_violation_mean : float or None, optional
        Mean post-treatment violation. Defaults to final cumulative
        pre-violation.
    coverage_replications : int or None, optional
        Number of coverage replications. Defaults to simulations.
    true_post_violations : sequence of float or None, optional
        Per-period post-treatment violations.
    post_violations_form : {'iterative', 'overall'}, default 'iterative'
        Coordinate system of true_post_violations.

    Returns
    -------
    SimulationCoverageResult
        Coverage simulation result with rates and diagnostics.

    Raises
    ------
    ValueError
        If dimensions are inconsistent or inputs are invalid.
    """
    effect = _normalize_float("true_effect", true_effect)
    covariance = _normalize_covariance_matrix(covariance_matrix)
    _validate_positive_semidefinite_covariance(covariance)
    alpha_value = _normalize_unit_interval("alpha", alpha)
    simulation_count = _normalize_simulations(simulations)
    replication_count = (
        simulation_count
        if coverage_replications is None
        else _normalize_coverage_replications(coverage_replications)
    )
    sample = _normalize_positive_integer("sample_size", sample_size)
    threshold = _normalize_float("threshold_m", threshold_m)
    if threshold <= 0:
        raise ValueError("threshold_m must be positive")
    pre_periods = _normalize_pre_periods(t_pre)
    post_periods = _normalize_positive_integer("t_post", t_post)
    normalized_mode = normalize_mode(mode)
    normalized_covariance_form = _normalize_covariance_form(covariance_form)
    normalized_pre_violations_form = _normalize_coordinate_form(
        "pre_violations_form",
        pre_violations_form,
    )
    normalized_post_violations_form = _normalize_coordinate_form(
        "post_violations_form",
        post_violations_form,
    )
    if normalized_mode != "overall" and normalized_covariance_form == "overall":
        raise ValueError("covariance_form='overall' is only valid in overall mode")
    if normalized_mode != "overall" and normalized_pre_violations_form == "overall":
        raise ValueError("pre_violations_form='overall' is only valid in overall mode")
    normalized_p = normalize_p_norm(p_norm)
    normalized_seed = _normalize_integer("seed", seed)
    pre_terms = pre_periods - 1
    expected_dimension = pre_terms + post_periods
    if len(covariance) != expected_dimension:
        raise ValueError(
            f"covariance_matrix dimension mismatch: expected {expected_dimension} but got {len(covariance)}"
        )
    normalized_true_pre = _normalize_numeric_sequence(
        "true_pre_violations",
        true_pre_violations,
    )
    if len(normalized_true_pre) != pre_terms:
        raise ValueError(
            f"true_pre_violations dimension mismatch: expected {pre_terms} but got {len(normalized_true_pre)}"
        )

    resolved_kappa = _resolve_simulation_kappa(
        mode=normalized_mode,
        t_post=post_periods,
        p_norm=normalized_p,
        kappa=kappa,
    )
    if normalized_mode == "overall" and normalized_covariance_form == "iterative":
        covariance = _transform_covariance_for_overall_mode(
            covariance,
            pre_terms=pre_terms,
            post_periods=post_periods,
        )
    if normalized_mode == "overall" and normalized_pre_violations_form == "overall":
        true_pre_parameter = normalized_true_pre
    elif normalized_mode == "overall":
        true_pre_parameter = _cumulative_values(normalized_true_pre)
    else:
        true_pre_parameter = normalized_true_pre
    final_pre_overall_violation = (
        true_pre_parameter[-1]
        if normalized_mode == "overall"
        else _cumulative_values(normalized_true_pre)[-1]
    )
    if true_post_violation_mean is not None and true_post_violations is not None:
        raise ValueError(
            "pass either true_post_violation_mean or true_post_violations, not both"
        )
    if true_post_violation_mean is None:
        if true_post_violations is None:
            post_violation_mean = final_pre_overall_violation
        else:
            post_violation_mean = _post_violation_mean_from_path(
                final_pre_overall_violation=final_pre_overall_violation,
                true_post_violations=true_post_violations,
                post_violations_form=normalized_post_violations_form,
                post_periods=post_periods,
            )
    else:
        post_violation_mean = _normalize_float(
            "true_post_violation_mean",
            true_post_violation_mean,
        )
    delta_bar_center = effect - post_violation_mean

    lower = _cholesky_lower_psd(covariance)
    rng = random.Random(normalized_seed)
    f_alpha = _compute_critical_value_from_lower(
        lower_cholesky=lower,
        rng=rng,
        alpha=alpha_value,
        simulations=simulation_count,
        t_pre=pre_periods,
        t_post=post_periods,
        p_norm=normalized_p,
        mode=normalized_mode,
        kappa=resolved_kappa,
    )
    conventional_half_width = (
        NormalDist().inv_cdf(1.0 - alpha_value / 2.0)
        * math.sqrt(
            _post_mean_error_variance(
                covariance,
                pre_terms=pre_terms,
            )
        )
        / math.sqrt(sample)
    )
    scale = math.sqrt(sample)
    delta_bar_draws: list[float] = []
    s_pre_draws: list[float] = []
    for _ in range(replication_count):
        error_vector = _draw_gaussian_vector(lower_cholesky=lower, rng=rng)
        pre_parameter_draw = tuple(
            true_value + error_value / scale
            for true_value, error_value in zip(
                true_pre_parameter,
                error_vector[:pre_terms],
            )
        )
        s_pre_draws.append(
            _compute_pre_parameter_severity(
                pre_parameter_draw,
                p_norm=normalized_p,
                mode=normalized_mode,
            )
        )
        post_errors = error_vector[pre_terms:]
        delta_bar_draws.append(
            delta_bar_center + sum(post_errors) / len(post_errors) / scale
        )

    return simulate_coverage(
        true_effect=effect,
        delta_bar_draws=delta_bar_draws,
        s_pre_draws=s_pre_draws,
        f_alpha=f_alpha,
        sample_size=sample,
        threshold_m=threshold,
        mode=normalized_mode,
        kappa=resolved_kappa,
        conventional_half_width=conventional_half_width,
    )
