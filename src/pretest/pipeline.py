from __future__ import annotations

import math
from collections.abc import Sequence
from statistics import NormalDist

from .api import PretestCommandSpec, parse_stata_command
from .confidence_intervals import compute_ci_half_width, resolve_ci_availability
from .kappa import compute_kappa
from .result_schema import PretestResultSnapshot, apply_kernel_outputs, seed_result_snapshot
from .severity import classify_pretest, compute_severity, normalize_p_norm
from .simulation import compute_critical_value
from .validation import DatasetProfile, ValidationState, apply_validation_outcome, run_validation


def _coerce_spec(command_or_spec: str | PretestCommandSpec) -> PretestCommandSpec:
    if isinstance(command_or_spec, PretestCommandSpec):
        return command_or_spec
    if not isinstance(command_or_spec, str):
        raise ValueError("command_or_spec must be a Stata command string or PretestCommandSpec")
    return parse_stata_command(command_or_spec)


def _normalize_sample_size(sample_size: int | float | None) -> int:
    if sample_size is None or isinstance(sample_size, (str, bytes, bytearray, bool)):
        raise ValueError("sample_size is required for valid pretest snapshots")
    try:
        normalized = float(sample_size)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError("sample_size is required for valid pretest snapshots") from exc
    if not math.isfinite(normalized) or not normalized.is_integer() or normalized < 1:
        raise ValueError("sample_size must be a positive integer")
    return int(normalized)


def _normalize_optional_nonnegative_float(
    name: str,
    value: int | float | None,
) -> float | None:
    if value is None:
        return None
    if isinstance(value, (str, bytes, bytearray, bool)):
        raise ValueError(f"{name} must be finite and nonnegative")
    try:
        normalized = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be finite and nonnegative") from exc
    if not math.isfinite(normalized) or normalized < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return normalized


def _normalize_required_finite_float(name: str, value: int | float | None) -> float:
    if value is None or isinstance(value, (str, bytes, bytearray, bool)):
        raise ValueError(f"{name} must be finite")
    try:
        normalized = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be finite") from exc
    if not math.isfinite(normalized):
        raise ValueError(f"{name} must be finite")
    return normalized


def _normalize_boolean_flag(name: str, value: bool) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


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


