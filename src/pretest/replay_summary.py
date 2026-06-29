from __future__ import annotations

from copy import deepcopy
from collections.abc import Mapping
import hashlib
import math
from pathlib import Path
from statistics import NormalDist

from .api import _normalize_boolean_flag, parse_stata_command
from .confidence_intervals import resolve_ci_availability
from .result_schema import (
    apply_kernel_outputs,
    build_replay_capture_bundle,
    seed_result_snapshot,
)
from .replay_harness import (
    _CANONICAL_STORY_PACKET_ARTIFACT_PATH_FIELDS,
    _bundled_prop99_story_packet_scaffold_artifact_paths,
    _capture_status_value,
    _validate_existing_artifact_paths,
    _validate_capture_ready_overall_bundle_metadata,
    _validate_story_packet_artifact_paths_against_documents,
    materialize_replay_summary,
)
from .replay_packets import load_case_payloads, load_replay_yaml
from .validation import ValidationState, apply_validation_outcome

_EXPECTED_APPENDIX_C_AUTHORITY_MARKERS = [
    "phi^Delta = 0",
    "S_pre_hat^Delta <= M",
    "kappa-free",
]
_EXPECTED_APPENDIX_C_PAPER_REFS = [
    "paper/pretest_paper.md",
    "paper/pretest_paper_cn.md",
]
_EXPECTED_APPENDIX_C_BRIDGE_MARKERS = [
    "nu_bar = A * nu",
    "theta^Delta / Sigma^Delta",
]
_EXPECTED_PROTECTED_NON_AUTHORITATIVE = [
    "e(theta)",
    "e(S_pre_se)",
]
_EXPECTED_DIAGNOSTIC_REQUIRED_MODE = "overall"
_EXPECTED_DIAGNOSTIC_REQUIRED_EXACT_FIELDS = [
    "e(mode)",
    "e(T_pre)",
    "e(T_post)",
]
_EXPECTED_DIAGNOSTIC_SAFE_INPUTS = [
    "e(nu)",
    "e(delta)",
    "e(Sigma)",
]
_EXPECTED_COMPATIBILITY_ALIAS_PLAN = {
    "contract_ref": "pretest_stored_results_contract.yaml#compatibility_hazards.stata-att-alias-drift",
    "bug_log_id": "BUG-SC-001",
    "scalar_aliases": ["e(ATT)"],
    "matrix_aliases": ["e(b)", "e(V)"],
    "maps_to": {
        "e(ATT)": "e(delta_bar)",
        "e(b)": "delta_bar",
        "e(V)": "se_delta_bar^2",
    },
    "never_promote": ["e(ATT)", "e(b)", "e(V)"],
}
_EXPECTED_AUXILIARY_EXACT_DIMENSIONS = {
    "T_pre_minus_1": 3,
    "T_post": 7,
    "theta_delta_length": 10,
    "sigma_delta_shape": [10, 10],
    "pre_block_operator_shape": [3, 3],
}
_SPLIT_CAPTURE_IDENTITY_ERROR_MARKERS = (
    ".case_id ",
    ".producer must equal ",
    ".capture_kind must equal ",
)
_EXPECTED_DIAGNOSTIC_SHAPE_REQUIREMENTS = [
    "len(e(nu)) = T_pre - 1 = 3 for PROP99-WINDOW-1985-1995-M5-OVERALL.",
    "len(e(delta)) = T_post = 7 for PROP99-WINDOW-1985-1995-M5-OVERALL.",
    "e(Sigma) stays square with dimension T - 1 = 10 before diagnostic theta^Delta / Sigma^Delta reconstruction.",
]
_EXPECTED_GRAPH_CAPTURE_FIELDS = [
    "pre_treatment_series",
    "post_treatment_series",
    "threshold_line_m",
    "pass_fail_style",
    "graph_note",
]
_GRAPH_SERIES_PREVIEW_ABS_TOL = 5e-7
_EXPECTED_VERDICT_BUCKETS = [
    "exact",
    "display_rounded",
    "exact_absence",
    "unresolved",
]
_CAPTURE_READY_OVERALL_LOADABLE_DOCS_MESSAGE = (
    "capture-ready overall metadata requires loadable same-case "
    "stdout/stored-results capture docs"
)
_CANONICAL_PARITY_PYTHON_RESULTS_DIR = (
    Path(__file__).resolve().parents[3]
    / "_bmad-output/test-artifacts/parity/results/python"
)
_BUNDLED_PROP99_CASE_ID = "PROP99-WINDOW-1985-1995-M5-OVERALL"
_BUNDLED_PROP99_NONOVERALL_SPLIT_DOC_CASE_IDS = (
    "PROP99-FULL-M5-ITER",
    "PROP99-FULL-M1-ITER",
    "PROP99-WINDOW-1985-1995-M5-ITER",
)
_BUNDLED_PROP99_WINDOW_ITER_CASE_ID = "PROP99-WINDOW-1985-1995-M5-ITER"
_BUNDLED_PROP99_AUXILIARY_CONTRACT_ARTIFACT_ID = (
    "pretest-overall-auxiliary-contract-v1"
)
_BUNDLED_PROP99_AUXILIARY_CONTRACT_FRONTIER_ID = "OF-008"
_BUNDLED_PROP99_AUXILIARY_CONTRACT_STATUS = "protected-auxiliary-helper-ready"
_BUNDLED_PROP99_AUXILIARY_DIAGNOSTIC_ARTIFACT_ID = (
    "pretest-overall-auxiliary-diagnostic-verifier-input-v1"
)
_BUNDLED_PROP99_AUXILIARY_DIAGNOSTIC_FRONTIER_ID = "OF-008"
_BUNDLED_PROP99_AUXILIARY_DIAGNOSTIC_STATUS = "blocked-diagnostic-helper-ready"
_BUNDLED_PROP99_AUXILIARY_BUG_REF = "STATA-OVERALL-AUX-001"
_BUNDLED_PROP99_AUXILIARY_DIAGNOSTIC_REF = (
    "pretest_overall_auxiliary_diagnostic_verifier_input.yaml"
)
_BUNDLED_PROP99_PACKET_REGISTRY_REF = "prop99_replay_fixture_registry.yaml"
_BUNDLED_PROP99_PACKET_MODE_CONTRACT_REF = (
    "pretest_paper_first_mode_contract.yaml#qa_handoff.replay_policy.overall_mode"
)
_BUNDLED_PROP99_PACKET_VERIFIER_INPUT_REF = (
    "_bmad-output/test-artifacts/parity/prop99_overall_capture_verifier_input.yaml"
)
_BUNDLED_PROP99_PYTHON_PARITY_STATUS = (
    "deterministic-estimator-verified-rng-mismatch"
)
_BUNDLED_REPLAY_DOCUMENTS_CACHE: (
    tuple[
        tuple[object, ...],
        tuple[
            dict[str, object],
            dict[str, object],
            dict[str, object],
            dict[str, object],
            dict[str, object],
            dict[str, object],
            dict[str, Path],
        ],
    ]
    | None
) = None
_BUNDLED_AUXILIARY_DOCUMENTS_CACHE: (
    tuple[
        tuple[object, ...],
        tuple[dict[str, object], dict[str, object]],
    ]
    | None
) = None
_BUNDLED_REPLAY_STORY_PACKET_CACHE: (
    tuple[tuple[object, ...], dict[str, object]] | None
) = None
_BUNDLED_CAPTURE_READY_OVERALL_BUNDLES_CACHE: dict[
    tuple[object, ...],
    dict[str, dict[str, object]],
] = {}
_BUNDLED_REPLAY_SCAFFOLD_SPLIT_DOC_VALIDATION_CACHE_KEY: tuple[object, ...] | None = None
_BUNDLED_REPLAY_SCAFFOLD_ERROR_PREFIXES = (
    "overall_capture_verifier_input ",
)
_PYTHON_PLACEHOLDER_FALLBACK_FIELD = "_pretest_python_placeholder_fallback"


def _bundled_prop99_replay_root():
    return Path(__file__).resolve().parent / "data" / "prop99_replay"


def _cache_path_marker(path: Path) -> tuple[str, int, int, str]:
    stat = path.stat()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return (str(path), stat.st_mtime_ns, stat.st_size, digest)


def _bundled_replay_documents_cache_key() -> tuple[object, ...]:
    bundled_root = _bundled_prop99_replay_root()
    return (
        id(load_replay_yaml),
        _cache_path_marker(bundled_root / "prop99_replay_driver.yaml"),
        _cache_path_marker(bundled_root / "prop99_replay_summary_template.yaml"),
        _cache_path_marker(
            bundled_root / "prop99_overall_capture_packet_template.yaml"
        ),
        _cache_path_marker(
            bundled_root / "prop99_overall_capture_verifier_input.yaml"
        ),
        _cache_path_marker(bundled_root / "prop99_overall_precapture_contract.yaml"),
        _cache_path_marker(
            bundled_root
            / "results/stata/PROP99-WINDOW-1985-1995-M5-OVERALL-capture-metadata.yaml"
        ),
    )


def _bundled_auxiliary_documents_cache_key() -> tuple[object, ...]:
    bundled_root = _bundled_prop99_replay_root()
    return (
        id(load_replay_yaml),
        _cache_path_marker(bundled_root / "pretest_overall_auxiliary_contract.yaml"),
        _cache_path_marker(
            bundled_root
            / "pretest_overall_auxiliary_diagnostic_verifier_input.yaml"
        ),
    )


def _bundled_capture_ready_overall_bundles_cache_key(
    *, promote_authoritative_fields: bool
) -> tuple[object, ...]:
    bundled_root = _bundled_prop99_replay_root()
    return (
        id(load_replay_yaml),
        id(_load_bundled_prop99_replay_documents),
        id(_load_validated_bundled_prop99_replay_documents),
        promote_authoritative_fields,
        _cache_path_marker(bundled_root / "prop99_replay_driver.yaml"),
        _cache_path_marker(bundled_root / "prop99_replay_summary_template.yaml"),
        _cache_path_marker(
            bundled_root / "prop99_overall_capture_packet_template.yaml"
        ),
        _cache_path_marker(
            bundled_root / "prop99_overall_capture_verifier_input.yaml"
        ),
        _cache_path_marker(bundled_root / "prop99_overall_precapture_contract.yaml"),
        _cache_path_marker(
            bundled_root
            / "results/stata/PROP99-WINDOW-1985-1995-M5-OVERALL-capture-metadata.yaml"
        ),
        _cache_path_marker(
            bundled_root
            / "results/stata/PROP99-WINDOW-1985-1995-M5-OVERALL-graph-data.yaml"
        ),
        _cache_path_marker(
            bundled_root
            / "results/stata/PROP99-WINDOW-1985-1995-M5-OVERALL-stdout.yaml"
        ),
        _cache_path_marker(
            bundled_root
            / "results/stata/PROP99-WINDOW-1985-1995-M5-OVERALL-stored-results.yaml"
        ),
        _cache_path_marker(
            bundled_root
            / "results/python/PROP99-WINDOW-1985-1995-M5-OVERALL-stdout.yaml"
        ),
        _cache_path_marker(
            bundled_root
            / "results/python/PROP99-WINDOW-1985-1995-M5-OVERALL-stored-results.yaml"
        ),
    )


def _bundled_replay_story_packet_cache_key() -> tuple[object, ...]:
    bundled_root = _bundled_prop99_replay_root()
    return (
        id(_load_validated_bundled_prop99_replay_documents),
        id(load_prop99_replay_scaffold),
        id(load_prop99_overall_auxiliary_scaffold),
        id(_story_packet_artifact_paths),
        _bundled_replay_documents_cache_key(),
        _bundled_auxiliary_documents_cache_key(),
        _cache_path_marker(
            bundled_root
            / "results/stata/PROP99-WINDOW-1985-1995-M5-OVERALL-stdout.yaml"
        ),
        _cache_path_marker(
            bundled_root
            / "results/stata/PROP99-WINDOW-1985-1995-M5-OVERALL-stored-results.yaml"
        ),
        _cache_path_marker(
            bundled_root
            / "results/stata/PROP99-WINDOW-1985-1995-M5-OVERALL-graph-data.yaml"
        ),
        _cache_path_marker(
            bundled_root
            / "results/python/PROP99-WINDOW-1985-1995-M5-OVERALL-stdout.yaml"
        ),
        _cache_path_marker(
            bundled_root
            / "results/python/PROP99-WINDOW-1985-1995-M5-OVERALL-stored-results.yaml"
        ),
    )


def _bundled_replay_scaffold_split_doc_validation_cache_key(
    absolute_capture_paths: Mapping[str, Path],
) -> tuple[object, ...]:
    return (
        id(load_replay_yaml),
        *(
            (
                _cache_path_marker(Path(path))
                if Path(path).exists()
                else (str(Path(path)), None, None)
            )
            for _, path in sorted(absolute_capture_paths.items())
        ),
    )


def _load_bundled_prop99_replay_documents() -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, Path],
]:
    global _BUNDLED_REPLAY_DOCUMENTS_CACHE
    cache_key = _bundled_replay_documents_cache_key()
    if (
        _BUNDLED_REPLAY_DOCUMENTS_CACHE is not None
        and _BUNDLED_REPLAY_DOCUMENTS_CACHE[0] == cache_key
    ):
        return deepcopy(_BUNDLED_REPLAY_DOCUMENTS_CACHE[1])

    bundled_root = _bundled_prop99_replay_root()
    driver_document = load_replay_yaml(
        bundled_root / "prop99_replay_driver.yaml"
    )
    summary_template = load_replay_yaml(
        bundled_root / "prop99_replay_summary_template.yaml"
    )
    overall_capture_packet = load_replay_yaml(
        bundled_root / "prop99_overall_capture_packet_template.yaml"
    )
    overall_capture_verifier_input = load_replay_yaml(
        bundled_root / "prop99_overall_capture_verifier_input.yaml"
    )
    precapture_contract = load_replay_yaml(
        bundled_root / "prop99_overall_precapture_contract.yaml"
    )
    capture_metadata = load_replay_yaml(
        bundled_root
        / "results/stata/PROP99-WINDOW-1985-1995-M5-OVERALL-capture-metadata.yaml"
    )

    absolute_capture_paths = {
        "stata_stdout": bundled_root
        / "results/stata/PROP99-WINDOW-1985-1995-M5-OVERALL-stdout.yaml",
        "stata_stored_results": bundled_root
        / "results/stata/PROP99-WINDOW-1985-1995-M5-OVERALL-stored-results.yaml",
        "stata_graph_data": bundled_root
        / "results/stata/PROP99-WINDOW-1985-1995-M5-OVERALL-graph-data.yaml",
        "capture_metadata": bundled_root
        / "results/stata/PROP99-WINDOW-1985-1995-M5-OVERALL-capture-metadata.yaml",
        "python_stdout": bundled_root
        / "results/python/PROP99-WINDOW-1985-1995-M5-OVERALL-stdout.yaml",
        "python_stored_results": bundled_root
        / "results/python/PROP99-WINDOW-1985-1995-M5-OVERALL-stored-results.yaml",
    }

    overall_capture_packet["capture_paths"] = {
        "stata_stdout": str(absolute_capture_paths["stata_stdout"]),
        "stata_stored_results": str(
            absolute_capture_paths["stata_stored_results"]
        ),
        "stata_graph_data": str(absolute_capture_paths["stata_graph_data"]),
        "capture_metadata": str(absolute_capture_paths["capture_metadata"]),
    }

    for document in (driver_document, summary_template):
        overall_case = next(
            case
            for case in document["cases"]
            if case["case_id"] == _BUNDLED_PROP99_CASE_ID
        )
        overall_case["capture_paths"] = {
            "stata_stdout": str(absolute_capture_paths["stata_stdout"]),
            "python_stdout": str(absolute_capture_paths["python_stdout"]),
            "stata_stored_results": str(
                absolute_capture_paths["stata_stored_results"]
            ),
            "python_stored_results": str(
                absolute_capture_paths["python_stored_results"]
            ),
        }
        if "oracle_capture" in overall_case:
            overall_case["oracle_capture"] = {
                **overall_case["oracle_capture"],
                "graph_data_capture_path": str(
                    absolute_capture_paths["stata_graph_data"]
                ),
                "capture_metadata_path": str(
                    absolute_capture_paths["capture_metadata"]
                ),
            }

        for case_id in _BUNDLED_PROP99_NONOVERALL_SPLIT_DOC_CASE_IDS:
            split_doc_case = next(
                (
                    case
                    for case in document["cases"]
                    if case["case_id"] == case_id
                ),
                None,
            )
            if split_doc_case is None:
                continue
            split_doc_case["capture_paths"] = {
                "stata_stdout": str(
                    bundled_root
                    / f"results/stata/{case_id}-stdout.yaml"
                ),
                "python_stdout": str(
                    bundled_root
                    / f"results/python/{case_id}-stdout.yaml"
                ),
                "stata_stored_results": str(
                    bundled_root
                    / f"results/stata/{case_id}-stored-results.yaml"
                ),
                "python_stored_results": str(
                    bundled_root
                    / f"results/python/{case_id}-stored-results.yaml"
                ),
            }

    documents = (
        driver_document,
        summary_template,
        overall_capture_packet,
        overall_capture_verifier_input,
        precapture_contract,
        capture_metadata,
        absolute_capture_paths,
    )
    _BUNDLED_REPLAY_DOCUMENTS_CACHE = (cache_key, deepcopy(documents))
    return deepcopy(documents)


def _normalize_bundled_replay_scaffold_error_message(message: str) -> str:
    prefix = f"{_BUNDLED_PROP99_CASE_ID} "
    if message.startswith(prefix):
        message = message[len(prefix) :]
    nested_prefix = "load_prop99_replay_scaffold() requires "
    if message.startswith(nested_prefix):
        message = message[len(nested_prefix) :]
    for extra_prefix in _BUNDLED_REPLAY_SCAFFOLD_ERROR_PREFIXES:
        if message.startswith(extra_prefix):
            message = message[len(extra_prefix) :]
    return message.replace(".case_id must equal ", ".case_id to equal ")


def _load_bundled_prop99_overall_auxiliary_documents() -> tuple[
    dict[str, object],
    dict[str, object],
]:
    global _BUNDLED_AUXILIARY_DOCUMENTS_CACHE
    cache_key = _bundled_auxiliary_documents_cache_key()
    if (
        _BUNDLED_AUXILIARY_DOCUMENTS_CACHE is not None
        and _BUNDLED_AUXILIARY_DOCUMENTS_CACHE[0] == cache_key
    ):
        return deepcopy(_BUNDLED_AUXILIARY_DOCUMENTS_CACHE[1])

    bundled_root = _bundled_prop99_replay_root()
    protected_auxiliary_contract = load_replay_yaml(
        bundled_root / "pretest_overall_auxiliary_contract.yaml"
    )
    auxiliary_diagnostic_verifier_input = load_replay_yaml(
        bundled_root / "pretest_overall_auxiliary_diagnostic_verifier_input.yaml"
    )

    documents = (
        protected_auxiliary_contract,
        auxiliary_diagnostic_verifier_input,
    )
    _BUNDLED_AUXILIARY_DOCUMENTS_CACHE = (cache_key, deepcopy(documents))
    return deepcopy(documents)


def _bundled_prop99_overall_auxiliary_artifact_paths() -> dict[str, str]:
    bundled_root = _bundled_prop99_replay_root()
    return {
        "protected_auxiliary_contract": str(
            bundled_root / "pretest_overall_auxiliary_contract.yaml"
        ),
        "auxiliary_diagnostic_verifier_input": str(
            bundled_root
            / "pretest_overall_auxiliary_diagnostic_verifier_input.yaml"
        ),
    }


