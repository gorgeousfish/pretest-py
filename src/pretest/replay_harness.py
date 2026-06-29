from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import math
from pathlib import Path


_BUCKETS = ("exact", "display_rounded", "exact_absence", "unresolved")
_RNG_MISMATCH_STATUS = "deterministic-estimator-verified-rng-mismatch"
_VERDICTS = ("matched", "mismatch", "pending")
_RNG_BOUND_COMPARISON_FIELDS = {
    "stdout": {
        "display_rounded": ("critical_value", "ci_lower", "ci_upper"),
    },
    "stored_results": {
        "display_rounded": ("e(f_alpha)", "e(ci_lower)", "e(ci_upper)"),
    },
}
_ALLOWED_GRAPH_STATUSES = (
    "graph-exported",
    "graph-attempted-but-error-198",
    "suppressed-by-nograph",
    "blocked-pending-oracle",
)
_ALLOWED_CAPTURE_METADATA_FIELDS = (
    "capture_ready",
    "observed_years",
    "treat_time",
    "exact_counts_verified",
    "raw_e_snapshot_present",
    "graph_status",
    "numeric_fields_promoted",
    "protected_results_excluded",
)
_ALLOWED_SUMMARY_CAPTURE_STATUS_FIELDS = (
    "capture_ready",
    "capture_status",
    "observed_years",
    "treat_time",
    "exact_counts_verified",
    "raw_e_snapshot_present",
    "graph_status",
    "numeric_fields_promoted",
    "protected_results_excluded",
)
_ALLOWED_ORACLE_CAPTURE_SUMMARY_FIELDS = (
    "required_metadata_fields",
    "required_metadata",
    "blocked_defaults",
    "capture_metadata_status",
    "conditional_ci_gate",
    "precapture_contract_summary",
)
_ALLOWED_CONDITIONAL_CI_GATE_SECTIONS = ("stdout", "stored_results")
_ALLOWED_CONDITIONAL_CI_GATE_FIELDS = (
    "gate_fields",
    "display_rounded_when_valid_pass",
    "exact_absence_when_not_authoritative",
)
_ALLOWED_PRECAPTURE_CONTRACT_SUMMARY_FIELDS = (
    "sample_window",
    "observed_years",
    "treat_time",
    "mode",
    "exact_fields_available_before_capture",
)
_ALLOWED_PRECAPTURE_EXACT_SUMMARY_FIELDS = ("stdout", "stored_results")
_ALLOWED_BLOCKED_DEFAULTS_FIELDS = (
    "capture_ready",
    "raw_e_snapshot_present",
    "numeric_fields_promoted",
    "protected_results_excluded",
)
_CANONICAL_STORY_PACKET_ARTIFACT_PATH_FIELDS = (
    "driver",
    "summary_template",
    "overall_capture_packet",
    "overall_capture_verifier_input",
    "precapture_contract",
    "stata_stdout",
    "python_stdout",
    "stata_stored_results",
    "python_stored_results",
    "stata_graph_data",
    "capture_metadata",
    "protected_auxiliary_contract",
    "auxiliary_diagnostic_verifier_input",
)
_REQUIRED_PRECAPTURE_REQUIREMENT_MARKERS = (
    "precapture_contract is required before capture_ready may flip to true",
    "observed_years must be present before capture_ready may flip to true",
    "treat_time must be present before capture_ready may flip to true",
)
_SECTIONS = (
    ("stdout", "stdout_categories", "stdout_summary"),
    ("stored_results", "stored_results_categories", "stored_results_summary"),
)


def _bundled_prop99_story_packet_auxiliary_artifact_paths() -> dict[str, str]:
    bundled_root = Path(__file__).resolve().parent / "data" / "prop99_replay"
    return {
        "protected_auxiliary_contract": str(
            bundled_root / "pretest_overall_auxiliary_contract.yaml"
        ),
        "auxiliary_diagnostic_verifier_input": str(
            bundled_root / "pretest_overall_auxiliary_diagnostic_verifier_input.yaml"
        ),
    }


def _bundled_prop99_story_packet_scaffold_artifact_paths() -> dict[str, str]:
    bundled_root = Path(__file__).resolve().parent / "data" / "prop99_replay"
    return {
        "driver": str(bundled_root / "prop99_replay_driver.yaml"),
        "summary_template": str(
            bundled_root / "prop99_replay_summary_template.yaml"
        ),
        "overall_capture_packet": str(
            bundled_root / "prop99_overall_capture_packet_template.yaml"
        ),
        "overall_capture_verifier_input": str(
            bundled_root / "prop99_overall_capture_verifier_input.yaml"
        ),
        "precapture_contract": str(
            bundled_root / "prop99_overall_precapture_contract.yaml"
        ),
    }


def _authoritative_summary_conditional_ci_gate() -> dict[str, dict[str, list[str]]]:
    return {
        "stdout": {
            "gate_fields": ["pretest_result", "e(pretest_pass)", "e(data_valid)"],
            "display_rounded_when_valid_pass": ["ci_lower", "ci_upper"],
            "exact_absence_when_not_authoritative": ["ci_lower", "ci_upper"],
        },
        "stored_results": {
            "gate_fields": ["e(pretest_pass)", "e(data_valid)"],
            "display_rounded_when_valid_pass": ["e(ci_lower)", "e(ci_upper)"],
            "exact_absence_when_not_authoritative": ["e(ci_lower)", "e(ci_upper)"],
        },
    }


def _mapping_copy(value: Mapping[str, object], *, label: str) -> dict[str, object]:
    data = dict(value)
    if "case_id" not in data:
        raise ValueError(f"{label} must define case_id")
    data["case_id"] = _nonempty_string(data["case_id"], label=f"{label}.case_id")
    if "verdict" in data:
        data["verdict"] = _nonempty_string(data["verdict"], label=f"{label}.verdict")
    return data


def _document_mapping(value: Mapping[str, object], *, label: str) -> dict[str, object]:
    data = dict(value)
    cases = data.get("cases")
    if not isinstance(cases, list):
        raise ValueError(f"{label} must define cases")
    return data


def _string_list(
    value: object,
    *,
    label: str,
    require_unique: bool = False,
) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    strings: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{label} must contain only non-empty strings")
        if item != item.strip():
            raise ValueError(
                f"{label} must not contain leading or trailing whitespace"
            )
        if require_unique and item in seen:
            raise ValueError(f"{label} must not contain duplicate entries")
        seen.add(item)
        strings.append(item)
    return strings


def _bool_value(value: object, *, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a boolean")
    return value


def _int_value(value: object, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    return value


def _int_list(
    value: object,
    *,
    label: str,
    require_unique: bool = False,
) -> list[int]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list of integers")
    integers: list[int] = []
    seen: set[int] = set()
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int):
            raise ValueError(f"{label} must be a list of integers")
        if require_unique and item in seen:
            raise ValueError(f"{label} must not contain duplicate entries")
        seen.add(item)
        integers.append(item)
    return integers


def _bucket_values(
    bundle: Mapping[str, object],
    *,
    section: str,
    bucket: str,
) -> dict[str, object] | list[str]:
    section_payload = bundle.get(section)
    if not isinstance(section_payload, Mapping):
        raise ValueError(f"replay bundle missing {section} payload")

    bucket_payload = section_payload.get(bucket)
    if bucket == "exact_absence":
        return _string_list(
            bucket_payload,
            label=f"replay bundle {section}.{bucket}",
            require_unique=True,
        )
    if not isinstance(bucket_payload, Mapping):
        raise ValueError(f"replay bundle {section}.{bucket} must be a mapping")
    return {str(key): value for key, value in bucket_payload.items()}


def _graph_status(bundle: Mapping[str, object], *, label: str) -> str:
    return _nonempty_string(bundle.get("graph_status"), label=f"{label}.graph_status")


def _graph_series_comparison_verified(graph_data_summary: Mapping[str, object]) -> bool:
    def is_plain_int(value: object) -> bool:
        return isinstance(value, int) and not isinstance(value, bool)

    def finite_nonnegative(value: object) -> bool:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
            and float(value) >= 0
        )

    series_comparison = graph_data_summary.get("series_comparison")
    if not isinstance(series_comparison, Mapping):
        return False
    if series_comparison.get("status") != "estimates-match-derived-preview":
        return False
    if series_comparison.get("source") != "stored-results-reconstruction":
        return False
    if series_comparison.get("all_estimates_match") is not True:
        return False
    tolerance = series_comparison.get("tolerance")
    pre_max_abs_diff = series_comparison.get("pre_max_abs_diff")
    post_max_abs_diff = series_comparison.get("post_max_abs_diff")
    if not (
        finite_nonnegative(tolerance)
        and finite_nonnegative(pre_max_abs_diff)
        and finite_nonnegative(post_max_abs_diff)
    ):
        return False
    if pre_max_abs_diff > tolerance or post_max_abs_diff > tolerance:
        return False
    expected_pre = graph_data_summary.get("pre_treatment_points_expected")
    observed_pre = graph_data_summary.get("pre_treatment_points_observed")
    compared_pre = series_comparison.get("compared_pre_points")
    expected_post = graph_data_summary.get("post_treatment_points_expected")
    observed_post = graph_data_summary.get("post_treatment_points_observed")
    compared_post = series_comparison.get("compared_post_points")
    return (
        is_plain_int(expected_pre)
        and is_plain_int(observed_pre)
        and is_plain_int(compared_pre)
        and expected_pre == observed_pre == compared_pre
        and is_plain_int(expected_post)
        and is_plain_int(observed_post)
        and is_plain_int(compared_post)
        and expected_post == observed_post == compared_post
    )


def _graph_sidecar_core_summary(
    graph_data_summary: Mapping[str, object],
) -> dict[str, object]:
    return {
        key: deepcopy(graph_data_summary.get(key))
        for key in (
            "pre_treatment_points_expected",
            "pre_treatment_points_observed",
            "post_treatment_points_expected",
            "post_treatment_points_observed",
            "series_complete",
            "reason",
        )
    }


def _graph_summary_preview_comparison(
    *,
    reference_graph_data_summary: Mapping[str, object],
    article_graph_data_summary: Mapping[str, object],
) -> dict[str, object]:
    reference_series = reference_graph_data_summary.get("series_comparison")
    article_series = article_graph_data_summary.get("series_comparison")
    if not isinstance(reference_series, Mapping) or not isinstance(
        article_series, Mapping
    ):
        raise ValueError(
            "graph_data_summary series_comparison must be present on both bundles"
        )
    return {
        "status": (
            "same-sidecar-python-preview-differs-from-reference"
            if dict(reference_graph_data_summary) != dict(article_graph_data_summary)
            else "same-sidecar-python-preview-identical-to-reference"
        ),
        "reference": {
            "series_match_derived_preview": reference_graph_data_summary.get(
                "series_match_derived_preview"
            ),
            "series_comparison": deepcopy(dict(reference_series)),
        },
        "article": {
            "series_match_derived_preview": article_graph_data_summary.get(
                "series_match_derived_preview"
            ),
            "series_comparison": deepcopy(dict(article_series)),
        },
        "reason": (
            "Both bundles use the captured Stata graph sidecar for exported "
            "point estimates. The article-facing preview is derived from the "
            "Python stored results, so tiny sidecar-to-preview differences are "
            "recorded as reference metadata rather than treated as a failed "
            "Python graph."
        ),
    }


def _normalized_optional_mapping(
    value: object,
    *,
    case_id: str,
    label: str,
) -> dict[str, object] | None:
    if value is None:
        return None
    normalized = _string_mapping(value, label=f"{case_id} {label}")
    if any(any(character.isspace() for character in key) for key in normalized):
        raise ValueError(f"{label} keys must not contain whitespace")
    protected_results = normalized.get("protected_results")
    if protected_results is not None:
        normalized["protected_results"] = _string_list(
            protected_results,
            label=f"{case_id} {label}.protected_results",
            require_unique=True,
        )
    return normalized


def _string_mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    normalized: dict[str, object] = {}
    for key, item in value.items():
        normalized_key = str(key)
        if normalized_key in normalized:
            raise ValueError(f"{label} keys must remain unique after normalization")
        normalized[normalized_key] = deepcopy(item)

    for key in value:
        if not isinstance(key, str) or not key.strip() or key != key.strip():
            raise ValueError(f"{label} keys must be non-empty strings")

    return normalized


def _artifact_path_mapping(value: object, *, label: str) -> dict[str, str]:
    mapping = _string_mapping(value, label=label)
    normalized: dict[str, str] = {}
    for field_name, path_value in mapping.items():
        normalized[field_name] = _nonempty_string(
            path_value,
            label=f"{label}.{field_name}",
        )
    return normalized


def _validate_existing_artifact_paths(
    value: object,
    *,
    label: str,
    callable_name: str,
) -> dict[str, str]:
    normalized = _artifact_path_mapping(value, label=label)
    for field_name, path_value in normalized.items():
        if not Path(path_value).is_file():
            raise ValueError(
                f"{callable_name}() requires "
                f"{label}.{field_name} to point to an existing file"
            )
    return normalized


def _nonempty_string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    if value != value.strip():
        raise ValueError(f"{label} must not contain leading or trailing whitespace")
    return value


def _required_metadata_fields(
    value: object,
    *,
    label: str,
) -> list[str]:
    fields = _string_list(value, label=label, require_unique=True)
    unexpected_fields = sorted(set(fields) - set(_ALLOWED_CAPTURE_METADATA_FIELDS))
    if unexpected_fields:
        raise ValueError(
            f"{label} must stay within the allowed capture metadata field surface: "
            + ", ".join(unexpected_fields)
        )
    return fields


def _capture_metadata_requirements(
    value: object,
    *,
    label: str,
) -> list[str]:
    return _string_list(value, label=label, require_unique=True)


def _normalized_requirement_markers(requirements: list[str]) -> set[str]:
    return {
        requirement.strip().rstrip(".").lower()
        for requirement in requirements
    }


def _graph_status_value(value: object, *, label: str) -> str:
    normalized = _nonempty_string(value, label=label)
    if normalized not in _ALLOWED_GRAPH_STATUSES:
        allowed = ", ".join(_ALLOWED_GRAPH_STATUSES)
        raise ValueError(f"{label} must be one of: {allowed}")
    return normalized


def _capture_status_value(value: object, *, label: str) -> str:
    return _nonempty_string(value, label=label)


def _case_lookup(
    cases: object,
    *,
    label: str,
) -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
    if not isinstance(cases, list):
        raise ValueError(f"{label} must define cases")

    ordered_cases: list[dict[str, object]] = []
    lookup: dict[str, dict[str, object]] = {}
    for index, case in enumerate(cases):
        if not isinstance(case, Mapping):
            raise ValueError(f"{label}[{index}] must be a mapping")
        normalized_case = _mapping_copy(case, label=f"{label}[{index}]")
        case_id = str(normalized_case["case_id"])
        if case_id in lookup:
            raise ValueError(f"{label} defines duplicate case_id {case_id}")
        ordered_cases.append(normalized_case)
        lookup[case_id] = normalized_case
    return ordered_cases, lookup


def _validate_document_alignment(
    driver_document: dict[str, object],
    summary_template: dict[str, object],
    *,
    driver_cases: list[dict[str, object]],
    summary_cases: list[dict[str, object]],
) -> None:
    verdict_buckets = _string_list(
        summary_template.get("verdict_buckets"),
        label="summary_template.verdict_buckets",
    )
    if verdict_buckets != list(_BUCKETS):
        raise ValueError("summary_template verdict_buckets drift")

    driver_case_order = [str(case["case_id"]) for case in driver_cases]
    summary_case_order = [str(case["case_id"]) for case in summary_cases]
    if summary_case_order != driver_case_order:
        raise ValueError("summary_template case order drift")


