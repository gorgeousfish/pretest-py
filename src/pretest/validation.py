from __future__ import annotations

from collections.abc import Mapping as MappingABC
import math
from typing import Mapping, Sequence

from ._compat import frozen_slots_dataclass
from .api import PretestCommandSpec
from .options import error_spec
from .result_schema import PretestResultSnapshot

_EXACT_STATE_FIELDS = ("e(phi)", "e(pretest_pass)", "e(data_valid)")
_INVALID_STATE_MISSING_RESULTS = (
    "e(S_pre)",
    "e(f_alpha)",
    "e(ci_lower)",
    "e(ci_upper)",
)
_INVALID_STATE_EXACT_ABSENCE = ("e(ci_lower)", "e(ci_upper)")


def _normalize_binary_flag(
    name: str,
    value: object,
    *,
    allow_none: bool,
) -> int | None:
    suffix = " or None" if allow_none else ""
    if value is None:
        if allow_none:
            return None
        raise ValueError(f"{name} must be 0 or 1{suffix}")
    if isinstance(value, (bool, str, bytes, bytearray)):
        raise ValueError(f"{name} must be 0 or 1{suffix}")

    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be 0 or 1{suffix}") from exc

    if not normalized.is_integer() or int(normalized) not in {0, 1}:
        raise ValueError(f"{name} must be 0 or 1{suffix}")
    return int(normalized)


def _normalize_boolean_flag(
    name: str,
    value: object,
    *,
    default: bool,
) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _normalize_numeric_sequence(
    name: str,
    values: Sequence[object],
) -> tuple[float, ...]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise ValueError(f"{name} must be a non-string sequence of numerics")

    normalized: list[float] = []
    for index, value in enumerate(values):
        if isinstance(value, (str, bytes, bytearray)):
            raise ValueError(f"{name}[{index}] must not be a string-backed numeric")
        if isinstance(value, bool):
            raise ValueError(f"{name}[{index}] must not be a boolean-backed numeric")
        try:
            numeric_value = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{name}[{index}] must be finite") from exc
        if not math.isfinite(numeric_value):
            raise ValueError(f"{name}[{index}] must be finite")
        normalized.append(numeric_value)
    return tuple(normalized)


def _normalize_string_sequence(
    name: str,
    values: Sequence[object],
    *,
    require_unique: bool = True,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise ValueError(f"{name} must be a non-string sequence of strings")

    normalized: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(values):
        if not isinstance(value, str):
            raise ValueError(f"{name}[{index}] must be a string")
        if not value.strip():
            raise ValueError(f"{name}[{index}] must be a non-empty string")
        if value != value.strip():
            raise ValueError(
                f"{name}[{index}] must not contain leading or trailing whitespace"
            )
        if require_unique and value in seen:
            raise ValueError(f"{name} must not contain duplicate entries")
        normalized.append(value)
        seen.add(value)
    return tuple(normalized)


def _normalize_optional_case_id(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("case_id must be a non-empty string")
    if value != value.strip():
        raise ValueError("case_id must be a non-empty string")
    return value


class PretestValidationError(ValueError):
    """Raised when a pre-test option or data domain check fails.

    Carries an integer error code matching the Stata-companion error
    numbering scheme.

    Parameters
    ----------
    code : int
        Numeric error code (e.g., 103, 104, 105, 106, 107, 109).
    message : str
        Human-readable error description.

    Attributes
    ----------
    code : int
        The numeric error code.
    """

    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"Error {code}: {message}")
        self.code = code


@frozen_slots_dataclass
class DatasetProfile:
    """Describes the structure of an input dataset for validation.

    Captures the time-period and treatment-value distributions needed
    to determine whether data satisfies the pre-test requirements.

    Parameters
    ----------
    time_periods : tuple of float
        Observed time period values across all observations.
    treatment_values : tuple of float
        Observed treatment indicator values (should be {0, 1}).
    requires_explicit_treat_time : bool, default False
        Whether the command requires an explicit treat_time argument.
    is_panel : bool, default False
        Whether the data is panel (unit-level) structure.
    has_complete_group_time_support : bool, default True
        Whether all group-time cells are observed.
    missing_group_time_cells : tuple of str, default ()
        Descriptions of missing cells when support is incomplete.
    """

    time_periods: tuple[float, ...]
    treatment_values: tuple[float, ...]
    requires_explicit_treat_time: bool = False
    is_panel: bool = False
    has_complete_group_time_support: bool = True
    missing_group_time_cells: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "time_periods",
            _normalize_numeric_sequence("time_periods", self.time_periods),
        )
        object.__setattr__(
            self,
            "treatment_values",
            _normalize_numeric_sequence("treatment_values", self.treatment_values),
        )
        object.__setattr__(
            self,
            "requires_explicit_treat_time",
            _normalize_boolean_flag(
                "requires_explicit_treat_time",
                self.requires_explicit_treat_time,
                default=False,
            ),
        )
        object.__setattr__(
            self,
            "is_panel",
            _normalize_boolean_flag(
                "is_panel",
                self.is_panel,
                default=False,
            ),
        )
        object.__setattr__(
            self,
            "has_complete_group_time_support",
            _normalize_boolean_flag(
                "has_complete_group_time_support",
                self.has_complete_group_time_support,
                default=True,
            ),
        )
        object.__setattr__(
            self,
            "missing_group_time_cells",
            _normalize_string_sequence(
                "missing_group_time_cells",
                self.missing_group_time_cells,
            ),
        )
        if self.has_complete_group_time_support and self.missing_group_time_cells:
            raise ValueError(
                "missing_group_time_cells must be empty when group-time support is complete"
            )
        if (
            not self.has_complete_group_time_support
            and not self.missing_group_time_cells
        ):
            raise ValueError(
                "missing_group_time_cells must identify at least one missing cell when group-time support is incomplete"
            )

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "DatasetProfile":
        if not isinstance(payload, MappingABC):
            raise ValueError("dataset profile payload must be a mapping")
        return cls(
            time_periods=_normalize_numeric_sequence(
                "time_periods",
                payload.get("time_periods", ()),
            ),
            treatment_values=_normalize_numeric_sequence(
                "treatment_values",
                payload.get("treatment_values", ()),
            ),
            requires_explicit_treat_time=_normalize_boolean_flag(
                "requires_explicit_treat_time",
                payload.get("requires_explicit_treat_time"),
                default=False,
            ),
            is_panel=_normalize_boolean_flag(
                "is_panel",
                payload.get("is_panel"),
                default=False,
            ),
            has_complete_group_time_support=_normalize_boolean_flag(
                "has_complete_group_time_support",
                payload.get("has_complete_group_time_support"),
                default=True,
            ),
            missing_group_time_cells=_normalize_string_sequence(
                "missing_group_time_cells",
                payload.get("missing_group_time_cells", ()),
            ),
        )