def _validate_auxiliary_diagnostic_verifier_input_contract(
    auxiliary_diagnostic_verifier_input: Mapping[str, object],
    *,
    callable_name: str,
    label_prefix: str,
) -> None:
    if (
        auxiliary_diagnostic_verifier_input.get("artifact_id")
        != _BUNDLED_PROP99_AUXILIARY_DIAGNOSTIC_ARTIFACT_ID
    ):
        raise ValueError(
            f"{callable_name}() requires "
            f"{label_prefix}.artifact_id "
            f"to equal {_BUNDLED_PROP99_AUXILIARY_DIAGNOSTIC_ARTIFACT_ID}"
        )
    if (
        auxiliary_diagnostic_verifier_input.get("frontier_id")
        != _BUNDLED_PROP99_AUXILIARY_DIAGNOSTIC_FRONTIER_ID
    ):
        raise ValueError(
            f"{callable_name}() requires "
            f"{label_prefix}.frontier_id "
            f"to equal {_BUNDLED_PROP99_AUXILIARY_DIAGNOSTIC_FRONTIER_ID}"
        )
    if (
        auxiliary_diagnostic_verifier_input.get("status")
        != _BUNDLED_PROP99_AUXILIARY_DIAGNOSTIC_STATUS
    ):
        raise ValueError(
            f"{callable_name}() requires "
            f"{label_prefix}.status "
            f"to equal {_BUNDLED_PROP99_AUXILIARY_DIAGNOSTIC_STATUS}"
        )
    mode_gate = _mapping_payload(
        auxiliary_diagnostic_verifier_input.get("mode_gate"),
        label=f"{label_prefix}.mode_gate",
    )
    if mode_gate.get("required_mode") != _EXPECTED_DIAGNOSTIC_REQUIRED_MODE:
        raise ValueError(
            f"{callable_name}() requires "
            f"{label_prefix}.mode_gate.required_mode "
            f"to equal {_EXPECTED_DIAGNOSTIC_REQUIRED_MODE}"
        )
    if (
        mode_gate.get("required_exact_fields")
        != _EXPECTED_DIAGNOSTIC_REQUIRED_EXACT_FIELDS
    ):
        raise ValueError(
            f"{callable_name}() requires "
            f"{label_prefix}.mode_gate.required_exact_fields "
            "to keep e(mode), e(T_pre), and e(T_post) explicit"
        )
    if mode_gate.get("required_raw_inputs") != _EXPECTED_DIAGNOSTIC_SAFE_INPUTS:
        raise ValueError(
            f"{callable_name}() requires "
            f"{label_prefix}.mode_gate.required_raw_inputs "
            "to keep e(nu), e(delta), and e(Sigma) explicit"
        )
    if mode_gate.get("blocked_without_raw_snapshot") is not True:
        raise ValueError(
            f"{callable_name}() requires "
            f"{label_prefix}.mode_gate.blocked_without_raw_snapshot "
            "to stay true"
        )

    case_specific_expectations = _mapping_payload(
        auxiliary_diagnostic_verifier_input.get("case_specific_expectations"),
        label=f"{label_prefix}.case_specific_expectations",
    )
    if (
        case_specific_expectations.get("exact_dimensions")
        != _EXPECTED_AUXILIARY_EXACT_DIMENSIONS
    ):
        raise ValueError(
            f"{callable_name}() requires "
            f"{label_prefix}.case_specific_expectations.exact_dimensions "
            "must keep the canonical bundled Prop99 diagnostic dimensions"
        )


def _validate_bundled_prop99_overall_auxiliary_scaffold(
    protected_auxiliary_contract: Mapping[str, object],
    auxiliary_diagnostic_verifier_input: Mapping[str, object],
) -> None:
    if (
        protected_auxiliary_contract.get("artifact_id")
        != _BUNDLED_PROP99_AUXILIARY_CONTRACT_ARTIFACT_ID
    ):
        raise ValueError(
            "load_prop99_overall_auxiliary_scaffold() requires "
            "protected_auxiliary_contract.artifact_id "
            f"to equal {_BUNDLED_PROP99_AUXILIARY_CONTRACT_ARTIFACT_ID}"
        )
    if (
        protected_auxiliary_contract.get("frontier_id")
        != _BUNDLED_PROP99_AUXILIARY_CONTRACT_FRONTIER_ID
    ):
        raise ValueError(
            "load_prop99_overall_auxiliary_scaffold() requires "
            "protected_auxiliary_contract.frontier_id "
            f"to equal {_BUNDLED_PROP99_AUXILIARY_CONTRACT_FRONTIER_ID}"
        )
    if (
        protected_auxiliary_contract.get("status")
        != _BUNDLED_PROP99_AUXILIARY_CONTRACT_STATUS
    ):
        raise ValueError(
            "load_prop99_overall_auxiliary_scaffold() requires "
            "protected_auxiliary_contract.status "
            f"to equal {_BUNDLED_PROP99_AUXILIARY_CONTRACT_STATUS}"
        )
    if protected_auxiliary_contract.get("bug_ref") != _BUNDLED_PROP99_AUXILIARY_BUG_REF:
        raise ValueError(
            "load_prop99_overall_auxiliary_scaffold() requires "
            "protected_auxiliary_contract.bug_ref "
            f"to equal {_BUNDLED_PROP99_AUXILIARY_BUG_REF}"
        )

    qa_handoff = _mapping_payload(
        protected_auxiliary_contract.get("qa_handoff"),
        label="protected_auxiliary_contract.qa_handoff",
    )
    if qa_handoff.get("diagnostic_verifier_input_ref") != _BUNDLED_PROP99_AUXILIARY_DIAGNOSTIC_REF:
        raise ValueError(
            "load_prop99_overall_auxiliary_scaffold() requires "
            "protected_auxiliary_contract.qa_handoff.diagnostic_verifier_input_ref "
            f"to equal {_BUNDLED_PROP99_AUXILIARY_DIAGNOSTIC_REF}"
        )

    case_specific_expectations = _mapping_payload(
        auxiliary_diagnostic_verifier_input.get("case_specific_expectations"),
        label="auxiliary_diagnostic_verifier_input.case_specific_expectations",
    )
    if case_specific_expectations.get("case_id") != _BUNDLED_PROP99_CASE_ID:
        raise ValueError(
            "load_prop99_overall_auxiliary_scaffold() requires "
            "auxiliary_diagnostic_verifier_input.case_specific_expectations.case_id "
            f"to equal {_BUNDLED_PROP99_CASE_ID}"
        )
    _validate_auxiliary_diagnostic_verifier_input_contract(
        auxiliary_diagnostic_verifier_input,
        callable_name="load_prop99_overall_auxiliary_scaffold",
        label_prefix="auxiliary_diagnostic_verifier_input",
    )


def _validate_story_packet_replay_scaffold(
    replay_scaffold: Mapping[str, object],
    *,
    callable_name: str,
) -> None:
    if replay_scaffold.get("case_id") != _BUNDLED_PROP99_CASE_ID:
        raise ValueError(
            f"{callable_name}() requires "
            "replay_scaffold.case_id "
            f"to equal {_BUNDLED_PROP99_CASE_ID}"
        )

    overall_capture_packet = _mapping_payload(
        replay_scaffold.get("overall_capture_packet"),
        label="replay_scaffold.overall_capture_packet",
    )
    if overall_capture_packet.get("case_id") != _BUNDLED_PROP99_CASE_ID:
        raise ValueError(
            f"{callable_name}() requires "
            "replay_scaffold.overall_capture_packet.case_id "
            f"to equal {_BUNDLED_PROP99_CASE_ID}"
        )

    capture_metadata = _mapping_payload(
        replay_scaffold.get("capture_metadata"),
        label="replay_scaffold.capture_metadata",
    )
    if capture_metadata.get("case_id") != _BUNDLED_PROP99_CASE_ID:
        raise ValueError(
            f"{callable_name}() requires "
            "replay_scaffold.capture_metadata.case_id "
            f"to equal {_BUNDLED_PROP99_CASE_ID}"
        )

    driver_document = _mapping_payload(
        replay_scaffold.get("driver"),
        label="replay_scaffold.driver",
    )
    summary_template = _mapping_payload(
        replay_scaffold.get("summary_template"),
        label="replay_scaffold.summary_template",
    )
    overall_capture_verifier_input = _mapping_payload(
        replay_scaffold.get("overall_capture_verifier_input"),
        label="replay_scaffold.overall_capture_verifier_input",
    )
    precapture_contract = _mapping_payload(
        replay_scaffold.get("precapture_contract"),
        label="replay_scaffold.precapture_contract",
    )
    try:
        _validate_bundled_prop99_replay_scaffold(
            driver_document,
            summary_template,
            overall_capture_packet,
            overall_capture_verifier_input,
            precapture_contract,
            capture_metadata,
        )
    except ValueError as exc:
        message = _normalize_bundled_replay_scaffold_error_message(str(exc))
        raise ValueError(f"{callable_name}() requires " + message) from exc


def _validate_story_packet_replay_scaffold_capture_paths(
    replay_scaffold: Mapping[str, object],
    *,
    callable_name: str,
) -> None:
    capture_paths = _mapping_payload(
        replay_scaffold.get("capture_paths"),
        label="replay_scaffold.capture_paths",
    )
    expected_capture_paths = {
        key: str(path)
        for key, path in _load_validated_bundled_prop99_replay_documents(
            callable_name=callable_name
        )[6].items()
    }
    if sorted(capture_paths) != sorted(expected_capture_paths):
        raise ValueError(
            f"{callable_name}() requires "
            "replay_scaffold.capture_paths to define the canonical replay scaffold capture path keys"
        )
    for field_name, expected_path in expected_capture_paths.items():
        actual_path = capture_paths.get(field_name)
        if not isinstance(actual_path, str) or not actual_path.strip():
            raise ValueError(
                f"{callable_name}() requires "
                f"replay_scaffold.capture_paths.{field_name} "
                "to be a non-empty string"
            )
        if actual_path != expected_path:
            raise ValueError(
                f"{callable_name}() requires "
                f"replay_scaffold.capture_paths.{field_name} "
                f"to equal {expected_path}"
            )


def _validate_bundled_prop99_replay_scaffold(
    driver_document: Mapping[str, object],
    summary_template: Mapping[str, object],
    overall_capture_packet: Mapping[str, object],
    overall_capture_verifier_input: Mapping[str, object],
    precapture_contract: Mapping[str, object],
    capture_metadata: Mapping[str, object],
) -> None:
    _require_case_id(
        overall_capture_packet,
        case_id=_BUNDLED_PROP99_CASE_ID,
        label="overall_capture_packet",
    )
    _require_case_id(
        overall_capture_verifier_input,
        case_id=_BUNDLED_PROP99_CASE_ID,
        label="overall_capture_verifier_input",
    )
    _require_case_id(
        precapture_contract,
        case_id=_BUNDLED_PROP99_CASE_ID,
        label="precapture_contract",
    )
    _require_case_id(
        capture_metadata,
        case_id=_BUNDLED_PROP99_CASE_ID,
        label="capture_metadata",
    )
    driver_cases = _case_lookup(driver_document, label="driver_document")
    summary_cases = _case_lookup(summary_template, label="summary_template")
    driver_case = driver_cases.get(_BUNDLED_PROP99_CASE_ID)
    if driver_case is None:
        raise ValueError(
            "load_prop99_replay_scaffold() requires "
            f"driver_document to define case_id {_BUNDLED_PROP99_CASE_ID}"
        )
    summary_case = summary_cases.get(_BUNDLED_PROP99_CASE_ID)
    if summary_case is None:
        raise ValueError(
            "load_prop99_replay_scaffold() requires "
            f"summary_template to define case_id {_BUNDLED_PROP99_CASE_ID}"
        )
    _validate_capture_ready_scaffold_alignment(driver_document, summary_template)
    _validate_oracle_capture_alignment(
        driver_case,
        summary_case,
        case_id=_BUNDLED_PROP99_CASE_ID,
    )
    _validate_bundled_python_parity_status(
        driver_case,
        summary_case,
        case_id=_BUNDLED_PROP99_CASE_ID,
    )
    try:
        _validate_overall_capture_verifier_input_contract(
            overall_capture_verifier_input,
            case_id=_BUNDLED_PROP99_CASE_ID,
        )
    except ValueError as exc:
        message = str(exc)
        prefix = f"{_BUNDLED_PROP99_CASE_ID} "
        if message.startswith(prefix):
            message = message[len(prefix) :]
        raise ValueError(
            f"{_BUNDLED_PROP99_CASE_ID} overall_capture_verifier_input {message}"
        ) from exc
    _validate_overall_capture_packet_alignment(
        driver_case,
        overall_capture_packet,
        case_id=_BUNDLED_PROP99_CASE_ID,
    )
    _validate_bundled_overall_capture_packet_public_refs(overall_capture_packet)
    _validate_bundled_precapture_contract_authority(precapture_contract)
    _validate_capture_ready_overall_bundle_metadata(
        driver_case,
        summary_case,
        overall_capture_packet=overall_capture_packet,
        overall_capture_verifier_input=overall_capture_verifier_input,
        capture_metadata=capture_metadata,
        precapture_contract=precapture_contract,
    )


def _load_validated_bundled_prop99_replay_documents(
    *,
    callable_name: str,
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, Path],
]:
    (
        driver_document,
        summary_template,
        overall_capture_packet,
        overall_capture_verifier_input,
        precapture_contract,
        capture_metadata,
        absolute_capture_paths,
    ) = _load_bundled_prop99_replay_documents()
    try:
        _validate_bundled_prop99_replay_scaffold(
            driver_document,
            summary_template,
            overall_capture_packet,
            overall_capture_verifier_input,
            precapture_contract,
            capture_metadata,
        )
        driver_case = _case_lookup(
            driver_document,
            label="driver_document",
        ).get(_BUNDLED_PROP99_CASE_ID)
        if driver_case is None:
            raise ValueError(
                f"scaffold.driver must define case_id {_BUNDLED_PROP99_CASE_ID}"
            )
        embedded_capture_paths = {
            **_mapping_payload(
                overall_capture_packet.get("capture_paths"),
                label="scaffold.overall_capture_packet.capture_paths",
            ),
            **_mapping_payload(
                driver_case.get("capture_paths"),
                label=f"{_BUNDLED_PROP99_CASE_ID} scaffold.driver.capture_paths",
            ),
        }
        _validate_replay_scaffold_capture_paths(
            embedded_capture_paths,
            case_id=_BUNDLED_PROP99_CASE_ID,
            driver_document=driver_document,
            summary_template=summary_template,
            overall_capture_packet=overall_capture_packet,
        )
        if callable_name == "load_prop99_replay_scaffold":
            _validate_existing_artifact_paths(
                {key: str(path) for key, path in absolute_capture_paths.items()},
                label="scaffold.capture_paths",
                callable_name=callable_name,
            )
        global _BUNDLED_REPLAY_SCAFFOLD_SPLIT_DOC_VALIDATION_CACHE_KEY
        validation_cache_key = (
            _bundled_replay_scaffold_split_doc_validation_cache_key(
                absolute_capture_paths
            )
        )
        if (
            _BUNDLED_REPLAY_SCAFFOLD_SPLIT_DOC_VALIDATION_CACHE_KEY
            != validation_cache_key
        ):
            _load_capture_ready_overall_bundles(
                driver_document=driver_document,
                summary_template=summary_template,
                case_id=_BUNDLED_PROP99_CASE_ID,
                overall_capture_packet=overall_capture_packet,
                overall_capture_verifier_input=overall_capture_verifier_input,
                precapture_contract=precapture_contract,
                capture_metadata=capture_metadata,
                allow_python_placeholder_fallback=True,
            )
            _BUNDLED_REPLAY_SCAFFOLD_SPLIT_DOC_VALIDATION_CACHE_KEY = (
                validation_cache_key
            )
    except ValueError as exc:
        message = str(exc)
        prefix = f"{_BUNDLED_PROP99_CASE_ID} "
        if message.startswith(prefix):
            message = message[len(prefix) :]
        message = message.replace(".case_id must equal ", ".case_id to equal ")
        raise ValueError(f"{callable_name}() requires " + message) from exc
    return (
        driver_document,
        summary_template,
        overall_capture_packet,
        overall_capture_verifier_input,
        precapture_contract,
        capture_metadata,
        absolute_capture_paths,
    )


def _load_optional_case_payloads(
    payload_paths: Mapping[str, str | Path] | None,
    *,
    label: str,
    anchor_paths: tuple[Path, ...] = (),
) -> dict[str, dict[str, object]] | None:
    if payload_paths is None:
        return None
    resolved_paths = {
        case_id: _resolve_anchor_first_embedded_artifact_path(
            path,
            label=f"{label}[{case_id}]",
            anchor_paths=anchor_paths,
        )
        for case_id, path in payload_paths.items()
    }
    return load_case_payloads(resolved_paths, label=label)


def _validate_capture_companion_paths(
    capture_metadata_paths_by_case: Mapping[str, str | Path] | None,
    precapture_contract_paths_by_case: Mapping[str, str | Path] | None,
    *,
    overall_capture_packet_paths: Mapping[str, str | Path] | None,
    overall_capture_verifier_input_paths: Mapping[str, str | Path] | None,
) -> None:
    packet_case_ids = set(overall_capture_packet_paths or {})
    verifier_case_ids = set(overall_capture_verifier_input_paths or {})

    if packet_case_ids != verifier_case_ids:
        missing_verifier_case_ids = sorted(packet_case_ids - verifier_case_ids)
        if missing_verifier_case_ids:
            missing_case_id = missing_verifier_case_ids[0]
            raise ValueError(
                f"{missing_case_id} overall_capture_verifier_input_paths[{missing_case_id}] "
                "is required whenever overall capture packet and verifier inputs are "
                "loaded from paths"
            )
        missing_packet_case_ids = sorted(verifier_case_ids - packet_case_ids)
        missing_case_id = missing_packet_case_ids[0]
        raise ValueError(
            f"{missing_case_id} overall_capture_packet_paths[{missing_case_id}] "
            "is required whenever overall capture packet and verifier inputs are "
            "loaded from paths"
        )

    def require_same_case_companions(
        payload_paths_by_case: Mapping[str, str | Path] | None,
        *,
        label: str,
    ) -> None:
        if payload_paths_by_case is None:
            return
        for case_id in payload_paths_by_case:
            if case_id in packet_case_ids and case_id in verifier_case_ids:
                continue
            raise ValueError(
                f"{case_id} {label} requires "
                f"overall_capture_packet_paths[{case_id}] and "
                f"overall_capture_verifier_input_paths[{case_id}]"
            )

    require_same_case_companions(
        capture_metadata_paths_by_case,
        label="capture_metadata_paths_by_case",
    )
    require_same_case_companions(
        precapture_contract_paths_by_case,
        label="precapture_contract_paths_by_case",
    )


def _case_lookup(document: Mapping[str, object], *, label: str) -> dict[str, dict[str, object]]:
    cases = document.get("cases")
    if not isinstance(cases, list):
        raise ValueError(f"{label} must define cases")

    lookup: dict[str, dict[str, object]] = {}
    for index, case in enumerate(cases):
        if not isinstance(case, Mapping):
            raise ValueError(f"{label}.cases[{index}] must be a mapping")
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(f"{label}.cases[{index}].case_id must be a non-empty string")
        if case_id in lookup:
            raise ValueError(f"{label} defines duplicate case_id {case_id}")
        lookup[case_id] = dict(case)
    return lookup


def _case_order(document: Mapping[str, object], *, label: str) -> list[str]:
    cases = document.get("cases")
    if not isinstance(cases, list):
        raise ValueError(f"{label} must define cases")

    order: list[str] = []
    for index, case in enumerate(cases):
        if not isinstance(case, Mapping):
            raise ValueError(f"{label}.cases[{index}] must be a mapping")
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(f"{label}.cases[{index}].case_id must be a non-empty string")
        order.append(case_id)
    return order


def _mutable_case_payload(
    document: dict[str, object],
    *,
    label: str,
    case_id: str,
) -> dict[str, object]:
    cases = document.get("cases")
    if not isinstance(cases, list):
        raise ValueError(f"{label} must define cases")
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(f"{label}.cases[{index}] must be a mapping")
        if case.get("case_id") == case_id:
            return case
    raise ValueError(f"{label} is missing case_id {case_id}")