def _blocked_defaults(
    value: object,
    *,
    case_id: str,
    label: str,
) -> dict[str, object]:
    defaults = _string_mapping(value, label=f"{case_id} {label}")
    unexpected_fields = sorted(
        set(defaults) - set(_ALLOWED_BLOCKED_DEFAULTS_FIELDS)
    )
    if unexpected_fields:
        raise ValueError(
            f"{case_id} {label} contains unknown fields: "
            + ", ".join(unexpected_fields)
        )
    normalized: dict[str, object] = {}
    if "capture_ready" in defaults:
        normalized["capture_ready"] = _bool_value(
            defaults["capture_ready"],
            label=f"{case_id} {label}.capture_ready",
        )
    if "raw_e_snapshot_present" in defaults:
        normalized["raw_e_snapshot_present"] = _bool_value(
            defaults["raw_e_snapshot_present"],
            label=f"{case_id} {label}.raw_e_snapshot_present",
        )
    if "numeric_fields_promoted" in defaults:
        normalized["numeric_fields_promoted"] = _string_list(
            defaults["numeric_fields_promoted"],
            label=f"{case_id} {label}.numeric_fields_promoted",
            require_unique=True,
        )
    if "protected_results_excluded" in defaults:
        normalized["protected_results_excluded"] = _bool_value(
            defaults["protected_results_excluded"],
            label=f"{case_id} {label}.protected_results_excluded",
        )
    if normalized.get("protected_results_excluded") is not True:
        raise ValueError(
            f"{label}.protected_results_excluded must remain true"
        )
    return normalized


def _summary_conditional_ci_gate(
    value: object,
    *,
    case_id: str,
    label: str,
) -> dict[str, dict[str, list[str]]]:
    gate_summary = _string_mapping(value, label=f"{case_id} {label}")
    unexpected_sections = sorted(
        set(gate_summary) - set(_ALLOWED_CONDITIONAL_CI_GATE_SECTIONS)
    )
    if unexpected_sections:
        raise ValueError(
            f"{case_id} {label} contains unknown sections: "
            + ", ".join(unexpected_sections)
        )

    normalized: dict[str, dict[str, list[str]]] = {}
    for section in _ALLOWED_CONDITIONAL_CI_GATE_SECTIONS:
        section_gate = _string_mapping(
            gate_summary.get(section),
            label=f"{case_id} {label}.{section}",
        )
        unexpected_fields = sorted(
            set(section_gate) - set(_ALLOWED_CONDITIONAL_CI_GATE_FIELDS)
        )
        if unexpected_fields:
            raise ValueError(
                f"{case_id} {label}.{section} contains unknown fields: "
                + ", ".join(unexpected_fields)
            )
        normalized[section] = {
            "gate_fields": _string_list(
                section_gate.get("gate_fields"),
                label=f"{case_id} {label}.{section}.gate_fields",
                require_unique=True,
            ),
            "display_rounded_when_valid_pass": _string_list(
                section_gate.get("display_rounded_when_valid_pass"),
                label=(
                    f"{case_id} "
                    f"{label}.{section}.display_rounded_when_valid_pass"
                ),
            ),
            "exact_absence_when_not_authoritative": _string_list(
                section_gate.get("exact_absence_when_not_authoritative"),
                label=(
                    f"{case_id} "
                    f"{label}.{section}.exact_absence_when_not_authoritative"
                ),
            ),
        }
    return normalized


def _summary_precapture_contract_summary(
    value: object,
    *,
    case_id: str,
    label: str,
) -> dict[str, object]:
    summary = _string_mapping(value, label=f"{case_id} {label}")
    unexpected_fields = sorted(
        set(summary) - set(_ALLOWED_PRECAPTURE_CONTRACT_SUMMARY_FIELDS)
    )
    if unexpected_fields:
        raise ValueError(
            f"{case_id} {label} contains unknown fields: "
            + ", ".join(unexpected_fields)
        )

    exact_fields = _string_mapping(
        summary.get("exact_fields_available_before_capture"),
        label=f"{case_id} {label}.exact_fields_available_before_capture",
    )
    unexpected_exact_sections = sorted(
        set(exact_fields) - set(_ALLOWED_PRECAPTURE_EXACT_SUMMARY_FIELDS)
    )
    if unexpected_exact_sections:
        raise ValueError(
            f"{case_id} {label}.exact_fields_available_before_capture contains unknown sections: "
            + ", ".join(unexpected_exact_sections)
        )

    return {
        "sample_window": _int_list(
            summary.get("sample_window"),
            label=f"{case_id} {label}.sample_window",
        ),
        "observed_years": _int_list(
            summary.get("observed_years"),
            label=f"{case_id} {label}.observed_years",
            require_unique=True,
        ),
        "treat_time": _int_value(
            summary.get("treat_time"),
            label=f"{case_id} {label}.treat_time",
        ),
        "mode": _nonempty_string(
            summary.get("mode"),
            label=f"{case_id} {label}.mode",
        ),
        "exact_fields_available_before_capture": {
            "stdout": _string_mapping(
                exact_fields.get("stdout"),
                label=(
                    f"{case_id} "
                    f"{label}.exact_fields_available_before_capture.stdout"
                ),
            ),
            "stored_results": _string_mapping(
                exact_fields.get("stored_results"),
                label=(
                    f"{case_id} "
                    f"{label}.exact_fields_available_before_capture.stored_results"
                ),
            ),
        },
    }


def _normalized_oracle_capture_summary_fields(
    value: object,
    *,
    case_id: str,
) -> dict[str, object] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError(f"{case_id} oracle_capture_summary must be a mapping or null")

    oracle_capture_summary = dict(value)
    unexpected_summary_fields = sorted(
        set(oracle_capture_summary) - set(_ALLOWED_ORACLE_CAPTURE_SUMMARY_FIELDS)
    )
    if unexpected_summary_fields:
        raise ValueError(
            f"{case_id} oracle_capture_summary contains unknown fields: "
            + ", ".join(unexpected_summary_fields)
        )

    if "required_metadata_fields" in oracle_capture_summary:
        oracle_capture_summary["required_metadata_fields"] = _required_metadata_fields(
            oracle_capture_summary["required_metadata_fields"],
            label=f"{case_id} oracle_capture_summary.required_metadata_fields",
        )
    if "required_metadata" in oracle_capture_summary:
        oracle_capture_summary["required_metadata"] = _capture_metadata_requirements(
            oracle_capture_summary["required_metadata"],
            label=f"{case_id} oracle_capture_summary.required_metadata",
        )
    if "blocked_defaults" in oracle_capture_summary:
        oracle_capture_summary["blocked_defaults"] = _blocked_defaults(
            oracle_capture_summary["blocked_defaults"],
            case_id=case_id,
            label="oracle_capture_summary.blocked_defaults",
        )
    if "conditional_ci_gate" in oracle_capture_summary:
        oracle_capture_summary["conditional_ci_gate"] = _summary_conditional_ci_gate(
            oracle_capture_summary["conditional_ci_gate"],
            case_id=case_id,
            label="oracle_capture_summary.conditional_ci_gate",
        )
    if "precapture_contract_summary" in oracle_capture_summary:
        oracle_capture_summary["precapture_contract_summary"] = (
            _summary_precapture_contract_summary(
                oracle_capture_summary["precapture_contract_summary"],
                case_id=case_id,
                label="oracle_capture_summary.precapture_contract_summary",
            )
        )
    return oracle_capture_summary


def _metadata_status(
    *,
    case_id: str,
    blocked_defaults: Mapping[str, object],
    capture_metadata: Mapping[str, object] | None,
    required_metadata_fields: list[str],
) -> dict[str, object]:
    status = {
        "capture_status": None,
        "capture_ready": deepcopy(blocked_defaults.get("capture_ready")),
        "observed_years": None,
        "treat_time": None,
        "exact_counts_verified": None,
        "raw_e_snapshot_present": deepcopy(
            blocked_defaults.get("raw_e_snapshot_present")
        ),
        "graph_status": None,
        "numeric_fields_promoted": deepcopy(
            blocked_defaults.get("numeric_fields_promoted", [])
        ),
        "protected_results_excluded": deepcopy(
            blocked_defaults.get("protected_results_excluded")
        ),
    }

    if capture_metadata is None:
        return status

    capture_status = capture_metadata.get("capture_status")
    capture_status = _nonempty_string(
        capture_status,
        label=f"{case_id} capture_metadata.capture_status",
    )
    status["capture_status"] = capture_status

    payload = capture_metadata.get("metadata_payload")
    if payload is None:
        if not capture_status.startswith("blocked-"):
            raise ValueError(
                f"{case_id} capture_metadata.metadata_payload is required when capture_status leaves blocked state"
            )
        return status

    payload_mapping = _string_mapping(
        payload, label=f"{case_id} capture_metadata.metadata_payload"
    )
    if not payload_mapping and not capture_status.startswith("blocked-"):
        raise ValueError(
            f"{case_id} capture_metadata.metadata_payload must define at least one field when capture_status leaves blocked state"
        )
    unexpected_fields = sorted(
        set(payload_mapping) - set(_ALLOWED_CAPTURE_METADATA_FIELDS)
    )
    if unexpected_fields:
        raise ValueError(
            f"{case_id} capture_metadata.metadata_payload contains unknown fields: "
            + ", ".join(unexpected_fields)
        )
    if "capture_ready" in payload_mapping:
        status["capture_ready"] = _bool_value(
            payload_mapping["capture_ready"],
            label=f"{case_id} capture_metadata.metadata_payload.capture_ready",
        )
    if "observed_years" in payload_mapping:
        status["observed_years"] = _int_list(
            payload_mapping["observed_years"],
            label=f"{case_id} capture_metadata.metadata_payload.observed_years",
            require_unique=True,
        )
    if "treat_time" in payload_mapping:
        status["treat_time"] = _int_value(
            payload_mapping["treat_time"],
            label=f"{case_id} capture_metadata.metadata_payload.treat_time",
        )
    if "exact_counts_verified" in payload_mapping:
        status["exact_counts_verified"] = _bool_value(
            payload_mapping["exact_counts_verified"],
            label=f"{case_id} capture_metadata.metadata_payload.exact_counts_verified",
        )
    if "raw_e_snapshot_present" in payload_mapping:
        status["raw_e_snapshot_present"] = _bool_value(
            payload_mapping["raw_e_snapshot_present"],
            label=f"{case_id} capture_metadata.metadata_payload.raw_e_snapshot_present",
        )
    if "graph_status" in payload_mapping:
        status["graph_status"] = _graph_status_value(
            payload_mapping["graph_status"],
            label=f"{case_id} capture_metadata.metadata_payload.graph_status",
        )
    if "numeric_fields_promoted" in payload_mapping:
        status["numeric_fields_promoted"] = _string_list(
            payload_mapping["numeric_fields_promoted"],
            label=f"{case_id} capture_metadata.metadata_payload.numeric_fields_promoted",
            require_unique=True,
        )
    if "protected_results_excluded" in payload_mapping:
        status["protected_results_excluded"] = _bool_value(
            payload_mapping["protected_results_excluded"],
            label=f"{case_id} capture_metadata.metadata_payload.protected_results_excluded",
        )
    if capture_status.startswith("blocked-"):
        raise ValueError(
            f"{case_id} capture_metadata.metadata_payload must remain null while capture_status stays blocked"
        )

    if status["protected_results_excluded"] is not True:
        raise ValueError(
            f"{case_id} capture_metadata.metadata_payload.protected_results_excluded must remain true"
        )
    if (
        isinstance(capture_status, str)
        and capture_status.startswith("blocked-")
        and status["capture_ready"] is True
    ):
        raise ValueError(
            f"{case_id} capture_metadata.capture_status must leave blocked state before capture_ready may flip to true"
        )
    if status["capture_ready"] is not True and status["numeric_fields_promoted"]:
        raise ValueError(
            f"{case_id} capture_metadata.metadata_payload.numeric_fields_promoted must stay empty while capture_ready is false"
        )
    if status["capture_ready"] is True:
        for field in ("numeric_fields_promoted", "protected_results_excluded"):
            if field not in payload_mapping:
                raise ValueError(
                    f"{case_id} capture_metadata.metadata_payload.{field} must be present before capture_ready may flip to true"
                )
        if not status["numeric_fields_promoted"]:
            raise ValueError(
                f"{case_id} capture_metadata.metadata_payload.numeric_fields_promoted must list at least one promoted field before capture_ready may flip to true"
            )
        graph_status = status["graph_status"]
        if not isinstance(graph_status, str) or graph_status.startswith("blocked-"):
            raise ValueError(
                f"{case_id} capture_metadata.metadata_payload.graph_status must leave blocked state before capture_ready may flip to true"
            )
        if status["exact_counts_verified"] is not True:
            raise ValueError(
                f"{case_id} capture_metadata.metadata_payload.exact_counts_verified must be true before capture_ready may flip to true"
            )
        if status["raw_e_snapshot_present"] is not True:
            raise ValueError(
                f"{case_id} capture_metadata.metadata_payload.raw_e_snapshot_present must be true before capture_ready may flip to true"
            )
    return status


def _conditional_ci_gate(
    verifier_input: Mapping[str, object],
    *,
    case_id: str,
) -> dict[str, dict[str, list[str]]]:
    comparison_plan = verifier_input.get("comparison_plan")
    if not isinstance(comparison_plan, Mapping):
        raise ValueError(
            f"{case_id} overall capture verifier input missing comparison_plan"
        )

    gate_summary: dict[str, dict[str, list[str]]] = {}
    for section in ("stdout", "stored_results"):
        section_plan = comparison_plan.get(section)
        if not isinstance(section_plan, Mapping):
            raise ValueError(
                f"{case_id} overall capture verifier input missing {section} plan"
            )
        conditional_ci = section_plan.get("conditional_ci_after_capture")
        if not isinstance(conditional_ci, Mapping):
            raise ValueError(
                f"{case_id} overall capture verifier input missing {section} conditional CI plan"
            )
        valid_pass = conditional_ci.get("if_data_valid_and_pass")
        if not isinstance(valid_pass, Mapping):
            raise ValueError(
                f"{case_id} overall capture verifier input missing {section} valid-pass plan"
            )
        gate_summary[section] = {
            "gate_fields": _string_list(
                conditional_ci.get("gate_fields"),
                label=f"{case_id} {section} conditional_ci_after_capture.gate_fields",
                require_unique=True,
            ),
            "display_rounded_when_valid_pass": _string_list(
                valid_pass.get("display_rounded"),
                label=f"{case_id} {section} conditional_ci_after_capture.if_data_valid_and_pass.display_rounded",
            ),
            "exact_absence_when_not_authoritative": _string_list(
                conditional_ci.get("exact_absence_when_not_authoritative"),
                label=f"{case_id} {section} conditional_ci_after_capture.exact_absence_when_not_authoritative",
            ),
        }
    return gate_summary


