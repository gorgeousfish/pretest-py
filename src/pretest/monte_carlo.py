"""End-to-end Monte Carlo coverage experiments for the pretest framework.

Provides run_monte_carlo_coverage() which repeatedly:
1. Generates DID data from a DGP configuration
2. Runs pretest_from_dataframe() on each dataset
3. Accumulates coverage, pass rate, and CI width statistics

Reference: Mikhaeil & Harshaw (2026), Section 6.
"""
from __future__ import annotations

import math
import sys
from typing import Iterable, Iterator

from ._compat import frozen_slots_dataclass
from ._display import monte_carlo_html, monte_carlo_str
from .dgp import DGPConfig, generate_did_data


def _simple_progress(iterable: Iterable[int], total: int) -> Iterator[int]:
    """Simple text progress indicator when tqdm is unavailable."""
    milestones = set(range(0, total, max(1, total // 10)))
    for i, item in enumerate(iterable):
        if i in milestones:
            pct = 100 * i // total
            print(
                f"\rMonte Carlo: {pct}% ({i}/{total})",
                end="",
                file=sys.stderr,
                flush=True,
            )
        yield item
    print(
        f"\rMonte Carlo: 100% ({total}/{total})",
        file=sys.stderr,
        flush=True,
    )


@frozen_slots_dataclass
class MonteCarloResult:
    """Results from a Monte Carlo coverage experiment.

    Attributes
    ----------
    replications : int
        Number of Monte Carlo replications performed.
    pass_count : int
        Number of replications where pretest passed (phi=0).
    covered_count : int
        Number of replications where true_effect was in conditional CI (among passed).
    pass_rate : float
        Fraction of replications passing pretest.
    conditional_coverage : float or None
        Pr(tau in CI | phi=0). None if pass_count == 0.
    valid_reporting_rate : float
        Pr(phi=0 AND tau in CI) = pass_rate * conditional_coverage.
    mean_ci_width : float or None
        Mean CI width among passed replications.
    mean_s_pre : float
        Mean estimated S_pre across all replications.
    std_s_pre : float
        Std of estimated S_pre across all replications.
    config : DGPConfig
        The DGP configuration used.
    threshold_m : float
        The threshold M used.
    alpha : float
        Significance level.
    p_norm : float
        Severity norm used.
    mode : str
        'iterative' or 'overall'.
    """

    replications: int
    pass_count: int
    covered_count: int
    pass_rate: float
    conditional_coverage: float | None
    valid_reporting_rate: float
    mean_ci_width: float | None
    mean_s_pre: float
    std_s_pre: float
    config: DGPConfig
    threshold_m: float
    alpha: float
    p_norm: float
    mode: str

    def __str__(self) -> str:
        return monte_carlo_str(self)

    def _repr_html_(self) -> str:
        return monte_carlo_html(self)


def run_monte_carlo_coverage(
    config: DGPConfig,
    threshold_m: float,
    *,
    replications: int = 1000,
    alpha: float = 0.05,
    p_norm: float = 2.0,
    mode: str = "iterative",
    simulations: int = 5000,
    seed: int = 42,
    progress: bool = False,
) -> MonteCarloResult:
    """Run end-to-end Monte Carlo coverage experiment.

    For each replication (with different random data):
    1. Generate a fresh DID dataset from config (with a replication-specific seed)
    2. Run pretest_from_dataframe() with the given parameters
    3. Check phi, CI coverage, and accumulate statistics

    Parameters
    ----------
    config : DGPConfig
        Data generating process specification.
    threshold_m : float
        Acceptable violation threshold M > 0.
    replications : int
        Number of Monte Carlo replications (default 1000).
    alpha : float
        Significance level (default 0.05).
    p_norm : float
        Severity norm exponent (default 2.0).
    mode : str
        'iterative' or 'overall' (default 'iterative').
    simulations : int
        MC simulations for critical value within each replication (default 5000).
    seed : int
        Base random seed (each replication uses seed + rep_index).
    progress : bool
        If True, display a progress bar (uses tqdm if available, otherwise
        falls back to simple text output on stderr). Default False.

    Returns
    -------
    MonteCarloResult
        Aggregated results from all replications.
    """
    from .estimators import pretest_from_dataframe

    if replications < 1:
        raise ValueError("replications must be >= 1")
    if threshold_m <= 0:
        raise ValueError("threshold_m must be positive")
    if not (0 < alpha < 1):
        raise ValueError("alpha must be in (0, 1)")

    true_effect = config.true_effect
    pass_count = 0
    covered_count = 0
    s_pre_values: list[float] = []
    ci_widths: list[float] = []

    if progress:
        try:
            from tqdm.auto import tqdm
            iterator = tqdm(range(replications), desc="Monte Carlo", unit="rep")
        except ImportError:
            iterator = _simple_progress(range(replications), total=replications)
    else:
        iterator = range(replications)

    for rep in iterator:
        # Each replication uses a different seed for fresh data
        rep_config = DGPConfig(
            n_units=config.n_units,
            t_pre=config.t_pre,
            t_post=config.t_post,
            true_effect=config.true_effect,
            violation_path=config.violation_path,
            sigma_unit=config.sigma_unit,
            sigma_time=config.sigma_time,
            sigma_epsilon=config.sigma_epsilon,
            seed=seed + rep,
        )

        df = generate_did_data(rep_config)

        # Run pretest
        treat_time = float(config.t_pre + 1)
        snapshot = pretest_from_dataframe(
            df,
            outcome="outcome",
            treatment="treatment",
            time="time",
            threshold=threshold_m,
            treat_time=treat_time,
            p=p_norm,
            alpha=alpha,
            mode=mode,
            simulations=simulations,
            seed=seed,  # Fixed seed for critical value simulation
        )

        scalars = snapshot.canonical.get("scalars", {})
        s_pre = scalars.get("S_pre")
        phi = scalars.get("phi")
        ci_lower = scalars.get("ci_lower")
        ci_upper = scalars.get("ci_upper")

        if s_pre is not None:
            s_pre_values.append(float(s_pre))

        if phi == 0:
            pass_count += 1
            if ci_lower is not None and ci_upper is not None:
                ci_w = float(ci_upper) - float(ci_lower)
                ci_widths.append(ci_w)
                if float(ci_lower) <= true_effect <= float(ci_upper):
                    covered_count += 1

    # Compute summary statistics
    pass_rate = pass_count / replications if replications > 0 else 0.0
    conditional_coverage = (
        covered_count / pass_count if pass_count > 0 else None
    )
    valid_reporting_rate = covered_count / replications if replications > 0 else 0.0
    mean_ci_width = (
        sum(ci_widths) / len(ci_widths) if ci_widths else None
    )
    mean_s = sum(s_pre_values) / len(s_pre_values) if s_pre_values else 0.0
    std_s = (
        math.sqrt(sum((x - mean_s) ** 2 for x in s_pre_values) / len(s_pre_values))
        if len(s_pre_values) > 1
        else 0.0
    )

    return MonteCarloResult(
        replications=replications,
        pass_count=pass_count,
        covered_count=covered_count,
        pass_rate=pass_rate,
        conditional_coverage=conditional_coverage,
        valid_reporting_rate=valid_reporting_rate,
        mean_ci_width=mean_ci_width,
        mean_s_pre=mean_s,
        std_s_pre=std_s,
        config=config,
        threshold_m=threshold_m,
        alpha=alpha,
        p_norm=p_norm,
        mode=mode,
    )
