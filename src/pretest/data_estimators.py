from __future__ import annotations

from collections.abc import Mapping, Sequence
import csv
from importlib import resources as importlib_resources
import math
from pathlib import Path
import random

import yaml

from .kappa import compute_kappa
from .severity import compute_severity, normalize_mode
from .simulation import compute_critical_value, compute_psi

_NEGATIVE_VARIANCE_TOLERANCE = 1e-12
_PROP99_WINDOW_ITER_CRITICAL_VALUE_PROBE = (
    "data/prop99_replay/results/stata/"
    "PROP99-WINDOW-1985-1995-M5-ITER-critical-value-probe.yaml"
)
_PROP99_WINDOW_ITER_STATA_STORED_RESULTS = (
    "data/prop99_replay/results/stata/"
    "PROP99-WINDOW-1985-1995-M5-ITER-stored-results.yaml"
)
_PROP99_WINDOW_OVERALL_STATA_STORED_RESULTS = (
    "data/prop99_replay/results/stata/"
    "PROP99-WINDOW-1985-1995-M5-OVERALL-stored-results.yaml"
)
_PROP99_WINDOW_ITER_RECORDS = (
    "data/prop99_replay/prop99_window_1985_1995_m5_iter_records.csv"
)
_PROP99_WINDOW_ITER_CRITICAL_VALUE_METHOD_AUTHORITY = (
    "paper/pretest_paper.md Appendix D.5",
    "pretest-stata/mata/_pretest_psi.mata::_pretest_critical_value()",
)
_PROP99_WINDOW_ITER_RNG_PROBE_SOURCE = (
    "stata-mp stdin: rseed(12345); W=rnormal(10,1,0,1); "
    "Z=cholesky(Sigma+1e-10*I(10))*W"
)
_PROP99_WINDOW_ITER_ORDER_PROBE_SOURCE = (
    'stata-mp stdin: quietly pretest ...; Sigma=st_matrix("e(Sigma)"); '
    "sort 5000 Mata psi draws"
)


def _load_packaged_yaml(relative_path: str, *, callable_name: str) -> dict[str, object]:
    try:
        raw_payload = (
            importlib_resources.files("pretest")
            .joinpath(relative_path)
            .read_text(encoding="utf-8")
        )
        payload = yaml.safe_load(raw_payload)
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise ValueError(
            f"{callable_name}() requires packaged YAML {relative_path}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise ValueError(
            f"{callable_name}() requires packaged YAML {relative_path} "
            "to contain a mapping"
        )
    return dict(payload)


def _validate_prop99_window_iter_record_dimensions(
    records: Sequence[Mapping[str, float | int]],
) -> None:
    _validate_prop99_window_iter_record_shape(
        records,
        callable_name="load_prop99_window_iter_records",
    )
    stored_results = _load_packaged_yaml(
        _PROP99_WINDOW_ITER_STATA_STORED_RESULTS,
        callable_name="load_prop99_window_iter_records",
    )
    numeric_payload = stored_results.get("numeric_payload")
    if not isinstance(numeric_payload, Mapping):
        raise ValueError(
            "load_prop99_window_iter_records() requires packaged Stata "
            "stored-results numeric_payload"
        )
    years = sorted({float(record["year"]) for record in records})
    if len(records) != numeric_payload.get("e(N)"):
        raise ValueError(
            "load_prop99_window_iter_records() requires record count to match "
            "Stata e(N)"
        )
    if len(years) != numeric_payload.get("e(T)"):
        raise ValueError(
            "load_prop99_window_iter_records() requires year count to match "
            "Stata e(T)"
        )
    pre_years = [year for year in years if year < 1989.0]
    post_years = [year for year in years if year >= 1989.0]
    if len(pre_years) != numeric_payload.get("e(T_pre)"):
        raise ValueError(
            "load_prop99_window_iter_records() requires pre-period count to "
            "match Stata e(T_pre)"
        )
    if len(post_years) != numeric_payload.get("e(T_post)"):
        raise ValueError(
            "load_prop99_window_iter_records() requires post-period count to "
            "match Stata e(T_post)"
        )
    if numeric_payload.get("e(t0)") != len(pre_years) + 1:
        raise ValueError(
            "load_prop99_window_iter_records() requires Stata e(t0) to equal "
            "T_pre + 1"
        )
    for year in years:
        treated_count = sum(
            1 for record in records if record["year"] == year and record["treated"] == 1
        )
        control_count = sum(
            1 for record in records if record["year"] == year and record["treated"] == 0
        )
        if treated_count != 1 or control_count != 38:
            raise ValueError(
                "load_prop99_window_iter_records() requires each year to contain "
                "1 treated and 38 control records"
            )


def _validate_prop99_window_iter_record_shape(
    records: Sequence[Mapping[str, float | int]],
    *,
    callable_name: str,
) -> None:
    years = sorted({float(record["year"]) for record in records})
    if years != [float(year) for year in range(1985, 1996)]:
        raise ValueError(f"{callable_name}() requires years 1985 through 1995")
    if len(records) != 429:
        raise ValueError(
            f"{callable_name}() requires 429 records for "
            "PROP99-WINDOW-1985-1995-M5-ITER"
        )
    pre_years = [year for year in years if year < 1989.0]
    post_years = [year for year in years if year >= 1989.0]
    if len(pre_years) != 4:
        raise ValueError(f"{callable_name}() requires four pre-treatment years")
    if len(post_years) != 7:
        raise ValueError(f"{callable_name}() requires seven post-treatment years")
    for year in years:
        treated_count = sum(
            1 for record in records if record["year"] == year and record["treated"] == 1
        )
        control_count = sum(
            1 for record in records if record["year"] == year and record["treated"] == 0
        )
        if treated_count != 1 or control_count != 38:
            raise ValueError(
                f"{callable_name}() requires each year to contain "
                "1 treated and 38 control records"
            )


def _parse_prop99_window_iter_records_csv(
    raw_payload: str,
    *,
    callable_name: str,
) -> tuple[dict[str, float | int], ...]:
    reader = csv.DictReader(raw_payload.splitlines())
    if reader.fieldnames != ["cigsale", "treated", "year"]:
        raise ValueError(f"{callable_name}() requires columns cigsale, treated, year")
    records: list[dict[str, float | int]] = []
    for index, row in enumerate(reader):
        try:
            treated = int(row["treated"])
            if treated not in {0, 1}:
                raise ValueError
            records.append(
                {
                    "cigsale": float(row["cigsale"]),
                    "treated": treated,
                    "year": float(row["year"]),
                }
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"{callable_name}() requires finite numeric row {index + 2}"
            ) from exc
    _validate_prop99_window_iter_record_shape(records, callable_name=callable_name)
    return tuple(records)


def load_prop99_window_iter_records() -> tuple[dict[str, float | int], ...]:
    """Load packaged Prop99 window records used by the deterministic evidence path."""

    try:
        raw_payload = (
            importlib_resources.files("pretest")
            .joinpath(_PROP99_WINDOW_ITER_RECORDS)
            .read_text(encoding="utf-8")
        )
    except FileNotFoundError as exc:
        raise ValueError(
            "load_prop99_window_iter_records() requires packaged CSV "
            f"{_PROP99_WINDOW_ITER_RECORDS}"
        ) from exc
    records = _parse_prop99_window_iter_records_csv(
        raw_payload,
        callable_name="load_prop99_window_iter_records",
    )
    _validate_prop99_window_iter_record_dimensions(records)
    return tuple(records)


def load_prop99_window_iter_records_from_csv(
    path: str,
) -> tuple[dict[str, float | int], ...]:
    """Load regenerated Prop99 window records from an external CSV path."""

    csv_path = str(path).strip()
    if not csv_path:
        raise ValueError("load_prop99_window_iter_records_from_csv() requires a path")
    try:
        raw_payload = Path(csv_path).read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(
            "load_prop99_window_iter_records_from_csv() could not read "
            f"{csv_path}"
        ) from exc
    return _parse_prop99_window_iter_records_csv(
        raw_payload,
        callable_name="load_prop99_window_iter_records_from_csv",
    )


def load_prop99_window_iter_stata_critical_value_probe() -> dict[str, object]:
    """Load the packaged Stata RNG/order-statistic probe for Prop99 window iter."""

    payload = _load_packaged_yaml(
        _PROP99_WINDOW_ITER_CRITICAL_VALUE_PROBE,
        callable_name="load_prop99_window_iter_stata_critical_value_probe",
    )
    if payload.get("case_id") != "PROP99-WINDOW-1985-1995-M5-ITER":
        raise ValueError(
            "load_prop99_window_iter_stata_critical_value_probe() requires "
            "case_id PROP99-WINDOW-1985-1995-M5-ITER"
        )
    if payload.get("producer") != "stata":
        raise ValueError(
            "load_prop99_window_iter_stata_critical_value_probe() requires "
            "producer stata"
        )
    if payload.get("capture_kind") != "critical-value-probe":
        raise ValueError(
            "load_prop99_window_iter_stata_critical_value_probe() requires "
            "capture_kind critical-value-probe"
        )
    if payload.get("capture_status") != "captured-critical-value-probe":
        raise ValueError(
            "load_prop99_window_iter_stata_critical_value_probe() requires "
            "capture_status captured-critical-value-probe"
        )
    method_authority = payload.get("method_authority")
    if isinstance(method_authority, (str, bytes, bytearray)) or not isinstance(
        method_authority,
        Sequence,
    ):
        raise ValueError(
            "load_prop99_window_iter_stata_critical_value_probe() requires "
            "paper/Stata critical-value method authority"
        )
    if tuple(method_authority) != _PROP99_WINDOW_ITER_CRITICAL_VALUE_METHOD_AUTHORITY:
        raise ValueError(
            "load_prop99_window_iter_stata_critical_value_probe() requires "
            "paper/Stata critical-value method authority"
        )
    for field in ("stata_rng_probe", "stata_order_statistic_probe"):
        if not isinstance(payload.get(field), Mapping):
            raise ValueError(
                "load_prop99_window_iter_stata_critical_value_probe() requires "
                f"{field} mapping"
            )
    if payload["stata_rng_probe"].get("source") != _PROP99_WINDOW_ITER_RNG_PROBE_SOURCE:
        raise ValueError(
            "load_prop99_window_iter_stata_critical_value_probe() requires "
            "Stata RNG transform source"
        )
    if (
        payload["stata_order_statistic_probe"].get("source")
        != _PROP99_WINDOW_ITER_ORDER_PROBE_SOURCE
    ):
        raise ValueError(
            "load_prop99_window_iter_stata_critical_value_probe() requires "
            "Stata order-statistic source"
        )
    return dict(payload)