def _validate_conditional_ci_promotions(
    promoted_fields: list[str],
    conditional_ci_gate: Mapping[str, Mapping[str, list[str]]],
    *,
    case_id: str,
) -> None:
    promoted_field_set = set(promoted_fields)
    for section_gate in conditional_ci_gate.values():
        gate_fields = _string_list(
            section_gate.get("gate_fields"),
            label=f"{case_id} conditional_ci_gate.gate_fields",
        )
        conditional_fields = set(
            _string_list(
                section_gate.get("display_rounded_when_valid_pass"),
                label=f"{case_id} conditional_ci_gate.display_rounded_when_valid_pass",
            )
            + _string_list(
                section_gate.get("exact_absence_when_not_authoritative"),
                label=f"{case_id} conditional_ci_gate.exact_absence_when_not_authoritative",
            )
        )
        if conditional_fields.isdisjoint(promoted_field_set):
            continue

        missing_gate_fields = [
            field for field in gate_fields if field not in promoted_field_set
        ]
        if missing_gate_fields:
            raise ValueError(
                f"{case_id} conditional CI promoted fields must include gate fields before promotion: "
                + ", ".join(missing_gate_fields)
            )


def _precapture_contract_summary(
    precapture_contract: Mapping[str, object],
    *,
    case_id: str,
    capture_metadata: Mapping[str, object] | None,
    expected_sample_window: list[int],
    expected_required_fields: list[str],
    expected_blocked_defaults: Mapping[str, object],
) -> dict[str, object]:
    contract = _string_mapping(
        precapture_contract,
        label=f"{case_id} precapture_contract",
    )
    if str(contract.get("case_id")) != case_id:
        raise ValueError(f"{case_id} precapture contract case_id drift")

    dataset_slice = contract.get("dataset_slice")
    if not isinstance(dataset_slice, Mapping):
        raise ValueError(f"{case_id} precapture contract missing dataset_slice")
    command_contract = contract.get("command_contract")
    if not isinstance(command_contract, Mapping):
        raise ValueError(f"{case_id} precapture contract missing command_contract")
    exact_fields = contract.get("exact_fields_available_before_capture")
    if not isinstance(exact_fields, Mapping):
        raise ValueError(
            f"{case_id} precapture contract missing exact_fields_available_before_capture"
        )
    capture_metadata_contract = contract.get("capture_metadata_contract")
    if not isinstance(capture_metadata_contract, Mapping):
        raise ValueError(
            f"{case_id} precapture contract missing capture_metadata_contract"
        )

    sample_window = _int_list(
        dataset_slice.get("sample_window"),
        label=f"{case_id} precapture_contract.dataset_slice.sample_window",
    )
    if sample_window != expected_sample_window:
        raise ValueError(f"{case_id} precapture contract sample_window drift")
    observed_years = _int_list(
        dataset_slice.get("observed_years"),
        label=f"{case_id} precapture_contract.dataset_slice.observed_years",
        require_unique=True,
    )
    treat_time = _int_value(
        dataset_slice.get("treat_time"),
        label=f"{case_id} precapture_contract.dataset_slice.treat_time",
    )
    mode = command_contract.get("mode")
    if not isinstance(mode, str) or not mode:
        raise ValueError(
            f"{case_id} precapture contract command_contract.mode must be a string"
        )
    if mode != "overall":
        raise ValueError(
            f"{case_id} precapture contract command_contract.mode must remain overall"
        )

    row_count = _int_value(
        dataset_slice.get("row_count"),
        label=f"{case_id} precapture_contract.dataset_slice.row_count",
    )
    total_periods = _int_value(
        dataset_slice.get("total_periods"),
        label=f"{case_id} precapture_contract.dataset_slice.total_periods",
    )
    pre_period_count = _int_value(
        dataset_slice.get("pre_period_count"),
        label=f"{case_id} precapture_contract.dataset_slice.pre_period_count",
    )
    post_period_count = _int_value(
        dataset_slice.get("post_period_count"),
        label=f"{case_id} precapture_contract.dataset_slice.post_period_count",
    )

    stdout_exact = _string_mapping(
        exact_fields.get("stdout"),
        label=f"{case_id} precapture_contract.exact_fields_available_before_capture.stdout",
    )
    stored_results_exact = _string_mapping(
        exact_fields.get("stored_results"),
        label=f"{case_id} precapture_contract.exact_fields_available_before_capture.stored_results",
    )
    required_fields = _required_metadata_fields(
        capture_metadata_contract.get("required_fields"),
        label=f"{case_id} precapture_contract.capture_metadata_contract.required_fields",
    )
    if required_fields != expected_required_fields:
        raise ValueError(f"{case_id} precapture contract required_fields drift")
    blocked_defaults = _blocked_defaults(
        capture_metadata_contract.get("blocked_defaults"),
        case_id=case_id,
        label=f"{case_id} precapture_contract.capture_metadata_contract.blocked_defaults",
    )
    if blocked_defaults != dict(expected_blocked_defaults):
        raise ValueError(f"{case_id} precapture contract blocked_defaults drift")

    expected_stdout_exact = {
        "N": row_count,
        "T": total_periods,
        "T_pre": pre_period_count,
        "T_post": post_period_count,
    }
    for field, expected_value in expected_stdout_exact.items():
        if stdout_exact.get(field) != expected_value:
            raise ValueError(
                f"{case_id} precapture contract exact stdout drift for {field}"
            )

    expected_stored_results_exact = {
        "e(N)": row_count,
        "e(T)": total_periods,
        "e(T_pre)": pre_period_count,
        "e(T_post)": post_period_count,
        "e(mode)": mode,
    }
    for field, expected_value in expected_stored_results_exact.items():
        if stored_results_exact.get(field) != expected_value:
            raise ValueError(
                f"{case_id} precapture contract exact stored_results drift for {field}"
            )

    if capture_metadata is not None:
        payload = capture_metadata.get("metadata_payload")
        if isinstance(payload, Mapping):
            payload_mapping = _string_mapping(
                payload,
                label=f"{case_id} capture_metadata.metadata_payload",
            )
            if "observed_years" in payload_mapping:
                if (
                    _int_list(
                        payload_mapping["observed_years"],
                        label=f"{case_id} capture_metadata.metadata_payload.observed_years",
                        require_unique=True,
                    )
                    != observed_years
                ):
                    raise ValueError(
                        f"{case_id} capture_metadata.metadata_payload.observed_years must match precapture contract"
                    )
            if "treat_time" in payload_mapping:
                if (
                    _int_value(
                        payload_mapping["treat_time"],
                        label=f"{case_id} capture_metadata.metadata_payload.treat_time",
                    )
                    != treat_time
                ):
                    raise ValueError(
                        f"{case_id} capture_metadata.metadata_payload.treat_time must match precapture contract"
                    )

    return {
        "sample_window": sample_window,
        "observed_years": observed_years,
        "treat_time": treat_time,
        "mode": mode,
        "exact_fields_available_before_capture": {
            "stdout": stdout_exact,
            "stored_results": stored_results_exact,
        },
    }


def _precapture_graph_requested(
    precapture_contract: Mapping[str, object],
    *,
    case_id: str,
) -> bool:
    contract = _string_mapping(
        precapture_contract,
        label=f"{case_id} precapture_contract",
    )
    command_contract = contract.get("command_contract")
    if not isinstance(command_contract, Mapping):
        raise ValueError(f"{case_id} precapture contract missing command_contract")
    return _bool_value(
        command_contract.get("graph_requested"),
        label=f"{case_id} precapture_contract.command_contract.graph_requested",
    )


def _expected_precapture_contract_summary(
    precapture_contract: Mapping[str, object],
    *,
    case_id: str,
    expected_sample_window: list[int],
) -> dict[str, object]:
    contract = _string_mapping(
        precapture_contract,
        label=f"{case_id} precapture_contract",
    )
    capture_metadata_contract = contract.get("capture_metadata_contract")
    if not isinstance(capture_metadata_contract, Mapping):
        raise ValueError(
            f"{case_id} precapture contract missing capture_metadata_contract"
        )
    required_fields = _required_metadata_fields(
        capture_metadata_contract.get("required_fields"),
        label=f"{case_id} precapture_contract.capture_metadata_contract.required_fields",
    )
    blocked_defaults = _blocked_defaults(
        capture_metadata_contract.get("blocked_defaults"),
        case_id=case_id,
        label=f"{case_id} precapture_contract.capture_metadata_contract.blocked_defaults",
    )
    return _precapture_contract_summary(
        precapture_contract,
        case_id=case_id,
        capture_metadata=None,
        expected_sample_window=expected_sample_window,
        expected_required_fields=required_fields,
        expected_blocked_defaults=blocked_defaults,
    )


def _validate_summary_precapture_contract_summary(
    actual_summary: Mapping[str, object],
    *,
    precapture_contract: Mapping[str, object],
    case_id: str,
    expected_sample_window: list[int],
) -> None:
    expected_summary = _expected_precapture_contract_summary(
        precapture_contract,
        case_id=case_id,
        expected_sample_window=expected_sample_window,
    )
    normalized_summary = _summary_precapture_contract_summary(
        actual_summary,
        case_id=case_id,
        label="oracle_capture_summary.precapture_contract_summary",
    )
    if normalized_summary.get("sample_window") != expected_summary.get("sample_window"):
        raise ValueError(
            f"{case_id} oracle_capture_summary.precapture_contract_summary.sample_window "
            "must match precapture contract"
        )
    if normalized_summary.get("observed_years") != expected_summary.get("observed_years"):
        raise ValueError(
            f"{case_id} oracle_capture_summary.precapture_contract_summary.observed_years "
            "must match precapture contract"
        )
    if normalized_summary.get("treat_time") != expected_summary.get("treat_time"):
        raise ValueError(
            f"{case_id} oracle_capture_summary.precapture_contract_summary.treat_time "
            "must match precapture contract"
        )
    if normalized_summary.get("mode") != expected_summary.get("mode"):
        raise ValueError(
            f"{case_id} oracle_capture_summary.precapture_contract_summary.mode "
            "must match precapture contract"
        )
    actual_exact = normalized_summary.get("exact_fields_available_before_capture", {})
    expected_exact = expected_summary.get("exact_fields_available_before_capture", {})
    for section in _ALLOWED_PRECAPTURE_EXACT_SUMMARY_FIELDS:
        if actual_exact.get(section) != expected_exact.get(section):
            raise ValueError(
                f"{case_id} oracle_capture_summary.precapture_contract_summary."
                f"exact_fields_available_before_capture.{section} "
                "must match precapture contract"
            )


def _validate_graph_status_against_precapture_contract(
    status: Mapping[str, object],
    *,
    precapture_contract: Mapping[str, object],
    case_id: str,
    label: str,
) -> None:
    capture_status = status.get("capture_status")
    if capture_status is None or str(capture_status).startswith("blocked-"):
        return
    graph_requested = _precapture_graph_requested(
        precapture_contract,
        case_id=case_id,
    )
    graph_status = status.get("graph_status")
    if graph_requested:
        if graph_status == "suppressed-by-nograph":
            raise ValueError(
                f"{case_id} {label}.graph_status must not suppress graph export when precapture contract requests graph output"
            )
        return
    if graph_status not in (None, "suppressed-by-nograph"):
        raise ValueError(
            f"{case_id} {label}.graph_status must stay suppressed-by-nograph when precapture contract disables graph output"
        )