@frozen_slots_dataclass
class ValidationState:
    data_valid: int
    phi: int | None
    pretest_pass: int | None
    missing_results: tuple[str, ...] = ()
    exact_state_fields: tuple[str, ...] = _EXACT_STATE_FIELDS
    exact_absence_results: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()
    case_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "data_valid",
            _normalize_binary_flag("data_valid", self.data_valid, allow_none=False),
        )
        object.__setattr__(
            self,
            "phi",
            _normalize_binary_flag("phi", self.phi, allow_none=True),
        )
        object.__setattr__(
            self,
            "pretest_pass",
            _normalize_binary_flag("pretest_pass", self.pretest_pass, allow_none=True),
        )
        object.__setattr__(
            self,
            "missing_results",
            _normalize_string_sequence("missing_results", self.missing_results),
        )
        object.__setattr__(
            self,
            "exact_state_fields",
            _normalize_string_sequence("exact_state_fields", self.exact_state_fields),
        )
        object.__setattr__(
            self,
            "exact_absence_results",
            _normalize_string_sequence(
                "exact_absence_results",
                self.exact_absence_results,
            ),
        )
        object.__setattr__(
            self,
            "issues",
            _normalize_string_sequence(
                "issues",
                self.issues,
            ),
        )
        object.__setattr__(self, "case_id", _normalize_optional_case_id(self.case_id))
        if self.data_valid == 0:
            if self.phi is not None or self.pretest_pass != 0:
                raise ValueError(
                    "invalid data state must keep phi unset and pretest_pass at 0"
                )
            return
        if (self.phi is None) != (self.pretest_pass is None):
            raise ValueError(
                "phi and pretest_pass must either both be set or both be unset"
            )
        if self.phi is None:
            return
        if self.pretest_pass != 1 - self.phi:
            raise ValueError("phi and pretest_pass must remain complementary")

    @classmethod
    def valid(cls, *, case_id: str | None = None) -> "ValidationState":
        return cls(data_valid=1, phi=None, pretest_pass=None, case_id=case_id)

    @classmethod
    def invalid_data(
        cls,
        *,
        issues: Sequence[str] = (),
        case_id: str | None = None,
    ) -> "ValidationState":
        return cls(
            data_valid=0,
            phi=None,
            pretest_pass=0,
            missing_results=_INVALID_STATE_MISSING_RESULTS,
            exact_absence_results=_INVALID_STATE_EXACT_ABSENCE,
            issues=issues,
            case_id=case_id,
        )


ValidationOutcome = ValidationState
ValidationContractError = PretestValidationError


def _raise_option_error(code: int) -> None:
    spec = error_spec(code)
    raise PretestValidationError(spec.code, spec.message)


def _unique_sorted(values: Sequence[float]) -> list[float]:
    return sorted(set(values))


