"""Plotting utilities for M-sensitivity analysis."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .m_sensitivity import MSensitivityResult


def plot_m_sensitivity(
    result: MSensitivityResult,
    *,
    ax: Optional[Any] = None,
    show_breakdown: bool = True,
    show_validity_region: bool = True,
    show_ci_annotation: bool = True,
    title: Optional[str] = None,
    figsize: tuple[float, float] = (8, 4),
) -> Any:
    """Plot the M-sensitivity step function phi(M).

    Parameters
    ----------
    result : MSensitivityResult
        Output of compute_m_sensitivity().
    ax : matplotlib Axes, optional
        If provided, draw on this axes. Otherwise create a new figure.
    show_breakdown : bool, default True
        Show vertical dashed line at the breakdown point M* = S_pre.
    show_validity_region : bool, default True
        Shade regions where |S_pre - M| > separation_threshold.
    show_ci_annotation : bool, default True
        Annotate the plot with CI information.
    title : str, optional
        Custom title. Defaults to "M-Sensitivity Analysis".
    figsize : tuple of float, default (8, 4)
        Figure size if creating a new figure.

    Returns
    -------
    matplotlib.axes.Axes
        The axes object with the plot.

    Raises
    ------
    ImportError
        If matplotlib is not installed.
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise ImportError(
            "matplotlib is required for plotting. "
            "Install it with: pip install matplotlib"
        ) from exc

    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=figsize)

    m_values = result.m_values
    phi_values = result.phi_values

    # Plot step function phi(M)
    ax.step(
        m_values,
        phi_values,
        where="pre",
        color="#2c3e50",
        linewidth=2.0,
        label=r"$\varphi(M) = \mathbf{1}\{\hat{S}_{pre} > M\}$",
    )

    # Breakdown point vertical line
    if show_breakdown:
        ax.axvline(
            result.breakdown_point,
            color="#e74c3c",
            linestyle="--",
            linewidth=1.5,
            label=f"Breakdown $M^* = {result.breakdown_point:.4g}$",
        )

    # Validity region shading
    if show_validity_region and result.validity_separations is not None:
        threshold = result.separation_threshold
        # Shade regions where separation > threshold (valid inference)
        valid_start = None
        for i, sep in enumerate(result.validity_separations):
            if sep > threshold:
                if valid_start is None:
                    valid_start = i
            else:
                if valid_start is not None:
                    ax.axvspan(
                        m_values[valid_start],
                        m_values[i - 1],
                        alpha=0.12,
                        color="#27ae60",
                        label="Valid region" if valid_start == 0 or i == 1 else None,
                    )
                    valid_start = None
        # Close final region
        if valid_start is not None:
            ax.axvspan(
                m_values[valid_start],
                m_values[-1],
                alpha=0.12,
                color="#27ae60",
                label="Valid region" if valid_start == 0 else None,
            )

    # CI annotation
    if show_ci_annotation:
        ci_text = (
            f"CI = [{result.ci_lower:.4g}, {result.ci_upper:.4g}]\n"
            f"Half-width = {result.ci_half_width:.4g}"
        )
        ax.annotate(
            ci_text,
            xy=(0.97, 0.5),
            xycoords="axes fraction",
            ha="right",
            va="center",
            fontsize=9,
            bbox=dict(boxstyle="round,pad=0.3", fc="#ecf0f1", alpha=0.8),
        )

    # Formatting
    ax.set_xlabel("Threshold $M$", fontsize=11)
    ax.set_ylabel(r"$\varphi(M)$", fontsize=11)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["PASS (0)", "FAIL (1)"])
    ax.set_ylim(-0.1, 1.3)
    ax.set_xlim(min(m_values) * 0.95, max(m_values) * 1.05)
    ax.legend(loc="upper right", fontsize=9)
    ax.set_title(title or "M-Sensitivity Analysis", fontsize=12)
    ax.grid(True, alpha=0.3)

    return ax