def _populate_overall_capture_summary(
    driver_case: dict[str, object],
    summary_case: dict[str, object],
    *,
    overall_capture_packet: Mapping[str, object],
    overall_capture_verifier_input: Mapping[str, object],
    capture_metadata: Mapping[str, object] | None,
    precapture_contract: Mapping[str, object] | None,
) -> None:
    case_id = str(driver_case["case_id"])
    driver_oracle_capture = _normalized_optional_mapping(
        driver_case.get("oracle_capture"),
        case_id=case_id,
        label="driver oracle_capture",
    )
    if driver_oracle_capture is None:
        raise ValueError(f"{case_id} overall capture ingestion requires oracle_capture")

    packet = _string_mapping(
        overall_capture_packet, label=f"{case_id} overall_capture_packet"
    )
    verifier_input = _string_mapping(
        overall_capture_verifier_input,
        label=f"{case_id} overall_capture_verifier_input",
    )

    if str(packet.get("case_id")) != case_id:
        raise ValueError(f"{case_id} overall capture packet case_id drift")
    packet_mode = _nonempty_string(
        packet.get("mode"),
        label=f"{case_id} overall capture packet mode",
    )
    if packet_mode != str(driver_case.get("mode")):
        raise ValueError(f"{case_id} overall capture packet mode drift")
    packet_sample_window = _int_list(
        packet.get("sample_window"),
        label=f"{case_id} overall capture packet sample_window",
    )
    driver_sample_window = _int_list(
        driver_case.get("sample_window"),
        label=f"{case_id} driver sample_window",
    )
    if packet_sample_window != driver_sample_window:
        raise ValueError(f"{case_id} overall capture packet sample_window drift")
    if str(verifier_input.get("case_id")) != case_id:
        raise ValueError(f"{case_id} overall capture verifier input case_id drift")
    if packet.get("precapture_contract_ref") != driver_oracle_capture.get(
        "precapture_contract_ref"
    ):
        raise ValueError(
            f"{case_id} overall capture packet drifted from driver precapture contract"
        )
    if packet.get("capture_metadata_contract_ref") != driver_oracle_capture.get(
        "capture_metadata_contract_ref"
    ):
        raise ValueError(
            f"{case_id} overall capture packet drifted from driver capture metadata contract"
        )
    if _string_list(
        packet.get("excluded_non_authoritative_results"),
        label=f"{case_id} overall capture packet excluded_non_authoritative_results",
    ) != _string_list(
        driver_oracle_capture.get("protected_results"),
        label=f"{case_id} driver oracle_capture.protected_results",
    ):
        raise ValueError(
            f"{case_id} overall capture packet drifted from driver protected results"
        )

    capture_paths = packet.get("capture_paths")
    if not isinstance(capture_paths, Mapping):
        raise ValueError(f"{case_id} overall capture packet missing capture_paths")
    summary_capture_paths = summary_case.get("capture_paths")
    if not isinstance(summary_capture_paths, Mapping):
        raise ValueError(f"{case_id} summary template missing capture_paths")
    for field in ("stata_stdout", "stata_stored_results"):
        summary_capture_path = _nonempty_string(
            summary_capture_paths.get(field),
            label=f"{case_id} summary template capture_paths.{field}",
        )
        packet_capture_path = _nonempty_string(
            capture_paths.get(field),
            label=f"{case_id} overall capture packet capture_paths.{field}",
        )
        if summary_capture_path != packet_capture_path:
            raise ValueError(
                f"{case_id} summary template capture_paths.{field} drift from overall capture packet"
            )
    if capture_paths.get("stata_graph_data") != driver_oracle_capture.get(
        "graph_data_capture_path"
    ):
        raise ValueError(
            f"{case_id} overall capture packet drifted from driver graph_data_capture_path"
        )
    if capture_paths.get("capture_metadata") != driver_oracle_capture.get(
        "capture_metadata_path"
    ):
        raise ValueError(
            f"{case_id} overall capture packet drifted from driver capture_metadata_path"
        )
    if verifier_input.get("precapture_contract_ref") != driver_oracle_capture.get(
        "precapture_contract_ref"
    ):
        raise ValueError(
            f"{case_id} overall capture verifier input drifted from driver precapture contract"
        )

    blocked_defaults = _blocked_defaults(
        packet.get("capture_metadata_blocked_defaults"),
        case_id=case_id,
        label=f"{case_id} overall capture packet capture_metadata_blocked_defaults",
    )
    required_metadata_fields = _required_metadata_fields(
        packet.get("capture_metadata_required_fields"),
        label=f"{case_id} overall capture packet capture_metadata_required_fields",
    )
    capture_metadata_requirements = _capture_metadata_requirements(
        packet.get("capture_metadata_requirements"),
        label=f"{case_id} overall capture packet capture_metadata_requirements",
    )
    normalized_capture_metadata_requirements = _normalized_requirement_markers(
        capture_metadata_requirements
    )
    missing_requirement_markers = [
        marker
        for marker in _REQUIRED_PRECAPTURE_REQUIREMENT_MARKERS
        if marker not in normalized_capture_metadata_requirements
    ]
    if missing_requirement_markers:
        raise ValueError(
            f"{case_id} capture metadata requirements must include precapture contract verification rules"
        )

    capture_metadata_mapping: dict[str, object] | None = None
    if capture_metadata is not None:
        capture_metadata_mapping = _string_mapping(
            capture_metadata,
            label=f"{case_id} capture metadata",
        )
        if str(capture_metadata_mapping.get("case_id")) != case_id:
            raise ValueError(f"{case_id} capture metadata case_id drift")
        if capture_metadata_mapping.get("capture_kind") != "capture-metadata":
            raise ValueError(f"{case_id} capture metadata kind drift")
        if capture_metadata_mapping.get("capture_metadata_contract_ref") != packet.get(
            "capture_metadata_contract_ref"
        ):
            raise ValueError(f"{case_id} capture metadata contract drift")
        if _capture_metadata_requirements(
            capture_metadata_mapping.get("required_metadata"),
            label=f"{case_id} capture metadata required_metadata",
        ) != capture_metadata_requirements:
            raise ValueError(f"{case_id} capture metadata required_metadata drift")
        if (
            _required_metadata_fields(
                capture_metadata_mapping.get("required_metadata_fields"),
                label=f"{case_id} capture metadata required_metadata_fields",
            )
            != required_metadata_fields
        ):
            raise ValueError(
                f"{case_id} capture metadata required_metadata_fields drift"
            )
        if (
            _blocked_defaults(
                capture_metadata_mapping.get("blocked_defaults"),
                case_id=case_id,
                label="capture metadata blocked_defaults",
            )
            != blocked_defaults
        ):
            raise ValueError(f"{case_id} capture metadata blocked_defaults drift")

    status = _metadata_status(
        case_id=case_id,
        blocked_defaults=blocked_defaults,
        capture_metadata=capture_metadata_mapping,
        required_metadata_fields=required_metadata_fields,
    )
    promoted_fields = status["numeric_fields_promoted"]
    protected_results = _string_list(
        driver_oracle_capture.get("protected_results"),
        label=f"{case_id} driver oracle_capture.protected_results",
    )
    if any(field in protected_results for field in promoted_fields):
        raise ValueError(
            f"{case_id} capture_metadata.metadata_payload.numeric_fields_promoted must exclude protected_results"
        )
    authoritative_capture_fields = set(
        _string_list(
            packet.get("authoritative_stdout_fields"),
            label=f"{case_id} overall capture packet authoritative_stdout_fields",
        )
        + _string_list(
            packet.get("authoritative_stored_results"),
            label=f"{case_id} overall capture packet authoritative_stored_results",
        )
    )
    if any(field not in authoritative_capture_fields for field in promoted_fields):
        raise ValueError(
            f"{case_id} capture_metadata.metadata_payload.numeric_fields_promoted must stay within authoritative capture fields"
        )
    conditional_ci_gate = _conditional_ci_gate(verifier_input, case_id=case_id)
    _validate_conditional_ci_promotions(
        promoted_fields,
        conditional_ci_gate,
        case_id=case_id,
    )
    if precapture_contract is None and (
        status["observed_years"] is not None or status["treat_time"] is not None
    ):
        raise ValueError(
            f"{case_id} precapture_contract is required before observed_years or treat_time may be promoted"
        )
    if status["capture_ready"] is True:
        if precapture_contract is None:
            raise ValueError(
                f"{case_id} precapture_contract is required before capture_ready may flip to true"
            )
        if status["observed_years"] is None:
            raise ValueError(
                f"{case_id} capture_metadata.metadata_payload.observed_years must be present before capture_ready may flip to true"
            )
        if status["treat_time"] is None:
            raise ValueError(
                f"{case_id} capture_metadata.metadata_payload.treat_time must be present before capture_ready may flip to true"
            )
    precapture_summary = None
    if precapture_contract is not None:
        precapture_summary = _precapture_contract_summary(
            precapture_contract,
            case_id=case_id,
            capture_metadata=capture_metadata_mapping,
            expected_sample_window=driver_sample_window,
            expected_required_fields=required_metadata_fields,
            expected_blocked_defaults=blocked_defaults,
        )
        _validate_graph_status_against_precapture_contract(
            status,
            precapture_contract=precapture_contract,
            case_id=case_id,
            label="capture_metadata.metadata_payload",
        )
    if capture_metadata_mapping is not None and not str(
        capture_metadata_mapping.get("capture_status", "")
    ).startswith("blocked-"):
        payload_mapping = capture_metadata_mapping.get("metadata_payload")
        if isinstance(payload_mapping, Mapping):
            normalized_payload = _string_mapping(
                payload_mapping,
                label=f"{case_id} capture_metadata.metadata_payload",
            )
            missing_required_fields = [
                field
                for field in required_metadata_fields
                if field not in normalized_payload
            ]
            if missing_required_fields:
                raise ValueError(
                    f"{case_id} capture_metadata.metadata_payload missing required fields "
                    f"after capture_status leaves blocked state: "
                    + ", ".join(missing_required_fields)
                )

    summary_case["oracle_capture"] = deepcopy(driver_oracle_capture)
    summary_case["oracle_capture"]["capture_ready"] = bool(status["capture_ready"])
    summary_case["oracle_capture_summary"] = {
        "required_metadata_fields": required_metadata_fields,
        "required_metadata": _capture_metadata_requirements(
            (capture_metadata_mapping or {}).get(
                "required_metadata",
                packet.get("capture_metadata_requirements"),
            ),
            label=f"{case_id} overall capture required_metadata",
        ),
        "blocked_defaults": blocked_defaults,
        "capture_metadata_status": status,
        "conditional_ci_gate": conditional_ci_gate,
    }
    if precapture_summary is not None:
        summary_case["oracle_capture_summary"]["precapture_contract_summary"] = (
            precapture_summary
        )


def _validate_capture_ready_overall_bundle_metadata(
    driver_case: Mapping[str, object],
    summary_case: Mapping[str, object],
    *,
    overall_capture_packet: Mapping[str, object],
    overall_capture_verifier_input: Mapping[str, object],
    capture_metadata: Mapping[str, object] | None,
    precapture_contract: Mapping[str, object] | None,
) -> None:
    _populate_overall_capture_summary(
        deepcopy(dict(driver_case)),
        deepcopy(dict(summary_case)),
        overall_capture_packet=overall_capture_packet,
        overall_capture_verifier_input=overall_capture_verifier_input,
        capture_metadata=capture_metadata,
        precapture_contract=precapture_contract,
    )


def _oracle_capture_status(
    summary_case: Mapping[str, object],
    *,
    case_id: str,
) -> Mapping[str, object] | None:
    oracle_capture_summary = _normalized_oracle_capture_summary_fields(
        summary_case.get("oracle_capture_summary"),
        case_id=case_id,
    )
    if oracle_capture_summary is None:
        return None
    status = oracle_capture_summary.get("capture_metadata_status")
    if not isinstance(status, Mapping):
        raise ValueError(
            f"{case_id} oracle_capture_summary.capture_metadata_status must be a mapping"
        )
    normalized_status = dict(status)
    precapture_summary = oracle_capture_summary.get("precapture_contract_summary")
    unexpected_fields = sorted(
        set(normalized_status) - set(_ALLOWED_SUMMARY_CAPTURE_STATUS_FIELDS)
    )
    if unexpected_fields:
        raise ValueError(
            f"{case_id} oracle_capture_summary.capture_metadata_status contains unknown fields: "
            + ", ".join(unexpected_fields)
        )
    normalized_status["capture_ready"] = _bool_value(
        normalized_status.get("capture_ready"),
        label=(
            f"{case_id} "
            "oracle_capture_summary.capture_metadata_status.capture_ready"
        ),
    )
    capture_status = normalized_status.get("capture_status")
    if "capture_status" in normalized_status:
        if capture_status is None:
            normalized_status["capture_status"] = None
        elif isinstance(capture_status, str):
            normalized_status["capture_status"] = _nonempty_string(
                capture_status,
                label=(
                    f"{case_id} "
                    "oracle_capture_summary.capture_metadata_status.capture_status"
                ),
            )
        else:
            raise ValueError(
                f"{case_id} oracle_capture_summary.capture_metadata_status.capture_status "
                "must be a string or null"
            )
    capture_status = normalized_status.get("capture_status")
    if (
        capture_status is None
        and normalized_status.get("graph_status") is not None
        and normalized_status.get("capture_ready") is not True
    ):
        raise ValueError(
            f"{case_id} oracle_capture_summary.capture_metadata_status "
            "must not define graph_status without capture_status"
        )
    if (
        capture_status is not None
        and str(capture_status).startswith("blocked-")
        and normalized_status.get("capture_ready") is not True
        and normalized_status.get("graph_status") is not None
    ):
        raise ValueError(
            f"{case_id} oracle_capture_summary.capture_metadata_status.graph_status "
            f"must stay null while capture_status remains blocked {capture_status}"
        )
    if (
        capture_status is not None
        and not str(capture_status).startswith("blocked-")
        and normalized_status.get("graph_status") is None
    ):
        raise ValueError(
            f"{case_id} oracle_capture_summary.capture_metadata_status "
            "must define graph_status once capture_status leaves blocked state"
        )
    if (
        capture_status is not None
        and not str(capture_status).startswith("blocked-")
        and normalized_status.get("capture_ready") is not True
        and isinstance(normalized_status.get("graph_status"), str)
        and str(normalized_status["graph_status"]).startswith("blocked-")
    ):
        raise ValueError(
            f"{case_id} oracle_capture_summary.capture_metadata_status.graph_status "
            "must leave blocked state once capture_status leaves blocked state"
        )
    if normalized_status.get("capture_ready") is True:
        if capture_status is None:
            raise ValueError(
                f"{case_id} oracle_capture_summary.capture_metadata_status "
                "must not mark capture_ready=true without capture_status"
            )
        if str(capture_status).startswith("blocked-"):
            raise ValueError(
                f"{case_id} oracle_capture_summary.capture_metadata_status "
                f"must not mark capture_ready=true with blocked capture_status "
                f"{capture_status}"
            )
    if normalized_status.get("graph_status") is not None:
        normalized_status["graph_status"] = _graph_status_value(
            normalized_status["graph_status"],
            label=f"{case_id} oracle_capture_summary.capture_metadata_status.graph_status",
        )
    if "observed_years" in normalized_status:
        observed_years = normalized_status["observed_years"]
        normalized_status["observed_years"] = (
            None
            if observed_years is None
            else _int_list(
                observed_years,
                label=(
                    f"{case_id} "
                    "oracle_capture_summary.capture_metadata_status.observed_years"
                ),
                require_unique=True,
            )
        )
    if "treat_time" in normalized_status:
        treat_time = normalized_status["treat_time"]
        normalized_status["treat_time"] = (
            None
            if treat_time is None
            else _int_value(
                treat_time,
                label=(
                    f"{case_id} "
                    "oracle_capture_summary.capture_metadata_status.treat_time"
                ),
            )
        )
    if "exact_counts_verified" in normalized_status:
        exact_counts_verified = normalized_status["exact_counts_verified"]
        normalized_status["exact_counts_verified"] = (
            None
            if exact_counts_verified is None
            else _bool_value(
                exact_counts_verified,
                label=(
                    f"{case_id} "
                    "oracle_capture_summary.capture_metadata_status.exact_counts_verified"
                ),
            )
        )
    if "raw_e_snapshot_present" in normalized_status:
        raw_e_snapshot_present = normalized_status["raw_e_snapshot_present"]
        normalized_status["raw_e_snapshot_present"] = (
            None
            if raw_e_snapshot_present is None
            else _bool_value(
                raw_e_snapshot_present,
                label=(
                    f"{case_id} "
                    "oracle_capture_summary.capture_metadata_status.raw_e_snapshot_present"
                ),
            )
        )
    if (
        capture_status is not None
        and str(capture_status).startswith("blocked-")
        and normalized_status.get("capture_ready") is not True
        and normalized_status.get("raw_e_snapshot_present") not in (None, False)
    ):
        raise ValueError(
            f"{case_id} oracle_capture_summary.capture_metadata_status.raw_e_snapshot_present "
            f"must stay false while capture_status remains blocked {capture_status}"
        )
    if "numeric_fields_promoted" in normalized_status:
        numeric_fields_promoted = normalized_status["numeric_fields_promoted"]
        normalized_status["numeric_fields_promoted"] = (
            None
            if numeric_fields_promoted is None
            else _string_list(
                numeric_fields_promoted,
                label=(
                    f"{case_id} "
                    "oracle_capture_summary.capture_metadata_status.numeric_fields_promoted"
                ),
                require_unique=True,
            )
        )
    if "protected_results_excluded" in normalized_status:
        protected_results_excluded = normalized_status["protected_results_excluded"]
        normalized_status["protected_results_excluded"] = (
            None
            if protected_results_excluded is None
            else _bool_value(
                protected_results_excluded,
                label=(
                    f"{case_id} "
                    "oracle_capture_summary.capture_metadata_status.protected_results_excluded"
                ),
            )
        )
    if (
        capture_status is not None
        and str(capture_status).startswith("blocked-")
        and normalized_status.get("capture_ready") is not True
    ):
        for field in ("observed_years", "treat_time", "exact_counts_verified"):
            if normalized_status.get(field) is not None:
                raise ValueError(
                    f"{case_id} oracle_capture_summary.capture_metadata_status.{field} "
                    f"must stay null while capture_status remains blocked {capture_status}"
                )
        numeric_fields_promoted = normalized_status.get("numeric_fields_promoted")
        if numeric_fields_promoted not in (None, []):
            raise ValueError(
                f"{case_id} oracle_capture_summary.capture_metadata_status.numeric_fields_promoted "
                f"must stay empty while capture_status remains blocked {capture_status}"
            )
    if capture_status is None and normalized_status.get("capture_ready") is not True:
        for field in ("observed_years", "treat_time", "exact_counts_verified"):
            if normalized_status.get(field) is not None:
                raise ValueError(
                    f"{case_id} oracle_capture_summary.capture_metadata_status.{field} "
                    "must stay null until capture_status is defined"
                )
        if normalized_status.get("raw_e_snapshot_present") not in (None, False):
            raise ValueError(
                f"{case_id} oracle_capture_summary.capture_metadata_status.raw_e_snapshot_present "
                "must stay false until capture_status is defined"
            )
        numeric_fields_promoted = normalized_status.get("numeric_fields_promoted")
        if numeric_fields_promoted not in (None, []):
            raise ValueError(
                f"{case_id} oracle_capture_summary.capture_metadata_status.numeric_fields_promoted "
                "must stay empty until capture_status is defined"
            )
    if (
        capture_status is not None
        and str(capture_status).startswith("blocked-")
        and normalized_status.get("capture_ready") is not True
        and normalized_status.get("protected_results_excluded") not in (None, True)
    ):
        raise ValueError(
            f"{case_id} oracle_capture_summary.capture_metadata_status.protected_results_excluded "
            f"must remain true while capture_status remains blocked {capture_status}"
        )
    if normalized_status.get("capture_ready") is not True:
        numeric_fields_promoted = normalized_status.get("numeric_fields_promoted")
        if numeric_fields_promoted not in (None, []):
            raise ValueError(
                f"{case_id} oracle_capture_summary.capture_metadata_status.numeric_fields_promoted "
                "must stay empty while capture_ready is false"
            )
        if normalized_status.get("protected_results_excluded") not in (None, True):
            raise ValueError(
                f"{case_id} oracle_capture_summary.capture_metadata_status.protected_results_excluded "
                "must remain true while capture_ready is false"
            )
    if normalized_status.get("capture_ready") is True:
        if normalized_status.get("graph_status") is None:
            raise ValueError(
                f"{case_id} oracle_capture_summary.capture_metadata_status "
                "must define graph_status before capture_ready may flip to true"
            )
    if (
        normalized_status.get("capture_ready") is True
        and normalized_status.get("graph_status") is not None
    ):
        graph_status = str(normalized_status["graph_status"])
        if graph_status.startswith("blocked-"):
            raise ValueError(
                f"{case_id} oracle_capture_summary.capture_metadata_status.graph_status "
                "must leave blocked state before capture_ready may flip to true"
            )
        if graph_status == "suppressed-by-nograph":
            raise ValueError(
                f"{case_id} oracle_capture_summary.capture_metadata_status.graph_status "
                "must not suppress graph export once capture_ready is true"
            )
        if normalized_status.get("observed_years") is None:
            raise ValueError(
                f"{case_id} oracle_capture_summary.capture_metadata_status "
                "must define observed_years before capture_ready may flip to true"
            )
        if normalized_status.get("treat_time") is None:
            raise ValueError(
                f"{case_id} oracle_capture_summary.capture_metadata_status "
                "must define treat_time before capture_ready may flip to true"
            )
        if normalized_status.get("exact_counts_verified") is not True:
            raise ValueError(
                f"{case_id} oracle_capture_summary.capture_metadata_status.exact_counts_verified "
                "must be true before capture_ready may flip to true"
            )
        if normalized_status.get("raw_e_snapshot_present") is not True:
            raise ValueError(
                f"{case_id} oracle_capture_summary.capture_metadata_status.raw_e_snapshot_present "
                "must be true before capture_ready may flip to true"
            )
        numeric_fields_promoted = normalized_status.get("numeric_fields_promoted")
        if numeric_fields_promoted is None:
            raise ValueError(
                f"{case_id} oracle_capture_summary.capture_metadata_status "
                "must define numeric_fields_promoted before capture_ready may flip to true"
            )
        if not numeric_fields_promoted:
            raise ValueError(
                f"{case_id} oracle_capture_summary.capture_metadata_status.numeric_fields_promoted "
                "must list at least one promoted field before capture_ready may flip to true"
            )
        if normalized_status.get("protected_results_excluded") is not True:
            raise ValueError(
                f"{case_id} oracle_capture_summary.capture_metadata_status.protected_results_excluded "
                "must remain true before capture_ready may flip to true"
            )
    if (
        capture_status is not None
        and not str(capture_status).startswith("blocked-")
        and normalized_status.get("capture_ready") is not True
    ):
        for field in (
            "observed_years",
            "treat_time",
            "exact_counts_verified",
            "raw_e_snapshot_present",
            "numeric_fields_promoted",
            "protected_results_excluded",
        ):
            if field not in normalized_status:
                raise ValueError(
                    f"{case_id} oracle_capture_summary.capture_metadata_status.{field} "
                    "must be present once capture_status leaves blocked state"
                )
        for field in (
            "observed_years",
            "treat_time",
            "exact_counts_verified",
            "raw_e_snapshot_present",
            "numeric_fields_promoted",
            "protected_results_excluded",
        ):
            if normalized_status.get(field) is None:
                raise ValueError(
                    f"{case_id} oracle_capture_summary.capture_metadata_status.{field} "
                    "must not stay null once capture_status leaves blocked state"
                )
    if (
        capture_status is not None
        and not str(capture_status).startswith("blocked-")
        and precapture_summary is None
    ):
        raise ValueError(
            f"{case_id} oracle_capture_summary must define precapture_contract_summary "
            "once capture_status leaves blocked state"
        )
    if (
        precapture_summary is not None
        and capture_status is not None
        and not str(capture_status).startswith("blocked-")
    ):
        if normalized_status.get("observed_years") != precapture_summary.get(
            "observed_years"
        ):
            raise ValueError(
                f"{case_id} oracle_capture_summary.capture_metadata_status.observed_years "
                "must match precapture contract summary"
            )
        if normalized_status.get("treat_time") != precapture_summary.get("treat_time"):
            raise ValueError(
                f"{case_id} oracle_capture_summary.capture_metadata_status.treat_time "
                "must match precapture contract summary"
            )
    return normalized_status


