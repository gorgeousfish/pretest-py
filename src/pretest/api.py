from __future__ import annotations

import math
import re

from ._compat import frozen_slots_dataclass
from .options import error_spec

_FLAG_OPTIONS = {"overall", "nograph", "diagnose"}
_VALUE_OPTIONS = {
    "treatment",
    "time",
    "threshold",
    "treat_time",
    "p",
    "alpha",
    "level",
    "cluster",
    "simulate",
    "seed",
}
_OPTION_ALIASES = {
    # Stata syntax marks uppercase letters as the minimum abbreviation, e.g.
    # TREATment(), THREshold(), ALpha(), OVERall, and NOGraph.
    "treat": "treatment",
    "treatm": "treatment",
    "treatme": "treatment",
    "treatmen": "treatment",
    "treatment": "treatment",
    "tre": "treat_time",
    "treat_": "treat_time",
    "treat_t": "treat_time",
    "treat_ti": "treat_time",
    "treat_tim": "treat_time",
    "treat_time": "treat_time",
    "time": "time",
    "thre": "threshold",
    "thres": "threshold",
    "thresh": "threshold",
    "thresho": "threshold",
    "threshol": "threshold",
    "threshold": "threshold",
    "p": "p",
    "al": "alpha",
    "alp": "alpha",
    "alph": "alpha",
    "alpha": "alpha",
    "l": "level",
    "le": "level",
    "lev": "level",
    "leve": "level",
    "level": "level",
    "cl": "cluster",
    "clu": "cluster",
    "clus": "cluster",
    "clust": "cluster",
    "cluste": "cluster",
    "cluster": "cluster",
    "sim": "simulate",
    "simu": "simulate",
    "simul": "simulate",
    "simula": "simulate",
    "simulat": "simulate",
    "simulate": "simulate",
    "seed": "seed",
    "over": "overall",
    "overa": "overall",
    "overal": "overall",
    "overall": "overall",
    "nog": "nograph",
    "nogr": "nograph",
    "nogra": "nograph",
    "nograp": "nograph",
    "nograph": "nograph",
    "diag": "diagnose",
    "diagn": "diagnose",
    "diagno": "diagnose",
    "diagnos": "diagnose",
    "diagnose": "diagnose",
}
_OPTION_PATTERN = re.compile(r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\((?P<value>[^()]*)\)$")
_STATA_VARIABLE_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_STATA_MAX_VARIABLE_NAME_LENGTH = 32


def _split_option_tokens(option_text: str) -> list[str]:
    tokens: list[str] = []
    start: int | None = None
    depth = 0
    for index, character in enumerate(option_text):
        if character.isspace() and depth == 0:
            if start is not None:
                tokens.append(option_text[start:index].strip())
                start = None
            continue
        if start is None:
            start = index
        if character == "(":
            depth += 1
        elif character == ")" and depth > 0:
            depth -= 1
    if start is not None:
        tokens.append(option_text[start:].strip())
    return tokens


def _resolve_option_name(name: str) -> str | None:
    return _OPTION_ALIASES.get(name.lower())


def _parse_command_surface(
    command: str,
) -> tuple[str, str, dict[str, object], float | None, float | None, str]:
    normalized = " ".join(command.strip().split())
    head, separator, option_text = normalized.partition(",")
    if not separator:
        raise ValueError("Expected a Stata-style command with a comma-separated option list.")

    head_tokens = head.split()
    if len(head_tokens) < 2:
        raise ValueError("Expected `pretest depvar` before the option list.")

    raw_cmd = head_tokens[0]
    outcome = head_tokens[1]
    cmd = raw_cmd.lower()
    if cmd != "pretest":
        raise ValueError("Only the `pretest` command is currently supported.")
    head_suffix = head_tokens[2:]
    if head_suffix:
        if head_suffix[0].lower() not in {"if", "in"}:
            raise ValueError("Expected only Stata if/in qualifiers before the option list.")
        in_positions = [
            index for index, token in enumerate(head_suffix) if token.lower() == "in"
        ]
        if head_suffix[0].lower() == "if" and (
            len(head_suffix) == 1 or (in_positions and in_positions[0] == 1)
        ):
            raise ValueError("Stata if qualifier must include an expression.")
        if len(in_positions) > 1:
            raise ValueError("Expected at most one Stata in qualifier before the option list.")
        if in_positions and in_positions[0] == len(head_suffix) - 1:
            raise ValueError("Stata in qualifier must include a range.")
    normalized = f"{cmd} {outcome}"
    if head_suffix:
        normalized = f"{normalized} {' '.join(head_suffix)}"
    if option_text:
        normalized = f"{normalized}, {option_text.strip()}"

    parsed_values: dict[str, object] = {}
    seen_options: set[str] = set()
    alpha_value: float | None = None
    level_value: float | None = None

    for token in _split_option_tokens(option_text):
        lowered = token.lower()
        option_name = _resolve_option_name(lowered)
        if option_name in _FLAG_OPTIONS:
            if option_name in seen_options:
                raise ValueError(f"Option `{option_name}` was specified more than once.")
            seen_options.add(option_name)
            parsed_values[option_name] = True
            continue

        match = _OPTION_PATTERN.fullmatch(token)
        if not match:
            raise ValueError(f"Unrecognized option token: {token}")

        raw_name = match.group("name").lower()
        name = _resolve_option_name(raw_name)
        raw_value = match.group("value")
        if name is None or name not in _VALUE_OPTIONS:
            raise ValueError(f"Unsupported option `{raw_name}`.")
        if name in seen_options:
            raise ValueError(f"Option `{name}` was specified more than once.")
        seen_options.add(name)

        if name in {"treatment", "time", "cluster"}:
            parsed_values[name] = raw_value.strip()
        elif name in {"simulate", "seed"}:
            parsed_values[name] = _parse_int(raw_value, label=f"{name}()")
        elif name == "p":
            parsed_values[name] = _parse_p_float(raw_value)
        else:
            parsed_values[name] = _parse_float(raw_value, label=f"{name}()")

        if name == "alpha":
            alpha_value = parsed_values[name]  # type: ignore[assignment]
        elif name == "level":
            level_value = parsed_values[name]  # type: ignore[assignment]

    missing = [name for name in ("treatment", "time", "threshold") if name not in parsed_values]
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"Missing required options: {missing_text}")

    return cmd, outcome, parsed_values, alpha_value, level_value, normalized


