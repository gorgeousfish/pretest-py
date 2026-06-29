from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from numbers import Integral
from typing import Any

from ._compat import frozen_slots_dataclass
from ._display import pretest_result_html, pretest_result_str
from .api import PretestCommandSpec

_VERDICT_BUCKETS = ("exact", "display_rounded", "exact_absence", "unresolved")
_PROTECTED_OVERALL_OUTPUTS = ["e(theta)", "e(S_pre_se)"]
_BLOCKED_OVERALL_CAPTURE_CASE = "PROP99-WINDOW-1985-1995-M5-OVERALL"
_ITERATIVE_GRAPH_ERROR_CASES = {
    "PROP99-FULL-M5-ITER",
    "PROP99-WINDOW-1985-1995-M5-ITER",
}
_ALLOWED_GRAPH_STATES = (
    "pending-implementation",
    "graph-exported",
    "graph-attempted",
    "suppressed",
)
_ALLOWED_REPLAY_GRAPH_STATUSES = (
    "graph-exported",
    "graph-attempted-but-error-198",
    "suppressed-by-nograph",
    "blocked-pending-oracle",
)
_STORED_RESULTS_EXACT = [
    "e(N)",
    "e(T)",
    "e(T_pre)",
    "e(T_post)",
    "e(phi)",
    "e(pretest_pass)",
    "e(data_valid)",
    "e(mode)",
]
_STORED_RESULTS_METADATA = [
    "e(cmd)",
    "e(cmdline)",
    "e(depvar)",
    "e(outcome)",
    "e(treatment)",
    "e(time)",
    "e(title)",
    "e(sims)",
    "e(seed)",
]
_STORED_RESULTS_CONTRACT_SCALARS = [
    "e(t0)",
    "e(n)",
    "e(is_panel)",
    "e(p)",
    "e(alpha)",
    "e(level)",
    "e(M)",
    "e(threshold)",
    "e(se_delta_bar)",
]
_STORED_RESULTS_EXACT_AUTHORITATIVE = [
    "e(N)",
    "e(T)",
    "e(T_pre)",
    "e(T_post)",
    *_STORED_RESULTS_CONTRACT_SCALARS,
    "e(sims)",
    "e(seed)",
    "e(phi)",
    "e(pretest_pass)",
    "e(data_valid)",
    "e(mode)",
]
_OPTIONAL_CLUSTER_METADATA = [
    "e(clustvar)",
    "e(cluster)",
]
_STORED_RESULTS_DISPLAY_ROUNDED_BASE = [
    "e(S_pre)",
    "e(kappa)",
    "e(f_alpha)",
    "e(delta_bar)",
]
_CONDITIONAL_CI_EXACT_ABSENCE = [
    "ci_lower",
    "ci_upper",
    "e(ci_lower)",
    "e(ci_upper)",
]
_STDOUT_EXACT = [
    "N",
    "T",
    "T_pre",
    "T_post",
    "pretest_result",
]
_STDOUT_DISPLAY_ROUNDED_BASE = [
    "severity",
    "kappa",
    "critical_value",
    "delta_bar",
]
_CONDITIONAL_CI_FIELDS = ["e(ci_lower)", "e(ci_upper)"]
_CONVENTIONAL_CI_FIELDS = ["e(ci_conv_lower)", "e(ci_conv_upper)"]
_STDOUT_CONDITIONAL_CI_FIELDS = ["ci_lower", "ci_upper"]
_STDOUT_CONVENTIONAL_CI_FIELDS = ["ci_conv_lower", "ci_conv_upper"]
_INTEGER_EXACT_REPLAY_FIELDS = {
    "N",
    "T",
    "T_pre",
    "T_post",
    "t0",
    "n",
    "is_panel",
}
_NUMERIC_EXACT_REPLAY_FIELDS = _INTEGER_EXACT_REPLAY_FIELDS | {
    "p",
    "alpha",
    "level",
    "M",
    "threshold",
    "se_delta_bar",
    "S_pre",
    "kappa",
    "f_alpha",
    "delta_bar",
    "ci_lower",
    "ci_upper",
    "ci_conv_lower",
    "ci_conv_upper",
}
_REPLAY_NUMERIC_FIELD_LABELS = {
    "ci_lower": "conditional CI lower",
    "ci_upper": "conditional CI upper",
    "ci_conv_lower": "conventional CI lower",
    "ci_conv_upper": "conventional CI upper",
}