def validate_option_domain(
    spec: PretestCommandSpec,
    *,
    treatment_values: Sequence[int | float] | None = None,
    time_periods: Sequence[int | float] | None = None,
    require_treat_time: bool = False,
    case_id: str | None = None,
) -> ValidationState:
    """Validate command options against observed data domain.

    Convenience wrapper that constructs a DatasetProfile and delegates
    to ``run_validation``. Use when treatment values and time periods
    are available as flat sequences.

    Parameters
    ----------
    spec : PretestCommandSpec
        Parsed command specification.
    treatment_values : sequence of float or None, optional
        Observed treatment indicators.
    time_periods : sequence of float or None, optional
        Observed time period values.
    require_treat_time : bool, default False
        Whether to require an explicit treat_time in the spec.
    case_id : str or None, optional
        Identifier for this validation case.

    Returns
    -------
    ValidationState
        Validation outcome with data_valid, phi, and pretest_pass.

    Raises
    ------
    PretestValidationError
        If a domain constraint is violated.
    """
    profile = DatasetProfile(
        time_periods=_normalize_numeric_sequence(
            "time_periods",
            () if time_periods is None else time_periods,
        ),
        treatment_values=_normalize_numeric_sequence(
            "treatment_values",
            () if treatment_values is None else treatment_values,
        ),
        requires_explicit_treat_time=require_treat_time,
    )
    return run_validation(spec, profile, case_id=case_id)


def run_validation(
    spec: PretestCommandSpec,
    profile: DatasetProfile,
    *,
    case_id: str | None = None,
) -> ValidationState:
    """Run the full pre-test data validation pipeline.

    Checks command-option domains (threshold, p, alpha), treatment
    structure, time-period sufficiency, and group-time cell support.

    Parameters
    ----------
    spec : PretestCommandSpec
        Parsed command specification with threshold, p, alpha, etc.
    profile : DatasetProfile
        Dataset structure profile.
    case_id : str or None, optional
        Identifier for this validation case.

    Returns
    -------
    ValidationState
        Outcome with data_valid = 1 if all checks pass, or
        data_valid = 0 with issues describing failures.

    Raises
    ------
    PretestValidationError
        If an option-domain check fails (codes 103-109).
    """
    if spec.threshold <= 0:
        _raise_option_error(105)
    if spec.p < 1:
        _raise_option_error(106)
    if spec.alpha <= 0 or spec.alpha >= 1:
        _raise_option_error(107)

    unique_treatment = set(profile.treatment_values)
    if not unique_treatment.issubset({0.0, 1.0}) or unique_treatment != {0.0, 1.0}:
        _raise_option_error(103)

    if profile.requires_explicit_treat_time and spec.treat_time is None:
        _raise_option_error(104)

    observed_periods = _unique_sorted(profile.time_periods)
    if len(observed_periods) < 3:
        _raise_option_error(104)

    if spec.treat_time is not None and profile.time_periods:
        if spec.treat_time < observed_periods[0] or spec.treat_time > observed_periods[-1]:
            _raise_option_error(109)
        if spec.treat_time not in observed_periods:
            _raise_option_error(109)
        pre_periods = [
            period
            for period in observed_periods
            if period < spec.treat_time
        ]
        if len(pre_periods) < 2:
            _raise_option_error(104)

    if not profile.has_complete_group_time_support:
        return ValidationState.invalid_data(
            issues=profile.missing_group_time_cells,
            case_id=case_id,
        )

    return ValidationState.valid(case_id=case_id)


def apply_validation_outcome(
    snapshot: PretestResultSnapshot,
    outcome: ValidationState,
) -> PretestResultSnapshot:
    canonical = {
        "scalars": dict(snapshot.canonical["scalars"]),
        "macros": dict(snapshot.canonical["macros"]),
        "matrices": dict(snapshot.canonical["matrices"]),
    }
    replay_contract = dict(snapshot.replay_contract)
    diagnostics = dict(snapshot.diagnostics)

    canonical["scalars"]["data_valid"] = outcome.data_valid
    canonical["scalars"]["phi"] = outcome.phi
    canonical["scalars"]["pretest_pass"] = outcome.pretest_pass

    for result_name in outcome.missing_results:
        scalar_name = result_name[2:-1] if result_name.startswith("e(") else result_name
        if scalar_name in canonical["scalars"]:
            canonical["scalars"][scalar_name] = None

    replay_contract["exact_state_fields"] = list(outcome.exact_state_fields)
    replay_contract["exact_absence_when_invalid"] = list(outcome.exact_absence_results)
    diagnostics["validation"] = {
        "case_id": outcome.case_id,
        "issues": list(outcome.issues),
        "data_valid": outcome.data_valid,
    }

    return PretestResultSnapshot(
        provenance=dict(snapshot.provenance),
        canonical=canonical,
        compatibility=dict(snapshot.compatibility),
        replay_contract=replay_contract,
        graph_status=dict(snapshot.graph_status),
        oracle=dict(snapshot.oracle),
        diagnostics=diagnostics,
    )
