from __future__ import annotations

from collections.abc import Mapping, Sequence
from html import escape
import math


def _finite_float(value: object, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        raise ValueError(f"{label} must be a finite number")
    return numeric_value


def _event_study_point(point: object, *, label: str) -> dict[str, float]:
    if not isinstance(point, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return {
        "period": _finite_float(point.get("period"), label=f"{label}.period"),
        "estimate": _finite_float(point.get("estimate"), label=f"{label}.estimate"),
        "ci_lower": _finite_float(point.get("ci_lower"), label=f"{label}.ci_lower"),
        "ci_upper": _finite_float(point.get("ci_upper"), label=f"{label}.ci_upper"),
    }


def _event_study_series(value: object, *, label: str) -> list[dict[str, float]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{label} must be a list")
    return [
        _event_study_point(point, label=f"{label}[{index}]")
        for index, point in enumerate(value)
    ]


def _nice_ticks(minimum: float, maximum: float, *, count: int = 5) -> list[float]:
    if count < 2:
        raise ValueError("tick count must be at least 2")
    if minimum == maximum:
        pad = abs(minimum) * 0.1 or 1.0
        minimum -= pad
        maximum += pad
    raw_step = (maximum - minimum) / (count - 1)
    magnitude = 10 ** math.floor(math.log10(raw_step))
    normalized = raw_step / magnitude
    if normalized <= 1:
        step = magnitude
    elif normalized <= 2:
        step = 2 * magnitude
    elif normalized <= 5:
        step = 5 * magnitude
    else:
        step = 10 * magnitude
    first = math.floor(minimum / step) * step
    ticks = []
    value = first
    while value <= maximum + step * 0.5:
        if value >= minimum - step * 0.5:
            ticks.append(0.0 if abs(value) < step * 1e-9 else value)
        value += step
    return ticks


def _format_tick(value: float) -> str:
    if math.isclose(value, round(value), rel_tol=0.0, abs_tol=1e-9):
        return f"{value:.0f}"
    if abs(value) >= 10:
        return f"{value:.0f}"
    return f"{value:.1f}"


def _svg_text(x: float, y: float, text: object, *, css_class: str, anchor: str = "middle") -> str:
    return (
        f'<text class="{css_class}" x="{x:.2f}" y="{y:.2f}" '
        f'text-anchor="{anchor}">{escape(str(text))}</text>'
    )


def render_event_study_svg(
    graph_data_summary: Mapping[str, object],
    *,
    title: str = "Prop99 Event-Study Preview",
    subtitle: str = "Python-computed preview from packaged Prop99 records",
    width: int = 960,
    height: int = 560,
) -> str:
    """Render a dependency-free SVG event-study preview from graph_data_summary."""

    if width < 640 or height < 420:
        raise ValueError("SVG preview requires width >= 640 and height >= 420")
    preview = graph_data_summary.get("derived_event_study_preview")
    if not isinstance(preview, Mapping):
        raise ValueError("graph_data_summary.derived_event_study_preview must be a mapping")
    pre_points = _event_study_series(
        preview.get("pre_treatment_series"),
        label="derived_event_study_preview.pre_treatment_series",
    )
    post_points = _event_study_series(
        preview.get("post_treatment_series"),
        label="derived_event_study_preview.post_treatment_series",
    )
    points = pre_points + post_points
    if not points:
        raise ValueError("event-study preview requires at least one point")

    periods = [point["period"] for point in points]
    y_values = [
        value
        for point in points
        for value in (point["ci_lower"], point["estimate"], point["ci_upper"])
    ]
    min_period = min(periods)
    max_period = max(periods)
    x_pad = 0.45
    min_x = min_period - x_pad
    max_x = max_period + x_pad
    min_y = min(y_values)
    max_y = max(y_values)
    y_span = max_y - min_y or 1.0
    min_y -= y_span * 0.12
    max_y += y_span * 0.12
    if min_y > 0:
        min_y = 0.0
    if max_y < 0:
        max_y = 0.0

    left = 84
    right = 38
    top = 88
    bottom = 76
    plot_width = width - left - right
    plot_height = height - top - bottom

    def x_scale(period: float) -> float:
        return left + ((period - min_x) / (max_x - min_x)) * plot_width

    def y_scale(value: float) -> float:
        return top + ((max_y - value) / (max_y - min_y)) * plot_height

    x_ticks = [float(value) for value in range(int(min_period), int(max_period) + 1)]
    y_ticks = _nice_ticks(min_y, max_y, count=6)
    zero_y = y_scale(0.0)
    treatment_x = x_scale(0.0)

    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        "<title id=\"title\">" + escape(title) + "</title>",
        "<desc id=\"desc\">" + escape(subtitle) + "</desc>",
        "<style>",
        "text{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;fill:#202124}",
        ".title{font-size:22px;font-weight:700}.subtitle{font-size:13px;fill:#5f6368}",
        ".axis{stroke:#3c4043;stroke-width:1.2}.grid{stroke:#dadce0;stroke-width:1}.zero{stroke:#5f6368;stroke-width:1.4;stroke-dasharray:5 5}",
        ".treat{stroke:#111827;stroke-width:1.6;stroke-dasharray:7 5}.ci-pre{stroke:#1f77b4;stroke-width:2}.ci-post{stroke:#b23a48;stroke-width:2}",
        ".pt-pre{fill:#1f77b4;stroke:#ffffff;stroke-width:1.6}.pt-post{fill:#b23a48;stroke:#ffffff;stroke-width:1.6}",
        ".tick{font-size:12px;fill:#5f6368}.label{font-size:13px;font-weight:600;fill:#3c4043}.legend{font-size:12px;fill:#3c4043}",
        "</style>",
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        _svg_text(left, 34, title, css_class="title", anchor="start"),
        _svg_text(left, 57, subtitle, css_class="subtitle", anchor="start"),
    ]

    for tick in y_ticks:
        y = y_scale(tick)
        elements.append(f'<line class="grid" x1="{left}" y1="{y:.2f}" x2="{width-right}" y2="{y:.2f}"/>')
        elements.append(_svg_text(left - 12, y + 4, _format_tick(tick), css_class="tick", anchor="end"))
    for tick in x_ticks:
        x = x_scale(tick)
        elements.append(f'<line class="grid" x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{height-bottom}"/>')
        elements.append(_svg_text(x, height - bottom + 24, _format_tick(tick), css_class="tick"))

    elements.extend(
        [
            f'<line class="zero" x1="{left}" y1="{zero_y:.2f}" x2="{width-right}" y2="{zero_y:.2f}"/>',
            f'<line class="treat" x1="{treatment_x:.2f}" y1="{top}" x2="{treatment_x:.2f}" y2="{height-bottom}"/>',
            f'<line class="axis" x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}"/>',
            f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}"/>',
            _svg_text(width / 2, height - 22, "Time relative to treatment", css_class="label"),
            _svg_text(20, top + plot_height / 2, "Estimate and 95% CI", css_class="label", anchor="middle").replace("<text ", '<text transform="rotate(-90 20 ' + f'{top + plot_height / 2:.2f})" ', 1),
        ]
    )

    for series, css_line, css_point in (
        (pre_points, "ci-pre", "pt-pre"),
        (post_points, "ci-post", "pt-post"),
    ):
        for point in series:
            x = x_scale(point["period"])
            y_low = y_scale(point["ci_lower"])
            y_high = y_scale(point["ci_upper"])
            y_est = y_scale(point["estimate"])
            elements.append(f'<line class="{css_line}" x1="{x:.2f}" y1="{y_low:.2f}" x2="{x:.2f}" y2="{y_high:.2f}"/>')
            elements.append(f'<line class="{css_line}" x1="{x-7:.2f}" y1="{y_low:.2f}" x2="{x+7:.2f}" y2="{y_low:.2f}"/>')
            elements.append(f'<line class="{css_line}" x1="{x-7:.2f}" y1="{y_high:.2f}" x2="{x+7:.2f}" y2="{y_high:.2f}"/>')
            elements.append(f'<circle class="{css_point}" cx="{x:.2f}" cy="{y_est:.2f}" r="5.2"/>')

    legend_x = width - right - 220
    legend_y = top - 24
    elements.extend(
        [
            f'<circle class="pt-pre" cx="{legend_x:.2f}" cy="{legend_y:.2f}" r="5.2"/>',
            _svg_text(legend_x + 14, legend_y + 4, "Pre-treatment", css_class="legend", anchor="start"),
            f'<circle class="pt-post" cx="{legend_x + 118:.2f}" cy="{legend_y:.2f}" r="5.2"/>',
            _svg_text(legend_x + 132, legend_y + 4, "Post-treatment", css_class="legend", anchor="start"),
            _svg_text(treatment_x + 8, top + 15, "Treatment", css_class="legend", anchor="start"),
            "</svg>",
        ]
    )
    return "\n".join(elements) + "\n"


# ---------------------------------------------------------------------------
# Matplotlib-based event study plotting (optional dependency)
# ---------------------------------------------------------------------------


def _require_matplotlib():
    """Lazily import matplotlib.pyplot, raising a helpful error if missing."""
    try:
        import matplotlib.pyplot as plt
        return plt
    except ImportError:
        raise ImportError(
            "plot_event_study requires matplotlib. "
            "Install with: pip install matplotlib"
        ) from None


def extract_plot_data(
    snapshot: "PretestResultSnapshot",
    nu_vector: Sequence[float],
    delta_vector: Sequence[float],
    covariance_matrix: Sequence[Sequence[float]],
    sample_size: int,
    *,
    alpha: float = 0.05,
) -> dict:
    """Extract structured plot data from a pretest result snapshot.

    Parameters
    ----------
    snapshot : PretestResultSnapshot
        Result snapshot from pretest computation.
    nu_vector : sequence of float
        Iterative violations nu_t for t=2,...,t0-1 (T_pre-1 values).
    delta_vector : sequence of float
        DID estimates delta_t for t=t0,...,T (T_post values).
    covariance_matrix : sequence of sequences of float
        Asymptotic covariance matrix Sigma (T-1 x T-1).
    sample_size : int
        Sample size n.
    alpha : float
        Significance level for pointwise CIs (default 0.05).

    Returns
    -------
    dict
        Structured plot data with keys:
        - pre_periods: list[float] (relative time for pre-treatment)
        - post_periods: list[float] (relative time for post-treatment)
        - pre_estimates: list[float] (nu_t or nu_bar_t values)
        - post_estimates: list[float] (delta_t values)
        - pre_ci_lower/upper: list[float] (pointwise CIs)
        - post_ci_lower/upper: list[float] (pointwise CIs)
        - threshold: float (M value)
        - pretest_pass: bool
        - mode: str ('iterative' or 'overall')
        - delta_bar: float
        - ci_lower/upper: float|None (conditional CI)
        - ci_conv_lower/upper: float|None (conventional CI)
    """
    from statistics import NormalDist

    scalars = snapshot.canonical["scalars"]
    macros = snapshot.canonical["macros"]

    mode = str(macros.get("mode", "iterative"))
    threshold_val = float(scalars["threshold"])
    pretest_pass = bool(scalars.get("pretest_pass") == 1)
    delta_bar_val = float(scalars["delta_bar"])

    ci_lower_val = scalars.get("ci_lower")
    ci_upper_val = scalars.get("ci_upper")
    ci_conv_lower_val = scalars.get("ci_conv_lower")
    ci_conv_upper_val = scalars.get("ci_conv_upper")

    ci_lower_out = float(ci_lower_val) if ci_lower_val is not None else None
    ci_upper_out = float(ci_upper_val) if ci_upper_val is not None else None
    ci_conv_lower_out = float(ci_conv_lower_val) if ci_conv_lower_val is not None else None
    ci_conv_upper_out = float(ci_conv_upper_val) if ci_conv_upper_val is not None else None

    nu = list(nu_vector)
    delta = list(delta_vector)
    T_pre_minus_1 = len(nu)
    T_post = len(delta)
    T_pre = T_pre_minus_1 + 1

    z_crit = NormalDist().inv_cdf(1.0 - alpha / 2.0)

    # Pre-treatment estimates and CIs
    if mode == "overall":
        # Cumulative sum for overall mode
        nu_bar: list[float] = []
        cumulative = 0.0
        for v in nu:
            cumulative += v
            nu_bar.append(cumulative)
        pre_estimates = nu_bar

        # Transform covariance: Sigma_overall = A * Sigma_nu * A'
        # where A is lower-triangular of ones (cumsum operator)
        sigma_nu = [
            [float(covariance_matrix[i][j]) for j in range(T_pre_minus_1)]
            for i in range(T_pre_minus_1)
        ]
        # Compute A * Sigma_nu * A' manually
        sigma_overall: list[list[float]] = [
            [0.0] * T_pre_minus_1 for _ in range(T_pre_minus_1)
        ]
        for i in range(T_pre_minus_1):
            for j in range(T_pre_minus_1):
                total = 0.0
                for r in range(i + 1):
                    for c in range(j + 1):
                        total += sigma_nu[r][c]
                sigma_overall[i][j] = total

        pre_ci_lower: list[float] = []
        pre_ci_upper: list[float] = []
        for i in range(T_pre_minus_1):
            se_i = math.sqrt(sigma_overall[i][i] / sample_size)
            half = z_crit * se_i
            pre_ci_lower.append(pre_estimates[i] - half)
            pre_ci_upper.append(pre_estimates[i] + half)
    else:
        pre_estimates = list(nu)
        pre_ci_lower = []
        pre_ci_upper = []
        for i in range(T_pre_minus_1):
            var_i = float(covariance_matrix[i][i])
            se_i = math.sqrt(var_i / sample_size)
            half = z_crit * se_i
            pre_ci_lower.append(pre_estimates[i] - half)
            pre_ci_upper.append(pre_estimates[i] + half)

    # Pre-treatment periods: relative time -(T_pre-1), ..., -1
    pre_periods = [float(i + 1 - T_pre) for i in range(T_pre_minus_1)]

    # Post-treatment estimates and CIs
    post_estimates = list(delta)
    post_ci_lower: list[float] = []
    post_ci_upper: list[float] = []
    for i in range(T_post):
        idx = T_pre_minus_1 + i
        var_i = float(covariance_matrix[idx][idx])
        se_i = math.sqrt(var_i / sample_size)
        half = z_crit * se_i
        post_ci_lower.append(post_estimates[i] - half)
        post_ci_upper.append(post_estimates[i] + half)

    # Post-treatment periods: 0, 1, ..., T_post-1
    post_periods = [float(i) for i in range(T_post)]

    return {
        "pre_periods": pre_periods,
        "post_periods": post_periods,
        "pre_estimates": pre_estimates,
        "post_estimates": post_estimates,
        "pre_ci_lower": pre_ci_lower,
        "pre_ci_upper": pre_ci_upper,
        "post_ci_lower": post_ci_lower,
        "post_ci_upper": post_ci_upper,
        "threshold": threshold_val,
        "pretest_pass": pretest_pass,
        "mode": mode,
        "delta_bar": delta_bar_val,
        "ci_lower": ci_lower_out,
        "ci_upper": ci_upper_out,
        "ci_conv_lower": ci_conv_lower_out,
        "ci_conv_upper": ci_conv_upper_out,
    }


def plot_event_study(
    snapshot: "PretestResultSnapshot",
    nu_vector: Sequence[float],
    delta_vector: Sequence[float],
    covariance_matrix: Sequence[Sequence[float]],
    sample_size: int,
    *,
    # Figure options
    title: str | None = None,
    xlabel: str = "Time relative to treatment",
    ylabel: str = "Estimate",
    figsize: tuple[float, float] = (10, 6),
    # Colors and style
    pre_color: str = "navy",
    post_color_pass: str = "maroon",
    post_color_fail: str = "maroon",
    post_alpha_fail: float = 0.5,
    threshold_color: str = "orange",
    # Marker style
    marker_pre: str = "o",
    marker_post_pass: str = "o",
    marker_post_fail: str = "o",
    marker_size: float = 8,
    # CI style
    ci_linewidth: float = 2.0,
    ci_capsize: float = 4.0,
    ci_linestyle_fail: str = "--",
    # Threshold M line
    show_threshold: bool = True,
    threshold_linestyle: str = "--",
    # ATT comparison intervals
    show_att_comparison: bool = True,
    att_conventional_color: str = "gray",
    att_conditional_color: str = "orange",
    # Reference lines
    show_zero_line: bool = True,
    show_treatment_line: bool = True,
    # Annotation
    show_note: bool = True,
    # Export
    save_path: str | None = None,
    dpi: int = 150,
    # matplotlib Axes
    ax: "Any | None" = None,
    alpha: float = 0.05,
) -> "Any":
    """Generate a matplotlib event study plot matching Stata pretest graph output.

    Produces a publication-quality event study figure with pre-treatment
    parallel-trend violations, post-treatment DID estimates, pointwise
    confidence intervals, threshold M reference lines, and average ATT
    comparison intervals (conditional vs. conventional).

    Parameters
    ----------
    snapshot : PretestResultSnapshot
        Result snapshot from pretest computation.
    nu_vector : sequence of float
        Iterative violations nu_t (T_pre-1 values).
    delta_vector : sequence of float
        DID estimates delta_t (T_post values).
    covariance_matrix : sequence of sequences of float
        Asymptotic covariance Sigma (T-1 x T-1).
    sample_size : int
        Sample size n.
    title : str or None
        Custom title. Default: "Event Study with Pre-test (Mikhaeil-Harshaw 2025)".
    ax : matplotlib Axes or None
        If provided, plot onto this Axes instead of creating a new figure.
    alpha : float
        Significance level for pointwise CIs (default 0.05).

    Returns
    -------
    matplotlib.axes.Axes
        The Axes object for further customization.
    """
    plt = _require_matplotlib()

    # Extract plot data
    data = extract_plot_data(
        snapshot, nu_vector, delta_vector, covariance_matrix, sample_size,
        alpha=alpha,
    )

    pretest_pass = data["pretest_pass"]
    mode = data["mode"]

    # Create figure if no axes provided
    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.get_figure()

    # --- Layer 1: Pre-treatment CIs (errorbar, rcap style) ---
    pre_errors_lower = [
        est - lo for est, lo in zip(data["pre_estimates"], data["pre_ci_lower"])
    ]
    pre_errors_upper = [
        hi - est for est, hi in zip(data["pre_estimates"], data["pre_ci_upper"])
    ]
    ax.errorbar(
        data["pre_periods"],
        data["pre_estimates"],
        yerr=[pre_errors_lower, pre_errors_upper],
        fmt="none",
        ecolor=pre_color,
        elinewidth=ci_linewidth,
        capsize=ci_capsize,
        capthick=ci_linewidth,
        zorder=2,
    )

    # --- Layer 2: Pre-treatment point estimates ---
    mode_label = "Overall viol." if mode == "overall" else "Iter. viol."
    ax.scatter(
        data["pre_periods"],
        data["pre_estimates"],
        color=pre_color,
        marker=marker_pre,
        s=marker_size ** 2,
        zorder=3,
        label=mode_label,
    )

    # --- Layer 3: Post-treatment CIs ---
    post_errors_lower = [
        est - lo for est, lo in zip(data["post_estimates"], data["post_ci_lower"])
    ]
    post_errors_upper = [
        hi - est for est, hi in zip(data["post_estimates"], data["post_ci_upper"])
    ]
    if pretest_pass:
        post_color = post_color_pass
        post_line_alpha = 1.0
        post_linestyle = "-"
        post_marker = marker_post_pass
    else:
        post_color = post_color_fail
        post_line_alpha = post_alpha_fail
        post_linestyle = ci_linestyle_fail
        post_marker = marker_post_fail

    ax.errorbar(
        data["post_periods"],
        data["post_estimates"],
        yerr=[post_errors_lower, post_errors_upper],
        fmt="none",
        ecolor=post_color,
        elinewidth=ci_linewidth,
        capsize=ci_capsize,
        capthick=ci_linewidth,
        alpha=post_line_alpha,
        linestyle=post_linestyle,
        zorder=2,
    )

    # --- Layer 4: Post-treatment point estimates ---
    ax.scatter(
        data["post_periods"],
        data["post_estimates"],
        color=post_color,
        marker=post_marker,
        s=marker_size ** 2,
        alpha=post_line_alpha,
        zorder=3,
        label="DID est.",
    )

    # --- Layer 5: Average ATT comparison intervals ---
    if show_att_comparison:
        x_max_data = max(data["post_periods"]) if data["post_periods"] else 0.0
        att_x_base = x_max_data + 0.7

        # Conventional CI (gray)
        if data["ci_conv_lower"] is not None and data["ci_conv_upper"] is not None:
            att_x_conv = att_x_base - 0.15
            conv_lo = data["ci_conv_lower"]
            conv_hi = data["ci_conv_upper"]
            ax.errorbar(
                [att_x_conv],
                [data["delta_bar"]],
                yerr=[[data["delta_bar"] - conv_lo], [conv_hi - data["delta_bar"]]],
                fmt="none",
                ecolor=att_conventional_color,
                elinewidth=ci_linewidth + 0.5,
                capsize=ci_capsize,
                capthick=ci_linewidth,
                zorder=4,
            )
            ax.scatter(
                [att_x_conv],
                [data["delta_bar"]],
                color=att_conventional_color,
                marker="o",
                s=(marker_size - 1) ** 2,
                zorder=5,
                label="Conv. CI",
            )

        # Conditional CI (orange, only when pretest passes)
        if pretest_pass and data["ci_lower"] is not None and data["ci_upper"] is not None:
            att_x_cond = att_x_base + 0.15
            cond_lo = data["ci_lower"]
            cond_hi = data["ci_upper"]
            ax.errorbar(
                [att_x_cond],
                [data["delta_bar"]],
                yerr=[[data["delta_bar"] - cond_lo], [cond_hi - data["delta_bar"]]],
                fmt="none",
                ecolor=att_conditional_color,
                elinewidth=ci_linewidth + 1.0,
                capsize=ci_capsize,
                capthick=ci_linewidth + 0.5,
                zorder=4,
            )
            ax.scatter(
                [att_x_cond],
                [data["delta_bar"]],
                color=att_conditional_color,
                marker="D",
                s=(marker_size) ** 2,
                zorder=5,
                label="Cond. CI",
            )

    # --- Reference lines ---
    if show_zero_line:
        ax.axhline(0, color="gray", linewidth=0.8, linestyle="--", alpha=0.6, zorder=1)

    if show_treatment_line:
        ax.axvline(-0.5, color="gray", linewidth=1.2, linestyle="--", alpha=0.7, zorder=1)

    if show_threshold:
        m_val = data["threshold"]
        ax.axhline(
            m_val, color=threshold_color, linewidth=1.2,
            linestyle=threshold_linestyle, alpha=0.7, zorder=1,
            label=f"M = {m_val:.3f}",
        )
        ax.axhline(
            -m_val, color=threshold_color, linewidth=1.2,
            linestyle=threshold_linestyle, alpha=0.7, zorder=1,
        )

    # --- Labels and title ---
    if title is None:
        title = "Event Study with Pre-test (Mikhaeil-Harshaw 2025)"
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)

    # --- Legend ---
    ax.legend(loc="best", fontsize=9, framealpha=0.9)

    # --- Annotation note ---
    if show_note:
        pass_label = "PASS" if pretest_pass else "FAIL"
        note_text = f"M = {data['threshold']:.3f}  |  Pretest: {pass_label}"
        ax.annotate(
            note_text,
            xy=(0.5, -0.08),
            xycoords="axes fraction",
            ha="center",
            fontsize=9,
            color="#444444",
        )

    # --- Formatting ---
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(labelsize=9)

    if fig is not None:
        fig.tight_layout()

    # --- Export ---
    if save_path is not None:
        fig.savefig(save_path, dpi=dpi, bbox_inches="tight")

    return ax


