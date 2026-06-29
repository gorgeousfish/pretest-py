from importlib import metadata as importlib_metadata
from importlib import import_module
import os
from pathlib import Path
import tomllib

from .api import PretestCommandSpec, parse_stata_command
from .confidence_intervals import (
    ConfidenceIntervalAvailability,
    compute_ci_half_width,
    resolve_ci_availability,
)
from .covariance import (
    compute_cluster_robust_covariance,
    compute_influence_matrix,
    compute_standard_covariance,
    extract_nu_covariance,
)
from .dgp import (
    DGPConfig,
    compute_true_covariance,
    generate_did_data,
    generate_did_data_from_preset,
)
from .monte_carlo import MonteCarloResult, run_monte_carlo_coverage
from .critical_value import compute_bias_bound, normalize_critical_value
from .data_estimators import (
    compute_pretest_kernel_inputs_from_records,
    compute_pretest_snapshot_from_records,
    load_prop99_window_iter_records_from_csv,
)
from .estimators import (
    compute_kappa_weighted,
    pretest_from_dataframe,
)
from .kappa import compute_kappa
from .pipeline import compute_pretest_snapshot
from .result_schema import (
    PretestResultSnapshot,
)
from .m_sensitivity import MSensitivityResult, compute_m_sensitivity
from .severity import SeverityDecision, classify_pretest, compute_severity
from .severity_se import compute_severity_gradient, compute_severity_se
from .simulation import (
    SimulationCoverageResult,
    compute_critical_value,
    compute_psi,
    compute_section6_violation_path,
    simulate_coverage,
    simulate_coverage_from_covariance,
)
from .validation import (
    DatasetProfile,
    PretestValidationError,
    ValidationContractError,
    ValidationOutcome,
    ValidationState,
    apply_validation_outcome,
    run_validation,
    validate_option_domain,
)


_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_PYPROJECT_PATH = _PACKAGE_ROOT / "pyproject.toml"


def _load_local_project_version() -> str:
    project = tomllib.loads(_PYPROJECT_PATH.read_text(encoding="utf-8"))
    return project["project"]["version"]


def _resolve_package_version() -> str:
    try:
        return importlib_metadata.version("pretest-py")
    except importlib_metadata.PackageNotFoundError:
        return _load_local_project_version()


__version__ = _resolve_package_version()

_LEGACY_HELPER_MODULES = {
    "load_prop99_window_iter_records": "pretest.data_estimators",
    "build_prop99_window_iter_deterministic_split_capture_evidence": "pretest.data_estimators",
    "build_prop99_window_overall_deterministic_split_capture_evidence": "pretest.data_estimators",
    "build_prop99_window_iter_parity_summary": "pretest.data_estimators",
    "build_prop99_python_handoff_summary": "pretest.data_estimators",
    "build_pretest_deterministic_split_capture_evidence": "pretest.data_estimators",
    "load_prop99_window_iter_stata_critical_value_probe": "pretest.data_estimators",
    "load_case_payloads": "pretest.replay_packets",
    "load_replay_yaml": "pretest.replay_packets",
    "materialize_replay_summary": "pretest.replay_harness",
    "populate_replay_case_summary": "pretest.replay_harness",
    "load_prop99_capture_ready_overall_bundles": "pretest.replay_summary",
    "load_prop99_nonoverall_split_capture_inventory": "pretest.replay_summary",
    "load_prop99_overall_auxiliary_scaffold": "pretest.replay_summary",
    "load_prop99_replay_scaffold": "pretest.replay_summary",
    "load_prop99_replay_story_packet": "pretest.replay_summary",
    "load_prop99_window_iter_stata_split_capture_evidence": "pretest.replay_summary",
    "load_capture_ready_overall_bundles": "pretest.replay_summary",
    "load_capture_ready_overall_bundles_from_paths": "pretest.replay_summary",
    "load_stata_split_capture_evidence": "pretest.replay_summary",
    "load_stata_split_capture_evidence_from_paths": "pretest.replay_summary",
    "materialize_prop99_replay_summary": "pretest.replay_summary",
    "materialize_replay_summary_from_scaffold": "pretest.replay_summary",
    "materialize_replay_summary_from_story_packet": "pretest.replay_summary",
    "materialize_replay_summary_from_paths": "pretest.replay_summary",
    "render_event_study_svg": "pretest.plotting",
    "apply_kernel_outputs": "pretest.result_schema",
    "build_replay_capture_bundle": "pretest.result_schema",
    "resolve_replay_graph_status": "pretest.result_schema",
    "resolve_stored_results_categories": "pretest.result_schema",
    "resolve_stdout_categories": "pretest.result_schema",
    "seed_result_snapshot": "pretest.result_schema",
}


def __getattr__(name: str) -> object:
    module_name = _LEGACY_HELPER_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module 'pretest' has no attribute {name!r}")
    if os.environ.get("PRETEST_ENABLE_SOURCE_TREE_HELPERS") != "1":
        raise AttributeError(
            f"module 'pretest' has no public root attribute {name!r}; "
            "set PRETEST_ENABLE_SOURCE_TREE_HELPERS=1 in a source checkout "
            "or import source-tree reference helpers from their explicit submodules"
        )
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


__all__ = [
    "__version__",
    "classify_pretest",
    "compute_bias_bound",
    "compute_ci_half_width",
    "compute_cluster_robust_covariance",
    "compute_m_sensitivity",
    "compute_influence_matrix",
    "compute_kappa",
    "compute_kappa_weighted",
    "compute_pretest_snapshot",
    "compute_pretest_kernel_inputs_from_records",
    "compute_pretest_snapshot_from_records",
    "compute_critical_value",
    "compute_section6_violation_path",
    "compute_severity",
    "compute_severity_gradient",
    "compute_severity_se",
    "compute_standard_covariance",
    "compute_psi",
    "ConfidenceIntervalAvailability",
    "DatasetProfile",
    "MSensitivityResult",
    "extract_nu_covariance",
    "load_prop99_window_iter_records_from_csv",
    "normalize_critical_value",
    "pretest_from_dataframe",
    "PretestCommandSpec",
    "PretestResultSnapshot",
    "PretestValidationError",
    "resolve_ci_availability",
    "run_validation",
    "SeverityDecision",
    "SimulationCoverageResult",
    "simulate_coverage",
    "simulate_coverage_from_covariance",
    "ValidationContractError",
    "validate_option_domain",
    "parse_stata_command",
    "DGPConfig",
    "compute_true_covariance",
    "generate_did_data",
    "generate_did_data_from_preset",
    "MonteCarloResult",
    "run_monte_carlo_coverage",
]