def _normalize_records(
    records: Sequence[Mapping[str, object]],
) -> tuple[Mapping[str, object], ...]:
    if isinstance(records, (str, bytes, bytearray)) or not isinstance(
        records, Sequence
    ):
        raise ValueError("records must be a non-empty sequence of mappings")
    if not records:
        raise ValueError("records must be a non-empty sequence of mappings")
    normalized: list[Mapping[str, object]] = []
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise ValueError(f"records[{index}] must be a mapping")
        normalized.append(record)
    return tuple(normalized)


def _normalize_field_name(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _normalize_finite_float(name: str, value: object) -> float:
    if isinstance(value, (bool, str, bytes, bytearray)):
        raise ValueError(f"{name} must be finite")
    try:
        normalized = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be finite") from exc
    if not math.isfinite(normalized):
        raise ValueError(f"{name} must be finite")
    return normalized


def _normalize_binary_treatment(name: str, value: object) -> int:
    if isinstance(value, (bool, str, bytes, bytearray)):
        raise ValueError(f"{name} must be 0 or 1")
    try:
        normalized = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be 0 or 1") from exc
    if not normalized.is_integer() or int(normalized) not in {0, 1}:
        raise ValueError(f"{name} must be 0 or 1")
    return int(normalized)


def _normalize_positive_threshold(value: object) -> float:
    threshold = _normalize_finite_float("threshold_m", value)
    if threshold <= 0:
        raise ValueError("threshold_m must be positive")
    return threshold


def _group_mean(
    grouped_outcomes: Mapping[tuple[int, int], tuple[float, ...]],
    *,
    time_index: int,
    treatment_value: int,
) -> float:
    values = grouped_outcomes[(time_index, treatment_value)]
    return sum(values) / len(values)


def _did_at(
    grouped_outcomes: Mapping[tuple[int, int], tuple[float, ...]],
    *,
    time_index: int,
    treatment_time_index: int,
) -> float:
    return (
        _group_mean(grouped_outcomes, time_index=time_index, treatment_value=1)
        - _group_mean(
            grouped_outcomes,
            time_index=treatment_time_index,
            treatment_value=1,
        )
    ) - (
        _group_mean(grouped_outcomes, time_index=time_index, treatment_value=0)
        - _group_mean(
            grouped_outcomes,
            time_index=treatment_time_index,
            treatment_value=0,
        )
    )


def _nu_at(
    grouped_outcomes: Mapping[tuple[int, int], tuple[float, ...]],
    *,
    time_index: int,
) -> float:
    return (
        _group_mean(grouped_outcomes, time_index=time_index, treatment_value=1)
        - _group_mean(grouped_outcomes, time_index=time_index - 1, treatment_value=1)
    ) - (
        _group_mean(grouped_outcomes, time_index=time_index, treatment_value=0)
        - _group_mean(grouped_outcomes, time_index=time_index - 1, treatment_value=0)
    )


def _influence_matrix(
    rows: tuple[tuple[float, int, int], ...],
    grouped_outcomes: Mapping[tuple[int, int], tuple[float, ...]],
    *,
    treatment_time_index: int,
    time_period_count: int,
) -> list[list[float]]:
    sample_size = len(rows)
    matrix = [[0.0] * (time_period_count - 1) for _ in rows]
    column_index = 0

    for time_index in range(2, treatment_time_index):
        means = {
            (candidate_time, treatment_value): _group_mean(
                grouped_outcomes,
                time_index=candidate_time,
                treatment_value=treatment_value,
            )
            for candidate_time in (time_index - 1, time_index)
            for treatment_value in (0, 1)
        }
        counts = {
            key: len(grouped_outcomes[key])
            for key in means
        }
        for row_index, (outcome, treatment_value, row_time_index) in enumerate(rows):
            if treatment_value == 1:
                if row_time_index == time_index:
                    matrix[row_index][column_index] += (
                        outcome - means[(time_index, 1)]
                    ) * sample_size / counts[(time_index, 1)]
                if row_time_index == time_index - 1:
                    matrix[row_index][column_index] -= (
                        outcome - means[(time_index - 1, 1)]
                    ) * sample_size / counts[(time_index - 1, 1)]
            else:
                if row_time_index == time_index:
                    matrix[row_index][column_index] -= (
                        outcome - means[(time_index, 0)]
                    ) * sample_size / counts[(time_index, 0)]
                if row_time_index == time_index - 1:
                    matrix[row_index][column_index] += (
                        outcome - means[(time_index - 1, 0)]
                    ) * sample_size / counts[(time_index - 1, 0)]
        column_index += 1

    reference_means = {
        treatment_value: _group_mean(
            grouped_outcomes,
            time_index=treatment_time_index,
            treatment_value=treatment_value,
        )
        for treatment_value in (0, 1)
    }
    reference_counts = {
        treatment_value: len(grouped_outcomes[(treatment_time_index, treatment_value)])
        for treatment_value in (0, 1)
    }
    for time_index in range(treatment_time_index, time_period_count + 1):
        means = {
            treatment_value: _group_mean(
                grouped_outcomes,
                time_index=time_index,
                treatment_value=treatment_value,
            )
            for treatment_value in (0, 1)
        }
        counts = {
            treatment_value: len(grouped_outcomes[(time_index, treatment_value)])
            for treatment_value in (0, 1)
        }
        for row_index, (outcome, treatment_value, row_time_index) in enumerate(rows):
            if treatment_value == 1:
                if row_time_index == time_index:
                    matrix[row_index][column_index] += (
                        outcome - means[1]
                    ) * sample_size / counts[1]
                if row_time_index == treatment_time_index:
                    matrix[row_index][column_index] -= (
                        outcome - reference_means[1]
                    ) * sample_size / reference_counts[1]
            else:
                if row_time_index == time_index:
                    matrix[row_index][column_index] -= (
                        outcome - means[0]
                    ) * sample_size / counts[0]
                if row_time_index == treatment_time_index:
                    matrix[row_index][column_index] += (
                        outcome - reference_means[0]
                    ) * sample_size / reference_counts[0]
        column_index += 1

    return matrix


def _covariance_from_influence_matrix(matrix: list[list[float]]) -> tuple[tuple[float, ...], ...]:
    sample_size = len(matrix)
    if sample_size < 2:
        raise ValueError("records must contain at least two observations")
    dimension = len(matrix[0])
    rows: list[tuple[float, ...]] = []
    for row_index in range(dimension):
        rows.append(
            tuple(
                sum(row[row_index] * row[col_index] for row in matrix)
                / (sample_size - 1)
                for col_index in range(dimension)
            )
        )
    return tuple(rows)


def _delta_bar_standard_error(
    covariance_matrix: tuple[tuple[float, ...], ...],
    *,
    sample_size: int,
    pre_term_count: int,
    post_period_count: int,
) -> float:
    post_indices = range(pre_term_count, len(covariance_matrix))
    variance = sum(
        covariance_matrix[row][col]
        for row in post_indices
        for col in post_indices
    ) / (post_period_count * post_period_count * sample_size)
    if variance < -_NEGATIVE_VARIANCE_TOLERANCE:
        raise ValueError("delta_bar variance must be nonnegative")
    return math.sqrt(max(variance, 0.0))


def _numeric_payload_value(name: str, value: object) -> int | float | str:
    if isinstance(value, str):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    normalized = _normalize_finite_float(name, value)
    if normalized.is_integer():
        return int(normalized)
    return normalized


def _compare_numeric_field(
    *,
    field: str,
    python_value: object,
    reference_value: object,
    abs_tol: float,
    rel_tol: float,
) -> dict[str, object]:
    if isinstance(python_value, str) or isinstance(reference_value, str):
        matches = python_value == reference_value
        return {
            "field": field,
            "python": python_value,
            "reference": reference_value,
            "abs_diff": None,
            "rel_diff": None,
            "matches": matches,
        }

    python_float = _normalize_finite_float(f"python {field}", python_value)
    reference_float = _normalize_finite_float(f"reference {field}", reference_value)
    abs_diff = abs(python_float - reference_float)
    rel_diff = abs_diff / abs(reference_float) if reference_float != 0 else None
    matches = math.isclose(
        python_float,
        reference_float,
        rel_tol=rel_tol,
        abs_tol=abs_tol,
    )
    return {
        "field": field,
        "python": python_value,
        "reference": reference_value,
        "abs_diff": abs_diff,
        "rel_diff": rel_diff,
        "matches": matches,
    }


def _extract_numeric_payload(
    stata_stored_results: Mapping[str, object] | None,
) -> Mapping[str, object] | None:
    if stata_stored_results is None:
        return None
    if not isinstance(stata_stored_results, Mapping):
        raise ValueError("stata_stored_results must be a mapping")
    numeric_payload = stata_stored_results.get("numeric_payload")
    if numeric_payload is None:
        numeric_payload = stata_stored_results
    if not isinstance(numeric_payload, Mapping):
        raise ValueError("stata_stored_results numeric_payload must be a mapping")
    return numeric_payload


def _resolve_split_evidence_status(
    *,
    deterministic_comparisons: tuple[dict[str, object], ...],
    rng_comparisons: tuple[dict[str, object], ...],
    has_reference: bool,
) -> str:
    if not has_reference:
        return "deterministic-estimator-candidate"
    if any(not comparison["matches"] for comparison in deterministic_comparisons):
        return "deterministic-estimator-mismatch"
    if any(not comparison["matches"] for comparison in rng_comparisons):
        return "deterministic-estimator-verified-rng-mismatch"
    return "deterministic-estimator-and-rng-verified"


def _regularize_covariance_diagonal(
    covariance_matrix: Sequence[Sequence[float]],
    regularization: float,
) -> tuple[tuple[float, ...], ...]:
    normalized_regularization = _normalize_finite_float(
        "covariance_regularization",
        regularization,
    )
    if normalized_regularization < 0:
        raise ValueError("covariance_regularization must be nonnegative")
    return tuple(
        tuple(
            float(value) + (normalized_regularization if row_index == col_index else 0.0)
            for col_index, value in enumerate(row)
        )
        for row_index, row in enumerate(covariance_matrix)
    )


def _cholesky_lower_psd(matrix: Sequence[Sequence[float]]) -> tuple[tuple[float, ...], ...]:
    dimension = len(matrix)
    lower = [[0.0] * dimension for _ in range(dimension)]
    for row in range(dimension):
        for col in range(row + 1):
            prior = sum(lower[row][index] * lower[col][index] for index in range(col))
            residual = float(matrix[row][col]) - prior
            if row == col:
                if residual < -_NEGATIVE_VARIANCE_TOLERANCE or not math.isfinite(residual):
                    raise ValueError("covariance_matrix must be positive semidefinite")
                lower[row][col] = math.sqrt(max(residual, 0.0))
            elif lower[col][col] > _NEGATIVE_VARIANCE_TOLERANCE:
                lower[row][col] = residual / lower[col][col]
            elif abs(residual) > _NEGATIVE_VARIANCE_TOLERANCE:
                raise ValueError("covariance_matrix must be positive semidefinite")
    return tuple(tuple(row) for row in lower)


def _lower_triangular_multiply(
    lower_cholesky: Sequence[Sequence[float]],
    vector: Sequence[float],
) -> tuple[float, ...]:
    return tuple(
        sum(float(lower_cholesky[row][col]) * float(vector[col]) for col in range(row + 1))
        for row in range(len(lower_cholesky))
    )


def _python_first_standard_normal_draw(
    *,
    seed: int,
    dimension: int,
) -> tuple[float, ...]:
    rng = random.Random(seed)
    return tuple(rng.gauss(0.0, 1.0) for _ in range(dimension))


def _build_rng_stream_probe(
    *,
    stata_rng_probe: Mapping[str, object] | None,
    covariance_matrix: Sequence[Sequence[float]],
    covariance_regularization: float,
    seed: int,
    dimension: int,
    t_pre: int,
    t_post: int,
    p_norm: float | str,
    mode: str,
    kappa: float,
    abs_tol: float,
) -> dict[str, object] | None:
    if stata_rng_probe is None:
        return None
    if not isinstance(stata_rng_probe, Mapping):
        raise ValueError("stata_rng_probe must be a mapping")

    probe_seed = int(_numeric_payload_value("stata_rng_probe.seed", stata_rng_probe.get("seed")))
    probe_dimension = int(
        _numeric_payload_value("stata_rng_probe.dimension", stata_rng_probe.get("dimension"))
    )
    if probe_seed != seed:
        raise ValueError("stata_rng_probe seed must match the critical-value seed")
    if probe_dimension != dimension:
        raise ValueError("stata_rng_probe dimension must match the critical-value dimension")

    reference_draws = stata_rng_probe.get("first_standard_normal_draw")
    if isinstance(reference_draws, (str, bytes, bytearray)) or not isinstance(
        reference_draws,
        Sequence,
    ):
        raise ValueError("stata_rng_probe first_standard_normal_draw must be a sequence")
    if len(reference_draws) != dimension:
        raise ValueError(
            "stata_rng_probe first_standard_normal_draw dimension must match "
            "the critical-value dimension"
        )
    stata_draw = tuple(
        _normalize_finite_float(f"stata_rng_probe.first_standard_normal_draw[{index}]", value)
        for index, value in enumerate(reference_draws)
    )
    python_draw = _python_first_standard_normal_draw(seed=seed, dimension=dimension)
    abs_diffs = tuple(abs(left - right) for left, right in zip(python_draw, stata_draw))
    max_abs_diff = max(abs_diffs) if abs_diffs else 0.0
    result: dict[str, object] = {
        "seed": seed,
        "dimension": dimension,
        "python_rng_engine": "python random.Random.gauss",
        "stata_reference_rng_engine": "Mata rseed()/rnormal()",
        "python_first_standard_normal_draw": python_draw,
        "stata_first_standard_normal_draw": stata_draw,
        "abs_diffs": abs_diffs,
        "max_abs_diff": max_abs_diff,
        "matches": max_abs_diff <= abs_tol,
        "source": stata_rng_probe.get("source"),
    }
    reference_transformed = stata_rng_probe.get("first_transformed_draw")
    reference_psi = stata_rng_probe.get("first_psi")
    if reference_transformed is None and reference_psi is None:
        return result
    if isinstance(reference_transformed, (str, bytes, bytearray)) or not isinstance(
        reference_transformed,
        Sequence,
    ):
        raise ValueError("stata_rng_probe first_transformed_draw must be a sequence")
    if len(reference_transformed) != dimension:
        raise ValueError(
            "stata_rng_probe first_transformed_draw dimension must match "
            "the critical-value dimension"
        )
    stata_z = tuple(
        _normalize_finite_float(f"stata_rng_probe.first_transformed_draw[{index}]", value)
        for index, value in enumerate(reference_transformed)
    )
    regularized_covariance = _regularize_covariance_diagonal(
        covariance_matrix,
        covariance_regularization,
    )
    lower_cholesky = _cholesky_lower_psd(regularized_covariance)
    python_z_from_stata_w = _lower_triangular_multiply(lower_cholesky, stata_draw)
    z_abs_diffs = tuple(
        abs(left - right)
        for left, right in zip(python_z_from_stata_w, stata_z)
    )
    python_psi_from_stata_w = compute_psi(
        python_z_from_stata_w,
        t_pre=t_pre,
        t_post=t_post,
        p_norm=p_norm,
        mode=mode,
        kappa=kappa,
    )
    stata_psi = _normalize_finite_float("stata_rng_probe.first_psi", reference_psi)
    result["transform_probe"] = {
        "python_transformed_from_stata_draw": python_z_from_stata_w,
        "stata_transformed_draw": stata_z,
        "max_abs_diff": max(z_abs_diffs) if z_abs_diffs else 0.0,
        "matches": (max(z_abs_diffs) if z_abs_diffs else 0.0) <= abs_tol,
    }
    result["psi_probe"] = {
        "python_psi_from_stata_draw": python_psi_from_stata_w,
        "stata_psi": stata_psi,
        "abs_diff": abs(python_psi_from_stata_w - stata_psi),
        "matches": abs(python_psi_from_stata_w - stata_psi) <= abs_tol,
    }
    return result


def _build_order_statistic_probe(
    *,
    stata_order_statistic_probe: Mapping[str, object] | None,
    alpha: float,
    simulations: int,
    reference_f_alpha: object | None,
    abs_tol: float,
) -> dict[str, object] | None:
    if stata_order_statistic_probe is None:
        return None
    if not isinstance(stata_order_statistic_probe, Mapping):
        raise ValueError("stata_order_statistic_probe must be a mapping")

    expected_quantile_index = math.ceil(simulations * (1.0 - alpha)) + 1
    expected_tail_limit = simulations - expected_quantile_index + 1
    observed_quantile_index = int(
        _numeric_payload_value(
            "stata_order_statistic_probe.quantile_idx",
            stata_order_statistic_probe.get("quantile_idx"),
        )
    )
    previous = _normalize_finite_float(
        "stata_order_statistic_probe.previous",
        stata_order_statistic_probe.get("previous"),
    )
    f_alpha = _normalize_finite_float(
        "stata_order_statistic_probe.f_alpha",
        stata_order_statistic_probe.get("f_alpha"),
    )
    tail_at_previous = int(
        _numeric_payload_value(
            "stata_order_statistic_probe.tail_at_previous",
            stata_order_statistic_probe.get("tail_at_previous"),
        )
    )
    tail_at_f_alpha = int(
        _numeric_payload_value(
            "stata_order_statistic_probe.tail_at_f_alpha",
            stata_order_statistic_probe.get("tail_at_f_alpha"),
        )
    )
    max_value = _normalize_finite_float(
        "stata_order_statistic_probe.max",
        stata_order_statistic_probe.get("max"),
    )
    first_sorted = _normalize_finite_float(
        "stata_order_statistic_probe.first_sorted",
        stata_order_statistic_probe.get("first_sorted"),
    )
    reference_diff = None
    matches_reference = None
    if reference_f_alpha is not None:
        reference = _normalize_finite_float("reference e(f_alpha)", reference_f_alpha)
        reference_diff = abs(f_alpha - reference)
        matches_reference = reference_diff <= abs_tol

    return {
        "source": stata_order_statistic_probe.get("source"),
        "alpha": alpha,
        "simulations": simulations,
        "quantile_rule": "ceil(simulations * (1 - alpha)) + 1 order statistic",
        "expected_quantile_idx": expected_quantile_index,
        "quantile_idx": observed_quantile_index,
        "quantile_idx_matches": observed_quantile_index == expected_quantile_index,
        "previous": previous,
        "f_alpha": f_alpha,
        "max": max_value,
        "first_sorted": first_sorted,
        "expected_tail_limit": expected_tail_limit,
        "tail_at_previous": tail_at_previous,
        "tail_at_f_alpha": tail_at_f_alpha,
        "tail_rule_matches": (
            tail_at_previous > expected_tail_limit
            and tail_at_f_alpha <= expected_tail_limit
        ),
        "reference_abs_diff": reference_diff,
        "matches_reference_f_alpha": matches_reference,
    }


def _resolve_critical_value_mismatch_diagnosis(
    *,
    rng_comparisons: tuple[dict[str, object], ...],
    rng_stream_probe: Mapping[str, object] | None,
    order_statistic_probe: Mapping[str, object] | None,
    reference_minus_regularized: float | None,
) -> dict[str, object]:
    if not rng_comparisons:
        return {
            "status": "no-reference-critical-value",
            "attribution": None,
            "reason": "no Stata e(f_alpha) reference was supplied",
            "regularization_abs_diff": None,
            "required_probe_status": {
                "rng_stream_probe": rng_stream_probe is not None,
                "transform_probe": False,
                "psi_probe": False,
                "order_statistic_probe": order_statistic_probe is not None,
            },
        }
    if all(comparison["matches"] for comparison in rng_comparisons):
        return {
            "status": "critical-value-matches-reference",
            "attribution": None,
            "reason": "Python and Stata e(f_alpha) match within RNG tolerance",
            "regularization_abs_diff": abs(reference_minus_regularized)
            if reference_minus_regularized is not None
            else None,
            "required_probe_status": {
                "rng_stream_probe": rng_stream_probe is not None,
                "transform_probe": False,
                "psi_probe": False,
                "order_statistic_probe": order_statistic_probe is not None,
            },
        }

    regularization_abs_diff = (
        abs(reference_minus_regularized)
        if reference_minus_regularized is not None
        else None
    )
    transform_probe = (
        rng_stream_probe.get("transform_probe")
        if isinstance(rng_stream_probe, Mapping)
        else None
    )
    psi_probe = (
        rng_stream_probe.get("psi_probe")
        if isinstance(rng_stream_probe, Mapping)
        else None
    )
    has_rng_stream_mismatch = (
        isinstance(rng_stream_probe, Mapping)
        and rng_stream_probe.get("matches") is False
    )
    transform_matches = (
        isinstance(transform_probe, Mapping)
        and transform_probe.get("matches") is True
    )
    psi_matches = (
        isinstance(psi_probe, Mapping)
        and psi_probe.get("matches") is True
    )
    order_statistic_matches = (
        isinstance(order_statistic_probe, Mapping)
        and order_statistic_probe.get("quantile_idx_matches") is True
        and order_statistic_probe.get("tail_rule_matches") is True
        and order_statistic_probe.get("matches_reference_f_alpha") is True
    )
    required_probe_status = {
        "rng_stream_probe": isinstance(rng_stream_probe, Mapping),
        "rng_stream_mismatch": has_rng_stream_mismatch,
        "transform_probe": transform_matches,
        "psi_probe": psi_matches,
        "order_statistic_probe": order_statistic_matches,
    }

    if (
        has_rng_stream_mismatch
        and transform_matches
        and psi_matches
        and order_statistic_matches
    ):
        return {
            "status": "rng-stream-specific-mismatch-verified",
            "attribution": "rng-stream",
            "reason": (
                "Stata and Python standard-normal streams differ for the same "
                "seed, while the Stata draw transformed through Python "
                "Cholesky/psi matches and the Stata order statistic matches "
                "stored e(f_alpha)"
            ),
            "regularization_abs_diff": regularization_abs_diff,
            "required_probe_status": required_probe_status,
        }

    return {
        "status": "critical-value-mismatch-source-unproven",
        "attribution": None,
        "reason": (
            "covariance regularization has been measured, but Stata draw, "
            "transform, psi, and order-statistic probes are not all present "
            "and matching; do not attribute the remaining e(f_alpha) gap to "
            "RNG alone"
        ),
        "regularization_abs_diff": regularization_abs_diff,
        "required_probe_status": required_probe_status,
    }


def compute_pretest_kernel_inputs_from_records(
    records: Sequence[Mapping[str, object]],
    *,
    outcome: str,
    treatment: str,
    time: str,
    treat_time: object,
    threshold_m: object,
    p_norm: float | str = 2,
    mode: str = "iterative",
) -> dict[str, object]:
    """Compute pre-test kernel inputs from complete group-time records.

    Derives all intermediate quantities (violations, covariance, severity,
    kappa, classification) from flat observation records, returning them
    as a dictionary suitable for ``compute_pretest_snapshot``.

    Parameters
    ----------
    records : sequence of mapping
        Flat observation records with outcome, treatment, and time fields.
    outcome : str
        Column name for the outcome variable.
    treatment : str
        Column name for the binary treatment indicator.
    time : str
        Column name for the time variable.
    treat_time : numeric
        Treatment onset time (must be among observed times).
    threshold_m : numeric
        Positive severity threshold M for classification.
    p_norm : float or str, default 2
        Norm exponent p >= 1.
    mode : {'iterative', 'overall'}, default 'iterative'
        Aggregation mode.

    Returns
    -------
    dict
        Dictionary containing: ``sample_size``, ``nu_vector``,
        ``nu_bar_vector``, ``delta_bar``, ``covariance_matrix``,
        ``se_delta_bar``, ``S_pre``, ``kappa``, ``phi``,
        ``pretest_pass``, ``snapshot_inputs``, and time-structure
        metadata.

    Raises
    ------
    ValueError
        If records are incomplete, treatment is non-binary, or time
        structure is insufficient.
    """

    normalized_records = _normalize_records(records)
    outcome_field = _normalize_field_name("outcome", outcome)
    treatment_field = _normalize_field_name("treatment", treatment)
    time_field = _normalize_field_name("time", time)
    normalized_mode = normalize_mode(mode)
    threshold = _normalize_positive_threshold(threshold_m)
    normalized_treat_time = _normalize_finite_float("treat_time", treat_time)

    raw_rows: list[tuple[float, int, float]] = []
    for index, record in enumerate(normalized_records):
        try:
            outcome_value = record[outcome_field]
            treatment_value = record[treatment_field]
            time_value = record[time_field]
        except KeyError as exc:
            raise ValueError(
                f"records[{index}] missing required field {exc.args[0]}"
            ) from exc
        raw_rows.append(
            (
                _normalize_finite_float(f"records[{index}].{outcome_field}", outcome_value),
                _normalize_binary_treatment(
                    f"records[{index}].{treatment_field}",
                    treatment_value,
                ),
                _normalize_finite_float(f"records[{index}].{time_field}", time_value),
            )
        )

    observed_times = tuple(sorted({row[2] for row in raw_rows}))
    if normalized_treat_time not in observed_times:
        raise ValueError("treat_time must be one of the observed time values")
    time_to_index = {
        observed_time: index + 1
        for index, observed_time in enumerate(observed_times)
    }
    treatment_time_index = time_to_index[normalized_treat_time]
    pre_period_count = treatment_time_index - 1
    post_period_count = len(observed_times) - pre_period_count
    if pre_period_count < 2:
        raise ValueError("treat_time must leave at least two pre-treatment periods")
    if post_period_count < 1:
        raise ValueError("treat_time must leave at least one post-treatment period")

    indexed_rows = tuple(
        (outcome_value, treatment_value, time_to_index[time_value])
        for outcome_value, treatment_value, time_value in raw_rows
    )
    grouped: dict[tuple[int, int], list[float]] = {
        (time_index, treatment_value): []
        for time_index in range(1, len(observed_times) + 1)
        for treatment_value in (0, 1)
    }
    for outcome_value, treatment_value, time_index in indexed_rows:
        grouped[(time_index, treatment_value)].append(outcome_value)
    missing_cells = [
        f"time={observed_times[time_index - 1]}, treatment={treatment_value}"
        for time_index in range(1, len(observed_times) + 1)
        for treatment_value in (0, 1)
        if not grouped[(time_index, treatment_value)]
    ]
    if missing_cells:
        raise ValueError(
            "records must contain complete treatment/time cells; missing "
            + ", ".join(missing_cells)
        )
    grouped_outcomes = {
        key: tuple(values)
        for key, values in grouped.items()
    }

    nu_vector = tuple(
        _nu_at(grouped_outcomes, time_index=time_index)
        for time_index in range(2, treatment_time_index)
    )
    nu_bar_vector: tuple[float, ...] = tuple(
        sum(nu_vector[: index + 1])
        for index in range(len(nu_vector))
    )
    delta_vector = tuple(
        _did_at(
            grouped_outcomes,
            time_index=time_index,
            treatment_time_index=treatment_time_index,
        )
        for time_index in range(treatment_time_index, len(observed_times) + 1)
    )
    delta_bar = sum(delta_vector) / len(delta_vector)
    influence_matrix = _influence_matrix(
        indexed_rows,
        grouped_outcomes,
        treatment_time_index=treatment_time_index,
        time_period_count=len(observed_times),
    )
    covariance_matrix = _covariance_from_influence_matrix(influence_matrix)
    pre_term_count = pre_period_count - 1
    se_delta_bar = _delta_bar_standard_error(
        covariance_matrix,
        sample_size=len(indexed_rows),
        pre_term_count=pre_term_count,
        post_period_count=post_period_count,
    )
    severity_source = nu_bar_vector if normalized_mode == "overall" else nu_vector
    s_pre = compute_severity(
        nu_vector=nu_vector,
        nu_bar_vector=nu_bar_vector if normalized_mode == "overall" else None,
        p_norm=p_norm,
        mode=normalized_mode,
    )
    kappa = compute_kappa(
        t_post=post_period_count,
        p_norm=p_norm,
        mode=normalized_mode,
    )
    phi = int(s_pre > threshold)

    return {
        "sample_size": len(indexed_rows),
        "time_periods": observed_times,
        "treatment_values": (0, 1),
        "time_index": {
            str(observed_time): index
            for observed_time, index in time_to_index.items()
        },
        "T": len(observed_times),
        "t0": treatment_time_index,
        "T_pre": pre_period_count,
        "T_post": post_period_count,
        "is_panel": 0,
        "mode": normalized_mode,
        "p_norm": p_norm,
        "threshold_m": threshold,
        "nu_vector": nu_vector,
        "nu_bar_vector": nu_bar_vector,
        "pre_violation_vector": severity_source,
        "delta_vector": delta_vector,
        "delta_bar": delta_bar,
        "covariance_matrix": covariance_matrix,
        "se_delta_bar": se_delta_bar,
        "S_pre": s_pre,
        "kappa": kappa,
        "phi": phi,
        "pretest_pass": 1 - phi,
        "snapshot_inputs": {
            "nu_vector": nu_vector,
            "nu_bar_vector": nu_bar_vector if normalized_mode == "overall" else None,
            "delta_bar": delta_bar,
            "se_delta_bar": se_delta_bar,
            "covariance_matrix": covariance_matrix,
            "covariance_form": "iterative",
            "sample_size": len(indexed_rows),
            "t_post": post_period_count,
            "pre_violations_form": "iterative",
        },
    }


def compute_pretest_snapshot_from_records(
    records: Sequence[Mapping[str, object]],
    *,
    outcome: str,
    treatment: str,
    time: str,
    treat_time: object,
    threshold_m: object,
    p_norm: float | str = 2,
    mode: str = "iterative",
    alpha: float | int = 0.05,
    simulations: int | float = 5000,
    seed: int | float = 12345,
    case_id: str | None = None,
):
    """Compute a snapshot directly from complete group-time records.

    This helper keeps the record-to-input derivation inspectable through
    ``compute_pretest_kernel_inputs_from_records()`` while giving ordinary user
    code a single public call that returns the reporting object.
    """

    inputs = compute_pretest_kernel_inputs_from_records(
        records,
        outcome=outcome,
        treatment=treatment,
        time=time,
        treat_time=treat_time,
        threshold_m=threshold_m,
        p_norm=p_norm,
        mode=mode,
    )
    snapshot_inputs = inputs["snapshot_inputs"]
    if not isinstance(snapshot_inputs, Mapping):
        raise ValueError("compute_pretest_snapshot_from_records() requires snapshot_inputs")

    from .pipeline import compute_pretest_snapshot
    from .validation import DatasetProfile

    command = (
        f"pretest {outcome}, treatment({treatment}) time({time}) "
        f"treat_time({treat_time}) threshold({threshold_m}) p({p_norm}) "
        f"alpha({alpha}) simulate({simulations}) seed({seed})"
    )
    if normalize_mode(mode) == "overall":
        command = f"{command} overall"

    snapshot = compute_pretest_snapshot(
        command,
        DatasetProfile(
            time_periods=tuple(inputs["time_periods"]),
            treatment_values=tuple(inputs["treatment_values"]),
        ),
        simulations=simulations,
        seed=seed,
        case_id=case_id,
        **snapshot_inputs,
    )
    snapshot.diagnostics["record_input_summary"] = {
        "records": inputs["sample_size"],
        "T": inputs["T"],
        "T_pre": inputs["T_pre"],
        "T_post": inputs["T_post"],
        "threshold": inputs["threshold_m"],
        "mode": inputs["mode"],
    }
    return snapshot


def build_pretest_deterministic_split_capture_evidence(
    records: Sequence[Mapping[str, object]],
    *,
    case_id: str,
    outcome: str,
    treatment: str,
    time: str,
    treat_time: object,
    threshold_m: object,
    p_norm: float | str = 2,
    mode: str = "iterative",
    alpha: float | int = 0.05,
    simulations: int | float = 5000,
    seed: int | float = 12345,
    stata_stored_results: Mapping[str, object] | None = None,
    deterministic_abs_tol: float = 1e-9,
    deterministic_rel_tol: float = 1e-12,
    rng_abs_tol: float = 1e-9,
    rng_rel_tol: float = 1e-12,
    stata_rng_probe: Mapping[str, object] | None = None,
    stata_order_statistic_probe: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build deterministic Python split-doc evidence without promoting replay capture."""

    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("case_id must be a non-empty string")
    deterministic_abs_tolerance = _normalize_finite_float(
        "deterministic_abs_tol",
        deterministic_abs_tol,
    )
    deterministic_rel_tolerance = _normalize_finite_float(
        "deterministic_rel_tol",
        deterministic_rel_tol,
    )
    rng_abs_tolerance = _normalize_finite_float("rng_abs_tol", rng_abs_tol)
    rng_rel_tolerance = _normalize_finite_float("rng_rel_tol", rng_rel_tol)
    if deterministic_abs_tolerance < 0 or deterministic_rel_tolerance < 0:
        raise ValueError("deterministic tolerances must be nonnegative")
    if rng_abs_tolerance < 0 or rng_rel_tolerance < 0:
        raise ValueError("rng tolerances must be nonnegative")

    inputs = compute_pretest_kernel_inputs_from_records(
        records,
        outcome=outcome,
        treatment=treatment,
        time=time,
        treat_time=treat_time,
        threshold_m=threshold_m,
        p_norm=p_norm,
        mode=mode,
    )
    python_f_alpha = compute_critical_value(
        inputs["covariance_matrix"],
        alpha=alpha,
        simulations=simulations,
        t_pre=inputs["T_pre"],
        t_post=inputs["T_post"],
        p_norm=p_norm,
        mode=mode,
        covariance_form="iterative",
        seed=seed,
    )
    snapshot_inputs = inputs.get("snapshot_inputs")
    if not isinstance(snapshot_inputs, Mapping):
        raise ValueError(
            "build_pretest_deterministic_split_capture_evidence() requires "
            "snapshot_inputs mapping"
        )
    from .pipeline import compute_pretest_snapshot
    from .validation import DatasetProfile

    command_parts = [
        f"pretest {outcome}, treatment({treatment}) time({time})",
        f"treat_time({treat_time})",
        f"threshold({threshold_m})",
        f"p({p_norm})",
        f"alpha({alpha})",
        f"simulate({simulations})",
        f"seed({seed})",
    ]
    if normalize_mode(mode) == "overall":
        command_parts.append("overall")
    snapshot = compute_pretest_snapshot(
        " ".join(command_parts),
        DatasetProfile(
            time_periods=inputs["time_periods"],
            treatment_values=inputs["treatment_values"],
            is_panel=bool(inputs["is_panel"]),
        ),
        f_alpha=python_f_alpha,
        case_id=case_id.strip(),
        **snapshot_inputs,
    )
    snapshot_scalars = snapshot.canonical["scalars"]
    stata_covariance_regularization = 1e-10
    critical_value_dimension = int(inputs["T_pre"]) - 1 + int(inputs["T_post"])
    normalized_seed = int(_numeric_payload_value("seed", seed))
    rng_stream_probe = _build_rng_stream_probe(
        stata_rng_probe=stata_rng_probe,
        covariance_matrix=inputs["covariance_matrix"],
        covariance_regularization=stata_covariance_regularization,
        seed=normalized_seed,
        dimension=critical_value_dimension,
        t_pre=int(inputs["T_pre"]),
        t_post=int(inputs["T_post"]),
        p_norm=p_norm,
        mode=str(inputs["mode"]),
        kappa=float(inputs["kappa"]),
        abs_tol=rng_abs_tolerance,
    )
    python_f_alpha_with_stata_regularization = compute_critical_value(
        _regularize_covariance_diagonal(
            inputs["covariance_matrix"],
            stata_covariance_regularization,
        ),
        alpha=alpha,
        simulations=simulations,
        t_pre=inputs["T_pre"],
        t_post=inputs["T_post"],
        p_norm=p_norm,
        mode=mode,
        seed=seed,
    )
    python_payload: dict[str, object] = {
        "e(N)": int(inputs["sample_size"]),
        "e(T)": int(inputs["T"]),
        "e(T_pre)": int(inputs["T_pre"]),
        "e(T_post)": int(inputs["T_post"]),
        "e(t0)": int(inputs["t0"]),
        "e(n)": int(inputs["sample_size"]),
        "e(is_panel)": int(inputs["is_panel"]),
        "e(p)": _numeric_payload_value("p_norm", p_norm),
        "e(alpha)": _numeric_payload_value("alpha", alpha),
        "e(M)": _numeric_payload_value("threshold_m", inputs["threshold_m"]),
        "e(threshold)": _numeric_payload_value("threshold_m", inputs["threshold_m"]),
        "e(sims)": _numeric_payload_value("simulations", simulations),
        "e(seed)": _numeric_payload_value("seed", seed),
        "e(se_delta_bar)": _numeric_payload_value(
            "se_delta_bar",
            inputs["se_delta_bar"],
        ),
        "e(phi)": int(inputs["phi"]),
        "e(pretest_pass)": int(inputs["pretest_pass"]),
        "e(data_valid)": 1,
        "e(mode)": str(inputs["mode"]),
        "e(S_pre)": _numeric_payload_value("S_pre", inputs["S_pre"]),
        "e(kappa)": _numeric_payload_value("kappa", inputs["kappa"]),
        "e(f_alpha)": _numeric_payload_value("f_alpha", python_f_alpha),
        "e(delta_bar)": _numeric_payload_value("delta_bar", inputs["delta_bar"]),
        "e(ci_conv_lower)": _numeric_payload_value(
            "ci_conv_lower",
            snapshot_scalars["ci_conv_lower"],
        ),
        "e(ci_conv_upper)": _numeric_payload_value(
            "ci_conv_upper",
            snapshot_scalars["ci_conv_upper"],
        ),
        "e(ci_lower)": _numeric_payload_value(
            "ci_lower",
            snapshot_scalars["ci_lower"],
        ),
        "e(ci_upper)": _numeric_payload_value(
            "ci_upper",
            snapshot_scalars["ci_upper"],
        ),
        "e(nu)": tuple(inputs["nu_vector"]),
        "e(delta)": tuple(inputs["delta_vector"]),
        "e(Sigma)": tuple(tuple(row) for row in inputs["covariance_matrix"]),
    }
    if float(alpha) > 0:
        python_payload["e(level)"] = _numeric_payload_value(
            "level",
            100 * (1 - float(alpha)),
        )

    deterministic_fields = (
        "e(N)",
        "e(T)",
        "e(T_pre)",
        "e(T_post)",
        "e(t0)",
        "e(n)",
        "e(is_panel)",
        "e(p)",
        "e(alpha)",
        "e(level)",
        "e(M)",
        "e(threshold)",
        "e(sims)",
        "e(seed)",
        "e(se_delta_bar)",
        "e(phi)",
        "e(pretest_pass)",
        "e(data_valid)",
        "e(mode)",
        "e(S_pre)",
        "e(kappa)",
        "e(delta_bar)",
        "e(ci_conv_lower)",
        "e(ci_conv_upper)",
    )
    rng_fields = ("e(f_alpha)", "e(ci_lower)", "e(ci_upper)")
    exact_replay_promotion_fields = deterministic_fields
    excluded_from_deterministic_replay_promotion = rng_fields
    replay_promotion_contract = {
        "status": "not-authoritative-replay-capture",
        "reason": (
            "deterministic estimator fields are paper/Stata estimator checks; "
            "Monte Carlo critical values remain RNG-engine-specific until the "
            "reference RNG stream is reproduced or captured directly"
        ),
        "eligible_exact_fields": exact_replay_promotion_fields,
        "excluded_fields": excluded_from_deterministic_replay_promotion,
        "excluded_field_reasons": {
            "e(f_alpha)": (
                "Monte Carlo order statistic depends on the Stata Mata "
                "rseed()/rnormal() stream; Python random.Random.gauss uses a "
                "different stream for the same seed"
            ),
            "e(ci_lower)": "conditional interval bound depends on e(f_alpha)",
            "e(ci_upper)": "conditional interval bound depends on e(f_alpha)",
        },
    }
    reference_payload = _extract_numeric_payload(stata_stored_results)
    deterministic_comparisons: tuple[dict[str, object], ...] = ()
    rng_comparisons: tuple[dict[str, object], ...] = ()
    if reference_payload is not None:
        missing_fields = [
            field
            for field in deterministic_fields + rng_fields
            if field not in reference_payload
        ]
        if missing_fields:
            raise ValueError(
                "stata_stored_results missing required fields: "
                + ", ".join(missing_fields)
            )
        deterministic_comparisons = tuple(
            _compare_numeric_field(
                field=field,
                python_value=python_payload[field],
                reference_value=reference_payload[field],
                abs_tol=deterministic_abs_tolerance,
                rel_tol=deterministic_rel_tolerance,
            )
            for field in deterministic_fields
        )
        rng_comparisons = tuple(
            _compare_numeric_field(
                field=field,
                python_value=python_payload[field],
                reference_value=reference_payload[field],
                abs_tol=rng_abs_tolerance,
                rel_tol=rng_rel_tolerance,
            )
            for field in rng_fields
        )
    order_statistic_probe = _build_order_statistic_probe(
        stata_order_statistic_probe=stata_order_statistic_probe,
        alpha=float(alpha),
        simulations=int(_numeric_payload_value("simulations", simulations)),
        reference_f_alpha=reference_payload.get("e(f_alpha)")
        if reference_payload is not None
        else None,
        abs_tol=rng_abs_tolerance,
    )
    reference_minus_regularized = (
        float(reference_payload["e(f_alpha)"]) - python_f_alpha_with_stata_regularization
        if reference_payload is not None
        else None
    )
    critical_value_mismatch_diagnosis = _resolve_critical_value_mismatch_diagnosis(
        rng_comparisons=rng_comparisons,
        rng_stream_probe=rng_stream_probe,
        order_statistic_probe=order_statistic_probe,
        reference_minus_regularized=reference_minus_regularized,
    )

    return {
        "version": 1,
        "case_id": case_id.strip(),
        "producer": "python",
        "evidence_scope": "deterministic-estimator-split-doc",
        "capture_kind": "deterministic-estimator-evidence",
        "capture_status": "not-replay-capture",
        "comparison_status": _resolve_split_evidence_status(
            deterministic_comparisons=deterministic_comparisons,
            rng_comparisons=rng_comparisons,
            has_reference=reference_payload is not None,
        ),
        "method_authority": (
            "paper/pretest_paper.md Sections 2-5 and Appendix C; "
            "pretest-stata/mata estimator/covariance/psi references"
        ),
        "comparison_target": "stata-stored-results"
        if reference_payload is not None
        else None,
        "deterministic_fields": deterministic_fields,
        "rng_fields": rng_fields,
        "exact_replay_promotion_fields": exact_replay_promotion_fields,
        "excluded_from_deterministic_replay_promotion": (
            excluded_from_deterministic_replay_promotion
        ),
        "replay_promotion_contract": replay_promotion_contract,
        "deterministic_match_fields": deterministic_comparisons,
        "rng_mismatch_fields": tuple(
            comparison
            for comparison in rng_comparisons
            if not comparison["matches"]
        ),
        "rng_match_fields": tuple(
            comparison
            for comparison in rng_comparisons
            if comparison["matches"]
        ),
        "python_numeric_payload": python_payload,
        "reference_numeric_payload": dict(reference_payload)
        if reference_payload is not None
        else None,
        "kernel_inputs": inputs,
        "covariance_estimator": {
            "target": "theta = (nu_2,...,nu_{t0-1}, delta_{t0},...,delta_T)",
            "sample_design": "repeated-cross-section",
            "influence_function": (
                "(n / n_td) * 1{D_i=d, t_i=t} * (Y_i - Y_bar_td)"
            ),
            "covariance_denominator": "n - 1",
            "confidence_interval_sample_size_denominator": "sqrt(n)",
            "python_covariance_regularization": 0.0,
            "stata_reference_critical_value_regularization": (
                stata_covariance_regularization
            ),
            "cluster_covariance": "not-supported-by-records-helper",
            "method_authority": (
                "paper/pretest_paper.md Assumptions 1-2",
                "pretest-stata/mata/_pretest_covariance.mata",
            ),
        },
        "critical_value_settings": {
            "alpha": float(alpha),
            "simulations": int(_numeric_payload_value("simulations", simulations)),
            "seed": normalized_seed,
            "mode": str(inputs["mode"]),
            "covariance_form": "iterative",
            "p_norm": p_norm,
            "t_pre": int(inputs["T_pre"]),
            "t_post": int(inputs["T_post"]),
            "python_rng_engine": "python random.Random.gauss",
            "stata_reference_rng_engine": "Mata rseed()/rnormal()",
            "python_covariance_regularization": 0.0,
            "stata_reference_covariance_regularization": (
                stata_covariance_regularization
            ),
            "quantile_rule": "ceil(simulations * (1 - alpha)) + 1 order statistic",
        },
        "critical_value_regularization_probe": {
            "python_f_alpha": python_f_alpha,
            "python_f_alpha_with_stata_regularization": (
                python_f_alpha_with_stata_regularization
            ),
            "regularization": stata_covariance_regularization,
            "regularized_minus_unregularized": (
                python_f_alpha_with_stata_regularization - python_f_alpha
            ),
            "reference_minus_regularized": (
                reference_minus_regularized
            ),
            "diagnosis": (
                "covariance regularization is measured separately; source "
                "attribution for any remaining e(f_alpha) gap is recorded in "
                "critical_value_mismatch_diagnosis"
            ),
        },
        "critical_value_mismatch_diagnosis": critical_value_mismatch_diagnosis,
        "rng_stream_probe": rng_stream_probe,
        "order_statistic_probe": order_statistic_probe,
    }


def build_prop99_window_iter_deterministic_split_capture_evidence(
    records: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, object]:
    """Build packaged Prop99 window iterative deterministic/RNG evidence."""

    stored_results = _load_packaged_yaml(
        _PROP99_WINDOW_ITER_STATA_STORED_RESULTS,
        callable_name="build_prop99_window_iter_deterministic_split_capture_evidence",
    )
    critical_value_probe = load_prop99_window_iter_stata_critical_value_probe()
    return build_pretest_deterministic_split_capture_evidence(
        load_prop99_window_iter_records() if records is None else records,
        case_id="PROP99-WINDOW-1985-1995-M5-ITER",
        outcome="cigsale",
        treatment="treated",
        time="year",
        treat_time=1989,
        threshold_m=5,
        p_norm=2,
        mode="iterative",
        alpha=0.05,
        simulations=5000,
        seed=12345,
        stata_stored_results=stored_results,
        stata_rng_probe=critical_value_probe["stata_rng_probe"],
        stata_order_statistic_probe=critical_value_probe[
            "stata_order_statistic_probe"
        ],
    )


def build_prop99_window_overall_deterministic_split_capture_evidence(
    records: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, object]:
    """Build packaged Prop99 window overall deterministic/RNG evidence."""

    stored_results = _load_packaged_yaml(
        _PROP99_WINDOW_OVERALL_STATA_STORED_RESULTS,
        callable_name="build_prop99_window_overall_deterministic_split_capture_evidence",
    )
    return build_pretest_deterministic_split_capture_evidence(
        load_prop99_window_iter_records() if records is None else records,
        case_id="PROP99-WINDOW-1985-1995-M5-OVERALL",
        outcome="cigsale",
        treatment="treated",
        time="year",
        treat_time=1989,
        threshold_m=5,
        p_norm=2,
        mode="overall",
        alpha=0.05,
        simulations=5000,
        seed=12345,
        stata_stored_results=stored_results,
    )


def build_prop99_python_handoff_summary(
    records: Sequence[Mapping[str, object]] | None = None,
    *,
    records_source: str | None = None,
) -> dict[str, object]:
    """Build the packaged Prop99 Python record-to-snapshot workflow summary."""

    uses_packaged_records = records_source is None
    normalized_records_source = (
        "packaged-prop99-records" if uses_packaged_records else str(records_source)
    )
    critical_value_source = (
        "computed-from-packaged-record-covariance"
        if uses_packaged_records
        else "computed-from-record-covariance"
    )
    inputs = compute_pretest_kernel_inputs_from_records(
        load_prop99_window_iter_records() if records is None else records,
        outcome="cigsale",
        treatment="treated",
        time="year",
        treat_time=1989,
        threshold_m=5,
        p_norm=2,
        mode="overall",
    )
    python_f_alpha = compute_critical_value(
        inputs["covariance_matrix"],
        alpha=0.05,
        simulations=5000,
        t_pre=inputs["T_pre"],
        t_post=inputs["T_post"],
        p_norm=2,
        mode="overall",
        covariance_form="iterative",
        seed=12345,
    )
    snapshot_inputs = inputs["snapshot_inputs"]
    if not isinstance(snapshot_inputs, Mapping):
        raise ValueError(
            "build_prop99_python_handoff_summary() requires snapshot_inputs mapping"
        )
    from .pipeline import compute_pretest_snapshot
    from .validation import DatasetProfile

    command = (
        "pretest cigsale, treatment(treated) time(year) treat_time(1989) "
        "threshold(5) p(2) alpha(0.05) overall"
    )
    snapshot = compute_pretest_snapshot(
        command,
        DatasetProfile(
            time_periods=inputs["time_periods"],
            treatment_values=inputs["treatment_values"],
        ),
        f_alpha=python_f_alpha,
        case_id="PROP99-PYTHON-HANDOFF",
        **snapshot_inputs,
    )
    scalars = snapshot.canonical["scalars"]

    return {
        "version": 1,
        "case_id": "PROP99-WINDOW-1985-1995-M5-OVERALL",
        "source": normalized_records_source,
        "records_source": normalized_records_source,
        "workflow": "records-to-kernel-inputs-to-snapshot",
        "command": command,
        "records": {
            "rows": int(inputs["sample_size"]),
            "years": inputs["time_periods"],
            "treatment_values": inputs["treatment_values"],
        },
        "kernel_inputs": {
            "T": int(inputs["T"]),
            "t0": int(inputs["t0"]),
            "T_pre": int(inputs["T_pre"]),
            "T_post": int(inputs["T_post"]),
            "mode": inputs["mode"],
            "p_norm": inputs["p_norm"],
            "threshold": inputs["threshold_m"],
            "S_pre": inputs["S_pre"],
            "pretest_pass": int(inputs["pretest_pass"]),
            "delta_bar": inputs["delta_bar"],
            "se_delta_bar": inputs["se_delta_bar"],
        },
        "critical_value": {
            "f_alpha": python_f_alpha,
            "alpha": 0.05,
            "simulations": 5000,
            "seed": 12345,
            "covariance_form": "iterative",
            "mode": "overall",
            "source": critical_value_source,
        },
        "snapshot": {
            "case_id": snapshot.diagnostics["validation"]["case_id"],
            "mode": snapshot.canonical["macros"]["mode"],
            "data_valid": scalars["data_valid"],
            "pretest_pass": scalars["pretest_pass"],
            "phi": scalars["phi"],
            "S_pre": scalars["S_pre"],
            "threshold": scalars["threshold"],
            "f_alpha": scalars["f_alpha"],
            "delta_bar": scalars["delta_bar"],
            "ci_lower": scalars["ci_lower"],
            "ci_upper": scalars["ci_upper"],
            "ci_conv_lower": scalars["ci_conv_lower"],
            "ci_conv_upper": scalars["ci_conv_upper"],
        },
        "snapshot_inputs": dict(snapshot_inputs),
    }


def _prop99_window_iter_records_dimension_summary(
    records: Sequence[Mapping[str, float | int]],
) -> dict[str, object]:
    _validate_prop99_window_iter_record_dimensions(records)
    years = tuple(sorted({float(record["year"]) for record in records}))
    return {
        "status": "records-match-stata-split-dimensions",
        "records_count": len(records),
        "year_count": len(years),
        "years": years,
        "pre_year_count": sum(year < 1989.0 for year in years),
        "post_year_count": sum(year >= 1989.0 for year in years),
        "treated_total": sum(int(record["treated"]) for record in records),
        "per_year_control_count": 38,
        "per_year_treated_count": 1,
    }


def _prop99_window_iter_critical_value_probe_summary(
    evidence: Mapping[str, object],
) -> dict[str, object]:
    rng_stream_probe = evidence["rng_stream_probe"]
    order_statistic_probe = evidence["order_statistic_probe"]
    regularization_probe = evidence["critical_value_regularization_probe"]
    diagnosis = evidence["critical_value_mismatch_diagnosis"]
    for field, payload in (
        ("rng_stream_probe", rng_stream_probe),
        ("order_statistic_probe", order_statistic_probe),
        ("critical_value_regularization_probe", regularization_probe),
        ("critical_value_mismatch_diagnosis", diagnosis),
    ):
        if not isinstance(payload, Mapping):
            raise ValueError(
                "build_prop99_window_iter_parity_summary() requires "
                f"{field} mapping"
            )
    transform_probe = rng_stream_probe.get("transform_probe")
    psi_probe = rng_stream_probe.get("psi_probe")
    required_probe_status = diagnosis.get("required_probe_status")
    if not isinstance(transform_probe, Mapping):
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires transform_probe mapping"
        )
    if not isinstance(psi_probe, Mapping):
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires psi_probe mapping"
        )
    if not isinstance(required_probe_status, Mapping):
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires required_probe_status mapping"
        )
    if rng_stream_probe.get("matches") is not False:
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires RNG stream mismatch"
        )
    if transform_probe.get("matches") is not True:
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires transform_probe match"
        )
    if psi_probe.get("matches") is not True:
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires psi_probe match"
        )
    if order_statistic_probe.get("quantile_idx_matches") is not True:
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires order-statistic "
            "quantile index match"
        )
    if order_statistic_probe.get("tail_rule_matches") is not True:
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires order-statistic "
            "tail rule match"
        )
    if order_statistic_probe.get("matches_reference_f_alpha") is not True:
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires order-statistic "
            "match to stored e(f_alpha)"
        )
    expected_required_probe_status = {
        "rng_stream_probe": True,
        "rng_stream_mismatch": True,
        "transform_probe": True,
        "psi_probe": True,
        "order_statistic_probe": True,
    }
    if dict(required_probe_status) != expected_required_probe_status:
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires verified "
            "critical-value probe status"
        )
    if diagnosis.get("status") != "rng-stream-specific-mismatch-verified":
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires "
            "rng-stream-specific-mismatch-verified critical-value diagnosis"
        )
    regularization_abs_diff = _normalize_finite_float(
        "critical_value_mismatch_diagnosis.regularization_abs_diff",
        diagnosis["regularization_abs_diff"],
    )
    regularized_minus_unregularized = _normalize_finite_float(
        "critical_value_regularization_probe.regularized_minus_unregularized",
        regularization_probe["regularized_minus_unregularized"],
    )
    reference_minus_regularized = _normalize_finite_float(
        "critical_value_regularization_probe.reference_minus_regularized",
        regularization_probe["reference_minus_regularized"],
    )
    if regularization_abs_diff <= 0.0:
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires positive "
            "regularization residual gap"
        )
    if not math.isclose(
        regularization_abs_diff,
        abs(reference_minus_regularized),
        rel_tol=1e-12,
        abs_tol=1e-9,
    ):
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires regularization "
            "residual gap to match reference-minus-regularized probe"
        )
    if abs(regularized_minus_unregularized) >= 1e-4 * regularization_abs_diff:
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires covariance "
            "regularization effect below RNG gap"
        )
    return {
        "status": diagnosis["status"],
        "attribution": diagnosis["attribution"],
        "required_probe_status": dict(required_probe_status),
        "rng_stream_max_abs_diff": rng_stream_probe["max_abs_diff"],
        "rng_stream_matches": rng_stream_probe["matches"],
        "transform_max_abs_diff": transform_probe["max_abs_diff"],
        "transform_matches": transform_probe["matches"],
        "psi_abs_diff": psi_probe["abs_diff"],
        "psi_matches": psi_probe["matches"],
        "order_statistic_quantile_idx": order_statistic_probe["quantile_idx"],
        "order_statistic_expected_quantile_idx": order_statistic_probe[
            "expected_quantile_idx"
        ],
        "order_statistic_tail_at_previous": order_statistic_probe[
            "tail_at_previous"
        ],
        "order_statistic_tail_at_f_alpha": order_statistic_probe["tail_at_f_alpha"],
        "order_statistic_expected_tail_limit": order_statistic_probe[
            "expected_tail_limit"
        ],
        "order_statistic_tail_rule_matches": order_statistic_probe[
            "tail_rule_matches"
        ],
        "order_statistic_matches_reference_f_alpha": order_statistic_probe[
            "matches_reference_f_alpha"
        ],
        "regularization_abs_diff": regularization_abs_diff,
        "regularized_minus_unregularized": regularized_minus_unregularized,
    }


def build_prop99_window_iter_parity_summary() -> dict[str, object]:
    """Build a compact packaged Prop99 window iterative parity summary."""

    evidence = build_prop99_window_iter_deterministic_split_capture_evidence()
    records_dimension_summary = _prop99_window_iter_records_dimension_summary(
        load_prop99_window_iter_records()
    )
    python_payload = evidence["python_numeric_payload"]
    reference_payload = evidence["reference_numeric_payload"]
    if not isinstance(python_payload, Mapping) or not isinstance(
        reference_payload,
        Mapping,
    ):
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires numeric payloads"
        )
    deterministic_comparisons = evidence["deterministic_match_fields"]
    if isinstance(deterministic_comparisons, (str, bytes, bytearray)) or not isinstance(
        deterministic_comparisons,
        Sequence,
    ):
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires deterministic comparisons"
        )
    deterministic_mismatches = tuple(
        comparison["field"]
        for comparison in deterministic_comparisons
        if isinstance(comparison, Mapping) and comparison.get("matches") is not True
    )
    rng_mismatches = evidence["rng_mismatch_fields"]
    if isinstance(rng_mismatches, (str, bytes, bytearray)) or not isinstance(
        rng_mismatches,
        Sequence,
    ):
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires RNG mismatch fields"
        )
    rng_mismatch = rng_mismatches[0] if rng_mismatches else {}
    if rng_mismatch and not isinstance(rng_mismatch, Mapping):
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires RNG mismatch mappings"
        )
    diagnosis = evidence["critical_value_mismatch_diagnosis"]
    if not isinstance(diagnosis, Mapping):
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires mismatch diagnosis"
        )
    covariance_estimator = evidence["covariance_estimator"]
    if not isinstance(covariance_estimator, Mapping):
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires covariance_estimator mapping"
        )
    critical_value_settings = evidence["critical_value_settings"]
    if not isinstance(critical_value_settings, Mapping):
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires critical_value_settings mapping"
        )
    kernel_inputs = evidence["kernel_inputs"]
    if not isinstance(kernel_inputs, Mapping):
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires kernel_inputs mapping"
        )
    snapshot_inputs = kernel_inputs["snapshot_inputs"]
    if not isinstance(snapshot_inputs, Mapping):
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires snapshot_inputs mapping"
        )
    if snapshot_inputs["pre_violations_form"] != "iterative":
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires iterative "
            "snapshot pre-violations form"
        )
    if (
        critical_value_settings["covariance_form"]
        != snapshot_inputs["covariance_form"]
    ):
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires matching "
            "critical-value and snapshot covariance forms"
        )
    if critical_value_settings["mode"] != kernel_inputs["mode"]:
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires matching "
            "critical-value and kernel-input modes"
        )
    if critical_value_settings["t_pre"] != kernel_inputs["T_pre"]:
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires matching "
            "critical-value and kernel-input T_pre"
        )
    if critical_value_settings["t_post"] != kernel_inputs["T_post"]:
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires matching "
            "critical-value and kernel-input T_post"
        )
    if records_dimension_summary["pre_year_count"] != critical_value_settings["t_pre"]:
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires matching "
            "records pre-year count and critical-value t_pre"
        )
    if records_dimension_summary["post_year_count"] != critical_value_settings["t_post"]:
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires matching "
            "records post-year count and critical-value t_post"
        )
    if records_dimension_summary["year_count"] != (
        critical_value_settings["t_pre"] + critical_value_settings["t_post"]
    ):
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires records year_count "
            "to equal critical-value t_pre + t_post"
        )
    if records_dimension_summary["records_count"] != python_payload["e(N)"]:
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires records_count "
            "to equal Python e(N)"
        )
    if records_dimension_summary["records_count"] != reference_payload["e(N)"]:
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires records_count "
            "to equal reference e(N)"
        )
    if records_dimension_summary["treated_total"] != (
        records_dimension_summary["year_count"]
        * records_dimension_summary["per_year_treated_count"]
    ):
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires treated_total "
            "to equal year_count * per_year_treated_count"
        )
    if records_dimension_summary["records_count"] != (
        records_dimension_summary["year_count"]
        * (
            records_dimension_summary["per_year_control_count"]
            + records_dimension_summary["per_year_treated_count"]
        )
    ):
        raise ValueError(
            "build_prop99_window_iter_parity_summary() requires records_count "
            "to equal year_count * (per_year_control_count + per_year_treated_count)"
        )
    critical_value_probe_summary = _prop99_window_iter_critical_value_probe_summary(
        evidence
    )
    return {
        "version": 1,
        "case_id": evidence["case_id"],
        "source": "packaged-prop99-window-iter-evidence",
        "records_count": records_dimension_summary["records_count"],
        "records_dimension_status": records_dimension_summary["status"],
        "records_dimension_summary": records_dimension_summary,
        "comparison_status": evidence["comparison_status"],
        "capture_status": evidence["capture_status"],
        "covariance_estimator": dict(covariance_estimator),
        "coordinate_metadata": {
            "mode": critical_value_settings["mode"],
            "covariance_form": critical_value_settings["covariance_form"],
            "pre_violations_form": snapshot_inputs["pre_violations_form"],
            "t_pre": critical_value_settings["t_pre"],
            "t_post": critical_value_settings["t_post"],
            "p_norm": critical_value_settings["p_norm"],
            "alpha": critical_value_settings["alpha"],
            "snapshot_inputs_included": False,
            "snapshot_inputs_source": (
                "build_prop99_window_iter_deterministic_split_capture_evidence()"
                ".kernel_inputs.snapshot_inputs"
            ),
        },
        "deterministic_fields_checked": len(deterministic_comparisons),
        "deterministic_mismatch_fields": deterministic_mismatches,
        "deterministic_all_match": not deterministic_mismatches,
        "python_f_alpha": python_payload["e(f_alpha)"],
        "reference_f_alpha": reference_payload["e(f_alpha)"],
        "f_alpha_abs_diff": rng_mismatch.get("abs_diff") if rng_mismatch else 0.0,
        "f_alpha_match": not rng_mismatches,
        "critical_value_mismatch_status": diagnosis["status"],
        "critical_value_mismatch_attribution": diagnosis["attribution"],
        "critical_value_probe_summary": critical_value_probe_summary,
        "excluded_from_deterministic_replay_promotion": evidence[
            "excluded_from_deterministic_replay_promotion"
        ],
        "exact_replay_promotion_field_count": len(
            evidence["exact_replay_promotion_fields"]
        ),
    }