def _validate_summary_capture_status_against_driver_oracle_capture(
    *,
    case_id: str,
    oracle_capture_status: Mapping[str, object],
    driver_oracle_capture: Mapping[str, object] | None,
) -> None:
    if driver_oracle_capture is None:
        if oracle_capture_status:
            raise ValueError(
                f"{case_id} oracle_capture_summary requires driver oracle_capture"
            )
        return
    protected_results = _string_list(
        driver_oracle_capture.get("protected_results", []),
        label=f"{case_id} driver oracle_capture.protected_results",
        require_unique=True,
    )
    numeric_fields_promoted = oracle_capture_status.get("numeric_fields_promoted")
    if not isinstance(numeric_fields_promoted, list):
        return
    if any(field in protected_results for field in numeric_fields_promoted):
        raise ValueError(
            f"{case_id} oracle_capture_summary.capture_metadata_status.numeric_fields_promoted "
            "must exclude protected_results"
        )


def _driver_authoritative_capture_fields(
    driver_case: Mapping[str, object],
    *,
    case_id: str,
) -> set[str]:
    stdout_categories = _string_mapping(
        driver_case.get("stdout_categories"),
        label=f"{case_id} driver stdout_categories",
    )
    stored_results_categories = _string_mapping(
        driver_case.get("stored_results_categories"),
        label=f"{case_id} driver stored_results_categories",
    )
    return set(
        _string_list(
            stdout_categories.get("exact"),
            label=f"{case_id} driver stdout_categories.exact",
            require_unique=True,
        )
        + _string_list(
            stdout_categories.get("display_rounded"),
            label=f"{case_id} driver stdout_categories.display_rounded",
            require_unique=True,
        )
        + _string_list(
            stored_results_categories.get("exact"),
            label=f"{case_id} driver stored_results_categories.exact",
            require_unique=True,
        )
        + _string_list(
            stored_results_categories.get("display_rounded"),
            label=f"{case_id} driver stored_results_categories.display_rounded",
            require_unique=True,
        )
    )


def _authoritative_conditional_ci_gate(
    driver_case: Mapping[str, object],
    *,
    case_id: str,
) -> dict[str, dict[str, list[str]]]:
    stdout_categories = _string_mapping(
        driver_case.get("stdout_categories"),
        label=f"{case_id} driver stdout_categories",
    )
    stored_results_categories = _string_mapping(
        driver_case.get("stored_results_categories"),
        label=f"{case_id} driver stored_results_categories",
    )

    stdout_display_rounded = _string_list(
        stdout_categories.get("display_rounded"),
        label=f"{case_id} driver stdout_categories.display_rounded",
        require_unique=True,
    )
    stored_results_display_rounded = _string_list(
        stored_results_categories.get("display_rounded"),
        label=f"{case_id} driver stored_results_categories.display_rounded",
        require_unique=True,
    )

    stdout_conditional_fields = [
        field for field in ("ci_lower", "ci_upper") if field in stdout_display_rounded
    ]
    stored_results_conditional_fields = [
        field
        for field in ("e(ci_lower)", "e(ci_upper)")
        if field in stored_results_display_rounded
    ]

    return {
        "stdout": {
            "gate_fields": ["pretest_result", "e(pretest_pass)", "e(data_valid)"],
            "display_rounded_when_valid_pass": stdout_conditional_fields,
            "exact_absence_when_not_authoritative": list(stdout_conditional_fields),
        },
        "stored_results": {
            "gate_fields": ["e(pretest_pass)", "e(data_valid)"],
            "display_rounded_when_valid_pass": stored_results_conditional_fields,
            "exact_absence_when_not_authoritative": list(
                stored_results_conditional_fields
            ),
        },
    }


def _validate_summary_conditional_ci_gate(
    *,
    case_id: str,
    summary_case: Mapping[str, object],
    driver_case: Mapping[str, object],
) -> None:
    oracle_capture_summary = summary_case.get("oracle_capture_summary")
    if not isinstance(oracle_capture_summary, Mapping):
        return
    conditional_ci_gate = oracle_capture_summary.get("conditional_ci_gate")
    if not isinstance(conditional_ci_gate, Mapping):
        return

    authoritative_gate = _authoritative_conditional_ci_gate(
        driver_case,
        case_id=case_id,
    )
    normalized_gate = _summary_conditional_ci_gate(
        conditional_ci_gate,
        case_id=case_id,
        label="oracle_capture_summary.conditional_ci_gate",
    )
    if normalized_gate != authoritative_gate:
        raise ValueError(
            f"{case_id} oracle_capture_summary.conditional_ci_gate must match authoritative conditional CI gate"
        )


def _validate_summary_promoted_fields_against_capture_surface(
    *,
    case_id: str,
    summary_case: Mapping[str, object],
    driver_case: Mapping[str, object],
    oracle_capture_status: Mapping[str, object],
) -> None:
    _validate_summary_conditional_ci_gate(
        case_id=case_id,
        summary_case=summary_case,
        driver_case=driver_case,
    )
    numeric_fields_promoted = oracle_capture_status.get("numeric_fields_promoted")
    if not isinstance(numeric_fields_promoted, list):
        return

    authoritative_fields = _driver_authoritative_capture_fields(
        driver_case,
        case_id=case_id,
    )
    if any(field not in authoritative_fields for field in numeric_fields_promoted):
        raise ValueError(
            f"{case_id} oracle_capture_summary.capture_metadata_status.numeric_fields_promoted "
            "must stay within authoritative capture fields"
        )

    authoritative_conditional_ci_gate = _authoritative_summary_conditional_ci_gate()
    _validate_conditional_ci_promotions(
        numeric_fields_promoted,
        authoritative_conditional_ci_gate,
        case_id=case_id,
    )

    oracle_capture_summary = summary_case.get("oracle_capture_summary")
    if not isinstance(oracle_capture_summary, Mapping):
        return
    conditional_ci_gate = oracle_capture_summary.get("conditional_ci_gate")
    if isinstance(conditional_ci_gate, Mapping):
        if conditional_ci_gate != authoritative_conditional_ci_gate:
            raise ValueError(
                f"{case_id} oracle_capture_summary.conditional_ci_gate "
                "must match authoritative conditional CI gate"
            )


def _section_field_lookup(
    bundle: Mapping[str, object],
    *,
    case_id: str,
    section: str,
) -> tuple[dict[str, object], set[str]]:
    values: dict[str, object] = {}
    for bucket in ("exact", "display_rounded", "unresolved"):
        bucket_values = _bucket_values(bundle, section=section, bucket=bucket)
        assert isinstance(bucket_values, dict)
        for field, value in bucket_values.items():
            if field in values and values[field] != value:
                raise ValueError(
                    f"{case_id} replay bundle {section}.{field} appears with conflicting values across buckets"
                )
            values[field] = deepcopy(value)

    exact_absence = set(
        _bucket_values(bundle, section=section, bucket="exact_absence")
    )
    return values, exact_absence


def _bundle_supports_authoritative_conditional_ci(
    bundle: Mapping[str, object],
    *,
    case_id: str,
) -> bool:
    stdout_values, _ = _section_field_lookup(
        bundle,
        case_id=case_id,
        section="stdout",
    )
    stored_values, _ = _section_field_lookup(
        bundle,
        case_id=case_id,
        section="stored_results",
    )
    return (
        stdout_values.get("pretest_result") == "PASS"
        and stored_values.get("e(pretest_pass)") == 1
        and stored_values.get("e(data_valid)") == 1
    )


def _capture_ready_overall_plan(
    summary_case: dict[str, object],
    *,
    case_id: str,
    verifier_input: Mapping[str, object],
    conditional_ci_authoritative: bool,
) -> dict[str, dict[str, list[str]]]:
    comparison_plan = verifier_input.get("comparison_plan")
    if not isinstance(comparison_plan, Mapping):
        raise ValueError(
            f"{case_id} overall capture verifier input missing comparison_plan"
        )

    promoted_plan: dict[str, dict[str, list[str]]] = {}
    for section, _, summary_key in _SECTIONS:
        section_plan = comparison_plan.get(section)
        if not isinstance(section_plan, Mapping):
            raise ValueError(
                f"{case_id} overall capture verifier input missing {section} plan"
            )
        section_summary = summary_case.get(summary_key)
        if not isinstance(section_summary, Mapping):
            raise ValueError(f"{case_id} summary template missing {summary_key}")
        unresolved_summary = section_summary.get("unresolved")
        if not isinstance(unresolved_summary, Mapping):
            raise ValueError(
                f"{case_id} summary template missing {summary_key}.unresolved"
            )
        unresolved_fields = _string_list(
            unresolved_summary.get("planned_fields"),
            label=f"{case_id} {summary_key}.unresolved.planned_fields",
        )
        exact_fields = _string_list(
            section_plan.get("exact_after_capture"),
            label=f"{case_id} {section} exact_after_capture",
        )
        display_fields = _string_list(
            section_plan.get("display_rounded_after_capture"),
            label=f"{case_id} {section} display_rounded_after_capture",
        )
        conditional_ci = section_plan.get("conditional_ci_after_capture")
        if not isinstance(conditional_ci, Mapping):
            raise ValueError(
                f"{case_id} overall capture verifier input missing {section} conditional CI plan"
            )
        valid_pass = conditional_ci.get("if_data_valid_and_pass")
        if not isinstance(valid_pass, Mapping):
            raise ValueError(
                f"{case_id} overall capture verifier input missing {section} valid-pass plan"
            )
        conditional_display = _string_list(
            valid_pass.get("display_rounded"),
            label=f"{case_id} {section} conditional_ci_after_capture.if_data_valid_and_pass.display_rounded",
        )
        conditional_exact_absence = _string_list(
            conditional_ci.get("exact_absence_when_not_authoritative"),
            label=f"{case_id} {section} conditional_ci_after_capture.exact_absence_when_not_authoritative",
        )
        if conditional_ci_authoritative:
            display_fields = list(dict.fromkeys(display_fields + conditional_display))
            exact_absence_fields: list[str] = []
        else:
            exact_absence_fields = conditional_exact_absence
        assigned_fields = set(exact_fields + display_fields + exact_absence_fields)
        unresolved_after_capture = [
            field for field in unresolved_fields if field not in assigned_fields
        ]
        promoted_plan[section] = {
            "exact": exact_fields,
            "display_rounded": display_fields,
            "exact_absence": exact_absence_fields,
            "unresolved": unresolved_after_capture,
        }
    return promoted_plan


