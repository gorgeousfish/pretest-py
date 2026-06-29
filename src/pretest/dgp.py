"""Built-in Data Generating Process (DGP) for Monte Carlo simulation.

Provides configurable DID data generators matching the simulation design
in Section 6 of Mikhaeil & Harshaw (2026).

Mathematical Model (Section 2.1):
    Y_{it} = alpha_i + gamma_t + D_i * nu_bar_t * 1{t < t0}
             + D_i * (tau_bar + nu_bar_t0 + delta_post_t) * 1{t >= t0}
             + epsilon_{it}

where:
    - alpha_i ~ N(0, sigma_unit^2) is a unit fixed effect
    - gamma_t is a deterministic time trend
    - nu_bar_t = sum_{s=2}^t nu_s is the cumulative violation
    - epsilon_{it} ~ N(0, sigma_epsilon^2) is idiosyncratic noise
"""
from __future__ import annotations

import math
import random
from collections.abc import Sequence
from typing import Any

from ._compat import frozen_slots_dataclass
from .severity import compute_severity, normalize_p_norm
from .simulation import compute_section6_violation_path


@frozen_slots_dataclass
class DGPConfig:
    """Configuration for a DID data generating process.

    Parameters
    ----------
    n_units : int
        Total number of units (half treated, half control). Must be even and >= 4.
    t_pre : int
        Number of pre-treatment periods. Must be >= 2.
    t_post : int
        Number of post-treatment periods. Must be >= 1.
    true_effect : float
        True average treatment effect tau_bar.
    violation_path : tuple of float
        Iterative violations nu_t for t=2,...,t0-1. Length must be t_pre - 1.
    sigma_unit : float
        Standard deviation of unit fixed effects. Default 1.0.
    sigma_time : float
        Scale of deterministic time trend. Default 0.0 (no trend).
    sigma_epsilon : float
        Standard deviation of idiosyncratic noise. Default 1.0.
    seed : int
        Random seed for reproducibility.
    """

    n_units: int
    t_pre: int
    t_post: int
    true_effect: float
    violation_path: tuple[float, ...]
    sigma_unit: float = 1.0
    sigma_time: float = 0.0
    sigma_epsilon: float = 1.0
    seed: int = 12345

    def __post_init__(self) -> None:
        if self.n_units < 4 or self.n_units % 2 != 0:
            raise ValueError("n_units must be even and >= 4")
        if self.t_pre < 2:
            raise ValueError("t_pre must be >= 2")
        if self.t_post < 1:
            raise ValueError("t_post must be >= 1")
        if len(self.violation_path) != self.t_pre - 1:
            raise ValueError(
                f"violation_path length must be t_pre-1={self.t_pre - 1}"
            )
        if self.sigma_unit < 0 or self.sigma_epsilon < 0:
            raise ValueError("sigma values must be non-negative")

    @property
    def total_periods(self) -> int:
        return self.t_pre + self.t_post

    @property
    def n_treated(self) -> int:
        return self.n_units // 2

    @property
    def n_control(self) -> int:
        return self.n_units - self.n_treated

    @property
    def true_severity(self) -> float:
        """Compute true S_pre from violation_path using L2 norm."""
        return compute_severity(nu_vector=self.violation_path, p_norm=2.0)


def generate_did_data(config: DGPConfig) -> Any:
    """Generate a balanced panel DID dataset as a pandas DataFrame.

    Model:
        Y_{it} = alpha_i + gamma_t + violation_effect_{it}
                 + treatment_effect_{it} + eps_{it}

    Parameters
    ----------
    config : DGPConfig
        DGP configuration specifying all parameters.

    Returns
    -------
    pandas.DataFrame
        DataFrame with columns: unit_id, time, treatment, outcome.

    Raises
    ------
    ImportError
        If pandas is not installed.
    """
    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError(
            "generate_did_data requires pandas. "
            "Install with: pip install pretest[data]"
        ) from exc

    rng = random.Random(config.seed)
    T = config.total_periods
    t0 = config.t_pre + 1  # first post-treatment period (1-based)

    # Compute cumulative violations nu_bar_t
    cumulative_violations = [0.0]  # period 1 has no violation
    running = 0.0
    for nu_t in config.violation_path:
        running += nu_t
        cumulative_violations.append(running)
    # cumulative_violations[t-1] = nu_bar_t for t=1,...,t_pre

    # Unit fixed effects
    n_treat = config.n_treated
    n_ctrl = config.n_control
    alpha_treated = [rng.gauss(0, config.sigma_unit) for _ in range(n_treat)]
    alpha_control = [rng.gauss(0, config.sigma_unit) for _ in range(n_ctrl)]

    # Deterministic time trend
    gamma = [config.sigma_time * rng.gauss(0, 1) for _ in range(T)]

    # Build panel data
    rows = []
    for i in range(n_treat):
        for t_idx in range(T):
            t = t_idx + 1  # period number (1-based)
            y = alpha_treated[i] + gamma[t_idx]

            # Violation effect (treated units in pre-treatment)
            if t < t0 and t >= 2:
                y += cumulative_violations[t - 1]

            # Treatment effect (treated units in post-treatment)
            if t >= t0:
                y += config.true_effect
                # Cumulative violation carries forward into post
                if cumulative_violations:
                    y += cumulative_violations[-1]

            # Idiosyncratic noise
            y += rng.gauss(0, config.sigma_epsilon)

            rows.append(
                {
                    "unit_id": i,
                    "time": t,
                    "treatment": 1,
                    "outcome": y,
                }
            )

    for i in range(n_ctrl):
        for t_idx in range(T):
            t = t_idx + 1
            y = alpha_control[i] + gamma[t_idx]
            y += rng.gauss(0, config.sigma_epsilon)

            rows.append(
                {
                    "unit_id": n_treat + i,
                    "time": t,
                    "treatment": 0,
                    "outcome": y,
                }
            )

    return pd.DataFrame(rows)