def _validate_capture_ready_scaffold_alignment(
    driver_document: Mapping[str, object],
    summary_template: Mapping[str, object],
) -> None:
    _case_lookup(driver_document, label="driver_document")
    _case_lookup(summary_template, label="summary_template")

    verdict_buckets = summary_template.get("verdict_buckets")
    if verdict_buckets != _EXPECTED_VERDICT_BUCKETS:
        raise ValueError("summary_template verdict_buckets drift")

    if _case_order(summary_template, label="summary_template") != _case_order(
        driver_document,
        label="driver_document",
    ):
        raise ValueError("summary_template case order drift")


def _validate_oracle_capture_alignment(
    driver_case: Mapping[str, object],
    summary_case: Mapping[str, object],
    *,
    case_id: str,
) -> None:
    driver_oracle_capture = _mapping_payload(
        driver_case.get("oracle_capture"),
        label=f"{case_id} driver_document.oracle_capture",
    )
    summary_oracle_capture = _mapping_payload(
        summary_case.get("oracle_capture"),
        label=f"{case_id} summary_template.oracle_capture",
    )
    if summary_oracle_capture != driver_oracle_capture:
        raise ValueError(f"{case_id} summary template drifted from driver in oracle_capture")


def _validate_bundled_python_parity_status(
    driver_case: Mapping[str, object],
    summary_case: Mapping[str, object],
    *,
    case_id: str,
) -> None:
    driver_status = driver_case.get("python_parity_status")
    summary_status = summary_case.get("python_parity_status")
    if driver_status != _BUNDLED_PROP99_PYTHON_PARITY_STATUS:
        raise ValueError(
            f"{case_id} driver_document.python_parity_status must equal "
            f"{_BUNDLED_PROP99_PYTHON_PARITY_STATUS}"
        )
    if summary_status != _BUNDLED_PROP99_PYTHON_PARITY_STATUS:
        raise ValueError(
            f"{case_id} summary_template.python_parity_status must equal "
            f"{_BUNDLED_PROP99_PYTHON_PARITY_STATUS}"
        )
    if summary_status != driver_status:
        raise ValueError(
            f"{case_id} summary_template.python_parity_status must match "
            "driver_document.python_parity_status"
        )