def _reclassify_capture_ready_bundle(
    bundle: Mapping[str, object],
    *,
    case_id: str,
    promoted_plan: Mapping[str, Mapping[str, list[str]]],
) -> dict[str, object]:
    normalized = deepcopy(dict(bundle))
    for section in ("stdout", "stored_results"):
        section_plan = promoted_plan[section]
        values, exact_absence = _section_field_lookup(
            bundle,
            case_id=case_id,
            section=section,
        )
        section_payload = bundle.get(section)
        if not isinstance(section_payload, Mapping):
            raise ValueError(f"{case_id} replay bundle missing {section} payload")
        normalized_section = deepcopy(dict(section_payload))

        exact_fields = section_plan["exact"]
        display_fields = section_plan["display_rounded"]
        exact_absence_fields = section_plan["exact_absence"]
        assigned_fields = set(exact_fields + display_fields + exact_absence_fields)

        normalized_section["exact"] = {
            field: deepcopy(values[field]) for field in exact_fields if field in values
        }
        normalized_section["display_rounded"] = {
            field: deepcopy(values[field])
            for field in display_fields
            if field in values
        }
        normalized_section["exact_absence"] = [
            field
            for field in exact_absence_fields
            if field in exact_absence or values.get(field) is None
        ]
        normalized_section["unresolved"] = {
            field: deepcopy(values[field])
            for field in section_plan["unresolved"]
            if field in values and field not in assigned_fields
        }
        normalized[section] = normalized_section
    return normalized