@frozen_slots_dataclass
class PretestResultSnapshot:
    """Complete pre-test result snapshot for a single estimation case.

    Captures all computed quantities, validation state, replay metadata,
    and diagnostics produced by the pre-test pipeline. This is the primary
    result object returned by ``compute_pretest_snapshot``.

    Attributes
    ----------
    provenance : dict
        Command metadata: cmd, cmdline, mode, depvar, threshold,
        treat_time, cluster, overall, nograph, simulate, seed, diagnose.
    canonical : dict
        Nested namespace with 'scalars' (S_pre, kappa, f_alpha, delta_bar,
        ci_lower, ci_upper, phi, pretest_pass, data_valid, etc.),
        'macros' (cmd, mode, depvar, etc.), and 'matrices' (nu, delta,
        theta).
    compatibility : dict
        Legacy field aliases (e.g., ATT -> delta_bar).
    replay_contract : dict
        Replay-system metadata: verdict buckets, category assignments,
        graph status field.
    graph_status : dict
        Graph export state and replay verdict.
    oracle : dict
        Authoritative result list and protected auxiliary outputs.
    diagnostics : dict
        Validation issues, simulation parameters, staged-only fields.
    """

    provenance: dict[str, object]
    canonical: dict[str, object]
    compatibility: dict[str, object]
    replay_contract: dict[str, object]
    graph_status: dict[str, object]
    oracle: dict[str, object]
    diagnostics: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "provenance": self.provenance,
            "canonical": self.canonical,
            "compatibility": self.compatibility,
            "replay_contract": self.replay_contract,
            "graph_status": self.graph_status,
            "oracle": self.oracle,
            "diagnostics": self.diagnostics,
        }

    def conditional_interval(self) -> tuple[float, float] | None:
        """Return the conditional interval when the pre-test permits reporting."""
        return self._interval_pair("ci_lower", "ci_upper")

    def conventional_interval(self) -> tuple[float, float] | None:
        """Return the conventional comparison interval when standard-error input exists."""
        return self._interval_pair("ci_conv_lower", "ci_conv_upper")

    def reporting_summary(self) -> dict[str, object]:
        """Return the fields a reporting script usually needs first.

        The nested canonical namespace remains available for replay and
        Stata-facing exact fields. This compact view is for user reports,
        tables, and examples that need the decision, intervals, and simulation
        setting without navigating the replay-oriented structure.
        """
        scalars = self._scalars()
        macros = self._macros()
        pretest_pass = scalars.get("pretest_pass")
        data_valid = scalars.get("data_valid")
        if data_valid != 1:
            decision = "INVALID"
        elif pretest_pass == 1:
            decision = "PASS"
        elif pretest_pass == 0:
            decision = "FAIL"
        else:
            decision = "UNKNOWN"

        return {
            "mode": macros.get("mode"),
            "data_valid": data_valid,
            "decision": decision,
            "phi": scalars.get("phi"),
            "pretest_pass": pretest_pass,
            "S_pre": scalars.get("S_pre"),
            "threshold": scalars.get("threshold"),
            "delta_bar": scalars.get("delta_bar"),
            "conditional_interval": self.conditional_interval(),
            "conventional_interval": self.conventional_interval(),
            "f_alpha": scalars.get("f_alpha"),
            "simulations": scalars.get("sims"),
            "seed": scalars.get("seed"),
        }

    def _scalars(self) -> Mapping[str, object]:
        scalars = self.canonical.get("scalars")
        if not isinstance(scalars, Mapping):
            raise ValueError("canonical.scalars must be a mapping")
        return scalars

    def _macros(self) -> Mapping[str, object]:
        macros = self.canonical.get("macros")
        if not isinstance(macros, Mapping):
            raise ValueError("canonical.macros must be a mapping")
        return macros

    def __str__(self) -> str:
        return pretest_result_str(self)

    def _repr_html_(self) -> str:
        return pretest_result_html(self)

    def _interval_pair(self, lower_field: str, upper_field: str) -> tuple[float, float] | None:
        scalars = self._scalars()
        lower = scalars.get(lower_field)
        upper = scalars.get(upper_field)
        if lower is None and upper is None:
            return None
        if lower is None or upper is None:
            raise ValueError(f"{lower_field} and {upper_field} must be reported together")
        normalized_lower = _coerce_float(lower_field, lower)
        normalized_upper = _coerce_float(upper_field, upper)
        if not math.isfinite(normalized_lower) or not math.isfinite(normalized_upper):
            raise ValueError(f"{lower_field} and {upper_field} must be finite")
        if normalized_lower > normalized_upper:
            raise ValueError(f"{lower_field} must be <= {upper_field}")
        return (normalized_lower, normalized_upper)


def _string_list(values: Any) -> list[str]:
    if not isinstance(values, (list, tuple)):
        return []
    return [str(value) for value in values]


def _normalize_availability_field_names(label: str, values: Any) -> list[str]:
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{label} must be a sequence of field names")

    normalized: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label}[{index}] must be a non-empty string")
        if value != value.strip():
            raise ValueError(
                f"{label}[{index}] must not contain leading or trailing whitespace"
            )
        if value in seen:
            raise ValueError(f"{label} must not contain duplicate field names")
        normalized.append(value)
        seen.add(value)
    return normalized


def _append_unique(target: list[str], values: list[str]) -> None:
    seen = set(target)
    for value in values:
        if value in seen:
            continue
        target.append(value)
        seen.add(value)


def _stdout_field_names(values: Any, *, label: str) -> list[str]:
    names: list[str] = []
    for value in _normalize_availability_field_names(label, values):
        if value.startswith("e(") and value.endswith(")"):
            names.append(value[2:-1])
        else:
            names.append(value)
    return names


def _validate_stdout_replay_category_namespace(
    categories: Mapping[str, list[str]],
    *,
    label: str,
) -> None:
    for bucket, fields in categories.items():
        aliases = [
            field
            for field in fields
            if field.startswith("e(") and field.endswith(")")
        ]
        if aliases:
            joined_aliases = ", ".join(aliases)
            raise ValueError(
                f"{label} {bucket} must use stdout field names, not e() aliases: "
                f"{joined_aliases}"
            )


def _validation_case_id(snapshot: PretestResultSnapshot) -> str | None:
    validation = snapshot.diagnostics.get("validation")
    if not isinstance(validation, dict):
        return None

    case_id = validation.get("case_id")
    if case_id is None:
        return None
    if not isinstance(case_id, str):
        raise ValueError("validation.case_id must be a non-empty string")
    normalized = case_id.strip()
    if not normalized or normalized != case_id:
        raise ValueError("validation.case_id must be a non-empty string")
    return normalized


def _coerce_float(name: str, value: object) -> float:
    if isinstance(value, (str, bytes, bytearray, bool)):
        raise ValueError(f"{name} must be finite")
    try:
        return float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be finite") from exc


def _normalize_required_float(name: str, value: object) -> float:
    if value is None:
        raise ValueError(f"{name} is required")
    normalized = _coerce_float(name, value)
    if not math.isfinite(normalized):
        raise ValueError(f"{name} must be finite")
    return normalized


def _normalize_nonnegative_float(name: str, value: object) -> float:
    normalized = _normalize_required_float(name, value)
    if not math.isfinite(normalized):
        raise ValueError(f"{name} must be finite")
    if normalized < 0:
        raise ValueError(f"{name} must be nonnegative")
    return normalized


def _normalize_positive_float(name: str, value: object) -> float:
    normalized = _normalize_required_float(name, value)
    if not math.isfinite(normalized):
        raise ValueError(f"{name} must be finite")
    if normalized <= 0:
        raise ValueError(f"{name} must be positive")
    return normalized


def _normalize_optional_float(name: str, value: object) -> float | None:
    if value is None:
        return None
    normalized = _coerce_float(name, value)
    if not math.isfinite(normalized):
        raise ValueError(f"{name} must be finite")
    return normalized


def _normalize_optional_float_sequence(
    name: str,
    values: Sequence[object] | None,
) -> list[float] | None:
    if values is None:
        return None
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise ValueError(f"{name} must be a non-string sequence of numerics")
    normalized: list[float] = []
    for index, value in enumerate(values):
        if isinstance(value, (str, bytes, bytearray)):
            raise ValueError(f"{name}[{index}] must not be a string-backed numeric")
        if isinstance(value, bool):
            raise ValueError(f"{name}[{index}] must not be a boolean-backed numeric")
        normalized.append(_normalize_required_float(f"{name}[{index}]", value))
    return normalized