def _normalize_covariance_form(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("covariance_form must be either 'iterative' or 'overall'")
    normalized = value.strip().lower()
    if normalized not in {"iterative", "overall"}:
        raise ValueError("covariance_form must be either 'iterative' or 'overall'")
    return normalized


def _normalize_pre_violations_form(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("pre_violations_form must be either 'iterative' or 'overall'")
    normalized = value.strip().lower()
    if normalized not in {"iterative", "overall"}:
        raise ValueError("pre_violations_form must be either 'iterative' or 'overall'")
    return normalized


def _iterative_values_from_cumulative(values: Sequence[float]) -> tuple[float, ...]:
    differences: list[float] = []
    previous = 0.0
    for value in values:
        current = float(value)
        differences.append(current - previous)
        previous = current
    return tuple(differences)


def _resolve_t_post(
    *,
    spec: PretestCommandSpec,
    profile: DatasetProfile,
    t_post: int | float | None,
) -> int | float:
    if t_post is not None:
        return t_post
    if spec.treat_time is None:
        raise ValueError("t_post is required when treat_time is not available")
    if not profile.time_periods:
        raise ValueError("t_post is required when profile.time_periods is empty")

    observed_periods = sorted(set(profile.time_periods))
    inferred_t_post = sum(period >= spec.treat_time for period in observed_periods)
    if inferred_t_post < 1:
        raise ValueError("t_post must resolve to a positive post-treatment horizon")
    return inferred_t_post


def _resolve_t_pre(
    *,
    profile: DatasetProfile,
    t_post: int | float,
) -> int:
    observed_period_count = len(set(profile.time_periods))
    post_period_count = _normalize_positive_integer("t_post", t_post)
    pre_period_count = observed_period_count - post_period_count
    if pre_period_count < 2:
        raise ValueError("t_pre must be >= 2")
    return pre_period_count


def _resolved_time_scalars(
    *,
    spec: PretestCommandSpec,
    profile: DatasetProfile,
    t_pre: int,
    t_post: int | float,
) -> dict[str, int]:
    observed_periods = sorted(set(profile.time_periods))
    if spec.treat_time is None or not observed_periods:
        return {}
    t0_index = sum(period < spec.treat_time for period in observed_periods) + 1
    return {
        "T": len(observed_periods),
        "t0": t0_index,
        "T_pre": t_pre,
        "T_post": _normalize_positive_integer("t_post", t_post),
        "is_panel": int(profile.is_panel),
    }


def _with_time_scalars(
    snapshot: PretestResultSnapshot,
    *,
    time_scalars: dict[str, int],
) -> PretestResultSnapshot:
    if not time_scalars:
        return snapshot
    canonical = {
        "scalars": dict(snapshot.canonical["scalars"]),
        "macros": dict(snapshot.canonical["macros"]),
        "matrices": dict(snapshot.canonical["matrices"]),
    }
    canonical["scalars"].update(time_scalars)
    return PretestResultSnapshot(
        provenance=dict(snapshot.provenance),
        canonical=canonical,
        compatibility=dict(snapshot.compatibility),
        replay_contract=dict(snapshot.replay_contract),
        graph_status=dict(snapshot.graph_status),
        oracle=dict(snapshot.oracle),
        diagnostics=dict(snapshot.diagnostics),
    )


def _validate_nu_vector_dimension(
    *,
    nu_vector: Sequence[float],
    t_pre: int,
) -> None:
    expected_dimension = t_pre - 1
    actual_dimension = len(nu_vector)
    if actual_dimension != expected_dimension:
        raise ValueError(
            f"nu_vector dimension mismatch: expected {expected_dimension} but got {actual_dimension}"
        )


def _missing_kernel_inputs(
    *,
    nu_vector: Sequence[float] | None,
    f_alpha: float | None,
    delta_bar: float | None,
    sample_size: int | float | None,
    covariance_matrix: Sequence[Sequence[float]] | None,
) -> list[str]:
    missing: list[str] = []
    if nu_vector is None:
        missing.append("nu_vector")
    if f_alpha is None and covariance_matrix is None:
        missing.append("f_alpha")
    if delta_bar is None:
        missing.append("delta_bar")
    if sample_size is None:
        missing.append("sample_size")
    return missing


def _conventional_ci_pair(
    *,
    delta_bar: float,
    alpha: float,
    se_delta_bar: float | None,
    variance_available: bool,
) -> tuple[float | None, float | None]:
    if not variance_available or se_delta_bar is None:
        return (None, None)
    conventional_half_width = NormalDist().inv_cdf(1.0 - alpha / 2.0) * se_delta_bar
    return (
        delta_bar - conventional_half_width,
        delta_bar + conventional_half_width,
    )


def compute_pretest_snapshot(
    command_or_spec: str | PretestCommandSpec,
    profile: DatasetProfile,
    *,
    nu_vector: Sequence[float] | None = None,
    f_alpha: float | None = None,
    covariance_matrix: Sequence[Sequence[float]] | None = None,
    covariance_form: str = "iterative",
    simulations: int | float | None = None,
    seed: int | float | None = None,
    delta_bar: float | None = None,
    se_delta_bar: float | None = None,
    sample_size: int | float | None = None,
    t_post: int | float | None = None,
    case_id: str | None = None,
    variance_available: bool = True,
    nu_bar_vector: Sequence[float] | None = None,
    pre_violations_form: str = "iterative",
    s_pre_se: float | None = None,
    theta: Sequence[float] | None = None,
    graph_state: str | None = None,
) -> PretestResultSnapshot:
    """Compute a complete pre-test result snapshot from raw inputs.

    Orchestrates the full pre-test pipeline: validation, severity
    computation, classification, critical value simulation (if needed),
    and confidence interval construction.

    Parameters
    ----------
    command_or_spec : str or PretestCommandSpec
        Stata-style command string or parsed command specification.
    profile : DatasetProfile
        Dataset profile with time periods and treatment values.
    nu_vector : sequence of float or None, optional
        Pre-treatment violation estimates.
    f_alpha : float or None, optional
        Pre-computed critical value. If None, computed via Monte Carlo.
    covariance_matrix : sequence of sequence of float or None, optional
        Estimated covariance matrix for Monte Carlo simulation.
    covariance_form : {'iterative', 'overall'}, default 'iterative'
        Coordinate system of the supplied covariance matrix.
    simulations : int or None, optional
        Number of Monte Carlo draws. Defaults to spec.simulate.
    seed : int or None, optional
        Random seed. Defaults to spec.seed.
    delta_bar : float or None, optional
        Estimated treatment effect (required when data is valid).
    se_delta_bar : float or None, optional
        Standard error of delta_bar for conventional CI.
    sample_size : int or None, optional
        Number of observations (required when data is valid).
    t_post : int or None, optional
        Post-treatment periods. Inferred from profile if not given.
    case_id : str or None, optional
        Identifier for this estimation case.
    variance_available : bool, default True
        Whether standard-error information is available.
    nu_bar_vector : sequence of float or None, optional
        Cumulative violation vector for overall mode.
    pre_violations_form : {'iterative', 'overall'}, default 'iterative'
        Coordinate system of the supplied nu_vector.
    s_pre_se : float or None, optional
        Standard error of the severity estimate.
    theta : sequence of float or None, optional
        Full parameter vector theta.
    graph_state : str or None, optional
        Graph export state label.

    Returns
    -------
    PretestResultSnapshot
        Complete result snapshot with all computed fields.

    Raises
    ------
    ValueError
        If required inputs are missing or inconsistent.
    """
    spec = _coerce_spec(command_or_spec)
    base_state = run_validation(spec, profile, case_id=case_id)
    seeded_snapshot = seed_result_snapshot(spec)
    validated_snapshot = apply_validation_outcome(seeded_snapshot, base_state)
    if base_state.data_valid == 0:
        return validated_snapshot

    missing_inputs = _missing_kernel_inputs(
        nu_vector=nu_vector,
        f_alpha=f_alpha,
        delta_bar=delta_bar,
        sample_size=sample_size,
        covariance_matrix=covariance_matrix,
    )
    if missing_inputs:
        raise ValueError(
            "valid pretest snapshots require "
            + ", ".join(missing_inputs)
        )
    resolved_delta_bar = _normalize_required_finite_float("delta_bar", delta_bar)

    mode = "overall" if spec.overall else "iterative"
    normalized_covariance_form = _normalize_covariance_form(covariance_form)
    if mode != "overall" and normalized_covariance_form == "overall":
        raise ValueError("covariance_form='overall' is only valid in overall mode")
    normalized_pre_violations_form = _normalize_pre_violations_form(
        pre_violations_form,
    )
    if mode != "overall" and normalized_pre_violations_form == "overall":
        raise ValueError("pre_violations_form='overall' is only valid in overall mode")
    resolved_t_post = _resolve_t_post(spec=spec, profile=profile, t_post=t_post)
    resolved_t_pre = _resolve_t_pre(profile=profile, t_post=resolved_t_post)
    _validate_nu_vector_dimension(nu_vector=nu_vector, t_pre=resolved_t_pre)
    resolved_sample_size = _normalize_sample_size(sample_size)
    resolved_se_delta_bar = _normalize_optional_nonnegative_float(
        "se_delta_bar",
        se_delta_bar,
    )
    resolved_variance_available = _normalize_boolean_flag(
        "variance_available",
        variance_available,
    )
    severity_nu_vector = nu_vector
    severity_nu_bar_vector = nu_bar_vector
    if mode == "overall" and normalized_pre_violations_form == "overall":
        severity_nu_vector = _iterative_values_from_cumulative(nu_vector)
        severity_nu_bar_vector = nu_bar_vector if nu_bar_vector is not None else nu_vector
    severity = compute_severity(
        nu_vector=severity_nu_vector,
        p_norm=spec.p,
        mode=mode,
        nu_bar_vector=severity_nu_bar_vector,
    )
    decision = classify_pretest(
        s_pre_hat=severity,
        threshold_m=spec.threshold,
    )
    classified_state = ValidationState(
        data_valid=1,
        phi=decision.phi,
        pretest_pass=decision.pretest_pass,
        case_id=case_id,
    )
    classified_snapshot = apply_validation_outcome(seeded_snapshot, classified_state)
    classified_snapshot = _with_time_scalars(
        classified_snapshot,
        time_scalars=_resolved_time_scalars(
            spec=spec,
            profile=profile,
            t_pre=resolved_t_pre,
            t_post=resolved_t_post,
        ),
    )
    conventional_variance_available = (
        resolved_variance_available and resolved_se_delta_bar is not None
    )
    availability = resolve_ci_availability(
        classified_state,
        variance_available=conventional_variance_available,
    )
    kappa = compute_kappa(
        t_post=resolved_t_post,
        p_norm=spec.p,
        mode=mode,
    )
    resolved_f_alpha = f_alpha
    simulation_diagnostics = None
    if resolved_f_alpha is None:
        if simulations is None:
            simulations = spec.simulate
        if seed is None:
            seed = spec.seed
        resolved_f_alpha = compute_critical_value(
            covariance_matrix=covariance_matrix,
            alpha=spec.alpha,
            simulations=simulations,
            t_pre=resolved_t_pre,
            t_post=resolved_t_post,
            p_norm=spec.p,
            kappa=kappa,
            seed=seed,
            mode=mode,
            covariance_form=normalized_covariance_form,
        )
        simulation_diagnostics = {
            "simulations": int(simulations),
            "seed": int(seed),
            "alpha": spec.alpha,
            "mode": mode,
            "covariance_form": normalized_covariance_form,
            "pre_violations_form": normalized_pre_violations_form,
            "t_pre": resolved_t_pre,
            "t_post": int(resolved_t_post),
            "p_norm": normalize_p_norm(spec.p),
            "kappa": kappa,
        }
    conditional_half_width = compute_ci_half_width(
        mode=mode,
        s_pre_hat=severity,
        kappa=kappa,
        f_alpha=resolved_f_alpha,
        n=resolved_sample_size,
    )
    ci_lower = None
    ci_upper = None
    if availability.conditional_available:
        ci_lower = resolved_delta_bar - conditional_half_width
        ci_upper = resolved_delta_bar + conditional_half_width
    ci_conv_lower, ci_conv_upper = _conventional_ci_pair(
        delta_bar=resolved_delta_bar,
        alpha=spec.alpha,
        se_delta_bar=resolved_se_delta_bar,
        variance_available=conventional_variance_available,
    )
    snapshot = apply_kernel_outputs(
        classified_snapshot,
        availability=availability,
        s_pre=severity,
        kappa=kappa,
        f_alpha=resolved_f_alpha,
        delta_bar=resolved_delta_bar,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        ci_conv_lower=ci_conv_lower,
        ci_conv_upper=ci_conv_upper,
        se_delta_bar=resolved_se_delta_bar,
        s_pre_se=s_pre_se,
        theta=theta,
        graph_state=graph_state,
    )
    snapshot.canonical["scalars"]["N"] = resolved_sample_size
    snapshot.canonical["scalars"]["n"] = resolved_sample_size
    if simulation_diagnostics is not None:
        snapshot.canonical["scalars"]["sims"] = simulation_diagnostics["simulations"]
        snapshot.canonical["scalars"]["seed"] = simulation_diagnostics["seed"]
        snapshot.provenance["simulate"] = simulation_diagnostics["simulations"]
        snapshot.provenance["seed"] = simulation_diagnostics["seed"]
        snapshot.diagnostics["simulation"] = simulation_diagnostics
    return snapshot
