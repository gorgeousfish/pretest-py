from __future__ import annotations

from ._compat import frozen_slots_dataclass


@frozen_slots_dataclass
class OptionDomainErrorSpec:
    code: int
    rule: str
    message: str


DOCUMENTED_OPTION_ERRORS: dict[int, OptionDomainErrorSpec] = {
    103: OptionDomainErrorSpec(
        code=103,
        rule="treatment must be binary 0/1",
        message="treatment() must contain only 0 and 1",
    ),
    104: OptionDomainErrorSpec(
        code=104,
        rule="treat_time must leave at least two pre-treatment periods",
        message="treat_time() must leave at least two pre-treatment periods",
    ),
    105: OptionDomainErrorSpec(
        code=105,
        rule="threshold must be strictly positive",
        message="threshold() must be positive",
    ),
    106: OptionDomainErrorSpec(
        code=106,
        rule="p must be >= 1",
        message="p() must be >= 1",
    ),
    107: OptionDomainErrorSpec(
        code=107,
        rule="alpha must be in (0, 1)",
        message="alpha() must be in (0, 1)",
    ),
    109: OptionDomainErrorSpec(
        code=109,
        rule="treat_time must be an observed time value within the data range",
        message="treat_time() must match an observed time value within the data range",
    ),
    110: OptionDomainErrorSpec(
        code=110,
        rule="simulate must be >= 100",
        message="simulate() must be >= 100 for reliable critical value estimation.",
    ),
}


def error_spec(code: int) -> OptionDomainErrorSpec:
    try:
        return DOCUMENTED_OPTION_ERRORS[code]
    except KeyError as exc:
        raise KeyError(f"Unsupported validation error code: {code}") from exc