def _format_number(value: float | int) -> str:
    if isinstance(value, bool):
        raise TypeError("Boolean values are not valid numeric options.")
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return format(number, ".15g")


def _format_p_option(value: float | int) -> str:
    number = float(value)
    if number >= 1e10:
        return "1e10"
    return _format_number(value)


def _parse_float(value: str, *, label: str) -> float:
    try:
        return float(value.strip())
    except ValueError as exc:
        raise ValueError(f"{label} must be numeric.") from exc


def _parse_p_float(value: str) -> float:
    normalized = value.strip()
    if normalized == ".":
        return 1e10
    return _parse_float(normalized, label="p()")


def _parse_int(value: str, *, label: str) -> int:
    try:
        return int(value.strip())
    except ValueError as exc:
        raise ValueError(f"{label} must be an integer.") from exc


def _raise_option_domain_error(code: int) -> None:
    raise ValueError(error_spec(code).message)


def _normalize_numeric_option(value: float | int, *, label: str) -> float:
    if isinstance(value, bool) or isinstance(value, str):
        raise ValueError(f"{label} must be numeric.")
    try:
        normalized = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric.") from exc
    if not math.isfinite(normalized):
        raise ValueError(f"{label} must be finite.")
    return normalized


def _normalize_p_option(value: float | int) -> float:
    p = _normalize_numeric_option(value, label="p()")
    if p < 1:
        _raise_option_domain_error(106)
    if p >= 1e10:
        return 1e10
    return p