def _promote_capture_ready_overall_summary(
    summary_case: dict[str, object],
    *,
    case_id: str,
    verifier_input: Mapping[str, object],
    stata_bundle: Mapping[str, object],
    python_bundle: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    conditional_ci_authoritative = _bundle_supports_authoritative_conditional_ci(
        stata_bundle,
        case_id=case_id,
    ) and _bundle_supports_authoritative_conditional_ci(
        python_bundle,
        case_id=case_id,
    )
    promoted_plan = _capture_ready_overall_plan(
        summary_case,
        case_id=case_id,
        verifier_input=verifier_input,
        conditional_ci_authoritative=conditional_ci_authoritative,
    )
    for _, _, summary_key in _SECTIONS:
        section = "stdout" if summary_key == "stdout_summary" else "stored_results"
        section_summary = summary_case[summary_key]
        assert isinstance(section_summary, dict)
        for bucket in _BUCKETS:
            bucket_summary = section_summary[bucket]
            assert isinstance(bucket_summary, dict)
            bucket_summary["planned_fields"] = list(promoted_plan[section][bucket])
            bucket_summary["matched_fields"] = []
            bucket_summary["mismatched_fields"] = []

    promoted_stata_bundle = _reclassify_capture_ready_bundle(
        stata_bundle,
        case_id=case_id,
        promoted_plan=promoted_plan,
    )
    promoted_python_bundle = _reclassify_capture_ready_bundle(
        python_bundle,
        case_id=case_id,
        promoted_plan=promoted_plan,
    )
    comparison_status = str(summary_case.get("python_parity_status", ""))
    if comparison_status:
        promoted_stata_bundle["comparison_status"] = comparison_status
        promoted_python_bundle["comparison_status"] = comparison_status
    return promoted_stata_bundle, promoted_python_bundle


def _compare_bucket(
    planned_fields: list[str],
    *,
    stata_bundle: Mapping[str, object],
    python_bundle: Mapping[str, object],
    section: str,
    bucket: str,
) -> tuple[list[str], list[str]]:
    matched: list[str] = []
    mismatched: list[str] = []
    planned_field_set = set(planned_fields)

    stata_values = _bucket_values(stata_bundle, section=section, bucket=bucket)
    python_values = _bucket_values(python_bundle, section=section, bucket=bucket)

    if bucket == "exact_absence":
        stata_missing = set(stata_values)
        python_missing = set(python_values)
        unexpected_fields = sorted(
            (stata_missing | python_missing) - planned_field_set
        )
        if unexpected_fields:
            raise ValueError(
                f"replay bundle {section}.{bucket} contains unexpected exact_absence fields: "
                + ", ".join(unexpected_fields)
            )
        for field in planned_fields:
            if field in stata_missing and field in python_missing:
                matched.append(field)
            else:
                mismatched.append(field)
        return matched, mismatched

    assert isinstance(stata_values, dict)
    assert isinstance(python_values, dict)
    unexpected_fields = sorted(
        (set(stata_values) | set(python_values)) - planned_field_set
    )
    if unexpected_fields:
        raise ValueError(
            f"replay bundle {section}.{bucket} contains unexpected fields: "
            + ", ".join(unexpected_fields)
        )
    for field in planned_fields:
        left_value = stata_values.get(field)
        right_value = python_values.get(field)
        if (
            field in stata_values
            and field in python_values
            and (
                left_value == right_value
                or (
                    isinstance(left_value, (int, float))
                    and not isinstance(left_value, bool)
                    and isinstance(right_value, (int, float))
                    and not isinstance(right_value, bool)
                    and math.isclose(
                        float(left_value),
                        float(right_value),
                        rel_tol=1e-9,
                        abs_tol=1e-8,
                    )
                )
            )
        ):
            matched.append(field)
        else:
            mismatched.append(field)
    return matched, mismatched


def _rng_bound_comparison_fields(*, section: str, bucket: str) -> set[str]:
    section_fields = _RNG_BOUND_COMPARISON_FIELDS.get(section, {})
    return set(section_fields.get(bucket, ()))


def _bundle_comparison_pending(bundle: Mapping[str, object] | None) -> bool:
    if bundle is None:
        return False
    return bundle.get("comparison_status") == "pending-python-implementation"


def _validate_template_alignment(
    driver_case: dict[str, object],
    summary_case: dict[str, object],
) -> None:
    case_id = str(driver_case["case_id"])
    if str(summary_case["case_id"]) != case_id:
        raise ValueError("driver_case and summary_case must point to the same case")

    if str(summary_case.get("mode")) != str(driver_case.get("mode")):
        raise ValueError(f"{case_id} mode drift between driver and summary template")

    if list(summary_case.get("sample_window", [])) != list(
        driver_case.get("sample_window", [])
    ):
        raise ValueError(
            f"{case_id} sample window drift between driver and summary template"
        )

    _nonempty_string(
        driver_case.get("graph_status"),
        label=f"{case_id} driver graph_status",
    )

    for _, categories_key, summary_key in _SECTIONS:
        driver_categories = driver_case.get(categories_key)
        summary_section = summary_case.get(summary_key)
        if not isinstance(driver_categories, Mapping):
            raise ValueError(f"{case_id} driver case missing {categories_key}")
        if not isinstance(summary_section, Mapping):
            raise ValueError(f"{case_id} summary template missing {summary_key}")

        for bucket in _BUCKETS:
            planned_fields = _string_list(
                driver_categories.get(bucket),
                label=f"{case_id} driver {categories_key}.{bucket}",
            )
            bucket_summary = summary_section.get(bucket)
            if not isinstance(bucket_summary, Mapping):
                raise ValueError(
                    f"{case_id} summary template missing {summary_key}.{bucket}"
                )

            template_fields = _string_list(
                bucket_summary.get("planned_fields"),
                label=f"{case_id} summary {summary_key}.{bucket}.planned_fields",
            )
            if template_fields != planned_fields:
                raise ValueError(
                    f"{case_id} summary template drifted from driver in {summary_key}.{bucket}"
                )

            _string_list(
                bucket_summary.get("matched_fields"),
                label=f"{case_id} summary {summary_key}.{bucket}.matched_fields",
            )
            _string_list(
                bucket_summary.get("mismatched_fields"),
                label=f"{case_id} summary {summary_key}.{bucket}.mismatched_fields",
            )

    driver_oracle_capture = _normalized_optional_mapping(
        driver_case.get("oracle_capture"),
        case_id=case_id,
        label="driver oracle_capture",
    )
    summary_oracle_capture = _normalized_optional_mapping(
        summary_case.get("oracle_capture"),
        case_id=case_id,
        label="summary oracle_capture",
    )
    if driver_oracle_capture != summary_oracle_capture:
        raise ValueError(
            f"{case_id} summary template drifted from driver in oracle_capture"
        )


def populate_replay_case_summary(
    driver_case: Mapping[str, object],
    summary_case: Mapping[str, object],
    *,
    stata_bundle: Mapping[str, object] | None = None,
    python_bundle: Mapping[str, object] | None = None,
    overall_capture_packet: Mapping[str, object] | None = None,
    overall_capture_verifier_input: Mapping[str, object] | None = None,
    capture_metadata: Mapping[str, object] | None = None,
    precapture_contract: Mapping[str, object] | None = None,
) -> dict[str, object]:
    driver = _mapping_copy(driver_case, label="driver_case")
    summary = deepcopy(_mapping_copy(summary_case, label="summary_case"))
    _validate_template_alignment(driver, summary)
    driver_oracle_capture = _normalized_optional_mapping(
        driver.get("oracle_capture"),
        case_id=str(driver["case_id"]),
        label="driver oracle_capture",
    )
    normalized_oracle_capture_summary = _normalized_oracle_capture_summary_fields(
        summary.get("oracle_capture_summary"),
        case_id=str(driver["case_id"]),
    )
    if normalized_oracle_capture_summary is not None:
        summary["oracle_capture_summary"] = normalized_oracle_capture_summary
        if precapture_contract is not None:
            precapture_contract_summary = normalized_oracle_capture_summary.get(
                "precapture_contract_summary"
            )
            if precapture_contract_summary is not None:
                _validate_summary_precapture_contract_summary(
                    precapture_contract_summary,
                    precapture_contract=precapture_contract,
                    case_id=str(driver["case_id"]),
                    expected_sample_window=_int_list(
                        driver.get("sample_window"),
                        label=f"{driver['case_id']} driver sample_window",
                    ),
                )

    if (
        overall_capture_packet is not None
        or overall_capture_verifier_input is not None
        or capture_metadata is not None
    ):
        if overall_capture_packet is None or overall_capture_verifier_input is None:
            raise ValueError(
                f"{driver['case_id']} overall capture ingestion requires packet template and verifier input"
            )
        _populate_overall_capture_summary(
            driver,
            summary,
            overall_capture_packet=overall_capture_packet,
            overall_capture_verifier_input=overall_capture_verifier_input,
            capture_metadata=capture_metadata,
            precapture_contract=precapture_contract,
        )

    case_id = str(driver["case_id"])
    oracle_capture_status = _oracle_capture_status(summary, case_id=case_id)
    _validate_summary_capture_status_against_driver_oracle_capture(
        case_id=case_id,
        oracle_capture_status=oracle_capture_status or {},
        driver_oracle_capture=driver_oracle_capture,
    )
    if oracle_capture_status is not None and bool(oracle_capture_status.get("capture_ready")):
        _validate_summary_promoted_fields_against_capture_surface(
            case_id=case_id,
            summary_case=summary,
            driver_case=driver,
            oracle_capture_status=oracle_capture_status,
        )
    if oracle_capture_status is not None and precapture_contract is not None:
        oracle_capture_summary = summary.get("oracle_capture_summary")
        if isinstance(oracle_capture_summary, Mapping):
            precapture_contract_summary = oracle_capture_summary.get(
                "precapture_contract_summary"
            )
            if precapture_contract_summary is not None:
                _validate_summary_precapture_contract_summary(
                    precapture_contract_summary,
                    precapture_contract=precapture_contract,
                    case_id=case_id,
                    expected_sample_window=_int_list(
                        driver.get("sample_window"),
                        label=f"{case_id} driver sample_window",
                    ),
                )
        _validate_graph_status_against_precapture_contract(
            oracle_capture_status,
            precapture_contract=precapture_contract,
            case_id=case_id,
            label="oracle_capture_summary.capture_metadata_status",
        )
    if (
        oracle_capture_status is not None
        and bool(oracle_capture_status.get("capture_ready"))
        and (stata_bundle is None or python_bundle is None)
    ):
        raise ValueError(
            f"{case_id} capture-ready overall metadata requires same-case stata_bundles and python_bundles"
        )
    if (stata_bundle is None) != (python_bundle is None):
        raise ValueError(
            f"{case_id} replay comparisons require same-case stata_bundles and python_bundles together or neither"
        )
    if (
        oracle_capture_status is not None
        and bool(oracle_capture_status.get("capture_ready"))
        and overall_capture_verifier_input is not None
        and stata_bundle is not None
        and python_bundle is not None
        and not _bundle_comparison_pending(stata_bundle)
        and not _bundle_comparison_pending(python_bundle)
    ):
        stata_bundle, python_bundle = _promote_capture_ready_overall_summary(
            summary,
            case_id=case_id,
            verifier_input=overall_capture_verifier_input,
            stata_bundle=stata_bundle,
            python_bundle=python_bundle,
        )

    comparison_pending = _bundle_comparison_pending(
        stata_bundle,
    ) or _bundle_comparison_pending(python_bundle)

    expected_graph_status = str(driver.get("graph_status"))
    if (
        oracle_capture_status is not None
        and oracle_capture_status.get("capture_status") is not None
        and not str(oracle_capture_status["capture_status"]).startswith("blocked-")
        and oracle_capture_status.get("graph_status") is not None
    ):
        expected_graph_status = _graph_status_value(
            oracle_capture_status["graph_status"],
            label=f"{case_id} oracle_capture_summary.capture_metadata_status.graph_status",
        )
    stata_graph_status = None
    python_graph_status = None
    observed_graph_statuses: list[str] = []

    if stata_bundle is not None:
        stata_graph_status = _graph_status(stata_bundle, label="stata_bundle")
        observed_graph_statuses.append(stata_graph_status)
    if python_bundle is not None:
        python_graph_status = _graph_status(python_bundle, label="python_bundle")
        observed_graph_statuses.append(python_graph_status)

    matches_driver: bool | None = None
    if observed_graph_statuses:
        matches_driver = all(
            graph_status == expected_graph_status
            for graph_status in observed_graph_statuses
        )

    summary["graph_status_summary"] = {
        "expected": expected_graph_status,
        "stata": stata_graph_status,
        "python": python_graph_status,
        "matches_driver": matches_driver,
    }
    stata_graph_data_summary = (
        stata_bundle.get("graph_data_summary")
        if isinstance(stata_bundle, Mapping)
        else None
    )
    python_graph_data_summary = (
        python_bundle.get("graph_data_summary")
        if isinstance(python_bundle, Mapping)
        else None
    )
    graph_data_summary: dict[str, object] | None = None
    if (
        isinstance(stata_graph_data_summary, Mapping)
        and isinstance(python_graph_data_summary, Mapping)
    ):
        if _graph_sidecar_core_summary(
            stata_graph_data_summary
        ) != _graph_sidecar_core_summary(python_graph_data_summary):
            raise ValueError(
                f"{case_id} graph sidecar core summary must match across replay bundles"
            )
        graph_data_summary = deepcopy(dict(python_graph_data_summary))
        graph_data_summary["article_source"] = "python-stored-results-preview"
        graph_data_summary["reference_graph_data_summary"] = deepcopy(
            dict(stata_graph_data_summary)
        )
        graph_data_summary["graph_reference_comparison"] = (
            _graph_summary_preview_comparison(
                reference_graph_data_summary=stata_graph_data_summary,
                article_graph_data_summary=python_graph_data_summary,
            )
        )
        summary["graph_data_summary"] = graph_data_summary

    if matches_driver is None:
        graph_readiness_state = "pending-capture"
        graph_publication_ready = False
        graph_readiness_reason = (
            "graph status has not been observed for both replay bundles"
        )
    elif matches_driver is not True:
        graph_readiness_state = "status-mismatch"
        graph_publication_ready = False
        graph_readiness_reason = (
            "observed graph status does not match the replay driver"
        )
    elif (
        isinstance(graph_data_summary, Mapping)
        and graph_data_summary.get("series_complete") is True
        and _graph_series_comparison_verified(graph_data_summary)
    ):
        graph_readiness_state = "publication-ready"
        graph_publication_ready = True
        graph_readiness_reason = (
            f"graph status {expected_graph_status} matches the replay driver "
            "and the article-facing Python event-study preview is complete"
        )
    else:
        graph_readiness_state = "status-matched-not-publishable"
        graph_publication_ready = False
        if expected_graph_status == "graph-exported":
            if (
                isinstance(graph_data_summary, Mapping)
                and graph_data_summary.get("series_complete") is True
                and graph_data_summary.get("series_match_derived_preview") is True
            ):
                graph_readiness_reason = (
                    "graph-exported status matches the replay driver but the graph "
                    "series comparison block does not prove the stored-results "
                    "event-study preview match"
                )
            elif (
                isinstance(graph_data_summary, Mapping)
                and graph_data_summary.get("series_complete") is True
            ):
                graph_readiness_reason = (
                    "graph-exported status matches the replay driver but the graph "
                    "sidecar estimates do not match the stored-results event-study preview"
                )
            else:
                graph_readiness_reason = (
                    "graph-exported status matches the replay driver but the graph "
                    "sidecar does not contain complete pre/post plotting series"
                )
        else:
            graph_readiness_reason = (
                f"graph status {expected_graph_status} matches the replay driver "
                "but is not publication-ready exported graph data"
            )

    summary["graph_readiness_summary"] = {
        "state": graph_readiness_state,
        "publication_ready": graph_publication_ready,
        "reason": graph_readiness_reason,
    }

    if "blockers" in summary and isinstance(driver.get("blocking_gaps"), list):
        summary["blockers"] = list(driver["blocking_gaps"])
    if (
        "oracle_capture" in summary
        and isinstance(driver.get("oracle_capture"), Mapping)
        and overall_capture_packet is None
    ):
        summary["oracle_capture"] = deepcopy(dict(driver["oracle_capture"]))

    if comparison_pending or stata_bundle is None or python_bundle is None:
        template_verdict = _nonempty_string(
            summary.get("verdict", "pending"),
            label=f"{case_id} summary template verdict",
        )
        if template_verdict != "pending":
            raise ValueError(
                f"{case_id} summary template verdict must stay pending until "
                "same-case stata_bundles and python_bundles are provided"
            )
        for _, _, summary_key in _SECTIONS:
            section_summary = summary.get(summary_key)
            if not isinstance(section_summary, Mapping):
                raise ValueError(
                    f"{case_id} summary template {summary_key} must be a mapping"
                )
            for bucket in _BUCKETS:
                bucket_summary = section_summary.get(bucket)
                if not isinstance(bucket_summary, Mapping):
                    raise ValueError(
                        f"{case_id} summary template {summary_key}.{bucket} must be a mapping"
                    )
                for field_name in ("matched_fields", "mismatched_fields"):
                    populated_fields = _string_list(
                        bucket_summary.get(field_name, []),
                        label=(
                            f"{case_id} summary template "
                            f"{summary_key}.{bucket}.{field_name}"
                        ),
                        require_unique=True,
                    )
                    if populated_fields:
                        raise ValueError(
                            f"{case_id} summary template "
                            f"{summary_key}.{bucket}.{field_name} must stay empty "
                            "until same-case stata_bundles and python_bundles are "
                            "provided"
                        )
        summary["verdict"] = template_verdict
        return summary

    has_mismatch = matches_driver is False
    has_rng_bound_mismatch = False
    rng_bound_mismatches: dict[str, dict[str, list[str]]] = {}
    for section, _, summary_key in _SECTIONS:
        section_summary = summary[summary_key]
        assert isinstance(section_summary, dict)
        for bucket in _BUCKETS:
            bucket_summary = section_summary[bucket]
            assert isinstance(bucket_summary, dict)
            planned_fields = _string_list(
                bucket_summary.get("planned_fields"),
                label=f"{driver['case_id']} {summary_key}.{bucket}.planned_fields",
            )
            matched_fields, mismatched_fields = _compare_bucket(
                planned_fields,
                stata_bundle=stata_bundle,
                python_bundle=python_bundle,
                section=section,
                bucket=bucket,
            )
            bucket_summary["matched_fields"] = matched_fields
            bucket_summary["mismatched_fields"] = mismatched_fields
            if mismatched_fields:
                rng_bound_fields = _rng_bound_comparison_fields(
                    section=section,
                    bucket=bucket,
                )
                rng_bucket_mismatches = [
                    field for field in mismatched_fields if field in rng_bound_fields
                ]
                deterministic_mismatches = [
                    field
                    for field in mismatched_fields
                    if field not in rng_bound_fields
                ]
                if rng_bucket_mismatches:
                    has_rng_bound_mismatch = True
                    rng_bound_mismatches.setdefault(section, {})[bucket] = (
                        rng_bucket_mismatches
                    )
                if deterministic_mismatches:
                    has_mismatch = True

    if has_mismatch:
        summary["verdict"] = "mismatch"
    elif has_rng_bound_mismatch:
        summary["verdict"] = "mismatch"
        summary["python_parity_status"] = _RNG_MISMATCH_STATUS
    else:
        summary["verdict"] = "matched"
    if has_rng_bound_mismatch:
        summary["python_parity_status"] = _RNG_MISMATCH_STATUS
    if rng_bound_mismatches:
        summary["rng_bound_mismatch_summary"] = {
            "status": "recorded-separately-from-deterministic-verdict",
            "reason": (
                "These fields depend on the simulated critical-value stream and "
                "are not counted as deterministic replay mismatches."
            ),
            "fields_by_section": rng_bound_mismatches,
        }
    return summary


def _case_overrides(
    value: Mapping[str, object] | None,
    *,
    label: str,
    known_case_ids: set[str],
) -> dict[str, Mapping[str, object]]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping keyed by case_id")

    normalized: dict[str, Mapping[str, object]] = {}
    for raw_case_id, payload in value.items():
        case_id = str(raw_case_id)
        if case_id in normalized:
            raise ValueError(f"{label} keys must remain unique after normalization")
        if (
            not isinstance(raw_case_id, str)
            or not raw_case_id.strip()
            or raw_case_id != raw_case_id.strip()
        ):
            raise ValueError(f"{label} keys must be non-empty strings")
        if case_id not in known_case_ids:
            raise ValueError(f"{label} contains unknown case_id {case_id}")
        if not isinstance(payload, Mapping):
            raise ValueError(f"{label}[{case_id}] must be a mapping")
        normalized[case_id] = payload
    return normalized


def _overall_capture_ready_override(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    capture_status = value.get("capture_status")
    metadata_payload = value.get("metadata_payload")
    return (
        isinstance(capture_status, str)
        and not capture_status.startswith("blocked-")
        and isinstance(metadata_payload, Mapping)
        and metadata_payload.get("capture_ready") is True
    )


def _reject_partial_capture_ready_bundle_overrides(
    *,
    capture_metadata_by_case: Mapping[str, object],
    left_mapping: Mapping[str, object],
    right_mapping: Mapping[str, object],
    left_label: str,
    right_label: str,
) -> None:
    for case_id, capture_metadata in capture_metadata_by_case.items():
        if not _overall_capture_ready_override(capture_metadata):
            continue
        has_left = case_id in left_mapping
        has_right = case_id in right_mapping
        if has_left == has_right:
            continue
        raise ValueError(
            f"{case_id} capture-ready overall metadata requires "
            f"{left_label}[{case_id}] and {right_label}[{case_id}] together or neither"
        )


def _reject_partial_bundle_overrides(
    *,
    known_case_ids: set[str],
    capture_metadata_by_case: Mapping[str, object],
    left_mapping: Mapping[str, object],
    right_mapping: Mapping[str, object],
    left_label: str,
    right_label: str,
) -> None:
    capture_ready_case_ids = {
        case_id
        for case_id, capture_metadata in capture_metadata_by_case.items()
        if _overall_capture_ready_override(capture_metadata)
    }
    for case_id in known_case_ids:
        if case_id in capture_ready_case_ids:
            continue
        has_left = case_id in left_mapping
        has_right = case_id in right_mapping
        if has_left == has_right:
            continue
        raise ValueError(
            f"{case_id} replay comparisons require "
            f"{left_label}[{case_id}] and {right_label}[{case_id}] together or neither"
        )


def _document_level_summary(
    summary_cases: list[dict[str, object]],
) -> dict[str, object]:
    case_totals = {verdict: 0 for verdict in _VERDICTS}
    case_ids_by_verdict = {key: [] for key in case_totals}
    graph_status_totals = {
        "matches_driver": 0,
        "mismatches_driver": 0,
        "pending": 0,
    }
    case_ids_by_graph_status = {key: [] for key in graph_status_totals}
    graph_readiness_totals = {
        "publication_ready": 0,
        "status_matched_not_publishable": 0,
        "status_mismatch": 0,
        "pending_capture": 0,
    }
    case_ids_by_graph_readiness = {key: [] for key in graph_readiness_totals}
    oracle_capture_totals = {
        "capture_ready": 0,
        "captured_not_ready": 0,
        "blocked": 0,
        "not_applicable": 0,
    }
    case_ids_by_oracle_capture = {key: [] for key in oracle_capture_totals}
    bucket_totals = {
        summary_key: {
            bucket: {
                "planned_fields": 0,
                "matched_fields": 0,
                "mismatched_fields": 0,
            }
            for bucket in _BUCKETS
        }
        for _, _, summary_key in _SECTIONS
    }
    seen_case_ids: set[str] = set()

    for case in summary_cases:
        case_id = _nonempty_string(case.get("case_id"), label="summary case.case_id")
        if case_id in seen_case_ids:
            raise ValueError(
                f"summary_cases must not contain duplicate case_id {case_id}"
            )
        seen_case_ids.add(case_id)
        verdict = _nonempty_string(
            case.get("verdict"),
            label=f"{case_id} verdict",
        )
        if verdict not in case_totals:
            raise ValueError(
                f"{case_id} verdict must be one of: "
                + ", ".join(_VERDICTS)
            )
        case_totals[verdict] += 1
        case_ids_by_verdict[verdict].append(case_id)

        graph_status_summary = case.get("graph_status_summary")
        if not isinstance(graph_status_summary, Mapping):
            raise ValueError(f"{case_id} graph_status_summary must be a mapping")
        matches_driver = graph_status_summary.get("matches_driver")
        pending_capture_ready_graph = False
        oracle_capture_summary_for_graph = case.get("oracle_capture_summary")
        if isinstance(oracle_capture_summary_for_graph, Mapping):
            capture_metadata_status_for_graph = oracle_capture_summary_for_graph.get(
                "capture_metadata_status"
            )
            if isinstance(capture_metadata_status_for_graph, Mapping):
                pending_capture_ready_graph = (
                    capture_metadata_status_for_graph.get("capture_ready") is True
                )
        if (
            verdict == "pending"
            and matches_driver is not None
            and not pending_capture_ready_graph
        ):
            raise ValueError(
                f"{case_id} pending verdict must keep "
                "graph_status_summary.matches_driver null"
            )
        if (
            verdict in {"matched", "mismatch"}
            and matches_driver is None
        ):
            raise ValueError(
                f"{case_id} {verdict} verdict must keep "
                "graph_status_summary.matches_driver boolean"
            )
        if matches_driver is True:
            graph_status_totals["matches_driver"] += 1
            case_ids_by_graph_status["matches_driver"].append(case_id)
        elif matches_driver is False:
            graph_status_totals["mismatches_driver"] += 1
            case_ids_by_graph_status["mismatches_driver"].append(case_id)
        elif matches_driver is None:
            graph_status_totals["pending"] += 1
            case_ids_by_graph_status["pending"].append(case_id)
        else:
            raise ValueError(
                f"{case_id} graph_status_summary.matches_driver must be true, false, or null"
            )

        graph_readiness_summary = case.get("graph_readiness_summary")
        if not isinstance(graph_readiness_summary, Mapping):
            raise ValueError(f"{case_id} graph_readiness_summary must be a mapping")
        graph_readiness_state = _nonempty_string(
            graph_readiness_summary.get("state"),
            label=f"{case_id} graph_readiness_summary.state",
        )
        graph_publication_ready = _bool_value(
            graph_readiness_summary.get("publication_ready"),
            label=f"{case_id} graph_readiness_summary.publication_ready",
        )
        _nonempty_string(
            graph_readiness_summary.get("reason"),
            label=f"{case_id} graph_readiness_summary.reason",
        )
        if graph_readiness_state == "publication-ready":
            if graph_publication_ready is not True:
                raise ValueError(
                    f"{case_id} graph_readiness_summary.publication_ready must be true for publication-ready state"
                )
            graph_readiness_totals["publication_ready"] += 1
            case_ids_by_graph_readiness["publication_ready"].append(case_id)
        elif graph_readiness_state == "status-matched-not-publishable":
            if graph_publication_ready is not False:
                raise ValueError(
                    f"{case_id} graph_readiness_summary.publication_ready must be false for non-publishable graph state"
                )
            graph_readiness_totals["status_matched_not_publishable"] += 1
            case_ids_by_graph_readiness["status_matched_not_publishable"].append(case_id)
        elif graph_readiness_state == "status-mismatch":
            if graph_publication_ready is not False:
                raise ValueError(
                    f"{case_id} graph_readiness_summary.publication_ready must be false for graph status mismatch"
                )
            graph_readiness_totals["status_mismatch"] += 1
            case_ids_by_graph_readiness["status_mismatch"].append(case_id)
        elif graph_readiness_state == "pending-capture":
            if graph_publication_ready is not False:
                raise ValueError(
                    f"{case_id} graph_readiness_summary.publication_ready must be false while graph capture is pending"
                )
            graph_readiness_totals["pending_capture"] += 1
            case_ids_by_graph_readiness["pending_capture"].append(case_id)
        else:
            raise ValueError(
                f"{case_id} graph_readiness_summary.state must be one of: "
                "publication-ready, status-matched-not-publishable, "
                "status-mismatch, pending-capture"
            )

        oracle_capture_summary = case.get("oracle_capture_summary")
        if oracle_capture_summary is None:
            oracle_capture_totals["not_applicable"] += 1
            case_ids_by_oracle_capture["not_applicable"].append(case_id)
        elif not isinstance(oracle_capture_summary, Mapping):
            raise ValueError(
                f"{case_id} oracle_capture_summary must be a mapping or null"
            )
        else:
            capture_metadata_status = _oracle_capture_status(case, case_id=case_id)
            if capture_metadata_status is None:
                raise ValueError(
                    f"{case_id} oracle_capture_summary.capture_metadata_status must be a mapping"
                )
            capture_ready = _bool_value(
                capture_metadata_status.get("capture_ready"),
                label=(
                    f"{case_id} "
                    "oracle_capture_summary.capture_metadata_status.capture_ready"
                ),
            )
            if capture_ready is True:
                capture_status = capture_metadata_status.get("capture_status")
                if capture_status is None:
                    raise ValueError(
                        f"{case_id} oracle_capture_summary.capture_metadata_status "
                        "must not mark capture_ready=true without capture_status"
                    )
                if (
                    isinstance(capture_status, str)
                    and _nonempty_string(
                        capture_status,
                        label=(
                            f"{case_id} "
                            "oracle_capture_summary.capture_metadata_status.capture_status"
                        ),
                    ).startswith("blocked-")
                ):
                    raise ValueError(
                        f"{case_id} oracle_capture_summary.capture_metadata_status "
                        f"must not mark capture_ready=true with blocked capture_status "
                        f"{capture_status}"
                    )
                oracle_capture_totals["capture_ready"] += 1
                case_ids_by_oracle_capture["capture_ready"].append(case_id)
            else:
                capture_status = capture_metadata_status.get("capture_status")
                if (
                    capture_status is None
                    or (
                        isinstance(capture_status, str)
                        and _nonempty_string(
                            capture_status,
                            label=(
                                f"{case_id} "
                                "oracle_capture_summary.capture_metadata_status.capture_status"
                            ),
                        ).startswith("blocked-")
                    )
                ):
                    oracle_capture_totals["blocked"] += 1
                    case_ids_by_oracle_capture["blocked"].append(case_id)
                elif isinstance(capture_status, str):
                    _nonempty_string(
                        capture_status,
                        label=(
                            f"{case_id} "
                            "oracle_capture_summary.capture_metadata_status.capture_status"
                        ),
                    )
                    oracle_capture_totals["captured_not_ready"] += 1
                    case_ids_by_oracle_capture["captured_not_ready"].append(case_id)
                else:
                    raise ValueError(
                        f"{case_id} oracle_capture_summary.capture_metadata_status.capture_status must be a string or null"
                    )

        for _, _, summary_key in _SECTIONS:
            section_summary = case.get(summary_key)
            if not isinstance(section_summary, Mapping):
                raise ValueError(f"{case_id} {summary_key} must be a mapping")
            section_planned_fields: set[str] = set()
            for bucket in _BUCKETS:
                bucket_summary = section_summary.get(bucket)
                if not isinstance(bucket_summary, Mapping):
                    raise ValueError(f"{case_id} {summary_key}.{bucket} must be a mapping")
                planned_fields = _string_list(
                    bucket_summary.get("planned_fields"),
                    label=f"{case_id} {summary_key}.{bucket}.planned_fields",
                    require_unique=True,
                )
                matched_fields = _string_list(
                    bucket_summary.get("matched_fields"),
                    label=f"{case_id} {summary_key}.{bucket}.matched_fields",
                    require_unique=True,
                )
                mismatched_fields = _string_list(
                    bucket_summary.get("mismatched_fields"),
                    label=f"{case_id} {summary_key}.{bucket}.mismatched_fields",
                    require_unique=True,
                )
                planned_field_set = set(planned_fields)
                matched_field_set = set(matched_fields)
                mismatched_field_set = set(mismatched_fields)
                overlapping_planned_fields = sorted(
                    section_planned_fields & planned_field_set
                )
                if overlapping_planned_fields:
                    raise ValueError(
                        f"{case_id} {summary_key} planned_fields must stay disjoint across buckets: "
                        + ", ".join(overlapping_planned_fields)
                    )
                unexpected_fields = sorted(
                    (matched_field_set | mismatched_field_set) - planned_field_set
                )
                if unexpected_fields:
                    raise ValueError(
                        f"{case_id} {summary_key}.{bucket} fields must stay within planned_fields: "
                        + ", ".join(unexpected_fields)
                    )
                overlapping_fields = sorted(
                    matched_field_set & mismatched_field_set
                )
                if overlapping_fields:
                    raise ValueError(
                        f"{case_id} {summary_key}.{bucket} matched_fields and mismatched_fields must stay disjoint: "
                        + ", ".join(overlapping_fields)
                    )
                section_planned_fields.update(planned_field_set)
                bucket_totals[summary_key][bucket]["planned_fields"] += len(
                    planned_fields
                )
                bucket_totals[summary_key][bucket]["matched_fields"] += len(
                    matched_fields
                )
                bucket_totals[summary_key][bucket]["mismatched_fields"] += len(
                    mismatched_fields
                )

    return {
        "case_totals": case_totals,
        "case_ids_by_verdict": case_ids_by_verdict,
        "graph_status_totals": graph_status_totals,
        "case_ids_by_graph_status": case_ids_by_graph_status,
        "graph_readiness_totals": graph_readiness_totals,
        "case_ids_by_graph_readiness": case_ids_by_graph_readiness,
        "oracle_capture_totals": oracle_capture_totals,
        "case_ids_by_oracle_capture": case_ids_by_oracle_capture,
        "bucket_totals": bucket_totals,
    }


def _autoload_capture_ready_overall_bundles(
    *,
    driver_document: Mapping[str, object],
    summary_template: Mapping[str, object],
    stata_bundles: dict[str, Mapping[str, object]],
    python_bundles: dict[str, Mapping[str, object]],
    overall_capture_packets: dict[str, Mapping[str, object]],
    overall_capture_verifier_inputs: dict[str, Mapping[str, object]],
    precapture_contracts_by_case: dict[str, Mapping[str, object]],
    capture_metadata_by_case: dict[str, Mapping[str, object]],
) -> tuple[dict[str, Mapping[str, object]], dict[str, Mapping[str, object]]]:
    from .replay_summary import (
        _capture_ready_overall_loadable_docs_message,
        _bundled_prop99_replay_root,
        _load_capture_ready_overall_bundles,
    )

    updated_stata_bundles = dict(stata_bundles)
    updated_python_bundles = dict(python_bundles)
    module_anchor = Path(__file__).resolve()
    prop99_replay_root = _bundled_prop99_replay_root()

    for case_id, capture_metadata in capture_metadata_by_case.items():
        capture_status = capture_metadata.get("capture_status")
        metadata_payload = capture_metadata.get("metadata_payload")
        if (
            not isinstance(capture_status, str)
            or capture_status.startswith("blocked-")
            or not isinstance(metadata_payload, Mapping)
            or metadata_payload.get("capture_ready") is not True
        ):
            continue
        has_stata_bundle = case_id in updated_stata_bundles
        has_python_bundle = case_id in updated_python_bundles
        if has_stata_bundle != has_python_bundle:
            raise ValueError(
                f"{case_id} capture-ready overall metadata requires "
                f"stata_bundles[{case_id}] and python_bundles[{case_id}] "
                "together or neither"
            )
        if has_stata_bundle and has_python_bundle:
            continue

        try:
            bundle_pair = _load_capture_ready_overall_bundles(
                driver_document=driver_document,
                summary_template=summary_template,
                case_id=case_id,
                overall_capture_packet=overall_capture_packets[case_id],
                overall_capture_verifier_input=overall_capture_verifier_inputs[case_id],
                precapture_contract=precapture_contracts_by_case[case_id],
                capture_metadata=capture_metadata,
                promote_authoritative_fields=False,
                allow_python_placeholder_fallback=True,
                anchor_paths=(prop99_replay_root, module_anchor),
            )
        except ValueError as exc:
            if str(exc).startswith(
                _capture_ready_overall_loadable_docs_message(case_id)
            ):
                raise ValueError(
                    _capture_ready_overall_loadable_docs_message(
                        case_id,
                        include_explicit_bundles=True,
                    )
                ) from exc
            raise
        updated_stata_bundles.setdefault(case_id, bundle_pair["stata_bundle"])
        updated_python_bundles.setdefault(case_id, bundle_pair["python_bundle"])

    return updated_stata_bundles, updated_python_bundles


def _validate_story_packet_artifact_paths_against_documents(
    story_packet_artifact_paths: Mapping[str, object],
    *,
    driver_lookup: Mapping[str, dict[str, object]],
    summary_lookup: Mapping[str, dict[str, object]],
    overall_capture_packets: Mapping[str, Mapping[str, object]],
) -> None:
    normalized_paths = _artifact_path_mapping(
        story_packet_artifact_paths,
        label="story_packet_artifact_paths",
    )
    if sorted(normalized_paths) != sorted(
        _CANONICAL_STORY_PACKET_ARTIFACT_PATH_FIELDS
    ):
        raise ValueError(
            "story_packet_artifact_paths must define the canonical story packet artifact path keys"
        )
    if len(overall_capture_packets) != 1:
        raise ValueError(
            "story_packet_artifact_paths requires exactly one overall capture packet"
        )
    case_id = next(iter(overall_capture_packets))
    driver_case = driver_lookup[case_id]
    summary_case = summary_lookup[case_id]
    driver_capture_paths = _string_mapping(
        driver_case.get("capture_paths"),
        label=f"{case_id} driver capture_paths",
    )
    summary_capture_paths = _string_mapping(
        summary_case.get("capture_paths"),
        label=f"{case_id} summary capture_paths",
    )
    packet_capture_paths = _string_mapping(
        overall_capture_packets[case_id].get("capture_paths"),
        label=f"{case_id} overall_capture_packet.capture_paths",
    )
    expected_pairs = (
        ("stata_stdout", driver_capture_paths.get("stata_stdout")),
        ("stata_stdout", summary_capture_paths.get("stata_stdout")),
        ("python_stdout", driver_capture_paths.get("python_stdout")),
        ("python_stdout", summary_capture_paths.get("python_stdout")),
        ("stata_stored_results", driver_capture_paths.get("stata_stored_results")),
        ("stata_stored_results", summary_capture_paths.get("stata_stored_results")),
        ("python_stored_results", driver_capture_paths.get("python_stored_results")),
        ("python_stored_results", summary_capture_paths.get("python_stored_results")),
        ("stata_graph_data", packet_capture_paths.get("stata_graph_data")),
        ("capture_metadata", packet_capture_paths.get("capture_metadata")),
    )
    for field_name, actual_path in expected_pairs:
        if not isinstance(actual_path, str) or not actual_path.strip():
            raise ValueError(
                f"{case_id} {field_name} capture path must be a non-empty string"
            )
        if normalized_paths.get(field_name) != actual_path:
            raise ValueError(
                f"story_packet_artifact_paths.{field_name} must align with {case_id} replay scaffold capture paths"
            )
    for field_name, expected_path in (
        _bundled_prop99_story_packet_scaffold_artifact_paths().items()
    ):
        if normalized_paths.get(field_name) != expected_path:
            raise ValueError(
                f"story_packet_artifact_paths.{field_name} must align with bundled overall capture scaffold"
            )
    for field_name, expected_path in (
        _bundled_prop99_story_packet_auxiliary_artifact_paths().items()
    ):
        if normalized_paths.get(field_name) != expected_path:
            raise ValueError(
                f"story_packet_artifact_paths.{field_name} must align with bundled overall auxiliary scaffold"
            )


def materialize_replay_summary(
    driver_document: Mapping[str, object],
    summary_template: Mapping[str, object],
    *,
    stata_bundles: Mapping[str, object] | None = None,
    python_bundles: Mapping[str, object] | None = None,
    overall_capture_packets: Mapping[str, object] | None = None,
    overall_capture_verifier_inputs: Mapping[str, object] | None = None,
    precapture_contracts_by_case: Mapping[str, object] | None = None,
    capture_metadata_by_case: Mapping[str, object] | None = None,
    story_packet_artifact_paths: Mapping[str, object] | None = None,
) -> dict[str, object]:
    driver = _document_mapping(driver_document, label="driver_document")
    summary = deepcopy(_document_mapping(summary_template, label="summary_template"))

    driver_cases, driver_lookup = _case_lookup(
        driver["cases"],
        label="driver_document.cases",
    )
    summary_cases, summary_lookup = _case_lookup(
        summary["cases"],
        label="summary_template.cases",
    )
    _validate_document_alignment(
        driver,
        summary,
        driver_cases=driver_cases,
        summary_cases=summary_cases,
    )

    driver_case_ids = set(driver_lookup)
    summary_case_ids = set(summary_lookup)
    if driver_case_ids != summary_case_ids:
        raise ValueError(
            "driver_document and summary_template must define the same cases"
        )

    normalized_stata_bundles = _case_overrides(
        stata_bundles,
        label="stata_bundles",
        known_case_ids=summary_case_ids,
    )
    normalized_python_bundles = _case_overrides(
        python_bundles,
        label="python_bundles",
        known_case_ids=summary_case_ids,
    )
    normalized_capture_packets = _case_overrides(
        overall_capture_packets,
        label="overall_capture_packets",
        known_case_ids=summary_case_ids,
    )
    if story_packet_artifact_paths is not None:
        _validate_story_packet_artifact_paths_against_documents(
            story_packet_artifact_paths,
            driver_lookup=driver_lookup,
            summary_lookup=summary_lookup,
            overall_capture_packets=normalized_capture_packets,
        )
        _validate_existing_artifact_paths(
            story_packet_artifact_paths,
            label="story_packet_artifact_paths",
            callable_name="materialize_replay_summary",
        )
    normalized_verifier_inputs = _case_overrides(
        overall_capture_verifier_inputs,
        label="overall_capture_verifier_inputs",
        known_case_ids=summary_case_ids,
    )
    normalized_precapture_contracts = _case_overrides(
        precapture_contracts_by_case,
        label="precapture_contracts_by_case",
        known_case_ids=summary_case_ids,
    )
    normalized_capture_metadata = _case_overrides(
        capture_metadata_by_case,
        label="capture_metadata_by_case",
        known_case_ids=summary_case_ids,
    )

    for case_id in normalized_capture_metadata:
        if (
            case_id not in normalized_capture_packets
            or case_id not in normalized_verifier_inputs
        ):
            raise ValueError(
                f"{case_id} capture_metadata_by_case requires "
                f"overall_capture_packets[{case_id}] and "
                f"overall_capture_verifier_inputs[{case_id}]"
            )

    for case_id in normalized_precapture_contracts:
        if (
            case_id not in normalized_capture_packets
            or case_id not in normalized_verifier_inputs
        ):
            raise ValueError(
                f"{case_id} precapture_contracts_by_case requires "
                f"overall_capture_packets[{case_id}] and "
                f"overall_capture_verifier_inputs[{case_id}]"
            )

    for case_id in normalized_capture_metadata:
        if case_id not in normalized_precapture_contracts:
            raise ValueError(
                f"{case_id} capture_metadata_by_case requires "
                f"precapture_contracts_by_case[{case_id}]"
            )

    _reject_partial_capture_ready_bundle_overrides(
        capture_metadata_by_case=normalized_capture_metadata,
        left_mapping=normalized_stata_bundles,
        right_mapping=normalized_python_bundles,
        left_label="stata_bundles",
        right_label="python_bundles",
    )
    _reject_partial_bundle_overrides(
        known_case_ids=summary_case_ids,
        capture_metadata_by_case=normalized_capture_metadata,
        left_mapping=normalized_stata_bundles,
        right_mapping=normalized_python_bundles,
        left_label="stata_bundles",
        right_label="python_bundles",
    )

    if normalized_capture_packets and normalized_capture_metadata:
        (
            normalized_stata_bundles,
            normalized_python_bundles,
        ) = _autoload_capture_ready_overall_bundles(
            driver_document=driver,
            summary_template=summary,
            stata_bundles=normalized_stata_bundles,
            python_bundles=normalized_python_bundles,
            overall_capture_packets=normalized_capture_packets,
            overall_capture_verifier_inputs=normalized_verifier_inputs,
            precapture_contracts_by_case=normalized_precapture_contracts,
            capture_metadata_by_case=normalized_capture_metadata,
        )

    ordered_summary_cases = []
    for summary_case in summary_cases:
        case_id = str(summary_case["case_id"])
        ordered_summary_cases.append(
            populate_replay_case_summary(
                driver_lookup[case_id],
                summary_case,
                stata_bundle=normalized_stata_bundles.get(case_id),
                python_bundle=normalized_python_bundles.get(case_id),
                overall_capture_packet=None
                if overall_capture_packets is None
                else normalized_capture_packets.get(case_id),
                overall_capture_verifier_input=None
                if overall_capture_verifier_inputs is None
                else normalized_verifier_inputs.get(case_id),
                precapture_contract=None
                if precapture_contracts_by_case is None
                else normalized_precapture_contracts.get(case_id),
                capture_metadata=None
                if capture_metadata_by_case is None
                else normalized_capture_metadata.get(case_id),
            )
        )

    summary["cases"] = ordered_summary_cases
    summary["case_count"] = len(ordered_summary_cases)
    summary["document_summary"] = _document_level_summary(ordered_summary_cases)
    return summary