_PRESETS: dict[str, dict] = {
    "no_violation": {
        "t_pre": 5,
        "t_post": 3,
        "true_effect": 1.0,
        "violation_severity": 0.0,
        "sigma_epsilon": 1.0,
    },
    "small_violation": {
        "t_pre": 5,
        "t_post": 3,
        "true_effect": 1.0,
        "violation_severity": 0.1,
        "sigma_epsilon": 1.0,
    },
    "large_violation": {
        "t_pre": 5,
        "t_post": 3,
        "true_effect": 1.0,
        "violation_severity": 1.0,
        "sigma_epsilon": 1.0,
    },
    "section6_baseline": {
        "t_pre": 5,
        "t_post": 3,
        "true_effect": 0.5,
        "violation_severity": 0.3,
        "sigma_epsilon": 1.0,
    },
    "many_periods": {
        "t_pre": 10,
        "t_post": 5,
        "true_effect": 1.0,
        "violation_severity": 0.2,
        "sigma_epsilon": 1.0,
    },
    "minimal": {
        "t_pre": 3,
        "t_post": 1,
        "true_effect": 0.5,
        "violation_severity": 0.15,
        "sigma_epsilon": 1.0,
    },
}


def generate_did_data_from_preset(
    preset: str,
    *,
    n_units: int = 200,
    seed: int = 12345,
) -> tuple[Any, DGPConfig]:
    """Generate DID data from a pre-defined scenario.

    Parameters
    ----------
    preset : str
        Name of the preset scenario. Available presets:
        'no_violation', 'small_violation', 'large_violation',
        'section6_baseline', 'many_periods', 'minimal'.
    n_units : int
        Total number of units (default 200).
    seed : int
        Random seed for reproducibility (default 12345).

    Returns
    -------
    tuple[pandas.DataFrame, DGPConfig]
        Generated data and the DGP configuration used.

    Raises
    ------
    ValueError
        If preset name is not recognized.
    """
    if preset not in _PRESETS:
        raise ValueError(
            f"Unknown preset '{preset}'. Available: {sorted(_PRESETS.keys())}"
        )

    params = _PRESETS[preset]
    t_pre = params["t_pre"]
    severity = params["violation_severity"]

    # Generate violation path from target severity
    if severity == 0.0:
        violation_path = tuple(0.0 for _ in range(t_pre - 1))
    else:
        violation_path = compute_section6_violation_path(
            t_start=2,
            t_end=t_pre,
            total_periods=t_pre + params["t_post"],
            target_severity=severity,
            p_norm=2.0,
        )

    config = DGPConfig(
        n_units=n_units,
        t_pre=t_pre,
        t_post=params["t_post"],
        true_effect=params["true_effect"],
        violation_path=violation_path,
        sigma_epsilon=params["sigma_epsilon"],
        seed=seed,
    )

    df = generate_did_data(config)
    return df, config


def compute_true_covariance(config: DGPConfig) -> tuple[tuple[float, ...], ...]:
    """Compute the true asymptotic covariance matrix Sigma for this DGP.

    Under the balanced panel DGP with iid epsilon ~ N(0, sigma^2) and
    equal group sizes (n/2 treated, n/2 control):

        Sigma_jk = 4 * sigma_epsilon^2 * I_{j==k}

    This is the population-level n * Var(theta_hat) matrix used in
    Monte Carlo critical-value simulation.

    Parameters
    ----------
    config : DGPConfig
        DGP configuration.

    Returns
    -------
    tuple of tuple of float
        (T-1) x (T-1) covariance matrix as nested tuples.
    """
    dim = config.t_pre - 1 + config.t_post  # T - 1
    sigma2 = config.sigma_epsilon**2
    diagonal_value = 4.0 * sigma2

    return tuple(
        tuple(diagonal_value if i == j else 0.0 for j in range(dim))
        for i in range(dim)
    )