def _normalize_graph_label(
    name: str,
    value: object,
    *,
    allowed_values: tuple[str, ...],
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    if value != value.strip():
        raise ValueError(f"{name} must not contain leading or trailing whitespace")
    normalized = value.strip()
    if normalized not in allowed_values:
        allowed = ", ".join(allowed_values)
        raise ValueError(f"{name} must be one of: {allowed}")
    return normalized


def _normalize_graph_state(name: str, value: object) -> str:
    return _normalize_graph_label(
        name,
        value,
        allowed_values=_ALLOWED_GRAPH_STATES,
    )


def _normalize_replay_graph_status(name: str, value: object) -> str:
    return _normalize_graph_label(
        name,
        value,
        allowed_values=_ALLOWED_REPLAY_GRAPH_STATUSES,
    )


def _validate_graph_state_against_provenance(
    *,
    graph_state: str,
    nograph: bool,
) -> None:
    if graph_state == "suppressed" and not nograph:
        raise ValueError("suppressed graph_state requires nograph")
    if nograph and graph_state != "suppressed":
        raise ValueError("nograph cases must keep graph_state suppressed")


def _normalize_replay_categories(
    categories: object,
    *,
    label: str,
) -> dict[str, list[str]]:
    if not isinstance(categories, dict):
        raise ValueError(
            f"{label} replay categories are required before building a capture bundle"
        )

    normalized: dict[str, list[str]] = {}
    bucket_by_field: dict[str, str] = {}
    for category in _VERDICT_BUCKETS:
        values = categories.get(category)
        if not isinstance(values, list):
            raise ValueError(
                f"{label} replay categories must define {category} as a field list"
            )
        normalized_fields = _normalize_availability_field_names(
            f"{label} replay categories {category}",
            values,
        )
        if len(normalized_fields) != len(set(normalized_fields)):
            raise ValueError(
                f"{label} replay categories {category} must not contain duplicate field names"
            )
        for field in normalized_fields:
            existing_bucket = bucket_by_field.get(field)
            if existing_bucket is not None:
                raise ValueError(
                    f"{label} replay categories field appears in multiple verdict buckets: {field}"
                )
            bucket_by_field[field] = category
        normalized[category] = normalized_fields
    return normalized


def _normalize_exact_values(values: Mapping[str, object] | None) -> dict[str, object]:
    if values is None:
        return {}
    if not isinstance(values, Mapping):
        raise ValueError("exact_values must be a mapping")

    normalized: dict[str, object] = {}
    for key, value in values.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("exact_values keys must be non-empty strings")
        if key != key.strip():
            raise ValueError(
                "exact_values keys must not contain leading or trailing whitespace"
            )
        if any(character.isspace() for character in key):
            raise ValueError(
                "exact_values keys must not contain whitespace or empty e() aliases"
            )
        contains_parentheses = "(" in key or ")" in key
        if contains_parentheses:
            if not (key.startswith("e(") and key.endswith(")")):
                raise ValueError(
                    "exact_values keys with parentheses must be well-formed e() aliases"
                )
            bare_key = key[2:-1]
            if not bare_key:
                raise ValueError(
                    "exact_values keys must not contain whitespace or empty e() aliases"
                )
            if "(" in bare_key or ")" in bare_key:
                raise ValueError(
                    "exact_values keys with parentheses must be well-formed e() aliases"
                )
        normalized[key] = value

    for key, value in list(normalized.items()):
        if key.startswith("e(") and key.endswith(")"):
            bare_key = key[2:-1]
            if bare_key in normalized and normalized[bare_key] != value:
                raise ValueError(f"conflicting replay exact alias: {bare_key}")
            normalized.setdefault(bare_key, value)
    return normalized


def _normalize_binary_state(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be 0 or 1")
    normalized = int(value)
    if normalized not in {0, 1}:
        raise ValueError(f"{name} must be 0 or 1")
    return normalized


def _normalize_exact_metadata_integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer")
    return int(value)


def _normalize_replay_exact_numeric_value(name: str, value: object) -> int | float:
    label = _REPLAY_NUMERIC_FIELD_LABELS.get(name, name)
    if name in _INTEGER_EXACT_REPLAY_FIELDS:
        if isinstance(value, bool) or not isinstance(value, Integral):
            raise ValueError(f"{label} must be an integer")
        return int(value)
    if isinstance(value, (str, bytes, bytearray, bool)):
        raise ValueError(f"{label} must be finite")
    normalized = _normalize_required_float(label, value)
    return normalized


def _normalize_availability_flag(name: str, value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _normalize_mapping_container(
    name: str,
    value: object,
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    return value


def _normalize_provenance_nograph(snapshot: PretestResultSnapshot) -> bool:
    provenance = _normalize_mapping_container("provenance", snapshot.provenance)
    return _normalize_availability_flag(
        "provenance.nograph",
        provenance.get("nograph", False),
    )


def _validate_exact_metadata_overrides(
    snapshot: PretestResultSnapshot,
    *,
    exact_values: dict[str, object],
) -> None:
    provenance = _normalize_mapping_container("provenance", snapshot.provenance)
    expected_values: dict[str, object] = {
        "cmd": provenance.get("cmd"),
        "cmdline": provenance.get("cmdline"),
        "depvar": snapshot.canonical["macros"].get("depvar"),
        "outcome": snapshot.canonical["macros"].get("outcome"),
        "treatment": snapshot.canonical["macros"].get("treatment"),
        "time": snapshot.canonical["macros"].get("time"),
        "title": snapshot.canonical["macros"].get("title"),
        "mode": snapshot.canonical["macros"].get("mode"),
        "data_valid": snapshot.canonical["scalars"].get("data_valid"),
        "sims": snapshot.canonical["scalars"].get("sims"),
        "seed": snapshot.canonical["scalars"].get("seed"),
    }

    cluster = snapshot.canonical["macros"].get("cluster")
    clustvar = snapshot.canonical["macros"].get("clustvar")
    if cluster not in (None, ""):
        expected_values["cluster"] = cluster
    if clustvar not in (None, ""):
        expected_values["clustvar"] = clustvar

    for field, expected in expected_values.items():
        if field not in exact_values or expected is None:
            continue

        actual = exact_values[field]
        if field == "data_valid":
            actual = _normalize_binary_state(field, actual)
            expected = _normalize_binary_state(field, expected)
        elif field in {"seed", "sims"}:
            actual = _normalize_exact_metadata_integer(field, actual)
            expected = _normalize_exact_metadata_integer(field, expected)
        else:
            actual = str(actual)
            expected = str(expected)

        if actual != expected:
            raise ValueError(f"conflicting replay exact metadata: {field}")


def _expected_exact_metadata_fields(snapshot: PretestResultSnapshot) -> set[str]:
    fields = {
        "cmd",
        "cmdline",
        "depvar",
        "outcome",
        "treatment",
        "time",
        "title",
        "mode",
        "data_valid",
        "sims",
        "seed",
    }

    cluster = snapshot.canonical["macros"].get("cluster")
    clustvar = snapshot.canonical["macros"].get("clustvar")
    if cluster not in (None, ""):
        fields.add("cluster")
    if clustvar not in (None, ""):
        fields.add("clustvar")
    return fields


def _validate_exact_input_fields(
    snapshot: PretestResultSnapshot,
    *,
    raw_exact_values: Mapping[str, object] | None,
    stored_results_categories: dict[str, list[str]],
) -> None:
    if raw_exact_values is None:
        return

    allowed_fields = _expected_exact_metadata_fields(snapshot)
    for category in ("exact", "unresolved"):
        for field in stored_results_categories[category]:
            if field.startswith("e(") and field.endswith(")"):
                allowed_fields.add(field[2:-1])
            else:
                allowed_fields.add(field)

    allowed_keys = allowed_fields | {f"e({field})" for field in allowed_fields}
    unexpected_fields = sorted(
        key for key in raw_exact_values if isinstance(key, str) and key not in allowed_keys
    )
    if unexpected_fields:
        raise ValueError(
            "unexpected replay exact fields: " + ", ".join(unexpected_fields)
        )


def _validate_protected_auxiliary_outputs_excluded(
    snapshot: PretestResultSnapshot,
    *,
    categories: dict[str, list[str]],
    label: str,
) -> None:
    oracle = _normalize_mapping_container("oracle", snapshot.oracle)
    protected_outputs = oracle.get("protected_auxiliary_outputs", ())
    normalized_protected_outputs = _normalize_availability_field_names(
        "oracle.protected_auxiliary_outputs",
        protected_outputs,
    )
    if not normalized_protected_outputs:
        return

    protected_output_set: set[str] = set()
    for field in normalized_protected_outputs:
        protected_output_set.add(field)
        if field.startswith("e(") and field.endswith(")"):
            protected_output_set.add(field[2:-1])
    for fields in categories.values():
        for field in fields:
            if field in protected_output_set:
                raise ValueError(
                    f"{label} replay categories must keep protected auxiliary "
                    f"outputs excluded: {field}"
                )


def _resolve_pretest_result_state(
    snapshot: PretestResultSnapshot,
    *,
    exact_values: dict[str, object],
) -> str:
    raw_phi = exact_values.get("phi")
    raw_pretest_pass = exact_values.get("pretest_pass")
    canonical_phi = snapshot.canonical["scalars"].get("phi")
    canonical_pretest_pass = snapshot.canonical["scalars"].get("pretest_pass")

    if raw_phi is None and raw_pretest_pass is None:
        if canonical_phi is None and canonical_pretest_pass is None:
            raise ValueError("missing replay exact field: pretest_result")
        if canonical_phi is None:
            normalized_pretest_pass = _normalize_binary_state(
                "pretest_pass",
                canonical_pretest_pass,
            )
            return "PASS" if normalized_pretest_pass == 1 else "FAIL"

        normalized_phi = _normalize_binary_state("phi", canonical_phi)
        normalized_pretest_pass = 1 - normalized_phi
        if canonical_pretest_pass is not None:
            explicit_pretest_pass = _normalize_binary_state(
                "pretest_pass",
                canonical_pretest_pass,
            )
            if explicit_pretest_pass != normalized_pretest_pass:
                raise ValueError("conflicting replay exact state: phi vs pretest_pass")
            normalized_pretest_pass = explicit_pretest_pass

        return "PASS" if normalized_pretest_pass == 1 else "FAIL"

    if raw_phi is None:
        normalized_pretest_pass = _normalize_binary_state(
            "pretest_pass",
            raw_pretest_pass,
        )
        if canonical_phi is not None:
            normalized_canonical_phi = _normalize_binary_state("phi", canonical_phi)
            if normalized_pretest_pass != 1 - normalized_canonical_phi:
                raise ValueError("conflicting replay exact state: phi vs pretest_pass")
        return "PASS" if normalized_pretest_pass == 1 else "FAIL"

    normalized_phi = _normalize_binary_state("phi", raw_phi)
    normalized_pretest_pass = 1 - normalized_phi
    if raw_pretest_pass is not None:
        explicit_pretest_pass = _normalize_binary_state(
            "pretest_pass",
            raw_pretest_pass,
        )
        if explicit_pretest_pass != normalized_pretest_pass:
            raise ValueError("conflicting replay exact state: phi vs pretest_pass")
        normalized_pretest_pass = explicit_pretest_pass
    elif canonical_pretest_pass is not None:
        explicit_pretest_pass = _normalize_binary_state(
            "pretest_pass",
            canonical_pretest_pass,
        )
        if explicit_pretest_pass != normalized_pretest_pass:
            raise ValueError("conflicting replay exact state: phi vs pretest_pass")
        normalized_pretest_pass = explicit_pretest_pass

    return "PASS" if normalized_pretest_pass == 1 else "FAIL"


def _resolve_replay_capture_value(
    snapshot: PretestResultSnapshot,
    field: str,
    *,
    exact_values: dict[str, object],
    category: str,
) -> object:
    if field == "pretest_result":
        return _resolve_pretest_result_state(
            snapshot,
            exact_values=exact_values,
        )

    field_name = field
    if field == "severity":
        field_name = "S_pre"
    elif field == "critical_value":
        field_name = "f_alpha"
    elif field.startswith("e(") and field.endswith(")"):
        field_name = field[2:-1]

    if category in {"exact", "unresolved"} and field_name in exact_values:
        if field_name in {"data_valid", "phi", "pretest_pass"}:
            return _normalize_binary_state(field_name, exact_values[field_name])
        if field_name in _NUMERIC_EXACT_REPLAY_FIELDS:
            return _normalize_replay_exact_numeric_value(
                field_name,
                exact_values[field_name],
            )
        return exact_values[field_name]

    scalar_value = snapshot.canonical["scalars"].get(field_name)
    if scalar_value is not None:
        if field_name in {"data_valid", "phi", "pretest_pass"}:
            return _normalize_binary_state(field_name, scalar_value)
        if field_name in _NUMERIC_EXACT_REPLAY_FIELDS:
            return _normalize_replay_exact_numeric_value(field_name, scalar_value)
        return scalar_value

    macro_value = snapshot.canonical["macros"].get(field_name)
    if macro_value is not None:
        return macro_value

    if field_name in exact_values:
        return exact_values[field_name]

    raise ValueError(f"missing replay {category} field: {field}")


def _build_bucketed_capture_payload(
    snapshot: PretestResultSnapshot,
    categories: dict[str, list[str]],
    *,
    exact_values: dict[str, object],
) -> dict[str, object]:
    payload: dict[str, object] = {
        "exact_absence": list(categories["exact_absence"]),
    }
    for category in ("exact", "display_rounded", "unresolved"):
        payload[category] = {
            field: _resolve_replay_capture_value(
                snapshot,
                field,
                exact_values=exact_values,
                category=category,
            )
            for field in categories[category]
        }
    return payload


def _resolve_interval_pair(
    *,
    label: str,
    available: bool,
    lower: object,
    upper: object,
) -> tuple[float | None, float | None]:
    normalized_lower = _normalize_optional_float(f"{label} lower", lower)
    normalized_upper = _normalize_optional_float(f"{label} upper", upper)
    if available:
        if normalized_lower is None or normalized_upper is None:
            raise ValueError(f"{label} values are required when the {label} gate is open")
        if normalized_lower > normalized_upper:
            raise ValueError(f"{label} lower must be <= {label} upper")
        return normalized_lower, normalized_upper

    if normalized_lower is not None or normalized_upper is not None:
        raise ValueError(
            f"{label} values must be omitted when the {label} gate is closed"
        )
    return None, None


def _validate_ci_category_fields(
    *,
    contract_label: str,
    display_label: str,
    exact_absence_label: str,
    available: bool,
    display_fields: object,
    exact_absence_fields: object,
    expected_fields: list[str],
) -> None:
    normalized_display_fields = _normalize_availability_field_names(
        display_label,
        display_fields,
    )
    normalized_exact_absence_fields = _normalize_availability_field_names(
        exact_absence_label,
        exact_absence_fields,
    )
    expected_display_fields = expected_fields if available else []
    expected_exact_absence_fields = [] if available else expected_fields
    if (
        normalized_display_fields != expected_display_fields
        or normalized_exact_absence_fields != expected_exact_absence_fields
    ):
        raise ValueError(f"{contract_label} category fields must match availability gate")


def _validate_stdout_ci_category_fields(
    *,
    contract_label: str,
    display_label: str,
    exact_absence_label: str,
    available: bool,
    display_fields: object,
    exact_absence_fields: object,
    expected_fields: list[str],
) -> None:
    normalized_display_fields = _stdout_field_names(
        display_fields,
        label=display_label,
    )
    normalized_exact_absence_fields = _stdout_field_names(
        exact_absence_fields,
        label=exact_absence_label,
    )
    expected_display_fields = expected_fields if available else []
    expected_exact_absence_fields = [] if available else expected_fields
    if (
        normalized_display_fields != expected_display_fields
        or normalized_exact_absence_fields != expected_exact_absence_fields
    ):
        raise ValueError(f"{contract_label} category fields must match availability gate")


def resolve_stored_results_categories(
    snapshot: PretestResultSnapshot,
    availability: Any,
) -> dict[str, list[str]]:
    mode = str(snapshot.canonical["macros"]["mode"])
    has_cluster = snapshot.canonical["macros"].get("cluster") not in (None, "")
    conditional_available = _normalize_availability_flag(
        "conditional_available",
        getattr(availability, "conditional_available", False),
    )
    conventional_available = _normalize_availability_flag(
        "conventional_available",
        getattr(availability, "conventional_available", False),
    )
    variance_available = _normalize_availability_flag(
        "variance_available",
        getattr(availability, "variance_available", True),
    )
    _validate_ci_category_fields(
        contract_label="conditional CI",
        display_label="conditional_display_rounded",
        exact_absence_label="conditional_exact_absence",
        available=conditional_available,
        display_fields=getattr(availability, "conditional_display_rounded", ()),
        exact_absence_fields=getattr(availability, "conditional_exact_absence", ()),
        expected_fields=_CONDITIONAL_CI_FIELDS,
    )
    _validate_ci_category_fields(
        contract_label="conventional CI",
        display_label="conventional_display_rounded",
        exact_absence_label="conventional_exact_absence",
        available=conventional_available,
        display_fields=getattr(availability, "conventional_display_rounded", ()),
        exact_absence_fields=getattr(availability, "conventional_exact_absence", ()),
        expected_fields=_CONVENTIONAL_CI_FIELDS,
    )
    validation = snapshot.diagnostics.get("validation")
    if (
        mode == "overall"
        and isinstance(validation, dict)
        and validation.get("case_id") == _BLOCKED_OVERALL_CAPTURE_CASE
    ):
        exact: list[str] = []
        if has_cluster:
            _append_unique(exact, _OPTIONAL_CLUSTER_METADATA)
        unresolved = list(_STORED_RESULTS_EXACT_AUTHORITATIVE)
        unresolved.extend(["e(S_pre)", "e(kappa)", "e(f_alpha)", "e(delta_bar)"])
        unresolved.extend(
            _normalize_availability_field_names(
                "conditional_display_rounded",
                getattr(availability, "conditional_display_rounded", ()),
            )
        )
        unresolved.extend(
            _normalize_availability_field_names(
                "conventional_display_rounded",
                getattr(availability, "conventional_display_rounded", ()),
            )
        )
        return {
            "exact": exact,
            "display_rounded": [],
            "exact_absence": [],
            "unresolved": unresolved,
        }

    display_rounded = list(_STORED_RESULTS_DISPLAY_ROUNDED_BASE)

    _append_unique(
        display_rounded,
        _normalize_availability_field_names(
            "conditional_display_rounded",
            getattr(availability, "conditional_display_rounded", ()),
        ),
    )
    _append_unique(
        display_rounded,
        _normalize_availability_field_names(
            "conventional_display_rounded",
            getattr(availability, "conventional_display_rounded", ()),
        ),
    )

    exact_absence: list[str] = []
    _append_unique(
        exact_absence,
        _normalize_availability_field_names(
            "conditional_exact_absence",
            getattr(availability, "conditional_exact_absence", ()),
        ),
    )
    _append_unique(
        exact_absence,
        _normalize_availability_field_names(
            "conventional_exact_absence",
            getattr(availability, "conventional_exact_absence", ()),
        ),
    )

    exact = list(_STORED_RESULTS_EXACT_AUTHORITATIVE)
    if not variance_available:
        exact = [field for field in exact if field != "e(se_delta_bar)"]
        _append_unique(exact_absence, ["e(se_delta_bar)"])
    if has_cluster:
        _append_unique(exact, _OPTIONAL_CLUSTER_METADATA)

    return {
        "exact": exact,
        "display_rounded": display_rounded,
        "exact_absence": exact_absence,
        "unresolved": [],
    }


def resolve_stdout_categories(
    snapshot: PretestResultSnapshot,
    availability: Any,
) -> dict[str, list[str]]:
    mode = str(snapshot.canonical["macros"]["mode"])
    case_id = _validation_case_id(snapshot)
    conditional_available = _normalize_availability_flag(
        "conditional_available",
        getattr(availability, "conditional_available", False),
    )
    conventional_available = _normalize_availability_flag(
        "conventional_available",
        getattr(availability, "conventional_available", False),
    )
    _normalize_availability_flag(
        "variance_available",
        getattr(availability, "variance_available", True),
    )
    _validate_stdout_ci_category_fields(
        contract_label="conditional CI",
        display_label="conditional_display_rounded",
        exact_absence_label="conditional_exact_absence",
        available=conditional_available,
        display_fields=getattr(availability, "conditional_display_rounded", ()),
        exact_absence_fields=getattr(availability, "conditional_exact_absence", ()),
        expected_fields=_STDOUT_CONDITIONAL_CI_FIELDS,
    )
    _validate_stdout_ci_category_fields(
        contract_label="conventional CI",
        display_label="conventional_display_rounded",
        exact_absence_label="conventional_exact_absence",
        available=conventional_available,
        display_fields=getattr(availability, "conventional_display_rounded", ()),
        exact_absence_fields=getattr(availability, "conventional_exact_absence", ()),
        expected_fields=_STDOUT_CONVENTIONAL_CI_FIELDS,
    )
    if mode == "overall" and case_id == _BLOCKED_OVERALL_CAPTURE_CASE:
        unresolved = list(_STDOUT_EXACT)
        unresolved.extend(_STDOUT_DISPLAY_ROUNDED_BASE)
        unresolved.extend(
            _stdout_field_names(
                getattr(availability, "conditional_display_rounded", ()),
                label="conditional_display_rounded",
            )
        )
        unresolved.extend(
            _stdout_field_names(
                getattr(availability, "conventional_display_rounded", ()),
                label="conventional_display_rounded",
            )
        )
        return {
            "exact": [],
            "display_rounded": [],
            "exact_absence": [],
            "unresolved": unresolved,
        }

    display_rounded = list(_STDOUT_DISPLAY_ROUNDED_BASE)
    _append_unique(
        display_rounded,
        _stdout_field_names(
            getattr(availability, "conditional_display_rounded", ()),
            label="conditional_display_rounded",
        ),
    )
    _append_unique(
        display_rounded,
        _stdout_field_names(
            getattr(availability, "conventional_display_rounded", ()),
            label="conventional_display_rounded",
        ),
    )

    exact_absence: list[str] = []
    _append_unique(
        exact_absence,
        _stdout_field_names(
            getattr(availability, "conditional_exact_absence", ()),
            label="conditional_exact_absence",
        ),
    )
    _append_unique(
        exact_absence,
        _stdout_field_names(
            getattr(availability, "conventional_exact_absence", ()),
            label="conventional_exact_absence",
        ),
    )

    return {
        "exact": list(_STDOUT_EXACT),
        "display_rounded": display_rounded,
        "exact_absence": exact_absence,
        "unresolved": [],
    }


def resolve_replay_graph_status(snapshot: PretestResultSnapshot) -> str:
    case_id = _validation_case_id(snapshot)
    nograph = _normalize_provenance_nograph(snapshot)
    graph_status = _normalize_mapping_container("graph_status", snapshot.graph_status)
    graph_state = _normalize_graph_state(
        "graph_status.state",
        graph_status.get("state", "pending-implementation"),
    )
    _validate_graph_state_against_provenance(
        graph_state=graph_state,
        nograph=nograph,
    )
    if case_id == _BLOCKED_OVERALL_CAPTURE_CASE:
        return "blocked-pending-oracle"
    if graph_state == "suppressed":
        return "suppressed-by-nograph"
    if graph_state == "graph-exported":
        return "graph-exported"
    return "graph-attempted-but-error-198"


def apply_kernel_outputs(
    snapshot: PretestResultSnapshot,
    *,
    availability: Any,
    s_pre: float,
    kappa: float,
    f_alpha: float,
    delta_bar: float,
    ci_lower: float | None = None,
    ci_upper: float | None = None,
    ci_conv_lower: float | None = None,
    ci_conv_upper: float | None = None,
    se_delta_bar: float | None = None,
    s_pre_se: float | None = None,
    theta: Sequence[float] | None = None,
    graph_state: str | None = None,
) -> PretestResultSnapshot:
    normalized_data_valid = _normalize_binary_state(
        "data_valid",
        snapshot.canonical["scalars"].get("data_valid"),
    )
    if normalized_data_valid != 1:
        raise ValueError("kernel outputs require data_valid = 1")

    normalized_s_pre = _normalize_nonnegative_float("s_pre", s_pre)
    threshold = _normalize_required_float(
        "threshold",
        snapshot.canonical["scalars"].get("threshold"),
    )
    expected_phi = int(normalized_s_pre > threshold)
    expected_pretest_pass = 1 - expected_phi
    observed_phi = snapshot.canonical["scalars"].get("phi")
    observed_pretest_pass = snapshot.canonical["scalars"].get("pretest_pass")
    if observed_phi is None or observed_pretest_pass is None:
        raise ValueError("kernel outputs require classified phi and pretest_pass state")
    normalized_observed_phi = _normalize_binary_state("phi", observed_phi)
    normalized_observed_pretest_pass = _normalize_binary_state(
        "pretest_pass",
        observed_pretest_pass,
    )
    if (
        normalized_observed_phi != expected_phi
        or normalized_observed_pretest_pass != expected_pretest_pass
    ):
        raise ValueError("kernel outputs must preserve the severity pass boundary")

    conditional_available = _normalize_availability_flag(
        "conditional_available",
        getattr(availability, "conditional_available", False),
    )
    conventional_available = _normalize_availability_flag(
        "conventional_available",
        getattr(availability, "conventional_available", False),
    )
    variance_available = _normalize_availability_flag(
        "variance_available",
        getattr(availability, "variance_available", True),
    )
    expected_conditional_available = normalized_observed_pretest_pass == 1
    if conditional_available != expected_conditional_available:
        raise ValueError("conditional CI availability must match validation state")
    expected_conventional_available = (
        snapshot.canonical["scalars"].get("data_valid") == 1
    ) and variance_available
    if conventional_available != expected_conventional_available:
        raise ValueError("conventional CI availability must match validation state")
    _validate_ci_category_fields(
        contract_label="conditional CI",
        display_label="conditional_display_rounded",
        exact_absence_label="conditional_exact_absence",
        available=conditional_available,
        display_fields=getattr(availability, "conditional_display_rounded", ()),
        exact_absence_fields=getattr(availability, "conditional_exact_absence", ()),
        expected_fields=_CONDITIONAL_CI_FIELDS,
    )
    _validate_ci_category_fields(
        contract_label="conventional CI",
        display_label="conventional_display_rounded",
        exact_absence_label="conventional_exact_absence",
        available=conventional_available,
        display_fields=getattr(availability, "conventional_display_rounded", ()),
        exact_absence_fields=getattr(availability, "conventional_exact_absence", ()),
        expected_fields=_CONVENTIONAL_CI_FIELDS,
    )

    conditional_pair = _resolve_interval_pair(
        label="conditional CI",
        available=conditional_available,
        lower=ci_lower,
        upper=ci_upper,
    )
    conventional_pair = _resolve_interval_pair(
        label="conventional CI",
        available=conventional_available,
        lower=ci_conv_lower,
        upper=ci_conv_upper,
    )
    mode = str(snapshot.canonical["macros"]["mode"])
    if mode == "overall":
        normalized_kappa = _normalize_required_float("kappa", kappa)
        if not math.isclose(
            normalized_kappa,
            1.0,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("overall mode requires kappa = 1")
    else:
        normalized_kappa = _normalize_positive_float("kappa", kappa)

    canonical = {
        "scalars": dict(snapshot.canonical["scalars"]),
        "macros": dict(snapshot.canonical["macros"]),
        "matrices": dict(snapshot.canonical["matrices"]),
    }
    canonical["scalars"]["S_pre"] = normalized_s_pre
    canonical["scalars"]["kappa"] = normalized_kappa
    canonical["scalars"]["f_alpha"] = _normalize_nonnegative_float("f_alpha", f_alpha)
    canonical["scalars"]["delta_bar"] = _normalize_required_float("delta_bar", delta_bar)
    canonical["scalars"]["ci_lower"] = conditional_pair[0]
    canonical["scalars"]["ci_upper"] = conditional_pair[1]
    canonical["scalars"]["ci_conv_lower"] = conventional_pair[0]
    canonical["scalars"]["ci_conv_upper"] = conventional_pair[1]
    canonical["scalars"]["se_delta_bar"] = _normalize_optional_float(
        "se_delta_bar",
        se_delta_bar,
    )
    canonical["scalars"]["S_pre_se"] = _normalize_optional_float("S_pre_se", s_pre_se)
    canonical["matrices"]["theta"] = _normalize_optional_float_sequence("theta", theta)

    replay_contract = dict(snapshot.replay_contract)
    graph_status = dict(
        _normalize_mapping_container("graph_status", snapshot.graph_status)
    )
    nograph = _normalize_provenance_nograph(snapshot)
    existing_graph_state = _normalize_graph_state(
        "graph_status.state",
        graph_status.get("state", "pending-implementation"),
    )
    if graph_state is not None:
        requested_graph_state = _normalize_graph_state("graph_state", graph_state)
        if (
            existing_graph_state == "suppressed"
            and requested_graph_state != "suppressed"
        ):
            raise ValueError("nograph cases must keep graph_state suppressed")
        if (
            requested_graph_state == "suppressed"
            and existing_graph_state != "suppressed"
            and not nograph
        ):
            raise ValueError("suppressed graph_state requires nograph")
        graph_status["state"] = requested_graph_state

    staged_snapshot = PretestResultSnapshot(
        provenance=dict(snapshot.provenance),
        canonical=canonical,
        compatibility=dict(snapshot.compatibility),
        replay_contract=replay_contract,
        graph_status=graph_status,
        oracle=dict(snapshot.oracle),
        diagnostics=dict(snapshot.diagnostics),
    )

    replay_contract["stored_results_categories"] = resolve_stored_results_categories(
        staged_snapshot,
        availability,
    )
    replay_contract["stdout_categories"] = resolve_stdout_categories(
        staged_snapshot,
        availability,
    )
    graph_status["replay_verdict"] = resolve_replay_graph_status(staged_snapshot)

    return PretestResultSnapshot(
        provenance=dict(snapshot.provenance),
        canonical=canonical,
        compatibility=dict(snapshot.compatibility),
        replay_contract=replay_contract,
        graph_status=graph_status,
        oracle=dict(snapshot.oracle),
        diagnostics=dict(snapshot.diagnostics),
    )


def build_replay_capture_bundle(
    snapshot: PretestResultSnapshot,
    *,
    exact_values: dict[str, object] | None = None,
) -> dict[str, object]:
    raw_exact_values = exact_values if isinstance(exact_values, Mapping) else None
    exact_payload = _normalize_exact_values(exact_values)
    has_cluster = snapshot.canonical["macros"].get("cluster") not in (None, "")
    if not has_cluster and {"cluster", "clustvar"} & set(exact_payload):
        raise ValueError(
            "cluster exact values are not allowed when cluster() is absent"
        )
    _validate_exact_metadata_overrides(
        snapshot,
        exact_values=exact_payload,
    )
    stdout_categories = _normalize_replay_categories(
        snapshot.replay_contract.get("stdout_categories"),
        label="stdout",
    )
    _validate_stdout_replay_category_namespace(
        stdout_categories,
        label="stdout replay categories",
    )
    _validate_protected_auxiliary_outputs_excluded(
        snapshot,
        categories=stdout_categories,
        label="stdout",
    )
    stored_results_categories = _normalize_replay_categories(
        snapshot.replay_contract.get("stored_results_categories"),
        label="stored-results",
    )
    _validate_protected_auxiliary_outputs_excluded(
        snapshot,
        categories=stored_results_categories,
        label="stored-results",
    )
    _validate_exact_input_fields(
        snapshot,
        raw_exact_values=raw_exact_values,
        stored_results_categories=stored_results_categories,
    )
    resolved_graph_status = resolve_replay_graph_status(snapshot)
    graph_status_payload = _normalize_mapping_container(
        "graph_status",
        snapshot.graph_status,
    )
    graph_status = graph_status_payload.get("replay_verdict")
    if graph_status in (None, ""):
        graph_status = resolved_graph_status
    else:
        graph_status = _normalize_replay_graph_status(
            "graph_status.replay_verdict",
            graph_status,
        )
        if graph_status != resolved_graph_status:
            raise ValueError(
                "graph_status.replay_verdict must match the replay graph status "
                "resolved from provenance and graph_status.state"
            )
    graph_status = _normalize_replay_graph_status(
        "graph_status.replay_verdict",
        graph_status,
    )

    return {
        "stdout": _build_bucketed_capture_payload(
            snapshot,
            stdout_categories,
            exact_values=exact_payload,
        ),
        "stored_results": _build_bucketed_capture_payload(
            snapshot,
            stored_results_categories,
            exact_values=exact_payload,
        ),
        "graph_status": str(graph_status),
    }


def seed_result_snapshot(spec: PretestCommandSpec) -> PretestResultSnapshot:
    graph_state = "suppressed" if spec.nograph else "pending-implementation"
    authoritative_results = [
        "e(N)",
        "e(T)",
        "e(T_pre)",
        "e(T_post)",
        "e(data_valid)",
        "e(phi)",
        "e(pretest_pass)",
        "e(mode)",
        "e(S_pre)",
        "e(kappa)",
        "e(f_alpha)",
        "e(delta_bar)",
        "e(ci_lower)",
        "e(ci_upper)",
        "e(ci_conv_lower)",
        "e(ci_conv_upper)",
    ]
    _append_unique(authoritative_results, _STORED_RESULTS_CONTRACT_SCALARS)
    _append_unique(authoritative_results, _STORED_RESULTS_METADATA)
    if spec.cluster:
        _append_unique(authoritative_results, _OPTIONAL_CLUSTER_METADATA)
    protected_outputs: list[str] = []
    if spec.mode == "iterative":
        authoritative_results.extend(_PROTECTED_OVERALL_OUTPUTS)
    else:
        protected_outputs = list(_PROTECTED_OVERALL_OUTPUTS)

    canonical = {
        "scalars": {
            "T": None,
            "t0": None,
            "T_pre": None,
            "T_post": None,
            "N": None,
            "n": None,
            "is_panel": None,
            "p": spec.p,
            "alpha": spec.alpha,
            "level": spec.level,
            "M": spec.threshold,
            "threshold": spec.threshold,
            "S_pre": None,
            "S_pre_se": None,
            "kappa": None,
            "f_alpha": None,
            "phi": None,
            "pretest_pass": None,
            "data_valid": None,
            "delta_bar": None,
            "se_delta_bar": None,
            "ci_lower": None,
            "ci_upper": None,
            "ci_conv_lower": None,
            "ci_conv_upper": None,
            "sims": spec.simulate,
            "seed": spec.seed,
        },
        "macros": {
            "cmd": spec.cmd,
            "cmdline": spec.cmdline,
            "depvar": spec.outcome,
            "outcome": spec.outcome,
            "treatment": spec.treatment,
            "time": spec.time,
            "mode": spec.mode,
            "cluster": spec.cluster,
            "clustvar": spec.cluster,
            "title": "Conditional Extrapolation Pre-Test",
        },
        "matrices": {
            "nu": None,
            "delta": None,
            "theta": None,
        },
    }
    compatibility = {
        "aliases": {
            "ATT": {
                "maps_to": "delta_bar",
                "kind": "compatibility-only",
            },
            "e(ATT)": {
                "maps_to": "e(delta_bar)",
                "kind": "compatibility-only",
            },
            "e(b)": {
                "maps_to": "delta_bar",
                "kind": "compatibility-only",
            },
            "e(V)": {
                "maps_to": "se_delta_bar^2",
                "kind": "compatibility-only",
            },
        }
    }
    replay_contract = {
        "verdict_buckets": list(_VERDICT_BUCKETS),
        "graph_status_field": "graph_status",
        "mode_specific_boundary": spec.mode,
    }
    graph_status = {
        "state": graph_state,
        "separate_from_numeric_verdicts": True,
    }
    oracle = {
        "authoritative_stata_results": authoritative_results,
        "protected_auxiliary_outputs": protected_outputs,
        "conditional_ci_gate": {
            "gate_fields": ["data_valid", "pretest_pass"],
            "otherwise": {
                "exact_absence": list(_CONDITIONAL_CI_EXACT_ABSENCE),
            },
        },
    }
    diagnostics = {
        "staged_only_fields": ["e(nu)", "e(delta)", "e(Sigma)"],
        "replay_provenance_hooks": [
            "cmd",
            "cmdline",
            "mode",
            "graph_status",
            "depvar",
            "threshold",
            "treat_time",
            "cluster",
            "overall",
            "nograph",
            "simulate",
            "seed",
            "diagnose",
        ],
    }

    return PretestResultSnapshot(
        provenance={
            "cmd": spec.cmd,
            "cmdline": spec.cmdline,
            "mode": spec.mode,
            "depvar": spec.outcome,
            "threshold": spec.threshold,
            "treat_time": spec.treat_time,
            "cluster": spec.cluster,
            "overall": spec.overall,
            "nograph": spec.nograph,
            "simulate": spec.simulate,
            "seed": spec.seed,
            "diagnose": spec.diagnose,
        },
        canonical=canonical,
        compatibility=compatibility,
        replay_contract=replay_contract,
        graph_status=graph_status,
        oracle=oracle,
        diagnostics=diagnostics,
    )