def plot_event_study_from_dataframe(
    df: "Any",
    outcome: str,
    treatment: str,
    time: str,
    threshold: float,
    *,
    treat_time: float | None = None,
    p: float = 2.0,
    alpha: float = 0.05,
    cluster: str | None = None,
    mode: str = "iterative",
    simulations: int = 5000,
    seed: int = 12345,
    **plot_kwargs,
) -> "Any":
    """Run pretest from DataFrame and generate event study plot in one call.

    Combines ``pretest_from_dataframe()`` + ``plot_event_study()``.
    All keyword arguments not consumed by the estimation step are forwarded
    to ``plot_event_study()``.

    Parameters
    ----------
    df : pandas.DataFrame
        Input data.
    outcome, treatment, time, threshold, treat_time, p, alpha, cluster,
    mode, simulations, seed
        Same as ``pretest_from_dataframe()``.
    **plot_kwargs
        Forwarded to ``plot_event_study()``.

    Returns
    -------
    matplotlib.axes.Axes
        The Axes object for further customization.
    """
    from .estimators import pretest_from_dataframe as _run_pretest
    from .covariance import (
        compute_cluster_robust_covariance,
        compute_influence_matrix,
        compute_standard_covariance,
    )
    from .severity import normalize_mode

    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError(
            "plot_event_study_from_dataframe requires pandas. "
            "Install with: pip install pretest-py[data]"
        ) from exc

    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    # Run the pretest to get the snapshot
    snapshot = _run_pretest(
        df,
        outcome,
        treatment,
        time,
        threshold,
        treat_time=treat_time,
        p=p,
        alpha=alpha,
        cluster=cluster,
        mode=mode,
        simulations=simulations,
        seed=seed,
    )

    # Re-compute nu_vector, delta_vector, covariance_matrix from data
    normalized_mode = normalize_mode(mode)

    required_cols = [outcome, treatment, time]
    if cluster is not None:
        required_cols.append(cluster)
    working_df = df[list(dict.fromkeys(required_cols + [outcome]))].dropna(
        subset=[outcome, treatment, time]
    ).copy()

    observed_times = sorted(working_df[time].unique())
    time_to_index = {t: i + 1 for i, t in enumerate(observed_times)}
    T = len(observed_times)
    treatment_time_index = time_to_index[treat_time]
    T_pre = treatment_time_index - 1

    outcomes_arr = list(working_df[outcome])
    treatments_arr = [int(x) for x in working_df[treatment]]
    time_indices_arr = [time_to_index[t] for t in working_df[time]]
    n = len(outcomes_arr)

    # Compute group means
    grouped: dict[tuple[int, int], list[float]] = {}
    for i in range(n):
        key = (time_indices_arr[i], treatments_arr[i])
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(outcomes_arr[i])

    means: dict[tuple[int, int], float] = {
        k: sum(v) / len(v) for k, v in grouped.items()
    }

    # Compute nu_vector
    nu_vector: list[float] = []
    for t in range(2, treatment_time_index):
        nu_t = (
            (means[(t, 1)] - means[(t - 1, 1)])
            - (means[(t, 0)] - means[(t - 1, 0)])
        )
        nu_vector.append(nu_t)

    # Compute delta_vector
    delta_vector: list[float] = []
    for t in range(treatment_time_index, T + 1):
        delta_t = (
            (means[(t, 1)] - means[(treatment_time_index, 1)])
            - (means[(t, 0)] - means[(treatment_time_index, 0)])
        )
        delta_vector.append(delta_t)

    # Compute covariance matrix
    influence_mat = compute_influence_matrix(
        outcomes_arr,
        treatments_arr,
        time_indices_arr,
        treatment_time_index=treatment_time_index,
        time_period_count=T,
    )

    if cluster is not None:
        cluster_ids = working_df[cluster].tolist()
        covariance_matrix = compute_cluster_robust_covariance(
            influence_mat, cluster_ids
        )
    else:
        covariance_matrix = compute_standard_covariance(influence_mat)

    return plot_event_study(
        snapshot,
        nu_vector,
        delta_vector,
        covariance_matrix,
        n,
        alpha=alpha,
        **plot_kwargs,
    )