def _normalize_integer_option(value: float | int, *, label: str) -> int:
    if isinstance(value, bool) or isinstance(value, str):
        raise ValueError(f"{label} must be an integer.")
    try:
        numeric = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer.") from exc
    if not math.isfinite(numeric):
        raise ValueError(f"{label} must be finite.")
    if not numeric.is_integer():
        raise ValueError(f"{label} must be an integer.")
    return int(numeric)


def _normalize_variable_name(
    value: object,
    *,
    label: str,
) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a non-empty variable name.")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} must be a non-empty variable name.")
    if any(character.isspace() for character in normalized):
        raise ValueError(f"{label} must not contain whitespace.")
    if not _STATA_VARIABLE_PATTERN.fullmatch(normalized):
        raise ValueError(f"{label} must be a valid Stata variable name.")
    if len(normalized) > _STATA_MAX_VARIABLE_NAME_LENGTH:
        raise ValueError(
            f"{label} must be at most {_STATA_MAX_VARIABLE_NAME_LENGTH} characters."
        )
    return normalized


def _normalize_command_name(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("cmd must be `pretest`.")
    normalized = value.strip().lower()
    if normalized != "pretest":
        raise ValueError("cmd must be `pretest`.")
    return normalized


def _normalize_raw_cmdline(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("raw_cmdline must start with `pretest `.")
    normalized = " ".join(value.strip().split())
    if not normalized.lower().startswith("pretest "):
        raise ValueError("raw_cmdline must start with `pretest `.")
    normalized = f"pretest {normalized.split(None, 1)[1]}"
    try:
        _, _, _, _, _, canonical = _parse_command_surface(normalized)
    except ValueError:
        return normalized
    return canonical


def _normalize_boolean_flag(
    value: object,
    *,
    label: str,
) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a boolean flag.")
    return value


def _resolve_alpha_level(
    alpha_value: float | None,
    level_value: float | None,
) -> tuple[float, float]:
    if alpha_value is not None:
        alpha_value = _normalize_numeric_option(alpha_value, label="alpha()")
        if alpha_value <= 0 or alpha_value >= 1:
            raise ValueError("alpha() must be in (0, 1)")
    if level_value is not None:
        level_value = _normalize_numeric_option(level_value, label="level()")
        if level_value <= 0 or level_value >= 100:
            raise ValueError("level() must be in (0, 100)")

    if alpha_value is None:
        alpha = round(1 - level_value / 100.0, 12) if level_value is not None else 0.05
    else:
        alpha = alpha_value
    level = round((1 - alpha) * 100.0, 10)
    return alpha, level


def _normalize_constructor_alpha_level(
    alpha_value: float,
    level_value: float,
) -> tuple[float, float]:
    alpha = _normalize_numeric_option(alpha_value, label="alpha()")
    if alpha <= 0 or alpha >= 1:
        _raise_option_domain_error(107)

    level = _normalize_numeric_option(level_value, label="level()")
    if level <= 0 or level >= 100:
        raise ValueError("level() must be in (0, 100)")

    if not _surface_numbers_match(alpha, 0.05):
        return alpha, round((1 - alpha) * 100.0, 10)
    if not _surface_numbers_match(level, 95.0):
        return round(1 - level / 100.0, 12), level
    return alpha, level


def _surface_numbers_match(left: float | None, right: float | None) -> bool:
    if left is None or right is None:
        return left is right
    return math.isclose(left, right, rel_tol=0.0, abs_tol=1e-10)


def _raw_cmdline_matches_spec(raw_cmdline: str, spec: "PretestCommandSpec") -> bool:
    try:
        cmd, outcome, parsed_values, alpha_value, level_value, _ = _parse_command_surface(
            raw_cmdline
        )
        alpha, level = _resolve_alpha_level(alpha_value, level_value)
        threshold = _normalize_numeric_option(parsed_values["threshold"], label="threshold()")
        if threshold <= 0:
            _raise_option_domain_error(105)

        p = _normalize_p_option(parsed_values.get("p", 2.0))

        if alpha <= 0 or alpha >= 1:
            _raise_option_domain_error(107)

        simulate = int(parsed_values.get("simulate", 5000))
        if simulate < 100:
            _raise_option_domain_error(110)

        return (
            cmd == spec.cmd
            and _normalize_variable_name(outcome, label="outcome") == spec.outcome
            and _normalize_variable_name(
                parsed_values["treatment"],
                label="treatment()",
            )
            == spec.treatment
            and _normalize_variable_name(parsed_values["time"], label="time()") == spec.time
            and _surface_numbers_match(threshold, spec.threshold)
            and _surface_numbers_match(
                _normalize_numeric_option(
                    parsed_values["treat_time"],
                    label="treat_time()",
                )
                if "treat_time" in parsed_values
                else None,
                spec.treat_time,
            )
            and _surface_numbers_match(p, spec.p)
            and _surface_numbers_match(alpha, spec.alpha)
            and _surface_numbers_match(level, spec.level)
            and (
                _normalize_variable_name(
                    parsed_values["cluster"],
                    label="cluster()",
                )
                if "cluster" in parsed_values
                else None
            )
            == spec.cluster
            and bool(parsed_values.get("overall", False)) is spec.overall
            and bool(parsed_values.get("nograph", False)) is spec.nograph
            and simulate == spec.simulate
            and int(parsed_values.get("seed", 12345)) == spec.seed
            and bool(parsed_values.get("diagnose", False)) is spec.diagnose
        )
    except ValueError:
        return False


@frozen_slots_dataclass
class PretestCommandSpec:
    """Canonical specification of a pretest command invocation.

    Encodes the validated and normalized parameters for a conditional
    extrapolation pre-test, including the violation threshold M, norm
    exponent p, significance level alpha, treatment time, cluster variable,
    and simulation settings.

    Instances are typically constructed via :func:`parse_stata_command`
    from a Stata-style command string, but can also be created directly
    for programmatic workflows.

    Parameters
    ----------
    outcome : str
        Name of the outcome variable.
    treatment : str
        Name of the binary treatment indicator.
    time : str
        Name of the time-period variable.
    threshold : float
        Positive violation threshold M > 0.
    treat_time : float or None
        Treatment onset time. None for auto-detection.
    p : float
        Severity norm exponent (p >= 1). Default 2.0.
    alpha : float
        Significance level for the pre-test. Default 0.05.
    level : float
        Confidence level for the interval. Default 95.0.
    cluster : str or None
        Cluster variable name for cluster-robust inference.
    overall : bool
        Whether to use overall (cumulative) mode.
    simulate : int
        Number of Monte Carlo draws for critical value. Default 5000.
    seed : int
        Random seed for simulation reproducibility.
    nograph : bool
        Suppress event-study plot generation.
    diagnose : bool
        Enable diagnostic output.
    """
    outcome: str
    treatment: str
    time: str
    threshold: float
    cmd: str = "pretest"
    raw_cmdline: str | None = None
    treat_time: float | None = None
    p: float = 2.0
    alpha: float = 0.05
    level: float = 95.0
    cluster: str | None = None
    overall: bool = False
    nograph: bool = False
    simulate: int = 5000
    seed: int = 12345
    diagnose: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "cmd", _normalize_command_name(self.cmd))
        object.__setattr__(
            self,
            "raw_cmdline",
            _normalize_raw_cmdline(self.raw_cmdline),
        )
        object.__setattr__(
            self,
            "outcome",
            _normalize_variable_name(self.outcome, label="outcome"),
        )
        object.__setattr__(
            self,
            "treatment",
            _normalize_variable_name(self.treatment, label="treatment()"),
        )
        object.__setattr__(
            self,
            "time",
            _normalize_variable_name(self.time, label="time()"),
        )
        if self.cluster is not None:
            object.__setattr__(
                self,
                "cluster",
                _normalize_variable_name(self.cluster, label="cluster()"),
            )
        object.__setattr__(
            self,
            "overall",
            _normalize_boolean_flag(self.overall, label="overall"),
        )
        object.__setattr__(
            self,
            "nograph",
            _normalize_boolean_flag(self.nograph, label="nograph"),
        )
        object.__setattr__(
            self,
            "diagnose",
            _normalize_boolean_flag(self.diagnose, label="diagnose"),
        )

        threshold = _normalize_numeric_option(self.threshold, label="threshold()")
        if threshold <= 0:
            _raise_option_domain_error(105)
        object.__setattr__(self, "threshold", threshold)

        if self.treat_time is not None:
            object.__setattr__(
                self,
                "treat_time",
                _normalize_numeric_option(self.treat_time, label="treat_time()"),
            )

        p = _normalize_p_option(self.p)
        object.__setattr__(self, "p", p)

        alpha, level = _normalize_constructor_alpha_level(self.alpha, self.level)
        object.__setattr__(self, "alpha", alpha)
        object.__setattr__(self, "level", level)

        simulate = _normalize_integer_option(self.simulate, label="simulate()")
        if simulate < 100:
            _raise_option_domain_error(110)
        object.__setattr__(self, "simulate", simulate)

        seed = _normalize_integer_option(self.seed, label="seed()")
        object.__setattr__(self, "seed", seed)

        if self.raw_cmdline is not None and not _raw_cmdline_matches_spec(
            self.raw_cmdline,
            self,
        ):
            raise ValueError("raw_cmdline must match the canonical pretest command surface.")

    @property
    def mode(self) -> str:
        return "overall" if self.overall else "iterative"

    @property
    def cmdline(self) -> str:
        return self.raw_cmdline or self.to_command_line()

    def to_command_line(self) -> str:
        options = [
            f"treatment({self.treatment})",
            f"time({self.time})",
            f"threshold({_format_number(self.threshold)})",
        ]
        if self.treat_time is not None:
            options.append(f"treat_time({_format_number(self.treat_time)})")
        if self.p != 2.0:
            options.append(f"p({_format_p_option(self.p)})")
        if self.alpha != 0.05:
            options.append(f"alpha({_format_number(self.alpha)})")
        elif self.level != 95.0:
            options.append(f"level({_format_number(self.level)})")
        if self.cluster:
            options.append(f"cluster({self.cluster})")
        if self.overall:
            options.append("overall")
        if self.nograph:
            options.append("nograph")
        if self.simulate != 5000:
            options.append(f"simulate({self.simulate})")
        if self.seed != 12345:
            options.append(f"seed({self.seed})")
        if self.diagnose:
            options.append("diagnose")
        return f"{self.cmd} {self.outcome}, " + " ".join(options)


def parse_stata_command(command: str) -> PretestCommandSpec:
    cmd, outcome, parsed_values, alpha_value, level_value, normalized = _parse_command_surface(
        command
    )
    alpha, level = _resolve_alpha_level(alpha_value, level_value)
    threshold = _normalize_numeric_option(parsed_values["threshold"], label="threshold()")
    if threshold <= 0:
        _raise_option_domain_error(105)

    p = _normalize_p_option(parsed_values.get("p", 2.0))

    if alpha <= 0 or alpha >= 1:
        _raise_option_domain_error(107)

    simulate = int(parsed_values.get("simulate", 5000))
    if simulate < 100:
        _raise_option_domain_error(110)

    return PretestCommandSpec(
        cmd=cmd,
        outcome=outcome,
        treatment=str(parsed_values["treatment"]),
        time=str(parsed_values["time"]),
        threshold=threshold,
        raw_cmdline=normalized,
        treat_time=(
            _normalize_numeric_option(
                parsed_values["treat_time"],
                label="treat_time()",
            )
            if "treat_time" in parsed_values
            else None
        ),
        p=p,
        alpha=alpha,
        level=level,
        cluster=str(parsed_values["cluster"]) if "cluster" in parsed_values else None,
        overall=bool(parsed_values.get("overall", False)),
        nograph=bool(parsed_values.get("nograph", False)),
        simulate=simulate,
        seed=int(parsed_values.get("seed", 12345)),
        diagnose=bool(parsed_values.get("diagnose", False)),
    )