def _validate_overall_capture_packet_alignment(
    driver_case: Mapping[str, object],
    overall_capture_packet: Mapping[str, object],
    *,
    case_id: str,
) -> None:
    driver_oracle_capture = _mapping_payload(
        driver_case.get("oracle_capture"),
        label=f"{case_id} driver_document.oracle_capture",
    )
    if overall_capture_packet.get("precapture_contract_ref") != driver_oracle_capture.get(
        "precapture_contract_ref"
    ):
        raise ValueError(
            f"{case_id} overall capture packet drifted from driver precapture contract"
        )
    if overall_capture_packet.get("capture_metadata_contract_ref") != driver_oracle_capture.get(
        "capture_metadata_contract_ref"
    ):
        raise ValueError(
            f"{case_id} overall capture packet drifted from driver capture metadata contract"
        )
    packet_protected_results = overall_capture_packet.get(
        "excluded_non_authoritative_results"
    )
    driver_protected_results = driver_oracle_capture.get("protected_results")
    if not isinstance(packet_protected_results, list):
        raise ValueError(
            f"{case_id} overall capture packet excluded_non_authoritative_results must be a list"
        )
    if not isinstance(driver_protected_results, list):
        raise ValueError(
            f"{case_id} driver_document.oracle_capture.protected_results must be a list"
        )
    if packet_protected_results != driver_protected_results:
        raise ValueError(
            f"{case_id} overall capture packet drifted from driver protected results"
        )

    capture_paths = _mapping_payload(
        overall_capture_packet.get("capture_paths"),
        label=f"{case_id} scaffold.overall_capture_packet.capture_paths",
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


def _validate_bundled_overall_capture_packet_public_refs(
    overall_capture_packet: Mapping[str, object],
) -> None:
    if overall_capture_packet.get("registry_ref") != _BUNDLED_PROP99_PACKET_REGISTRY_REF:
        raise ValueError(
            "overall_capture_packet.registry_ref "
            f"to equal {_BUNDLED_PROP99_PACKET_REGISTRY_REF}"
        )
    if (
        overall_capture_packet.get("mode_contract_ref")
        != _BUNDLED_PROP99_PACKET_MODE_CONTRACT_REF
    ):
        raise ValueError(
            "overall_capture_packet.mode_contract_ref "
            f"to equal {_BUNDLED_PROP99_PACKET_MODE_CONTRACT_REF}"
        )
    if (
        overall_capture_packet.get("verifier_input_ref")
        != _BUNDLED_PROP99_PACKET_VERIFIER_INPUT_REF
    ):
        raise ValueError(
            "overall_capture_packet.verifier_input_ref "
            f"to equal {_BUNDLED_PROP99_PACKET_VERIFIER_INPUT_REF}"
        )


def _validate_bundled_precapture_contract_authority(
    precapture_contract: Mapping[str, object],
) -> None:
    cross_paper_authority = _mapping_payload(
        precapture_contract.get("cross_paper_appendix_c_authority"),
        label="precapture_contract.cross_paper_appendix_c_authority",
    )
    if (
        cross_paper_authority.get("authority_markers")
        != _EXPECTED_APPENDIX_C_AUTHORITY_MARKERS
    ):
        raise ValueError(
            "precapture_contract.cross_paper_appendix_c_authority.authority_markers "
            "must keep phi^Delta = 0, S_pre_hat^Delta <= M, and kappa-free explicit"
        )


def _mapping_payload(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return dict(value)


def _require_capture_path_fields(
    value: object,
    *,
    label: str,
    required_fields: tuple[str, ...],
) -> dict[str, str]:
    capture_paths = _mapping_payload(value, label=label)
    missing_fields = sorted(set(required_fields) - set(capture_paths))
    if missing_fields:
        raise ValueError(
            f"{label} is missing required fields: " + ", ".join(missing_fields)
        )

    normalized: dict[str, str] = {}
    for field_name in required_fields:
        field_value = capture_paths.get(field_name)
        if not isinstance(field_value, str) or not field_value.strip():
            raise ValueError(f"{label}.{field_name} must be a non-empty string")
        normalized[field_name] = field_value
    return normalized


def _canonical_capture_path_string(
    value: str,
    *,
    label: str,
    anchor_paths: tuple[Path, ...],
) -> str:
    return str(
        _resolve_anchor_first_embedded_artifact_path(
            value,
            label=label,
            anchor_paths=anchor_paths,
        )
    )


def _canonicalize_overall_capture_paths(
    *,
    driver_document: Mapping[str, object],
    summary_template: Mapping[str, object],
    overall_capture_packet: Mapping[str, object],
    case_id: str,
    anchor_paths: tuple[Path, ...],
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    driver_copy = deepcopy(dict(driver_document))
    summary_copy = deepcopy(dict(summary_template))
    packet_copy = deepcopy(dict(overall_capture_packet))
    driver_case = _mutable_case_payload(
        driver_copy,
        label="driver_document",
        case_id=case_id,
    )
    summary_case = _mutable_case_payload(
        summary_copy,
        label="summary_template",
        case_id=case_id,
    )

    packet_capture_paths = _require_capture_path_fields(
        packet_copy.get("capture_paths"),
        label=f"{case_id} overall_capture_packet.capture_paths",
        required_fields=(
            "capture_metadata",
            "stata_graph_data",
            "stata_stdout",
            "stata_stored_results",
        ),
    )
    summary_capture_paths = _require_capture_path_fields(
        summary_case.get("capture_paths"),
        label=f"{case_id} summary_template.capture_paths",
        required_fields=(
            "python_stdout",
            "python_stored_results",
            "stata_stdout",
            "stata_stored_results",
        ),
    )
    packet_copy["capture_paths"] = {
        key: _canonical_capture_path_string(
            value,
            label=f"{case_id} overall_capture_packet.capture_paths.{key}",
            anchor_paths=anchor_paths,
        )
        for key, value in packet_capture_paths.items()
    }
    summary_case["capture_paths"] = {
        key: _canonical_capture_path_string(
            value,
            label=f"{case_id} summary_template.capture_paths.{key}",
            anchor_paths=anchor_paths,
        )
        for key, value in summary_capture_paths.items()
    }

    driver_oracle_capture = driver_case.get("oracle_capture")
    if isinstance(driver_oracle_capture, Mapping):
        normalized_oracle = dict(driver_oracle_capture)
        for key in ("graph_data_capture_path", "capture_metadata_path"):
            value = normalized_oracle.get(key)
            if isinstance(value, str) and value.strip():
                normalized_oracle[key] = _canonical_capture_path_string(
                    value,
                    label=f"{case_id} driver oracle_capture.{key}",
                    anchor_paths=anchor_paths,
                )
        driver_case["oracle_capture"] = normalized_oracle
    summary_oracle_capture = summary_case.get("oracle_capture")
    if isinstance(summary_oracle_capture, Mapping):
        normalized_oracle = dict(summary_oracle_capture)
        for key in ("graph_data_capture_path", "capture_metadata_path"):
            value = normalized_oracle.get(key)
            if isinstance(value, str) and value.strip():
                normalized_oracle[key] = _canonical_capture_path_string(
                    value,
                    label=f"{case_id} summary oracle_capture.{key}",
                    anchor_paths=anchor_paths,
                )
        summary_case["oracle_capture"] = normalized_oracle
    return driver_copy, summary_copy, packet_copy


def _canonicalize_capture_ready_documents_for_materialization(
    *,
    driver_document: Mapping[str, object],
    summary_template: Mapping[str, object],
    overall_capture_packets: Mapping[str, dict[str, object]] | None,
    capture_metadata_by_case: Mapping[str, dict[str, object]] | None,
    anchor_paths_by_case: Mapping[str, tuple[Path, ...]],
) -> tuple[dict[str, object], dict[str, object], dict[str, dict[str, object]] | None]:
    if not overall_capture_packets or not capture_metadata_by_case:
        return dict(driver_document), dict(summary_template), overall_capture_packets

    canonical_driver = dict(driver_document)
    canonical_summary = dict(summary_template)
    canonical_packets = dict(overall_capture_packets)
    for case_id, packet in overall_capture_packets.items():
        capture_metadata = capture_metadata_by_case.get(case_id)
        if capture_metadata is None or not _overall_capture_ready(capture_metadata):
            continue
        (
            canonical_driver,
            canonical_summary,
            canonical_packet,
        ) = _canonicalize_overall_capture_paths(
            driver_document=canonical_driver,
            summary_template=canonical_summary,
            overall_capture_packet=packet,
            case_id=case_id,
            anchor_paths=anchor_paths_by_case.get(case_id, ()),
        )
        canonical_packets[case_id] = canonical_packet
    return canonical_driver, canonical_summary, canonical_packets


def _validate_replay_scaffold_capture_paths(
    scaffold_capture_paths: Mapping[str, object],
    *,
    case_id: str,
    driver_document: Mapping[str, object],
    summary_template: Mapping[str, object],
    overall_capture_packet: Mapping[str, object],
) -> None:
    driver_case = _case_lookup(driver_document, label="driver_document").get(case_id)
    if driver_case is None:
        raise ValueError(f"scaffold.driver must define case_id {case_id}")
    summary_case = _case_lookup(summary_template, label="summary_template").get(case_id)
    if summary_case is None:
        raise ValueError(f"scaffold.summary_template must define case_id {case_id}")

    expected_capture_paths = _mapping_payload(
        overall_capture_packet.get("capture_paths"),
        label="scaffold.overall_capture_packet.capture_paths",
    )
    for capture_label in (
        "stata_stdout",
        "python_stdout",
        "stata_stored_results",
        "python_stored_results",
    ):
        driver_path = _mapping_payload(
            driver_case.get("capture_paths"),
            label=f"{case_id} scaffold.driver.capture_paths",
        ).get(capture_label)
        summary_path = _mapping_payload(
            summary_case.get("capture_paths"),
            label=f"{case_id} scaffold.summary_template.capture_paths",
        ).get(capture_label)
        if not isinstance(driver_path, str) or not driver_path.strip():
            raise ValueError(
                f"scaffold.driver.capture_paths.{capture_label} must be a non-empty string"
            )
        if summary_path != driver_path:
            raise ValueError(
                f"scaffold.summary_template.capture_paths.{capture_label} must match scaffold.driver.capture_paths.{capture_label}"
            )
        expected_capture_paths[capture_label] = driver_path

    actual_capture_paths = _mapping_payload(
        scaffold_capture_paths,
        label="scaffold.capture_paths",
    )
    unexpected_fields = sorted(set(actual_capture_paths) - set(expected_capture_paths))
    if unexpected_fields:
        raise ValueError(
            "scaffold.capture_paths contains unknown fields: "
            + ", ".join(unexpected_fields)
        )
    missing_fields = sorted(set(expected_capture_paths) - set(actual_capture_paths))
    if missing_fields:
        raise ValueError(
            "scaffold.capture_paths is missing required fields: "
            + ", ".join(missing_fields)
        )
    for field_name, expected_value in expected_capture_paths.items():
        actual_value = actual_capture_paths.get(field_name)
        if not isinstance(actual_value, str) or not actual_value.strip():
            raise ValueError(
                f"scaffold.capture_paths.{field_name} must be a non-empty string"
            )
        if actual_value != expected_value:
            raise ValueError(
                f"scaffold.capture_paths.{field_name} must match the embedded replay scaffold documents"
            )


def _capture_doc_is_loadable(document: Mapping[str, object]) -> bool:
    capture_status = document.get("capture_status")
    numeric_payload = document.get("numeric_payload")
    return (
        isinstance(capture_status, str)
        and not capture_status.startswith("blocked-")
        and isinstance(numeric_payload, Mapping)
    )


def _validate_split_capture_document_identity(
    document: Mapping[str, object],
    *,
    case_id: str,
    label: str,
    expected_producer: str,
    expected_capture_kind: str,
) -> dict[str, object]:
    _require_case_id(document, case_id=case_id, label=label)
    producer = document.get("producer")
    if producer != expected_producer:
        raise ValueError(f"{case_id} {label}.producer must equal {expected_producer}")
    capture_kind = document.get("capture_kind")
    if capture_kind != expected_capture_kind:
        raise ValueError(
            f"{case_id} {label}.capture_kind must equal {expected_capture_kind}"
        )
    return {str(key): value for key, value in document.items()}


def _coerce_embedded_path(value: str | Path, *, label: str) -> Path:
    if isinstance(value, Path):
        return value
    if isinstance(value, str) and value.strip():
        return Path(value)
    raise ValueError(f"{label} must be a filesystem path")


def _resolve_embedded_artifact_path(
    value: str | Path,
    *,
    label: str,
    anchor_paths: tuple[Path, ...] = (),
) -> Path:
    artifact_path = _coerce_embedded_path(value, label=label)
    if artifact_path.is_absolute() or artifact_path.exists():
        return artifact_path

    for anchor_path in anchor_paths:
        anchor_dir = anchor_path if anchor_path.is_dir() else anchor_path.parent
        for base_dir in (anchor_dir, *anchor_dir.parents):
            candidate = base_dir / artifact_path
            if candidate.exists():
                return candidate

    return artifact_path


def _resolve_anchor_first_embedded_artifact_path(
    value: str | Path,
    *,
    label: str,
    anchor_paths: tuple[Path, ...] = (),
) -> Path:
    artifact_path = _coerce_embedded_path(value, label=label)
    if artifact_path.is_absolute():
        return artifact_path

    for anchor_path in anchor_paths:
        anchor_dir = anchor_path if anchor_path.is_dir() else anchor_path.parent
        for base_dir in (anchor_dir, *anchor_dir.parents):
            candidate = base_dir / artifact_path
            if candidate.exists():
                return candidate

    if artifact_path.exists():
        return artifact_path
    return artifact_path


def _canonical_python_placeholder_path(case_id: str, *, capture_kind: str) -> Path:
    suffix_by_kind = {
        "stdout": "stdout",
        "stored-results": "stored-results",
    }
    suffix = suffix_by_kind.get(capture_kind)
    if suffix is None:
        raise ValueError(f"unsupported python placeholder capture kind: {capture_kind}")
    return _CANONICAL_PARITY_PYTHON_RESULTS_DIR / f"{case_id}-{suffix}.yaml"


def _allow_stata_fallback_for_python_placeholder(
    path: Path,
    *,
    canonical_placeholder_path: Path | None,
) -> bool:
    if canonical_placeholder_path is None or not path.exists():
        return False

    bundled_placeholder_path = (
        _bundled_prop99_replay_root() / "results/python" / canonical_placeholder_path.name
    )
    for allowed_path in (canonical_placeholder_path, bundled_placeholder_path):
        try:
            if path.resolve() == allowed_path.resolve():
                return True
        except OSError:
            continue

    return False


def _load_split_capture_document(
    path: str | Path,
    *,
    case_id: str,
    label: str,
    expected_producer: str,
    expected_capture_kind: str,
    fallback_path: str | Path | None = None,
    fallback_expected_producer: str | None = None,
    allow_stata_fallback_for_python_placeholder: bool = False,
    canonical_python_placeholder_path: Path | None = None,
    anchor_paths: tuple[Path, ...] = (),
) -> dict[str, object]:
    primary_error: ValueError | None = None
    resolved_path = _resolve_anchor_first_embedded_artifact_path(
        path,
        label=label,
        anchor_paths=anchor_paths,
    )
    try:
        document = load_replay_yaml(resolved_path)
        if _capture_doc_is_loadable(document):
            return _validate_split_capture_document_identity(
                document,
                case_id=case_id,
                label=label,
                expected_producer=expected_producer,
                expected_capture_kind=expected_capture_kind,
            )
        primary_error = ValueError(f"{case_id} {label} must carry a non-blocked numeric payload")
    except ValueError as exc:
        primary_error = exc

    if (
        fallback_path is not None
        and allow_stata_fallback_for_python_placeholder
        and _allow_stata_fallback_for_python_placeholder(
            resolved_path,
            canonical_placeholder_path=canonical_python_placeholder_path,
        )
    ):
        fallback_document = load_replay_yaml(
            _resolve_anchor_first_embedded_artifact_path(
                fallback_path,
                label=f"{label} fallback",
                anchor_paths=anchor_paths,
            )
        )
        if _capture_doc_is_loadable(fallback_document):
            validated_fallback = _validate_split_capture_document_identity(
                fallback_document,
                case_id=case_id,
                label=label,
                expected_producer=(
                    expected_producer
                    if fallback_expected_producer is None
                    else fallback_expected_producer
                ),
                expected_capture_kind=expected_capture_kind,
            )
            validated_fallback[_PYTHON_PLACEHOLDER_FALLBACK_FIELD] = True
            return validated_fallback

    if primary_error is not None:
        raise primary_error
    raise ValueError(f"{case_id} {label} must carry a non-blocked numeric payload")


def _graph_state_from_replay_status(graph_status: str) -> str:
    if graph_status == "graph-exported":
        return "graph-exported"
    if graph_status == "suppressed-by-nograph":
        return "suppressed"
    if graph_status == "graph-attempted-but-error-198":
        return "graph-attempted"
    if graph_status.startswith("blocked-"):
        raise ValueError("capture-ready overall metadata must leave blocked graph status")
    raise ValueError(f"unsupported replay graph status: {graph_status}")


def _overall_capture_ready(case_payload: Mapping[str, object]) -> bool:
    capture_status = case_payload.get("capture_status")
    payload = case_payload.get("metadata_payload")
    if not isinstance(capture_status, str) or capture_status.startswith("blocked-"):
        return False
    if not isinstance(payload, Mapping):
        return False
    return payload.get("capture_ready") is True


def _reject_partial_capture_ready_bundle_overrides(
    *,
    capture_metadata_by_case: Mapping[str, dict[str, object]] | None,
    left_mapping: Mapping[str, dict[str, object]] | None,
    right_mapping: Mapping[str, dict[str, object]] | None,
    left_label: str,
    right_label: str,
) -> None:
    if not capture_metadata_by_case:
        return

    left_cases = left_mapping or {}
    right_cases = right_mapping or {}
    for case_id, capture_metadata in capture_metadata_by_case.items():
        if not _overall_capture_ready(capture_metadata):
            continue
        has_left = case_id in left_cases
        has_right = case_id in right_cases
        if has_left == has_right:
            continue
        raise ValueError(
            f"{case_id} replay comparisons require "
            f"{left_label}[{case_id}] and {right_label}[{case_id}] together or neither"
        )


def _reject_partial_bundle_path_overrides(
    *,
    known_case_ids: set[str],
    capture_metadata_by_case: Mapping[str, dict[str, object]] | None,
    left_mapping: Mapping[str, str | Path] | None,
    right_mapping: Mapping[str, str | Path] | None,
    left_label: str,
    right_label: str,
) -> None:
    left_cases = left_mapping or {}
    right_cases = right_mapping or {}
    capture_ready_case_ids = {
        case_id
        for case_id, capture_metadata in (capture_metadata_by_case or {}).items()
        if _overall_capture_ready(capture_metadata)
    }
    for case_id in known_case_ids:
        if case_id in capture_ready_case_ids:
            continue
        has_left = case_id in left_cases
        has_right = case_id in right_cases
        if has_left == has_right:
            continue
        raise ValueError(
            f"{case_id} replay comparisons require "
            f"{left_label}[{case_id}] and {right_label}[{case_id}] together or neither"
        )


def _validate_overall_capture_verifier_input_contract(
    verifier_input: Mapping[str, object],
    *,
    case_id: str,
) -> None:
    cross_paper_authority = verifier_input.get("cross_paper_appendix_c_authority")
    if not isinstance(cross_paper_authority, Mapping):
        raise ValueError(
            f"{case_id} overall capture verifier input missing cross_paper_appendix_c_authority"
        )
    paper_refs = cross_paper_authority.get("paper_refs")
    if paper_refs != _EXPECTED_APPENDIX_C_PAPER_REFS:
        raise ValueError(
            f"{case_id} paper refs must keep both English and Chinese Appendix C authorities explicit"
        )
    bridge_markers = cross_paper_authority.get("bridge_markers")
    if bridge_markers != _EXPECTED_APPENDIX_C_BRIDGE_MARKERS:
        raise ValueError(
            f"{case_id} bridge markers must keep nu_bar = A * nu and theta^Delta / Sigma^Delta explicit"
        )
    authority_markers = cross_paper_authority.get("authority_markers")
    if authority_markers != _EXPECTED_APPENDIX_C_AUTHORITY_MARKERS:
        raise ValueError(
            f"{case_id} authority markers must keep phi^Delta = 0, "
            "S_pre_hat^Delta <= M, and kappa-free explicit"
        )

    comparison_plan = verifier_input.get("comparison_plan")
    if not isinstance(comparison_plan, Mapping):
        raise ValueError(
            f"{case_id} overall capture verifier input missing comparison_plan"
        )
    stored_results_plan = comparison_plan.get("stored_results")
    if not isinstance(stored_results_plan, Mapping):
        raise ValueError(
            f"{case_id} overall capture verifier input missing stored_results plan"
        )
    protected_non_authoritative = stored_results_plan.get(
        "protected_non_authoritative"
    )
    if protected_non_authoritative != _EXPECTED_PROTECTED_NON_AUTHORITATIVE:
        raise ValueError(
            f"{case_id} stored_results protected_non_authoritative must keep "
            "e(theta) and e(S_pre_se) outside authoritative promotion"
        )
    diagnostic_only_if_present = stored_results_plan.get("diagnostic_only_if_present")
    if not isinstance(diagnostic_only_if_present, Mapping):
        raise ValueError(
            f"{case_id} overall capture verifier input missing diagnostic_only_if_present plan"
        )
    safe_inputs = diagnostic_only_if_present.get("safe_inputs")
    if safe_inputs != _EXPECTED_DIAGNOSTIC_SAFE_INPUTS:
        raise ValueError(
            f"{case_id} stored_results diagnostic_only_if_present.safe_inputs must keep "
            "e(nu), e(delta), and e(Sigma) as the only safe diagnostic inputs"
        )
    shape_requirements = diagnostic_only_if_present.get("shape_requirements")
    if shape_requirements != _EXPECTED_DIAGNOSTIC_SHAPE_REQUIREMENTS:
        raise ValueError(
            f"{case_id} stored_results diagnostic_only_if_present.shape_requirements must keep "
            "the canonical theta^Delta / Sigma^Delta shape checks explicit"
        )
    compatibility_aliases = stored_results_plan.get(
        "compatibility_aliases_if_present"
    )
    if not isinstance(compatibility_aliases, Mapping):
        raise ValueError(
            f"{case_id} overall capture verifier input missing compatibility_aliases_if_present plan"
        )
    for key, expected in _EXPECTED_COMPATIBILITY_ALIAS_PLAN.items():
        if compatibility_aliases.get(key) != expected:
            raise ValueError(
                f"{case_id} stored_results compatibility_aliases_if_present.{key} "
                "must keep BUG-SC-001 ATT aliases diagnostic-only"
            )


def _require_case_id(payload: Mapping[str, object], *, case_id: str, label: str) -> None:
    payload_case_id = payload.get("case_id")
    if not isinstance(payload_case_id, str) or not payload_case_id.strip():
        raise ValueError(f"{label}.case_id must be a non-empty string")
    if payload_case_id != case_id:
        raise ValueError(f"{case_id} {label}.case_id must equal {case_id}")


def _validate_graph_capture_document(
    graph_document: Mapping[str, object],
    *,
    case_id: str,
) -> None:
    _require_case_id(
        graph_document,
        case_id=case_id,
        label="graph-data capture",
    )
    graph_capture_kind = graph_document.get("capture_kind")
    if graph_capture_kind != "graph-data":
        raise ValueError(f"{case_id} graph-data capture must declare capture_kind=graph-data")
    if graph_document.get("producer") != "stata":
        raise ValueError(f"{case_id} graph-data capture.producer must equal stata")
    graph_capture_status = _capture_status_value(
        graph_document.get("capture_status"),
        label=f"{case_id} graph-data capture.capture_status",
    )
    if graph_capture_status.startswith("blocked-"):
        raise ValueError(
            f"{case_id} graph-data capture.capture_status must leave blocked state for capture-ready overall bundles"
        )
    required_fields = graph_document.get("required_fields")
    if required_fields != _EXPECTED_GRAPH_CAPTURE_FIELDS:
        raise ValueError(
            f"{case_id} graph-data capture.required_fields must match canonical graph-data field surface"
        )
    numeric_payload = graph_document.get("numeric_payload")
    if not isinstance(numeric_payload, Mapping):
        raise ValueError(
            f"{case_id} graph-data capture.numeric_payload must be a mapping"
        )
    if set(numeric_payload) != set(_EXPECTED_GRAPH_CAPTURE_FIELDS):
        raise ValueError(
            f"{case_id} graph-data capture.numeric_payload must define the canonical graph-data fields"
        )
    for field_name in ("pre_treatment_series", "post_treatment_series"):
        series_values = numeric_payload.get(field_name)
        if not isinstance(series_values, list):
            raise ValueError(
                f"{case_id} graph-data capture.numeric_payload.{field_name} must be a list"
            )
        for index, value in enumerate(series_values):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(
                    f"{case_id} graph-data capture.numeric_payload.{field_name}[{index}] must be numeric"
                )
    threshold_line_m = numeric_payload.get("threshold_line_m")
    if isinstance(threshold_line_m, bool) or not isinstance(
        threshold_line_m, (int, float)
    ):
        raise ValueError(
            f"{case_id} graph-data capture.numeric_payload.threshold_line_m must be numeric"
        )
    for field_name in ("pass_fail_style", "graph_note"):
        field_value = numeric_payload.get(field_name)
        if not isinstance(field_value, str) or not field_value.strip():
            raise ValueError(
                f"{case_id} graph-data capture.numeric_payload.{field_name} must be a non-empty string"
            )
    graph_status = graph_document.get("graph_status")
    if not isinstance(graph_status, str) or not graph_status.strip():
        raise ValueError(
            f"{case_id} graph-data capture.graph_status must be a non-empty string"
        )
    if (
        graph_status == "graph-attempted-but-error-198"
        and (
            numeric_payload.get("pre_treatment_series")
            or numeric_payload.get("post_treatment_series")
        )
    ):
        raise ValueError(
            f"{case_id} graph-data capture.numeric_payload series must stay empty after Stata graph error 198"
        )


def _graph_data_summary(
    graph_document: Mapping[str, object],
    *,
    stored_results_payload: Mapping[str, object],
    case_id: str,
) -> dict[str, object]:
    numeric_payload = _mapping_payload(
        graph_document.get("numeric_payload"),
        label=f"{case_id} graph-data capture.numeric_payload",
    )
    pre_series = numeric_payload.get("pre_treatment_series")
    post_series = numeric_payload.get("post_treatment_series")
    if not isinstance(pre_series, list) or not isinstance(post_series, list):
        raise ValueError(
            f"{case_id} graph-data capture.numeric_payload series must be lists"
        )
    t_pre = stored_results_payload.get("e(T_pre)")
    t_post = stored_results_payload.get("e(T_post)")
    if isinstance(t_pre, bool) or not isinstance(t_pre, int) or t_pre < 2:
        raise ValueError(
            f"{case_id} stored-results numeric_payload.e(T_pre) must be an integer >= 2"
        )
    if isinstance(t_post, bool) or not isinstance(t_post, int) or t_post < 1:
        raise ValueError(
            f"{case_id} stored-results numeric_payload.e(T_post) must be an integer >= 1"
        )
    expected_pre_points = t_pre - 1
    expected_post_points = t_post
    pre_points_observed = len(pre_series)
    post_points_observed = len(post_series)
    series_complete = (
        pre_points_observed == expected_pre_points
        and post_points_observed == expected_post_points
    )
    graph_status = str(graph_document.get("graph_status"))
    if series_complete:
        reason = "graph sidecar contains the expected pre/post plotting series"
    elif graph_status == "graph-attempted-but-error-198":
        reason = "Stata graph error 198 left exported graph series unavailable"
    else:
        reason = "graph sidecar does not contain the expected pre/post plotting series"
    derived_preview = _derive_graph_event_study_preview(
        stored_results_payload,
        case_id=case_id,
    )
    series_comparison = _compare_graph_series_to_preview(
        pre_series=pre_series,
        post_series=post_series,
        derived_preview=derived_preview,
        series_complete=series_complete,
    )
    return {
        "pre_treatment_points_expected": expected_pre_points,
        "pre_treatment_points_observed": pre_points_observed,
        "post_treatment_points_expected": expected_post_points,
        "post_treatment_points_observed": post_points_observed,
        "series_complete": series_complete,
        "series_match_derived_preview": series_comparison["all_estimates_match"],
        "series_comparison": series_comparison,
        "reason": reason,
        "derived_event_study_preview": derived_preview,
    }


def _finite_number(value: object, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        raise ValueError(f"{label} must be a finite number")
    return numeric_value


def _finite_number_list(value: object, *, label: str) -> list[float]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return [
        _finite_number(item, label=f"{label}[{index}]")
        for index, item in enumerate(value)
    ]


def _finite_square_matrix(value: object, *, label: str, dimension: int) -> list[list[float]]:
    if not isinstance(value, list) or len(value) != dimension:
        raise ValueError(f"{label} must be a square matrix with dimension {dimension}")
    matrix: list[list[float]] = []
    for row_index, row in enumerate(value):
        if not isinstance(row, list) or len(row) != dimension:
            raise ValueError(
                f"{label} must be a square matrix with dimension {dimension}"
            )
        matrix.append(
            [
                _finite_number(item, label=f"{label}[{row_index}][{column_index}]")
                for column_index, item in enumerate(row)
            ]
        )
    return matrix


def _graph_point(
    *,
    period: int,
    estimate: float,
    variance: float,
    n: int,
    z_critical: float,
) -> dict[str, float | int]:
    if variance < 0:
        raise ValueError("graph event-study variance must be nonnegative")
    standard_error = math.sqrt(variance / n)
    return {
        "period": period,
        "estimate": estimate,
        "ci_lower": estimate - z_critical * standard_error,
        "ci_upper": estimate + z_critical * standard_error,
    }


def _preview_estimates(points: object) -> list[float]:
    if not isinstance(points, list):
        raise ValueError("graph preview series must be lists")
    estimates: list[float] = []
    for index, point in enumerate(points):
        if not isinstance(point, Mapping):
            raise ValueError(f"graph preview series[{index}] must be a mapping")
        estimates.append(
            _finite_number(
                point.get("estimate"),
                label=f"graph preview series[{index}].estimate",
            )
        )
    return estimates


def _series_max_abs_diff(left: list[object], right: list[float]) -> float:
    if not left and not right:
        return 0.0
    return max(abs(float(value) - reference) for value, reference in zip(left, right))


def _compare_graph_series_to_preview(
    *,
    pre_series: list[object],
    post_series: list[object],
    derived_preview: Mapping[str, object],
    series_complete: bool,
) -> dict[str, object]:
    if not series_complete:
        return {
            "status": "pending-exported-series",
            "source": "stored-results-reconstruction",
            "tolerance": _GRAPH_SERIES_PREVIEW_ABS_TOL,
            "compared_pre_points": 0,
            "compared_post_points": 0,
            "pre_max_abs_diff": None,
            "post_max_abs_diff": None,
            "all_estimates_match": None,
        }

    pre_preview = _preview_estimates(derived_preview.get("pre_treatment_series"))
    post_preview = _preview_estimates(derived_preview.get("post_treatment_series"))
    if len(pre_series) != len(pre_preview) or len(post_series) != len(post_preview):
        raise ValueError("complete graph sidecar must match derived preview dimensions")
    pre_max_abs_diff = _series_max_abs_diff(pre_series, pre_preview)
    post_max_abs_diff = _series_max_abs_diff(post_series, post_preview)
    all_estimates_match = (
        pre_max_abs_diff <= _GRAPH_SERIES_PREVIEW_ABS_TOL
        and post_max_abs_diff <= _GRAPH_SERIES_PREVIEW_ABS_TOL
    )
    return {
        "status": (
            "estimates-match-derived-preview"
            if all_estimates_match
            else "estimates-differ-from-derived-preview"
        ),
        "source": "stored-results-reconstruction",
        "tolerance": _GRAPH_SERIES_PREVIEW_ABS_TOL,
        "compared_pre_points": len(pre_series),
        "compared_post_points": len(post_series),
        "pre_max_abs_diff": pre_max_abs_diff,
        "post_max_abs_diff": post_max_abs_diff,
        "all_estimates_match": all_estimates_match,
    }


def _derive_graph_event_study_preview(
    stored_results_payload: Mapping[str, object],
    *,
    case_id: str,
) -> dict[str, object]:
    t_pre = stored_results_payload.get("e(T_pre)")
    t_post = stored_results_payload.get("e(T_post)")
    n = stored_results_payload.get("e(N)")
    if isinstance(t_pre, bool) or not isinstance(t_pre, int) or t_pre < 2:
        raise ValueError(
            f"{case_id} stored-results numeric_payload.e(T_pre) must be an integer >= 2"
        )
    if isinstance(t_post, bool) or not isinstance(t_post, int) or t_post < 1:
        raise ValueError(
            f"{case_id} stored-results numeric_payload.e(T_post) must be an integer >= 1"
        )
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ValueError(
            f"{case_id} stored-results numeric_payload.e(N) must be an integer >= 1"
        )
    dimension = (t_pre - 1) + t_post
    nu = _finite_number_list(
        stored_results_payload.get("e(nu)"),
        label=f"{case_id} stored-results numeric_payload.e(nu)",
    )
    delta = _finite_number_list(
        stored_results_payload.get("e(delta)"),
        label=f"{case_id} stored-results numeric_payload.e(delta)",
    )
    if len(nu) != t_pre - 1:
        raise ValueError(
            f"{case_id} stored-results numeric_payload.e(nu) length must equal e(T_pre) - 1"
        )
    if len(delta) != t_post:
        raise ValueError(
            f"{case_id} stored-results numeric_payload.e(delta) length must equal e(T_post)"
        )
    sigma = _finite_square_matrix(
        stored_results_payload.get("e(Sigma)"),
        label=f"{case_id} stored-results numeric_payload.e(Sigma)",
        dimension=dimension,
    )
    alpha = _finite_number(
        stored_results_payload.get("e(alpha)"),
        label=f"{case_id} stored-results numeric_payload.e(alpha)",
    )
    if not 0 < alpha < 1:
        raise ValueError(
            f"{case_id} stored-results numeric_payload.e(alpha) must be between 0 and 1"
        )
    mode = stored_results_payload.get("e(mode)")
    if mode not in {"iterative", "overall"}:
        raise ValueError(
            f"{case_id} stored-results numeric_payload.e(mode) must be iterative or overall"
        )
    z_critical = NormalDist().inv_cdf(1 - alpha / 2)
    pre_points = []
    if mode == "overall":
        cumulative_nu = []
        running_sum = 0.0
        for value in nu:
            running_sum += value
            cumulative_nu.append(running_sum)
        for index, estimate in enumerate(cumulative_nu):
            variance = sum(
                sigma[row][column]
                for row in range(index + 1)
                for column in range(index + 1)
            )
            pre_points.append(
                _graph_point(
                    period=(index + 1) - t_pre,
                    estimate=estimate,
                    variance=variance,
                    n=n,
                    z_critical=z_critical,
                )
            )
    else:
        for index, estimate in enumerate(nu):
            pre_points.append(
                _graph_point(
                    period=(index + 1) - t_pre,
                    estimate=estimate,
                    variance=sigma[index][index],
                    n=n,
                    z_critical=z_critical,
                )
            )
    post_points = []
    for index, estimate in enumerate(delta):
        sigma_index = (t_pre - 1) + index
        post_points.append(
            _graph_point(
                period=index,
                estimate=estimate,
                variance=sigma[sigma_index][sigma_index],
                n=n,
                z_critical=z_critical,
            )
        )
    return {
        "source": "stored-results-reconstruction",
        "mode": mode,
        "pre_treatment_series": pre_points,
        "post_treatment_series": post_points,
    }


def _synthesize_capture_bundle_from_split_docs(
    *,
    case_id: str,
    stdout_document: Mapping[str, object],
    stored_results_document: Mapping[str, object],
    graph_document: Mapping[str, object],
    capture_metadata: Mapping[str, object],
    precapture_contract: Mapping[str, object],
) -> dict[str, object]:
    _require_case_id(stdout_document, case_id=case_id, label="stdout capture")
    _require_case_id(
        stored_results_document,
        case_id=case_id,
        label="stored-results capture",
    )
    _validate_graph_capture_document(graph_document, case_id=case_id)
    stdout_payload = _mapping_payload(
        stdout_document.get("numeric_payload"),
        label=f"{case_id} stdout numeric_payload",
    )
    stored_results_payload = _mapping_payload(
        stored_results_document.get("numeric_payload"),
        label=f"{case_id} stored-results numeric_payload",
    )
    metadata_payload = _mapping_payload(
        capture_metadata.get("metadata_payload"),
        label=f"{case_id} capture_metadata.metadata_payload",
    )
    command_contract = _mapping_payload(
        precapture_contract.get("command_contract"),
        label=f"{case_id} precapture_contract.command_contract",
    )
    graph_status = metadata_payload.get("graph_status")
    if not isinstance(graph_status, str) or not graph_status.strip():
        raise ValueError(f"{case_id} capture-ready overall metadata requires graph_status")
    graph_capture_status = _capture_status_value(
        graph_document.get("capture_status"),
        label=f"{case_id} graph-data capture.capture_status",
    )
    capture_metadata_status = _capture_status_value(
        capture_metadata.get("capture_status"),
        label=f"{case_id} capture_metadata.capture_status",
    )
    if graph_capture_status != capture_metadata_status:
        raise ValueError(
            f"{case_id} graph-data capture.capture_status must match capture metadata capture_status"
        )
    graph_capture_status = graph_document.get("graph_status")
    if graph_capture_status != graph_status:
        raise ValueError(
            f"{case_id} graph-data capture.graph_status must match capture metadata graph_status"
        )

    command = command_contract.get("command")
    if not isinstance(command, str) or not command.strip():
        raise ValueError(f"{case_id} precapture contract must define command_contract.command")

    state = ValidationState(
        data_valid=stored_results_payload["e(data_valid)"],
        phi=stored_results_payload["e(phi)"],
        pretest_pass=stored_results_payload["e(pretest_pass)"],
        case_id=case_id,
    )
    availability = resolve_ci_availability(state)
    snapshot = apply_validation_outcome(seed_result_snapshot(parse_stata_command(command)), state)
    updated = apply_kernel_outputs(
        snapshot,
        availability=availability,
        s_pre=stored_results_payload["e(S_pre)"],
        kappa=stored_results_payload["e(kappa)"],
        f_alpha=stored_results_payload["e(f_alpha)"],
        delta_bar=stored_results_payload["e(delta_bar)"],
        ci_lower=stored_results_payload.get("e(ci_lower)"),
        ci_upper=stored_results_payload.get("e(ci_upper)"),
        ci_conv_lower=stored_results_payload.get("e(ci_conv_lower)"),
        ci_conv_upper=stored_results_payload.get("e(ci_conv_upper)"),
        se_delta_bar=stored_results_payload.get("e(se_delta_bar)"),
        s_pre_se=stored_results_payload.get("e(S_pre_se)"),
        theta=stored_results_payload.get("e(theta)"),
        graph_state=_graph_state_from_replay_status(graph_status),
    )
    stored_exact_fields = (
        updated.replay_contract["stored_results_categories"]["exact"]
        + updated.replay_contract["stored_results_categories"]["unresolved"]
    )
    exact_values = {
        "N": stdout_payload["N"],
        "T": stdout_payload["T"],
        "T_pre": stdout_payload["T_pre"],
        "T_post": stdout_payload["T_post"],
    }
    for field in stored_exact_fields:
        if field not in stored_results_payload:
            raise ValueError(
                f"{case_id} stored-results numeric_payload missing exact field {field}"
            )
        exact_values[field] = stored_results_payload[field]
    bundle = build_replay_capture_bundle(updated, exact_values=exact_values)
    bundle["graph_status"] = str(graph_capture_status)
    bundle["graph_data_summary"] = _graph_data_summary(
        graph_document,
        stored_results_payload=stored_results_payload,
        case_id=case_id,
    )
    return bundle


def _load_capture_ready_overall_bundles(
    *,
    driver_document: Mapping[str, object],
    summary_template: Mapping[str, object],
    case_id: str,
    overall_capture_packet: Mapping[str, object],
    overall_capture_verifier_input: Mapping[str, object],
    precapture_contract: Mapping[str, object],
    capture_metadata: Mapping[str, object],
    promote_authoritative_fields: bool = False,
    allow_python_placeholder_fallback: bool = False,
    anchor_paths: tuple[Path, ...] = (),
) -> dict[str, dict[str, object]]:
    promote_authoritative_fields = _normalize_boolean_flag(
        promote_authoritative_fields,
        label="promote_authoritative_fields",
    )
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("case_id must be a non-empty string")
    if not _overall_capture_ready(capture_metadata):
        raise ValueError(
            f"{case_id} capture-ready overall metadata must define a non-blocked capture_status "
            "and metadata_payload.capture_ready=true"
        )

    (
        driver_document,
        summary_template,
        overall_capture_packet,
    ) = _canonicalize_overall_capture_paths(
        driver_document=driver_document,
        summary_template=summary_template,
        overall_capture_packet=overall_capture_packet,
        case_id=case_id,
        anchor_paths=anchor_paths,
    )

    _validate_overall_capture_verifier_input_contract(
        overall_capture_verifier_input,
        case_id=case_id,
    )
    _require_case_id(overall_capture_packet, case_id=case_id, label="overall_capture_packet")
    _require_case_id(
        overall_capture_verifier_input,
        case_id=case_id,
        label="overall_capture_verifier_input",
    )
    _require_case_id(precapture_contract, case_id=case_id, label="precapture_contract")
    _require_case_id(capture_metadata, case_id=case_id, label="capture_metadata")
    _validate_capture_ready_scaffold_alignment(driver_document, summary_template)

    driver_cases = _case_lookup(driver_document, label="driver_document")
    summary_cases = _case_lookup(summary_template, label="summary_template")
    driver_case = driver_cases.get(case_id)
    if driver_case is None:
        raise ValueError(f"driver_document is missing case_id {case_id}")
    summary_case = summary_cases.get(case_id)
    if summary_case is None:
        raise ValueError(f"summary_template is missing case_id {case_id}")
    _validate_oracle_capture_alignment(
        driver_case,
        summary_case,
        case_id=case_id,
    )

    packet_paths = _require_capture_path_fields(
        overall_capture_packet.get("capture_paths"),
        label=f"{case_id} overall_capture_packet.capture_paths",
        required_fields=("stata_graph_data", "stata_stdout", "stata_stored_results"),
    )
    summary_capture_paths = _require_capture_path_fields(
        summary_case.get("capture_paths"),
        label=f"{case_id} summary_template.capture_paths",
        required_fields=("python_stdout", "python_stored_results"),
    )
    graph_document = load_replay_yaml(
        _resolve_anchor_first_embedded_artifact_path(
            packet_paths["stata_graph_data"],
            label=f"{case_id} overall_capture_packet.capture_paths.stata_graph_data",
            anchor_paths=anchor_paths,
        )
    )
    _validate_graph_capture_document(graph_document, case_id=case_id)

    try:
        stata_stdout_document = _load_split_capture_document(
            packet_paths["stata_stdout"],
            case_id=case_id,
            label="stdout capture",
            expected_producer="stata",
            expected_capture_kind="stdout",
            anchor_paths=anchor_paths,
        )
        stata_stored_results_document = _load_split_capture_document(
            packet_paths["stata_stored_results"],
            case_id=case_id,
            label="stored-results capture",
            expected_producer="stata",
            expected_capture_kind="stored-results",
            anchor_paths=anchor_paths,
        )
        python_stdout_document = _load_split_capture_document(
            summary_capture_paths["python_stdout"],
            case_id=case_id,
            label="python stdout capture",
            expected_producer="python",
            expected_capture_kind="stdout",
            fallback_path=packet_paths["stata_stdout"],
            fallback_expected_producer="stata",
            allow_stata_fallback_for_python_placeholder=allow_python_placeholder_fallback,
            canonical_python_placeholder_path=_canonical_python_placeholder_path(
                case_id,
                capture_kind="stdout",
            ),
            anchor_paths=anchor_paths,
        )
        python_stored_results_document = _load_split_capture_document(
            summary_capture_paths["python_stored_results"],
            case_id=case_id,
            label="python stored-results capture",
            expected_producer="python",
            expected_capture_kind="stored-results",
            fallback_path=packet_paths["stata_stored_results"],
            fallback_expected_producer="stata",
            allow_stata_fallback_for_python_placeholder=allow_python_placeholder_fallback,
            canonical_python_placeholder_path=_canonical_python_placeholder_path(
                case_id,
                capture_kind="stored-results",
            ),
            anchor_paths=anchor_paths,
        )
    except ValueError as exc:
        message = str(exc)
        if any(
            marker in message
            for marker in _SPLIT_CAPTURE_IDENTITY_ERROR_MARKERS
        ):
            raise
        raise ValueError(_capture_ready_overall_loadable_docs_message(case_id)) from exc

    _validate_capture_ready_overall_bundle_metadata(
        driver_case,
        summary_case,
        overall_capture_packet=overall_capture_packet,
        overall_capture_verifier_input=overall_capture_verifier_input,
        capture_metadata=capture_metadata,
        precapture_contract=precapture_contract,
    )

    stata_bundle = _synthesize_capture_bundle_from_split_docs(
        case_id=case_id,
        stdout_document=stata_stdout_document,
        stored_results_document=stata_stored_results_document,
        graph_document=graph_document,
        capture_metadata=capture_metadata,
        precapture_contract=precapture_contract,
    )
    python_bundle = _synthesize_capture_bundle_from_split_docs(
        case_id=case_id,
        stdout_document=python_stdout_document,
        stored_results_document=python_stored_results_document,
        graph_document=graph_document,
        capture_metadata=capture_metadata,
        precapture_contract=precapture_contract,
    )
    python_placeholder_fallback = (
        python_stdout_document.get(_PYTHON_PLACEHOLDER_FALLBACK_FIELD) is True
        or python_stored_results_document.get(_PYTHON_PLACEHOLDER_FALLBACK_FIELD)
        is True
    )
    if python_placeholder_fallback:
        python_bundle["comparison_status"] = "pending-python-implementation"
        python_bundle["comparison_pending_reason"] = (
            "canonical Python split documents are placeholders; Stata fallback "
            "values are scaffold evidence, not Python parity evidence"
        )
    else:
        comparison_status = str(summary_case.get("python_parity_status", ""))
        if comparison_status:
            stata_bundle["comparison_status"] = comparison_status
            python_bundle["comparison_status"] = comparison_status

    if not python_placeholder_fallback:
        from .replay_harness import (
            _populate_overall_capture_summary,
            _promote_capture_ready_overall_summary,
        )

        promoted_driver_case = deepcopy(driver_case)
        promoted_summary_case = deepcopy(summary_case)
        _populate_overall_capture_summary(
            promoted_driver_case,
            promoted_summary_case,
            overall_capture_packet=overall_capture_packet,
            overall_capture_verifier_input=overall_capture_verifier_input,
            capture_metadata=capture_metadata,
            precapture_contract=precapture_contract,
        )
        stata_bundle, python_bundle = _promote_capture_ready_overall_summary(
            promoted_summary_case,
            case_id=case_id,
            verifier_input=overall_capture_verifier_input,
            stata_bundle=stata_bundle,
            python_bundle=python_bundle,
        )

    return {
        "stata_bundle": stata_bundle,
        "python_bundle": python_bundle,
    }


def _flatten_case_planned_fields(
    case_payload: Mapping[str, object],
    *,
    section_name: str,
    label: str,
) -> list[str]:
    section = _mapping_payload(
        case_payload.get(section_name),
        label=f"{label}.{section_name}",
    )
    planned_fields: list[str] = []
    for bucket_name in _EXPECTED_VERDICT_BUCKETS:
        bucket = _mapping_payload(
            section.get(bucket_name),
            label=f"{label}.{section_name}.{bucket_name}",
        )
        raw_fields = bucket.get("planned_fields")
        if not isinstance(raw_fields, list) or any(
            not isinstance(field, str) or not field.strip() for field in raw_fields
        ):
            raise ValueError(
                f"{label}.{section_name}.{bucket_name}.planned_fields must be a list of non-empty strings"
            )
        planned_fields.extend(raw_fields)
    return planned_fields


def _validate_capture_numeric_payload_fields(
    capture_document: Mapping[str, object],
    *,
    planned_fields: list[str],
    label: str,
) -> dict[str, object]:
    numeric_payload = _mapping_payload(
        capture_document.get("numeric_payload"),
        label=f"{label}.numeric_payload",
    )
    missing_fields = [field for field in planned_fields if field not in numeric_payload]
    if missing_fields:
        raise ValueError(
            f"{label}.numeric_payload missing planned fields: "
            + ", ".join(missing_fields)
        )
    extra_fields = [field for field in numeric_payload if field not in planned_fields]
    if extra_fields:
        raise ValueError(
            f"{label}.numeric_payload contains fields outside planned surface: "
            + ", ".join(extra_fields)
        )
    return numeric_payload


def _validate_finite_numeric_payload_fields(
    numeric_payload: Mapping[str, object],
    *,
    fields: tuple[str, ...],
    label: str,
) -> None:
    for field in fields:
        if field not in numeric_payload:
            continue
        value = numeric_payload[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(
                f"{label}.numeric_payload.{field} must be a finite number"
            )
        if not math.isfinite(float(value)):
            raise ValueError(
                f"{label}.numeric_payload.{field} must be a finite number"
            )


def _validate_integer_numeric_payload_fields(
    numeric_payload: Mapping[str, object],
    *,
    fields: tuple[str, ...],
    label: str,
    minimum: int,
) -> None:
    for field in fields:
        if field not in numeric_payload:
            continue
        value = numeric_payload[field]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(
                f"{label}.numeric_payload.{field} must be an integer >= {minimum}"
            )
        if value < minimum:
            raise ValueError(
                f"{label}.numeric_payload.{field} must be an integer >= {minimum}"
            )


def _validate_binary_numeric_payload_fields(
    numeric_payload: Mapping[str, object],
    *,
    fields: tuple[str, ...],
    label: str,
) -> None:
    for field in fields:
        if field not in numeric_payload:
            continue
        value = numeric_payload[field]
        if isinstance(value, bool) or not isinstance(value, int) or value not in (0, 1):
            raise ValueError(
                f"{label}.numeric_payload.{field} must be integer 0 or 1"
            )


def _validate_matching_payload_fields(
    left_payload: Mapping[str, object],
    right_payload: Mapping[str, object],
    *,
    pairs: tuple[tuple[str, str], ...],
    left_label: str,
    right_label: str,
) -> None:
    for left_field, right_field in pairs:
        if left_field not in left_payload or right_field not in right_payload:
            continue
        if left_payload[left_field] != right_payload[right_field]:
            raise ValueError(
                f"{left_label}.numeric_payload.{left_field} must match "
                f"{right_label}.numeric_payload.{right_field}"
            )


def _validate_prop99_window_iter_exact_scalar_payload(
    evidence: Mapping[str, object],
    *,
    callable_name: str,
) -> None:
    stdout_payload = _mapping_payload(
        evidence.get("stdout_numeric_payload"),
        label=f"{callable_name}.stdout_numeric_payload",
    )
    stored_results_payload = _mapping_payload(
        evidence.get("stored_results_numeric_payload"),
        label=f"{callable_name}.stored_results_numeric_payload",
    )
    if stdout_payload.get("pretest_result") != "PASS":
        raise ValueError(
            f"{callable_name} requires stata_stdout numeric_payload pretest_result PASS"
        )
    for field, expected in (
        ("e(is_panel)", 0),
        ("e(p)", 2),
        ("e(alpha)", 0.05),
        ("e(level)", 95),
        ("e(M)", 5),
        ("e(threshold)", 5),
        ("e(sims)", 5000),
        ("e(seed)", 12345),
        ("e(phi)", 0),
        ("e(pretest_pass)", 1),
        ("e(data_valid)", 1),
        ("e(mode)", "iterative"),
    ):
        if stored_results_payload.get(field) != expected:
            raise ValueError(
                f"{callable_name} requires "
                f"stata_stored_results numeric_payload {field} {expected}"
            )


def _validate_prop99_window_iter_stata_split_contract(
    evidence: Mapping[str, object],
    *,
    stata_stdout: Mapping[str, object],
    stata_stored_results: Mapping[str, object],
    callable_name: str,
) -> None:
    if evidence["stdout_capture_status"] != "captured-log-verified":
        raise ValueError(
            f"{callable_name} requires "
            "stata_stdout capture_status captured-log-verified"
        )
    if evidence["stored_results_capture_status"] != "captured-e-snapshot-verified":
        raise ValueError(
            f"{callable_name} requires "
            "stata_stored_results capture_status captured-e-snapshot-verified"
        )
    if stata_stdout.get("source_refs") != [
        "pretest-stata/examples/example_prop99.log",
        "pretest-stata/examples/example_prop99.do",
    ]:
        raise ValueError(
            f"{callable_name} requires "
            "stata_stdout source_refs to match the Prop99 example log/do"
        )
    if stata_stored_results.get("source_refs") != [
        "_bmad-output/test-artifacts/parity/pretest_stored_results_contract.yaml",
        "pretest-stata/pretest.sthlp",
    ]:
        raise ValueError(
            f"{callable_name} requires "
            "stata_stored_results source_refs to match the stored-results contract"
        )
    _validate_prop99_window_iter_exact_scalar_payload(
        evidence,
        callable_name=callable_name,
    )
    for label, document in (
        ("stata_stdout", stata_stdout),
        ("stata_stored_results", stata_stored_results),
    ):
        if document.get("version") != 1:
            raise ValueError(f"{callable_name} requires {label} version 1")
        if document.get("mode") != "iterative":
            raise ValueError(f"{callable_name} requires {label} mode iterative")
        if document.get("sample_window") != [1985, 1995]:
            raise ValueError(
                f"{callable_name} requires {label} sample_window [1985, 1995]"
            )


def load_stata_split_capture_evidence(
    *,
    driver_document: Mapping[str, object],
    summary_template: Mapping[str, object],
    case_id: str,
    stata_stdout: Mapping[str, object],
    stata_stored_results: Mapping[str, object],
    _prop99_contract_callable_name: str = "load_stata_split_capture_evidence()",
) -> dict[str, object]:
    """Load Stata-only split-doc evidence without promoting Python parity."""

    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("case_id must be a non-empty string")
    if case_id == _BUNDLED_PROP99_CASE_ID:
        raise ValueError(
            f"{case_id} uses the capture-ready overall loader; Stata-only split capture evidence is for non-overall cases"
        )
    _validate_capture_ready_scaffold_alignment(driver_document, summary_template)
    driver_cases = _case_lookup(driver_document, label="driver_document")
    summary_cases = _case_lookup(summary_template, label="summary_template")
    driver_case = driver_cases.get(case_id)
    if driver_case is None:
        raise ValueError(f"driver_document is missing case_id {case_id}")
    summary_case = summary_cases.get(case_id)
    if summary_case is None:
        raise ValueError(f"summary_template is missing case_id {case_id}")

    if driver_case.get("mode") == "overall" or summary_case.get("mode") == "overall":
        raise ValueError(
            f"{case_id} uses the capture-ready overall loader; Stata-only split capture evidence is for non-overall cases"
        )

    stdout_document = _validate_split_capture_document_identity(
        stata_stdout,
        case_id=case_id,
        label="stata_stdout",
        expected_producer="stata",
        expected_capture_kind="stdout",
    )
    stored_results_document = _validate_split_capture_document_identity(
        stata_stored_results,
        case_id=case_id,
        label="stata_stored_results",
        expected_producer="stata",
        expected_capture_kind="stored-results",
    )
    if not _capture_doc_is_loadable(stdout_document):
        raise ValueError(f"{case_id} stata_stdout must carry a non-blocked numeric payload")
    if not _capture_doc_is_loadable(stored_results_document):
        raise ValueError(
            f"{case_id} stata_stored_results must carry a non-blocked numeric payload"
        )

    planned_stdout_fields = _flatten_case_planned_fields(
        summary_case,
        section_name="stdout_summary",
        label=f"{case_id} summary_template",
    )
    planned_stored_results_fields = _flatten_case_planned_fields(
        summary_case,
        section_name="stored_results_summary",
        label=f"{case_id} summary_template",
    )
    stdout_planned_from_doc = stdout_document.get("planned_fields")
    if stdout_planned_from_doc != planned_stdout_fields:
        raise ValueError(
            f"{case_id} stata_stdout.planned_fields must match summary_template stdout planned fields"
        )
    stored_planned_from_doc = stored_results_document.get("planned_fields")
    if stored_planned_from_doc != planned_stored_results_fields:
        raise ValueError(
            f"{case_id} stata_stored_results.planned_fields must match summary_template stored-results planned fields"
        )
    stdout_payload = _validate_capture_numeric_payload_fields(
        stdout_document,
        planned_fields=planned_stdout_fields,
        label=f"{case_id} stata_stdout",
    )
    stored_results_payload = _validate_capture_numeric_payload_fields(
        stored_results_document,
        planned_fields=planned_stored_results_fields,
        label=f"{case_id} stata_stored_results",
    )
    _validate_finite_numeric_payload_fields(
        stdout_payload,
        fields=(
            "severity",
            "kappa",
            "critical_value",
            "delta_bar",
            "ci_lower",
            "ci_upper",
            "ci_conv_lower",
            "ci_conv_upper",
        ),
        label=f"{case_id} stata_stdout",
    )
    _validate_finite_numeric_payload_fields(
        stored_results_payload,
        fields=(
            "e(se_delta_bar)",
            "e(S_pre)",
            "e(kappa)",
            "e(f_alpha)",
            "e(delta_bar)",
            "e(ci_lower)",
            "e(ci_upper)",
            "e(ci_conv_lower)",
            "e(ci_conv_upper)",
        ),
        label=f"{case_id} stata_stored_results",
    )
    _validate_integer_numeric_payload_fields(
        stdout_payload,
        fields=("N", "T", "T_pre", "T_post"),
        label=f"{case_id} stata_stdout",
        minimum=1,
    )
    _validate_integer_numeric_payload_fields(
        stored_results_payload,
        fields=(
            "e(N)",
            "e(T)",
            "e(T_pre)",
            "e(T_post)",
            "e(t0)",
            "e(n)",
            "e(p)",
            "e(M)",
            "e(threshold)",
            "e(sims)",
            "e(seed)",
        ),
        label=f"{case_id} stata_stored_results",
        minimum=1,
    )
    _validate_binary_numeric_payload_fields(
        stored_results_payload,
        fields=("e(is_panel)", "e(phi)", "e(pretest_pass)", "e(data_valid)"),
        label=f"{case_id} stata_stored_results",
    )
    _validate_matching_payload_fields(
        stdout_payload,
        stored_results_payload,
        pairs=(
            ("N", "e(N)"),
            ("N", "e(n)"),
            ("T", "e(T)"),
            ("T_pre", "e(T_pre)"),
            ("T_post", "e(T_post)"),
        ),
        left_label=f"{case_id} stata_stdout",
        right_label=f"{case_id} stata_stored_results",
    )
    if (
        "T_pre" in stdout_payload
        and "e(t0)" in stored_results_payload
        and stored_results_payload["e(t0)"] != stdout_payload["T_pre"] + 1
    ):
        raise ValueError(
            f"{case_id} stata_stored_results.numeric_payload.e(t0) must equal "
            "stata_stdout.numeric_payload.T_pre + 1"
        )
    evidence = {
        "case_id": case_id,
        "producer": "stata",
        "evidence_scope": "stata-only-split-doc",
        "comparison_status": "pending-python-implementation",
        "comparison_pending_reason": (
            "Stata split-doc capture is loaded as evidence; Python split-doc capture "
            "is still required before replay parity can be promoted"
        ),
        "mode": summary_case.get("mode"),
        "sample_window": summary_case.get("sample_window"),
        "stdout_capture_status": stdout_document.get("capture_status"),
        "stored_results_capture_status": stored_results_document.get("capture_status"),
        "planned_fields": {
            "stdout": planned_stdout_fields,
            "stored_results": planned_stored_results_fields,
        },
        "stdout_numeric_payload": stdout_payload,
        "stored_results_numeric_payload": stored_results_payload,
    }
    if case_id == _BUNDLED_PROP99_WINDOW_ITER_CASE_ID:
        _validate_prop99_window_iter_stata_split_contract(
            evidence,
            stata_stdout=stata_stdout,
            stata_stored_results=stata_stored_results,
            callable_name=_prop99_contract_callable_name,
        )
    return evidence


def load_stata_split_capture_evidence_from_paths(
    driver_document_path: str | Path,
    summary_template_path: str | Path,
    *,
    case_id: str,
    stata_stdout_path: str | Path,
    stata_stored_results_path: str | Path,
) -> dict[str, object]:
    module_anchor = Path(__file__).resolve()
    driver_path = _resolve_anchor_first_embedded_artifact_path(
        driver_document_path,
        label="driver_document_path",
        anchor_paths=(module_anchor,),
    )
    summary_path = _resolve_anchor_first_embedded_artifact_path(
        summary_template_path,
        label="summary_template_path",
        anchor_paths=(module_anchor,),
    )
    anchor_paths = (driver_path, summary_path, module_anchor)
    stdout_path = _resolve_anchor_first_embedded_artifact_path(
        stata_stdout_path,
        label="stata_stdout_path",
        anchor_paths=anchor_paths,
    )
    stored_results_path = _resolve_anchor_first_embedded_artifact_path(
        stata_stored_results_path,
        label="stata_stored_results_path",
        anchor_paths=anchor_paths,
    )
    stata_stdout = load_replay_yaml(stdout_path)
    stata_stored_results = load_replay_yaml(stored_results_path)
    evidence = load_stata_split_capture_evidence(
        driver_document=load_replay_yaml(driver_path),
        summary_template=load_replay_yaml(summary_path),
        case_id=case_id,
        stata_stdout=stata_stdout,
        stata_stored_results=stata_stored_results,
        _prop99_contract_callable_name="load_stata_split_capture_evidence_from_paths()",
    )
    if case_id == _BUNDLED_PROP99_WINDOW_ITER_CASE_ID:
        _validate_prop99_window_iter_stata_split_contract(
            evidence,
            stata_stdout=stata_stdout,
            stata_stored_results=stata_stored_results,
            callable_name="load_stata_split_capture_evidence_from_paths()",
        )
    return evidence


def load_prop99_window_iter_stata_split_capture_evidence() -> dict[str, object]:
    """Load packaged Stata-only evidence for the Prop99 window iterative case."""

    scaffold = load_prop99_replay_scaffold()
    case_id = _BUNDLED_PROP99_WINDOW_ITER_CASE_ID
    summary_cases = _case_lookup(
        scaffold["summary_template"],
        label="prop99_replay_scaffold.summary_template",
    )
    summary_case = summary_cases.get(case_id)
    if summary_case is None:
        raise ValueError(
            "load_prop99_window_iter_stata_split_capture_evidence() requires "
            f"summary_template to define case_id {case_id}"
        )
    capture_paths = _require_capture_path_fields(
        summary_case.get("capture_paths"),
        label=f"{case_id} summary_template.capture_paths",
        required_fields=("stata_stdout", "stata_stored_results"),
    )
    stata_stdout = load_replay_yaml(capture_paths["stata_stdout"])
    stata_stored_results = load_replay_yaml(capture_paths["stata_stored_results"])
    evidence = load_stata_split_capture_evidence(
        driver_document=scaffold["driver"],
        summary_template=scaffold["summary_template"],
        case_id=case_id,
        stata_stdout=stata_stdout,
        stata_stored_results=stata_stored_results,
        _prop99_contract_callable_name=(
            "load_prop99_window_iter_stata_split_capture_evidence()"
        ),
    )
    _validate_prop99_window_iter_stata_split_contract(
        evidence,
        stata_stdout=stata_stdout,
        stata_stored_results=stata_stored_results,
        callable_name="load_prop99_window_iter_stata_split_capture_evidence()",
    )
    package_root = _bundled_prop99_replay_root().resolve()
    evidence["artifact_paths"] = {
        key: {
            "path": str(Path(capture_paths[key])),
            "exists": Path(capture_paths[key]).is_file(),
            "package_data_path": (
                Path(capture_paths[key]).is_file()
                and Path(capture_paths[key]).resolve().is_relative_to(package_root)
            ),
        }
        for key in ("stata_stdout", "stata_stored_results")
    }
    return evidence


def _autoload_capture_ready_overall_bundles(
    *,
    driver_document: Mapping[str, object],
    summary_template: Mapping[str, object],
    driver_document_path: Path,
    summary_template_path: Path,
    stata_bundles: dict[str, dict[str, object]] | None,
    python_bundles: dict[str, dict[str, object]] | None,
    overall_capture_packets: dict[str, dict[str, object]] | None,
    overall_capture_packet_paths_by_case: Mapping[str, str | Path] | None,
    overall_capture_verifier_inputs: dict[str, dict[str, object]] | None,
    precapture_contracts_by_case: dict[str, dict[str, object]] | None,
    capture_metadata_by_case: dict[str, dict[str, object]] | None,
) -> tuple[dict[str, dict[str, object]] | None, dict[str, dict[str, object]] | None]:
    if not overall_capture_packets or not capture_metadata_by_case:
        return stata_bundles, python_bundles

    driver_cases = _case_lookup(driver_document, label="driver_document")
    summary_cases = _case_lookup(summary_template, label="summary_template")
    updated_stata_bundles = dict(stata_bundles or {})
    updated_python_bundles = dict(python_bundles or {})

    for case_id, capture_metadata in capture_metadata_by_case.items():
        if not _overall_capture_ready(capture_metadata):
            continue
        has_stata_bundle = case_id in updated_stata_bundles
        has_python_bundle = case_id in updated_python_bundles
        if has_stata_bundle != has_python_bundle:
            raise ValueError(
                f"{case_id} capture-ready overall metadata requires "
                f"stata_bundle_paths[{case_id}] and "
                f"python_bundle_paths[{case_id}] together or neither"
            )
        if has_stata_bundle and has_python_bundle:
            continue
        packet = overall_capture_packets.get(case_id)
        verifier_input = (overall_capture_verifier_inputs or {}).get(case_id)
        precapture_contract = (precapture_contracts_by_case or {}).get(case_id)
        driver_case = driver_cases.get(case_id)
        summary_case = summary_cases.get(case_id)
        if (
            packet is None
            or verifier_input is None
            or precapture_contract is None
            or driver_case is None
            or summary_case is None
        ):
            continue

        anchor_paths: tuple[Path, ...] = (driver_document_path, summary_template_path)
        raw_packet_path = (
            None
            if overall_capture_packet_paths_by_case is None
            else overall_capture_packet_paths_by_case.get(case_id)
        )
        if raw_packet_path is not None:
            resolved_packet_path = _resolve_anchor_first_embedded_artifact_path(
                raw_packet_path,
                label=f"overall_capture_packet_paths[{case_id}]",
                anchor_paths=anchor_paths,
            )
            anchor_paths = (*anchor_paths, resolved_packet_path)

        try:
            bundle_pair = _load_capture_ready_overall_bundles(
                driver_document=driver_document,
                summary_template=summary_template,
                case_id=case_id,
                overall_capture_packet=packet,
                overall_capture_verifier_input=verifier_input,
                precapture_contract=precapture_contract,
                capture_metadata=capture_metadata,
                promote_authoritative_fields=True,
                allow_python_placeholder_fallback=True,
                anchor_paths=anchor_paths,
            )
            if case_id not in updated_stata_bundles:
                updated_stata_bundles[case_id] = bundle_pair["stata_bundle"]
            if case_id not in updated_python_bundles:
                updated_python_bundles[case_id] = bundle_pair["python_bundle"]
        except ValueError as exc:
            cause = exc.__cause__
            if isinstance(cause, ValueError) and str(cause).startswith(
                f"{case_id} graph-data capture"
            ):
                raise cause
            if str(exc).startswith(f"{case_id} graph-data capture"):
                raise
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

    return (
        updated_stata_bundles or None,
        updated_python_bundles or None,
    )


def load_capture_ready_overall_bundles_from_paths(
    driver_document_path: str | Path,
    summary_template_path: str | Path,
    *,
    case_id: str,
    overall_capture_packet_path: str | Path,
    overall_capture_verifier_input_path: str | Path,
    precapture_contract_path: str | Path,
    capture_metadata_path: str | Path,
    promote_authoritative_fields: bool = True,
) -> dict[str, dict[str, object]]:
    module_anchor = Path(__file__).resolve()
    driver_path = _resolve_anchor_first_embedded_artifact_path(
        driver_document_path,
        label="driver_document_path",
        anchor_paths=(module_anchor,),
    )
    summary_path = _resolve_anchor_first_embedded_artifact_path(
        summary_template_path,
        label="summary_template_path",
        anchor_paths=(module_anchor,),
    )
    path_anchor_paths = (driver_path, summary_path, module_anchor)
    packet_path = _resolve_anchor_first_embedded_artifact_path(
        overall_capture_packet_path,
        label="overall_capture_packet_path",
        anchor_paths=path_anchor_paths,
    )
    packet_anchor_paths = (packet_path, *path_anchor_paths)
    verifier_input_path = _resolve_anchor_first_embedded_artifact_path(
        overall_capture_verifier_input_path,
        label="overall_capture_verifier_input_path",
        anchor_paths=packet_anchor_paths,
    )
    precapture_path = _resolve_anchor_first_embedded_artifact_path(
        precapture_contract_path,
        label="precapture_contract_path",
        anchor_paths=packet_anchor_paths,
    )
    capture_metadata_path = _resolve_anchor_first_embedded_artifact_path(
        capture_metadata_path,
        label="capture_metadata_path",
        anchor_paths=packet_anchor_paths,
    )
    try:
        return _load_capture_ready_overall_bundles(
            driver_document=load_replay_yaml(driver_path),
            summary_template=load_replay_yaml(summary_path),
            case_id=case_id,
            overall_capture_packet=load_replay_yaml(packet_path),
            overall_capture_verifier_input=load_replay_yaml(verifier_input_path),
            precapture_contract=load_replay_yaml(precapture_path),
            capture_metadata=load_replay_yaml(capture_metadata_path),
            promote_authoritative_fields=promote_authoritative_fields,
            allow_python_placeholder_fallback=True,
            anchor_paths=(driver_path, summary_path, packet_path),
        )
    except ValueError as exc:
        message = str(exc)
        if message.startswith(f"{case_id} capture_metadata."):
            raise ValueError(
                _rewrite_case_scoped_callable_requirement(
                    message,
                    callable_name="load_capture_ready_overall_bundles_from_paths",
                    case_id=case_id,
                )
            ) from exc
        raise


def load_capture_ready_overall_bundles(
    *,
    driver_document: Mapping[str, object],
    summary_template: Mapping[str, object],
    case_id: str,
    overall_capture_packet: Mapping[str, object],
    overall_capture_verifier_input: Mapping[str, object],
    precapture_contract: Mapping[str, object],
    capture_metadata: Mapping[str, object],
    promote_authoritative_fields: bool = True,
) -> dict[str, dict[str, object]]:
    module_anchor = Path(__file__).resolve()
    bundled_root = _bundled_prop99_replay_root()
    repo_root = module_anchor.parents[3]
    try:
        return _load_capture_ready_overall_bundles(
            driver_document=driver_document,
            summary_template=summary_template,
            case_id=case_id,
            overall_capture_packet=overall_capture_packet,
            overall_capture_verifier_input=overall_capture_verifier_input,
            precapture_contract=precapture_contract,
            capture_metadata=capture_metadata,
            promote_authoritative_fields=promote_authoritative_fields,
            allow_python_placeholder_fallback=True,
            anchor_paths=(
                module_anchor,
                Path.cwd(),
                repo_root,
                repo_root / "_bmad-output/test-artifacts/parity",
                bundled_root,
            ),
        )
    except ValueError as exc:
        message = str(exc)
        if message.startswith(f"{case_id} capture_metadata."):
            raise ValueError(
                _rewrite_case_scoped_callable_requirement(
                    message,
                    callable_name="load_capture_ready_overall_bundles",
                    case_id=case_id,
                )
            ) from exc
        raise


def materialize_replay_summary_from_paths(
    driver_document_path: str | Path,
    summary_template_path: str | Path,
    *,
    stata_bundle_paths: Mapping[str, str | Path] | None = None,
    python_bundle_paths: Mapping[str, str | Path] | None = None,
    overall_capture_packet_paths: Mapping[str, str | Path] | None = None,
    overall_capture_verifier_input_paths: Mapping[str, str | Path] | None = None,
    precapture_contract_paths_by_case: Mapping[str, str | Path] | None = None,
    capture_metadata_paths_by_case: Mapping[str, str | Path] | None = None,
) -> dict[str, object]:
    try:
        _validate_capture_companion_paths(
            capture_metadata_paths_by_case,
            precapture_contract_paths_by_case,
            overall_capture_packet_paths=overall_capture_packet_paths,
            overall_capture_verifier_input_paths=overall_capture_verifier_input_paths,
        )
    except ValueError as exc:
        raise ValueError(
            _rewrite_capture_companion_requirement(
                str(exc),
                callable_name="materialize_replay_summary_from_paths",
            )
        ) from exc
    module_anchor = Path(__file__).resolve()
    driver_path = _resolve_embedded_artifact_path(
        driver_document_path,
        label="driver_document_path",
        anchor_paths=(module_anchor,),
    )
    summary_path = _resolve_embedded_artifact_path(
        summary_template_path,
        label="summary_template_path",
        anchor_paths=(module_anchor,),
    )
    payload_anchor_paths = (driver_path, summary_path, module_anchor)
    driver_document = load_replay_yaml(driver_path)
    summary_template = load_replay_yaml(summary_path)
    driver_case_ids = set(_case_lookup(driver_document, label="driver_document"))
    summary_case_ids = set(_case_lookup(summary_template, label="summary_template"))
    stata_bundles = _load_optional_case_payloads(
        stata_bundle_paths,
        label="stata_bundle_paths",
        anchor_paths=payload_anchor_paths,
    )
    python_bundles = _load_optional_case_payloads(
        python_bundle_paths,
        label="python_bundle_paths",
        anchor_paths=payload_anchor_paths,
    )
    overall_capture_packets = _load_optional_case_payloads(
        overall_capture_packet_paths,
        label="overall_capture_packet_paths",
        anchor_paths=payload_anchor_paths,
    )
    overall_capture_verifier_inputs = _load_optional_case_payloads(
        overall_capture_verifier_input_paths,
        label="overall_capture_verifier_input_paths",
        anchor_paths=payload_anchor_paths,
    )
    precapture_contracts_by_case = _load_optional_case_payloads(
        precapture_contract_paths_by_case,
        label="precapture_contract_paths_by_case",
        anchor_paths=payload_anchor_paths,
    )
    capture_metadata_by_case = _load_optional_case_payloads(
        capture_metadata_paths_by_case,
        label="capture_metadata_paths_by_case",
        anchor_paths=payload_anchor_paths,
    )
    capture_ready_anchor_paths_by_case: dict[str, tuple[Path, ...]] = {}
    capture_ready_case_mappings = (
        overall_capture_packets,
        overall_capture_verifier_inputs,
        precapture_contracts_by_case,
        capture_metadata_by_case,
    )
    for mapping in capture_ready_case_mappings:
        if mapping is None:
            continue
        for case_id in mapping:
            if case_id not in driver_case_ids:
                raise ValueError(f"driver_document is missing case_id {case_id}")
            if case_id not in summary_case_ids:
                raise ValueError(f"summary_template is missing case_id {case_id}")
    _reject_partial_capture_ready_bundle_overrides(
        capture_metadata_by_case=capture_metadata_by_case,
        left_mapping=stata_bundles,
        right_mapping=python_bundles,
        left_label="stata_bundle_paths",
        right_label="python_bundle_paths",
    )
    _reject_partial_bundle_path_overrides(
        known_case_ids=summary_case_ids,
        capture_metadata_by_case=capture_metadata_by_case,
        left_mapping=stata_bundle_paths,
        right_mapping=python_bundle_paths,
        left_label="stata_bundle_paths",
        right_label="python_bundle_paths",
    )
    for case_id in sorted(overall_capture_packets or {}):
        if (
            overall_capture_packets is None
            or overall_capture_verifier_inputs is None
            or precapture_contracts_by_case is None
            or capture_metadata_by_case is None
            or case_id not in overall_capture_verifier_inputs
            or case_id not in precapture_contracts_by_case
            or case_id not in capture_metadata_by_case
        ):
            continue
        raw_packet_path = (
            None
            if overall_capture_packet_paths is None
            else overall_capture_packet_paths.get(case_id)
        )
        canonical_anchor_paths = payload_anchor_paths
        if raw_packet_path is not None:
            packet_path = _resolve_anchor_first_embedded_artifact_path(
                raw_packet_path,
                label=f"overall_capture_packet_paths[{case_id}]",
                anchor_paths=payload_anchor_paths,
            )
            canonical_anchor_paths = (packet_path, *payload_anchor_paths)
        (
            driver_document,
            summary_template,
            canonical_packet,
        ) = _canonicalize_overall_capture_paths(
            driver_document=driver_document,
            summary_template=summary_template,
            overall_capture_packet=overall_capture_packets[case_id],
            case_id=case_id,
            anchor_paths=canonical_anchor_paths,
        )
        overall_capture_packets[case_id] = canonical_packet
    stata_bundles, python_bundles = _autoload_capture_ready_overall_bundles(
        driver_document=driver_document,
        summary_template=summary_template,
        driver_document_path=driver_path,
        summary_template_path=summary_path,
        stata_bundles=stata_bundles,
        python_bundles=python_bundles,
        overall_capture_packets=overall_capture_packets,
        overall_capture_packet_paths_by_case=overall_capture_packet_paths,
        overall_capture_verifier_inputs=overall_capture_verifier_inputs,
        precapture_contracts_by_case=precapture_contracts_by_case,
        capture_metadata_by_case=capture_metadata_by_case,
    )
    if overall_capture_packet_paths is not None:
        for case_id, raw_packet_path in overall_capture_packet_paths.items():
            resolved_packet_path = _resolve_anchor_first_embedded_artifact_path(
                raw_packet_path,
                label=f"overall_capture_packet_paths[{case_id}]",
                anchor_paths=payload_anchor_paths,
            )
            capture_ready_anchor_paths_by_case[case_id] = (
                driver_path,
                summary_path,
                resolved_packet_path,
                module_anchor,
            )
    driver_document, summary_template, overall_capture_packets = (
        _canonicalize_capture_ready_documents_for_materialization(
            driver_document=driver_document,
            summary_template=summary_template,
            overall_capture_packets=overall_capture_packets,
            capture_metadata_by_case=capture_metadata_by_case,
            anchor_paths_by_case=capture_ready_anchor_paths_by_case,
        )
    )
    return materialize_replay_summary(
        driver_document,
        summary_template,
        stata_bundles=stata_bundles,
        python_bundles=python_bundles,
        overall_capture_packets=overall_capture_packets,
        overall_capture_verifier_inputs=overall_capture_verifier_inputs,
        precapture_contracts_by_case=precapture_contracts_by_case,
        capture_metadata_by_case=capture_metadata_by_case,
    )


def load_prop99_replay_scaffold() -> dict[str, object]:
    (
        driver_document,
        summary_template,
        overall_capture_packet,
        overall_capture_verifier_input,
        precapture_contract,
        capture_metadata,
        absolute_capture_paths,
    ) = _load_validated_bundled_prop99_replay_documents(
        callable_name="load_prop99_replay_scaffold"
    )
    capture_paths = _validate_existing_artifact_paths(
        {key: str(path) for key, path in absolute_capture_paths.items()},
        label="scaffold.capture_paths",
        callable_name="load_prop99_replay_scaffold",
    )

    return {
        "case_id": _BUNDLED_PROP99_CASE_ID,
        "driver": deepcopy(driver_document),
        "summary_template": deepcopy(summary_template),
        "overall_capture_packet": deepcopy(overall_capture_packet),
        "overall_capture_verifier_input": deepcopy(
            overall_capture_verifier_input
        ),
        "precapture_contract": deepcopy(precapture_contract),
        "capture_metadata": deepcopy(capture_metadata),
        "capture_paths": capture_paths,
    }


def load_prop99_nonoverall_split_capture_inventory() -> dict[str, object]:
    """Report packaged Prop99 non-overall split-doc readiness without promotion."""

    scaffold = load_prop99_replay_scaffold()
    package_root = _bundled_prop99_replay_root()
    summary_cases = _case_lookup(
        scaffold["summary_template"],
        label="prop99_replay_scaffold.summary_template",
    )
    cases: list[dict[str, object]] = []
    totals = {
        "case_count": 0,
        "python_blocked": 0,
        "python_loadable": 0,
        "stata_loadable": 0,
        "stata_pending": 0,
    }

    for case_id in _BUNDLED_PROP99_NONOVERALL_SPLIT_DOC_CASE_IDS:
        summary_case = summary_cases.get(case_id)
        if summary_case is None:
            raise ValueError(
                f"load_prop99_nonoverall_split_capture_inventory() requires "
                f"summary_template to define case_id {case_id}"
            )
        capture_paths = _require_capture_path_fields(
            summary_case.get("capture_paths"),
            label=f"{case_id} summary_template.capture_paths",
            required_fields=(
                "stata_stdout",
                "python_stdout",
                "stata_stored_results",
                "python_stored_results",
            ),
        )
        documents: dict[str, dict[str, object]] = {}
        path_status: dict[str, dict[str, object]] = {}
        for key, expected_producer, expected_kind in (
            ("stata_stdout", "stata", "stdout"),
            ("python_stdout", "python", "stdout"),
            ("stata_stored_results", "stata", "stored-results"),
            ("python_stored_results", "python", "stored-results"),
        ):
            path = Path(capture_paths[key])
            path_status[key] = {
                "path": str(path),
                "exists": path.is_file(),
                "package_data_path": (
                    path.is_file()
                    and path.resolve().is_relative_to(package_root.resolve())
                ),
            }
            documents[key] = _validate_split_capture_document_identity(
                load_replay_yaml(path),
                case_id=case_id,
                label=f"{case_id} {key}",
                expected_producer=expected_producer,
                expected_capture_kind=expected_kind,
            )

        python_loadable = (
            _capture_doc_is_loadable(documents["python_stdout"])
            and _capture_doc_is_loadable(documents["python_stored_results"])
        )
        stata_loadable = (
            _capture_doc_is_loadable(documents["stata_stdout"])
            and _capture_doc_is_loadable(documents["stata_stored_results"])
        )
        stata_exact_scalar_contract_verified = False
        stata_contract_status = "not-applicable"
        if case_id == _BUNDLED_PROP99_WINDOW_ITER_CASE_ID:
            stata_contract_status = "pending-stata-capture"
            if stata_loadable:
                stata_evidence = load_stata_split_capture_evidence(
                    driver_document=scaffold["driver"],
                    summary_template=scaffold["summary_template"],
                    case_id=case_id,
                    stata_stdout=documents["stata_stdout"],
                    stata_stored_results=documents["stata_stored_results"],
                    _prop99_contract_callable_name=(
                        "load_prop99_nonoverall_split_capture_inventory()"
                    ),
                )
                _validate_prop99_window_iter_stata_split_contract(
                    stata_evidence,
                    stata_stdout=documents["stata_stdout"],
                    stata_stored_results=documents["stata_stored_results"],
                    callable_name="load_prop99_nonoverall_split_capture_inventory()",
                )
                stata_exact_scalar_contract_verified = True
                stata_contract_status = "prop99-window-iter-exact-scalar-verified"
        python_blocked = not python_loadable
        totals["case_count"] += 1
        totals["python_loadable"] += int(python_loadable)
        totals["python_blocked"] += int(python_blocked)
        totals["stata_loadable"] += int(stata_loadable)
        totals["stata_pending"] += int(not stata_loadable)

        cases.append(
            {
                "case_id": case_id,
                "mode": summary_case.get("mode"),
                "sample_window": summary_case.get("sample_window"),
                "comparison_status": (
                    "pending-python-implementation"
                    if python_blocked
                    else "ready-for-python-stata-comparison"
                ),
                "comparison_pending_reason": (
                    "Python split-doc capture is blocked; do not promote Stata "
                    "fallback values as Python parity evidence"
                    if python_blocked
                    else None
                ),
                "stata_contract_status": stata_contract_status,
                "path_status": path_status,
                "capture_status": {
                    key: documents[key].get("capture_status")
                    for key in (
                        "stata_stdout",
                        "stata_stored_results",
                        "python_stdout",
                        "python_stored_results",
                    )
                },
                "payload_status": {
                    "stata_stdout_loadable": _capture_doc_is_loadable(
                        documents["stata_stdout"]
                    ),
                    "stata_stored_results_loadable": _capture_doc_is_loadable(
                        documents["stata_stored_results"]
                    ),
                    "python_stdout_loadable": _capture_doc_is_loadable(
                        documents["python_stdout"]
                    ),
                    "python_stored_results_loadable": _capture_doc_is_loadable(
                        documents["python_stored_results"]
                    ),
                    "stata_exact_scalar_contract_verified": (
                        stata_exact_scalar_contract_verified
                    ),
                },
            }
        )

    return {
        "case_count": len(cases),
        "cases": cases,
        "totals": totals,
    }


def load_prop99_overall_auxiliary_scaffold() -> dict[str, object]:
    (
        protected_auxiliary_contract,
        auxiliary_diagnostic_verifier_input,
    ) = _load_bundled_prop99_overall_auxiliary_documents()
    _validate_bundled_prop99_overall_auxiliary_scaffold(
        protected_auxiliary_contract,
        auxiliary_diagnostic_verifier_input,
    )
    artifact_paths = _validate_existing_artifact_paths(
        _bundled_prop99_overall_auxiliary_artifact_paths(),
        label="overall_auxiliary_scaffold.artifact_paths",
        callable_name="load_prop99_overall_auxiliary_scaffold",
    )

    return {
        "artifact_paths": artifact_paths,
        "protected_auxiliary_contract": deepcopy(protected_auxiliary_contract),
        "auxiliary_diagnostic_verifier_input": deepcopy(
            auxiliary_diagnostic_verifier_input
        ),
    }


def _validate_story_packet_auxiliary_scaffold(
    overall_auxiliary_scaffold: Mapping[str, object],
    *,
    callable_name: str,
) -> None:
    protected_auxiliary_contract = _mapping_payload(
        overall_auxiliary_scaffold.get("protected_auxiliary_contract"),
        label="overall_auxiliary_scaffold.protected_auxiliary_contract",
    )
    if (
        protected_auxiliary_contract.get("artifact_id")
        != _BUNDLED_PROP99_AUXILIARY_CONTRACT_ARTIFACT_ID
    ):
        raise ValueError(
            f"{callable_name}() requires "
            "overall_auxiliary_scaffold.protected_auxiliary_contract.artifact_id "
            f"to equal {_BUNDLED_PROP99_AUXILIARY_CONTRACT_ARTIFACT_ID}"
        )
    if (
        protected_auxiliary_contract.get("frontier_id")
        != _BUNDLED_PROP99_AUXILIARY_CONTRACT_FRONTIER_ID
    ):
        raise ValueError(
            f"{callable_name}() requires "
            "overall_auxiliary_scaffold.protected_auxiliary_contract.frontier_id "
            f"to equal {_BUNDLED_PROP99_AUXILIARY_CONTRACT_FRONTIER_ID}"
        )
    if (
        protected_auxiliary_contract.get("status")
        != _BUNDLED_PROP99_AUXILIARY_CONTRACT_STATUS
    ):
        raise ValueError(
            f"{callable_name}() requires "
            "overall_auxiliary_scaffold.protected_auxiliary_contract.status "
            f"to equal {_BUNDLED_PROP99_AUXILIARY_CONTRACT_STATUS}"
        )
    if protected_auxiliary_contract.get("bug_ref") != _BUNDLED_PROP99_AUXILIARY_BUG_REF:
        raise ValueError(
            f"{callable_name}() requires "
            "overall_auxiliary_scaffold.protected_auxiliary_contract.bug_ref "
            f"to equal {_BUNDLED_PROP99_AUXILIARY_BUG_REF}"
        )
    qa_handoff = _mapping_payload(
        protected_auxiliary_contract.get("qa_handoff"),
        label="overall_auxiliary_scaffold.protected_auxiliary_contract.qa_handoff",
    )
    if (
        qa_handoff.get("diagnostic_verifier_input_ref")
        != _BUNDLED_PROP99_AUXILIARY_DIAGNOSTIC_REF
    ):
        raise ValueError(
            f"{callable_name}() requires "
            "overall_auxiliary_scaffold.protected_auxiliary_contract.qa_handoff."
            "diagnostic_verifier_input_ref "
            f"to equal {_BUNDLED_PROP99_AUXILIARY_DIAGNOSTIC_REF}"
        )

    auxiliary_case_specific_expectations = _mapping_payload(
        _mapping_payload(
            overall_auxiliary_scaffold.get("auxiliary_diagnostic_verifier_input"),
            label="overall_auxiliary_scaffold.auxiliary_diagnostic_verifier_input",
        ).get("case_specific_expectations"),
        label="overall_auxiliary_scaffold.auxiliary_diagnostic_verifier_input.case_specific_expectations",
    )
    if auxiliary_case_specific_expectations.get("case_id") != _BUNDLED_PROP99_CASE_ID:
        raise ValueError(
            f"{callable_name}() requires "
            "overall_auxiliary_scaffold.auxiliary_diagnostic_verifier_input.case_specific_expectations.case_id "
            f"to equal {_BUNDLED_PROP99_CASE_ID}"
        )
    _validate_auxiliary_diagnostic_verifier_input_contract(
        _mapping_payload(
            overall_auxiliary_scaffold.get("auxiliary_diagnostic_verifier_input"),
            label="overall_auxiliary_scaffold.auxiliary_diagnostic_verifier_input",
        ),
        callable_name=callable_name,
        label_prefix="overall_auxiliary_scaffold.auxiliary_diagnostic_verifier_input",
    )
    artifact_paths = _mapping_payload(
        overall_auxiliary_scaffold.get("artifact_paths"),
        label="overall_auxiliary_scaffold.artifact_paths",
    )
    expected_artifact_paths = _bundled_prop99_overall_auxiliary_artifact_paths()
    if sorted(artifact_paths) != sorted(expected_artifact_paths):
        raise ValueError(
            f"{callable_name}() requires "
            "overall_auxiliary_scaffold.artifact_paths "
            "to define the canonical auxiliary artifact path keys"
        )
    for field_name, expected_path in expected_artifact_paths.items():
        actual_path = artifact_paths.get(field_name)
        if not isinstance(actual_path, str) or not actual_path.strip():
            raise ValueError(
                f"{callable_name}() requires "
                f"overall_auxiliary_scaffold.artifact_paths.{field_name} "
                "to be a non-empty string"
            )
        if actual_path != expected_path:
            raise ValueError(
                f"{callable_name}() requires "
                f"overall_auxiliary_scaffold.artifact_paths.{field_name} "
                f"to equal {expected_path}"
            )


def _story_packet_artifact_paths(
    replay_scaffold: Mapping[str, object],
    overall_auxiliary_scaffold: Mapping[str, object],
) -> dict[str, str]:
    capture_paths = _mapping_payload(
        replay_scaffold.get("capture_paths"),
        label="replay_scaffold.capture_paths",
    )
    auxiliary_artifact_paths = _mapping_payload(
        overall_auxiliary_scaffold.get("artifact_paths"),
        label="overall_auxiliary_scaffold.artifact_paths",
    )
    scaffold_artifact_paths = (
        _bundled_prop99_story_packet_scaffold_artifact_paths()
    )
    combined_paths = {
        "driver": scaffold_artifact_paths.get("driver"),
        "summary_template": scaffold_artifact_paths.get("summary_template"),
        "overall_capture_packet": scaffold_artifact_paths.get(
            "overall_capture_packet"
        ),
        "overall_capture_verifier_input": scaffold_artifact_paths.get(
            "overall_capture_verifier_input"
        ),
        "precapture_contract": scaffold_artifact_paths.get(
            "precapture_contract"
        ),
        "stata_stdout": capture_paths.get("stata_stdout"),
        "python_stdout": capture_paths.get("python_stdout"),
        "stata_stored_results": capture_paths.get("stata_stored_results"),
        "python_stored_results": capture_paths.get("python_stored_results"),
        "stata_graph_data": capture_paths.get("stata_graph_data"),
        "capture_metadata": capture_paths.get("capture_metadata"),
        "protected_auxiliary_contract": auxiliary_artifact_paths.get(
            "protected_auxiliary_contract"
        ),
        "auxiliary_diagnostic_verifier_input": auxiliary_artifact_paths.get(
            "auxiliary_diagnostic_verifier_input"
        ),
    }
    normalized: dict[str, str] = {}
    for field_name, value in combined_paths.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"story packet artifact_paths.{field_name} must be a non-empty string"
            )
        normalized[field_name] = value
    return normalized


def _validate_story_packet_artifact_paths(
    story_packet: Mapping[str, object],
    *,
    replay_scaffold: Mapping[str, object],
    overall_auxiliary_scaffold: Mapping[str, object],
    callable_name: str,
) -> dict[str, str]:
    artifact_paths = _mapping_payload(
        story_packet.get("artifact_paths"),
        label="story_packet.artifact_paths",
    )
    expected_paths = _story_packet_artifact_paths(
        replay_scaffold,
        overall_auxiliary_scaffold,
    )
    if sorted(artifact_paths) != sorted(
        _CANONICAL_STORY_PACKET_ARTIFACT_PATH_FIELDS
    ):
        raise ValueError(
            f"{callable_name}() requires "
            "story_packet.artifact_paths to define the canonical story packet artifact path keys"
        )
    normalized: dict[str, str] = {}
    for field_name, expected_path in expected_paths.items():
        actual_path = artifact_paths.get(field_name)
        if not isinstance(actual_path, str) or not actual_path.strip():
            raise ValueError(
                f"{callable_name}() requires "
                f"story_packet.artifact_paths.{field_name} "
                "to be a non-empty string"
            )
        if actual_path != expected_path:
            raise ValueError(
                f"{callable_name}() requires "
                f"story_packet.artifact_paths.{field_name} "
                f"to equal {expected_path}"
            )
        normalized[field_name] = actual_path
    return normalized


def load_prop99_replay_story_packet() -> dict[str, object]:
    global _BUNDLED_REPLAY_STORY_PACKET_CACHE
    cache_key = _bundled_replay_story_packet_cache_key()
    if (
        _BUNDLED_REPLAY_STORY_PACKET_CACHE is not None
        and _BUNDLED_REPLAY_STORY_PACKET_CACHE[0] == cache_key
    ):
        return deepcopy(_BUNDLED_REPLAY_STORY_PACKET_CACHE[1])

    replay_scaffold = load_prop99_replay_scaffold()
    _validate_story_packet_replay_scaffold(
        replay_scaffold,
        callable_name="load_prop99_replay_story_packet",
    )
    _validate_story_packet_replay_scaffold_capture_paths(
        replay_scaffold,
        callable_name="load_prop99_replay_story_packet",
    )
    try:
        _validate_replay_scaffold_capture_paths(
            _mapping_payload(
                replay_scaffold.get("capture_paths"),
                label="replay_scaffold.capture_paths",
            ),
            case_id=replay_scaffold["case_id"],
            driver_document=_mapping_payload(
                replay_scaffold.get("driver"),
                label="replay_scaffold.driver",
            ),
            summary_template=_mapping_payload(
                replay_scaffold.get("summary_template"),
                label="replay_scaffold.summary_template",
            ),
            overall_capture_packet=_mapping_payload(
                replay_scaffold.get("overall_capture_packet"),
                label="replay_scaffold.overall_capture_packet",
            ),
        )
    except ValueError as exc:
        raise ValueError(
            _rewrite_scaffold_nested_requirement(
                str(exc),
                callable_name="load_prop99_replay_story_packet",
            )
        ) from exc
    case_id = replay_scaffold["case_id"]
    driver_document = _mapping_payload(
        replay_scaffold.get("driver"),
        label="replay_scaffold.driver",
    )
    summary_template = _mapping_payload(
        replay_scaffold.get("summary_template"),
        label="replay_scaffold.summary_template",
    )
    driver_case = _case_lookup(driver_document, label="replay_scaffold.driver").get(case_id)
    summary_case = _case_lookup(
        summary_template,
        label="replay_scaffold.summary_template",
    ).get(case_id)
    if driver_case is None:
        raise ValueError(
            "load_prop99_replay_story_packet() requires "
            f"replay_scaffold.driver to define case_id {case_id}"
        )
    if summary_case is None:
        raise ValueError(
            "load_prop99_replay_story_packet() requires "
            f"replay_scaffold.summary_template to define case_id {case_id}"
        )
    overall_capture_packet = _mapping_payload(
        replay_scaffold.get("overall_capture_packet"),
        label="replay_scaffold.overall_capture_packet",
    )
    overall_capture_verifier_input = _mapping_payload(
        replay_scaffold.get("overall_capture_verifier_input"),
        label="replay_scaffold.overall_capture_verifier_input",
    )
    capture_metadata = _mapping_payload(
        replay_scaffold.get("capture_metadata"),
        label="replay_scaffold.capture_metadata",
    )
    precapture_contract = _mapping_payload(
        replay_scaffold.get("precapture_contract"),
        label="replay_scaffold.precapture_contract",
    )
    try:
        _validate_overall_capture_verifier_input_contract(
            overall_capture_verifier_input,
            case_id=case_id,
        )
        _validate_capture_ready_overall_bundle_metadata(
            driver_case,
            summary_case,
            overall_capture_packet=overall_capture_packet,
            overall_capture_verifier_input=overall_capture_verifier_input,
            capture_metadata=capture_metadata,
            precapture_contract=precapture_contract,
        )
    except ValueError as exc:
        raise ValueError(
            _rewrite_case_scoped_callable_requirement(
                str(exc),
                callable_name="load_prop99_replay_story_packet",
                case_id=case_id,
            )
        ) from exc
    overall_auxiliary_scaffold = load_prop99_overall_auxiliary_scaffold()
    _validate_story_packet_auxiliary_scaffold(
        overall_auxiliary_scaffold,
        callable_name="load_prop99_replay_story_packet",
    )
    artifact_paths = _story_packet_artifact_paths(
        replay_scaffold,
        overall_auxiliary_scaffold,
    )
    artifact_paths = _validate_existing_artifact_paths(
        artifact_paths,
        label="story_packet.artifact_paths",
        callable_name="load_prop99_replay_story_packet",
    )
    try:
        _validate_story_packet_artifact_paths_against_documents(
            artifact_paths,
            driver_lookup=_case_lookup(
                driver_document,
                label="replay_scaffold.driver",
            ),
            summary_lookup=_case_lookup(
                summary_template,
                label="replay_scaffold.summary_template",
            ),
            overall_capture_packets={case_id: overall_capture_packet},
        )
    except ValueError as exc:
        raise ValueError(
            _rewrite_case_scoped_callable_requirement(
                str(exc),
                callable_name="load_prop99_replay_story_packet",
                case_id=case_id,
            )
        ) from exc
    story_packet = {
        "case_id": replay_scaffold["case_id"],
        "artifact_paths": artifact_paths,
        "replay_scaffold": replay_scaffold,
        "overall_auxiliary_scaffold": overall_auxiliary_scaffold,
    }
    _BUNDLED_REPLAY_STORY_PACKET_CACHE = (cache_key, deepcopy(story_packet))
    return deepcopy(story_packet)


def materialize_replay_summary_from_scaffold(
    scaffold: Mapping[str, object],
) -> dict[str, object]:
    scaffold_mapping = _mapping_payload(scaffold, label="scaffold")

    case_id = scaffold_mapping.get("case_id")
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("scaffold.case_id must be a non-empty string")
    if case_id != _BUNDLED_PROP99_CASE_ID:
        raise ValueError(
            "materialize_replay_summary_from_scaffold() requires "
            f"scaffold.case_id to equal {_BUNDLED_PROP99_CASE_ID}"
        )

    driver_document = deepcopy(
        _mapping_payload(scaffold_mapping.get("driver"), label="scaffold.driver")
    )
    summary_template = deepcopy(
        _mapping_payload(
            scaffold_mapping.get("summary_template"),
            label="scaffold.summary_template",
        )
    )
    overall_capture_packet = deepcopy(
        _mapping_payload(
            scaffold_mapping.get("overall_capture_packet"),
            label="scaffold.overall_capture_packet",
        )
    )
    overall_capture_verifier_input = deepcopy(
        _mapping_payload(
            scaffold_mapping.get("overall_capture_verifier_input"),
            label="scaffold.overall_capture_verifier_input",
        )
    )
    precapture_contract = deepcopy(
        _mapping_payload(
            scaffold_mapping.get("precapture_contract"),
            label="scaffold.precapture_contract",
        )
    )
    capture_metadata = deepcopy(
        _mapping_payload(
            scaffold_mapping.get("capture_metadata"),
            label="scaffold.capture_metadata",
        )
    )
    try:
        _validate_bundled_prop99_replay_scaffold(
            driver_document,
            summary_template,
            overall_capture_packet,
            overall_capture_verifier_input,
            precapture_contract,
            capture_metadata,
        )
    except ValueError as exc:
        message = _normalize_bundled_replay_scaffold_error_message(str(exc))
        raise ValueError(
            _rewrite_scaffold_verifier_input_requirement(
                message,
                callable_name="materialize_replay_summary_from_scaffold",
            )
        ) from exc
    try:
        _validate_replay_scaffold_capture_paths(
            scaffold_mapping.get("capture_paths"),
            case_id=case_id,
            driver_document=driver_document,
            summary_template=summary_template,
            overall_capture_packet=overall_capture_packet,
        )
    except ValueError as exc:
        raise ValueError(
            _rewrite_scaffold_nested_requirement(
                str(exc),
                callable_name="materialize_replay_summary_from_scaffold",
            )
        ) from exc
    _validate_existing_artifact_paths(
        scaffold_mapping.get("capture_paths"),
        label="scaffold.capture_paths",
        callable_name="materialize_replay_summary_from_scaffold",
    )

    try:
        return materialize_replay_summary(
            driver_document,
            summary_template,
            overall_capture_packets={case_id: overall_capture_packet},
            overall_capture_verifier_inputs={
                case_id: overall_capture_verifier_input,
            },
            precapture_contracts_by_case={case_id: precapture_contract},
            capture_metadata_by_case={case_id: capture_metadata},
        )
    except ValueError as exc:
        raise ValueError(
            _rewrite_case_scoped_callable_requirement(
                str(exc),
                callable_name="materialize_replay_summary_from_scaffold",
                case_id=case_id,
            )
        ) from exc


def materialize_replay_summary_from_story_packet(
    story_packet: Mapping[str, object],
) -> dict[str, object]:
    story_packet_mapping = _mapping_payload(story_packet, label="story_packet")
    case_id = story_packet_mapping.get("case_id")
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("story_packet.case_id must be a non-empty string")

    replay_scaffold = deepcopy(
        _mapping_payload(
            story_packet_mapping.get("replay_scaffold"),
            label="story_packet.replay_scaffold",
        )
    )
    if replay_scaffold.get("case_id") != case_id:
        raise ValueError(
            "materialize_replay_summary_from_story_packet() requires "
            f"story_packet.replay_scaffold.case_id to equal {case_id}"
        )
    try:
        _validate_story_packet_replay_scaffold(
            replay_scaffold,
            callable_name="materialize_replay_summary_from_story_packet",
        )
    except ValueError as exc:
        raise ValueError(
            _rewrite_scaffold_verifier_input_requirement(
                str(exc),
                callable_name="materialize_replay_summary_from_story_packet",
            )
        ) from exc
    _validate_story_packet_replay_scaffold_capture_paths(
        replay_scaffold,
        callable_name="materialize_replay_summary_from_story_packet",
    )
    overall_auxiliary_scaffold = _mapping_payload(
        story_packet_mapping.get("overall_auxiliary_scaffold"),
        label="story_packet.overall_auxiliary_scaffold",
    )
    _validate_story_packet_auxiliary_scaffold(
        overall_auxiliary_scaffold,
        callable_name="materialize_replay_summary_from_story_packet",
    )
    story_packet_artifact_paths = _validate_story_packet_artifact_paths(
        story_packet_mapping,
        replay_scaffold=replay_scaffold,
        overall_auxiliary_scaffold=overall_auxiliary_scaffold,
        callable_name="materialize_replay_summary_from_story_packet",
    )
    story_packet_artifact_paths = _validate_existing_artifact_paths(
        story_packet_artifact_paths,
        label="story_packet.artifact_paths",
        callable_name="materialize_replay_summary_from_story_packet",
    )

    scaffold_mapping = _mapping_payload(replay_scaffold, label="replay_scaffold")
    case_id = scaffold_mapping.get("case_id")
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("replay_scaffold.case_id must be a non-empty string")

    driver_document = deepcopy(
        _mapping_payload(
            scaffold_mapping.get("driver"),
            label="replay_scaffold.driver",
        )
    )
    summary_template = deepcopy(
        _mapping_payload(
            scaffold_mapping.get("summary_template"),
            label="replay_scaffold.summary_template",
        )
    )
    overall_capture_packet = deepcopy(
        _mapping_payload(
            scaffold_mapping.get("overall_capture_packet"),
            label="replay_scaffold.overall_capture_packet",
        )
    )
    overall_capture_verifier_input = deepcopy(
        _mapping_payload(
            scaffold_mapping.get("overall_capture_verifier_input"),
            label="replay_scaffold.overall_capture_verifier_input",
        )
    )
    precapture_contract = deepcopy(
        _mapping_payload(
            scaffold_mapping.get("precapture_contract"),
            label="replay_scaffold.precapture_contract",
        )
    )
    capture_metadata = deepcopy(
        _mapping_payload(
            scaffold_mapping.get("capture_metadata"),
            label="replay_scaffold.capture_metadata",
        )
    )
    try:
        _validate_replay_scaffold_capture_paths(
            scaffold_mapping.get("capture_paths"),
            case_id=case_id,
            driver_document=driver_document,
            summary_template=summary_template,
            overall_capture_packet=overall_capture_packet,
        )
    except ValueError as exc:
        raise ValueError(
            _rewrite_scaffold_nested_requirement(
                str(exc),
                callable_name="materialize_replay_summary_from_story_packet",
            )
        ) from exc

    try:
        return materialize_replay_summary(
            driver_document,
            summary_template,
            overall_capture_packets={case_id: overall_capture_packet},
            overall_capture_verifier_inputs={
                case_id: overall_capture_verifier_input,
            },
            precapture_contracts_by_case={case_id: precapture_contract},
            capture_metadata_by_case={case_id: capture_metadata},
            story_packet_artifact_paths=story_packet_artifact_paths,
        )
    except ValueError as exc:
        raise ValueError(
            _rewrite_case_scoped_callable_requirement(
                str(exc),
                callable_name="materialize_replay_summary_from_story_packet",
                case_id=case_id,
            )
        ) from exc


def _rewrite_callable_requirement(
    message: str,
    *,
    callable_name: str,
) -> str:
    marker = "() requires "
    if marker not in message:
        return message
    _, _, requirement = message.partition(marker)
    return f"{callable_name}() requires {requirement}"


def _rewrite_case_scoped_callable_requirement(
    message: str,
    *,
    callable_name: str,
    case_id: str,
) -> str:
    rewritten = _rewrite_callable_requirement(
        message,
        callable_name=callable_name,
    )
    if rewritten != message:
        return rewritten

    prefix = f"{case_id} "
    if message.startswith(prefix):
        return f"{callable_name}() requires {message[len(prefix):]}"
    subject, separator, requirement = message.partition(" must ")
    if separator and subject.strip() and requirement.strip():
        return f"{callable_name}() requires {subject} to {requirement}"
    return message


def _rewrite_scaffold_nested_requirement(
    message: str,
    *,
    callable_name: str,
) -> str:
    rewritten = _rewrite_callable_requirement(
        message,
        callable_name=callable_name,
    )
    if rewritten != message:
        return rewritten
    if message.startswith("scaffold."):
        return f"{callable_name}() requires {message}"
    return message


def _rewrite_scaffold_verifier_input_requirement(
    message: str,
    *,
    callable_name: str,
) -> str:
    rewritten = _rewrite_callable_requirement(
        message,
        callable_name=callable_name,
    )
    requirement_prefix = f"{callable_name}() requires "
    requirement = (
        rewritten[len(requirement_prefix) :]
        if rewritten.startswith(requirement_prefix)
        else rewritten
    )

    prefix = f"{_BUNDLED_PROP99_CASE_ID} "
    if requirement.startswith(prefix):
        requirement = requirement[len(prefix) :]
    if requirement.startswith("overall_capture_verifier_input "):
        requirement = requirement[len("overall_capture_verifier_input ") :]

    replacements = {
        "overall capture verifier input missing cross_paper_appendix_c_authority": (
            "scaffold.overall_capture_verifier_input must define "
            "cross_paper_appendix_c_authority"
        ),
        "paper refs must keep both English and Chinese Appendix C authorities explicit": (
            "scaffold.overall_capture_verifier_input.cross_paper_appendix_c_authority."
            "paper_refs must keep both English and Chinese Appendix C authorities explicit"
        ),
        "bridge markers must keep nu_bar = A * nu and theta^Delta / Sigma^Delta explicit": (
            "scaffold.overall_capture_verifier_input.cross_paper_appendix_c_authority."
            "bridge_markers must keep nu_bar = A * nu and theta^Delta / Sigma^Delta explicit"
        ),
        "authority markers must keep phi^Delta = 0, S_pre_hat^Delta <= M, and kappa-free explicit": (
            "scaffold.overall_capture_verifier_input.cross_paper_appendix_c_authority."
            "authority_markers must keep phi^Delta = 0, S_pre_hat^Delta <= M, and "
            "kappa-free explicit"
        ),
        "overall capture verifier input missing comparison_plan": (
            "scaffold.overall_capture_verifier_input must define comparison_plan"
        ),
        "overall capture verifier input missing stored_results plan": (
            "scaffold.overall_capture_verifier_input.comparison_plan must define "
            "stored_results"
        ),
        "stored_results protected_non_authoritative must keep e(theta) and e(S_pre_se) outside authoritative promotion": (
            "scaffold.overall_capture_verifier_input.comparison_plan.stored_results."
            "protected_non_authoritative must keep e(theta) and e(S_pre_se) outside "
            "authoritative promotion"
        ),
        "overall capture verifier input missing diagnostic_only_if_present plan": (
            "scaffold.overall_capture_verifier_input.comparison_plan.stored_results "
            "must define diagnostic_only_if_present"
        ),
        "stored_results diagnostic_only_if_present.safe_inputs must keep e(nu), e(delta), and e(Sigma) as the only safe diagnostic inputs": (
            "scaffold.overall_capture_verifier_input.comparison_plan.stored_results."
            "diagnostic_only_if_present.safe_inputs must keep e(nu), e(delta), and "
            "e(Sigma) as the only safe diagnostic inputs"
        ),
        "stored_results diagnostic_only_if_present.shape_requirements must keep the canonical theta^Delta / Sigma^Delta shape checks explicit": (
            "scaffold.overall_capture_verifier_input.comparison_plan.stored_results."
            "diagnostic_only_if_present.shape_requirements must keep the canonical "
            "theta^Delta / Sigma^Delta shape checks explicit"
        ),
    }
    rewritten_requirement = replacements.get(requirement, requirement)
    return f"{callable_name}() requires {rewritten_requirement}"


def _rewrite_capture_companion_requirement(
    message: str,
    *,
    callable_name: str,
) -> str:
    rewritten = _rewrite_callable_requirement(
        message,
        callable_name=callable_name,
    )
    if rewritten != message:
        return rewritten

    case_id, separator, requirement = message.partition(" ")
    if not separator or " requires " not in requirement:
        return message
    label, _, companions = requirement.partition(" requires ")
    if not label or not companions:
        return message
    return (
        f"{callable_name}() requires {label}[{case_id}] "
        f"to carry same-case companion paths {companions}"
    )


def _rewrite_packaged_capture_ready_requirement(
    message: str,
    *,
    callable_name: str,
) -> str:
    rewritten = _rewrite_callable_requirement(
        message,
        callable_name=callable_name,
    )
    if rewritten != message:
        return rewritten

    normalized = message
    replacements = (
        ("scaffold.driver.", "driver_document."),
        ("scaffold.summary_template.", "summary_template."),
        ("scaffold.overall_capture_packet.", "overall_capture_packet."),
        ("scaffold.capture_paths.", "packaged_capture_paths."),
        ("scaffold.capture_paths ", "packaged_capture_paths "),
        ("scaffold.driver ", "driver_document "),
        ("scaffold.summary_template ", "summary_template "),
    )
    for source, target in replacements:
        normalized = normalized.replace(source, target)
    return f"{callable_name}() requires {normalized}"


def _capture_ready_overall_loadable_docs_message(
    case_id: str,
    *,
    include_explicit_bundles: bool = False,
) -> str:
    message = f"{case_id} {_CAPTURE_READY_OVERALL_LOADABLE_DOCS_MESSAGE}"
    if include_explicit_bundles:
        return message + " or explicit stata_bundles and python_bundles"
    return message


def materialize_prop99_replay_summary() -> dict[str, object]:
    try:
        return materialize_replay_summary_from_story_packet(
            load_prop99_replay_story_packet()
        )
    except ValueError as exc:
        raise ValueError(
            _rewrite_case_scoped_callable_requirement(
                str(exc),
                callable_name="materialize_prop99_replay_summary",
                case_id=_BUNDLED_PROP99_CASE_ID,
            )
        ) from exc


def load_prop99_capture_ready_overall_bundles(
    *,
    promote_authoritative_fields: bool = True,
) -> dict[str, object]:
    global _BUNDLED_CAPTURE_READY_OVERALL_BUNDLES_CACHE
    promote_authoritative_fields = _normalize_boolean_flag(
        promote_authoritative_fields,
        label="promote_authoritative_fields",
    )
    cache_key = _bundled_capture_ready_overall_bundles_cache_key(
        promote_authoritative_fields=promote_authoritative_fields
    )
    if cache_key in _BUNDLED_CAPTURE_READY_OVERALL_BUNDLES_CACHE:
        return deepcopy(_BUNDLED_CAPTURE_READY_OVERALL_BUNDLES_CACHE[cache_key])
    (
        driver_document,
        summary_template,
        overall_capture_packet,
        overall_capture_verifier_input,
        precapture_contract,
        capture_metadata,
        absolute_capture_paths,
    ) = _load_validated_bundled_prop99_replay_documents(
        callable_name="load_prop99_capture_ready_overall_bundles"
    )
    try:
        _validate_replay_scaffold_capture_paths(
            {key: str(path) for key, path in absolute_capture_paths.items()},
            case_id=_BUNDLED_PROP99_CASE_ID,
            driver_document=driver_document,
            summary_template=summary_template,
            overall_capture_packet=overall_capture_packet,
        )
    except ValueError as exc:
        raise ValueError(
            _rewrite_packaged_capture_ready_requirement(
                str(exc),
                callable_name="load_prop99_capture_ready_overall_bundles",
            )
        ) from exc

    try:
        bundles = _load_capture_ready_overall_bundles(
            driver_document=driver_document,
            summary_template=summary_template,
            case_id=_BUNDLED_PROP99_CASE_ID,
            overall_capture_packet=overall_capture_packet,
            overall_capture_verifier_input=overall_capture_verifier_input,
            precapture_contract=precapture_contract,
            capture_metadata=capture_metadata,
            promote_authoritative_fields=promote_authoritative_fields,
            allow_python_placeholder_fallback=True,
        )
        _BUNDLED_CAPTURE_READY_OVERALL_BUNDLES_CACHE[cache_key] = deepcopy(bundles)
        return bundles
    except ValueError as exc:
        raise ValueError(
            _rewrite_case_scoped_callable_requirement(
                str(exc),
                callable_name="load_prop99_capture_ready_overall_bundles",
                case_id=_BUNDLED_PROP99_CASE_ID,
            )
        ) from exc
