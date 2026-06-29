"""Display formatting utilities for pretest result objects.

Provides __str__ (text) and _repr_html_ (Jupyter) rendering helpers
for PretestResultSnapshot, SimulationCoverageResult, MSensitivityResult,
and MonteCarloResult.
"""
from __future__ import annotations

import math
from typing import Any

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

_LINE_WIDTH = 68
_NA = "\u2014"  # em-dash for None


def _fmt_float(value: Any, digits: int = 6) -> str:
    """Format a float to *digits* significant figures, or return NA placeholder."""
    if value is None:
        return _NA
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(v):
        return str(v)
    if v == 0.0:
        return "0.0"
    return f"{v:.{digits}g}"


def _fmt_pct(value: Any, decimals: int = 2) -> str:
    """Format a float as a percentage string."""
    if value is None:
        return _NA
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{v * 100:.{decimals}f}%"


def _fmt_int(value: Any) -> str:
    if value is None:
        return _NA
    return str(int(value))


def _center(text: str, width: int = _LINE_WIDTH) -> str:
    return text.center(width)


def _separator(char: str = "=", width: int = _LINE_WIDTH) -> str:
    return char * width


# ---------------------------------------------------------------------------
# Text report builders
# ---------------------------------------------------------------------------


def pretest_result_str(obj: Any) -> str:
    """Text summary for PretestResultSnapshot."""
    summary = obj.reporting_summary()
    scalars = obj.canonical.get("scalars", {})

    mode = summary.get("mode", _NA)
    alpha = _fmt_float(scalars.get("alpha"), 4)
    n = _fmt_int(scalars.get("n"))
    t_pre = _fmt_int(scalars.get("T_pre"))
    t_post = _fmt_int(scalars.get("T_post"))
    s_pre = _fmt_float(summary.get("S_pre"))
    kappa = _fmt_float(scalars.get("kappa"))
    phi = summary.get("phi")
    phi_label = "Pass (0)" if phi == 0 else "Fail (1)" if phi == 1 else _NA
    threshold_m = _fmt_float(summary.get("threshold"))
    delta_bar = _fmt_float(summary.get("delta_bar"))

    ci = summary.get("conditional_interval")
    if ci is not None:
        ci_lower = _fmt_float(ci[0])
        ci_upper = _fmt_float(ci[1])
        ci_half = _fmt_float((ci[1] - ci[0]) / 2.0)
        ci_available = "Yes"
    else:
        ci_lower = _NA
        ci_upper = _NA
        ci_half = _NA
        ci_available = "No"

    ci_level = scalars.get("alpha")
    if ci_level is not None:
        try:
            ci_pct = f"{(1 - float(ci_level)) * 100:.0f}%"
        except (TypeError, ValueError):
            ci_pct = "95%"
    else:
        ci_pct = "95%"

    lines = [
        _separator("="),
        _center("Pretest Result Summary"),
        _separator("="),
        f"{'Mode:':<25}{mode:<20}{'Alpha:':<20}{alpha}",
        f"{'Periods (pre/post):':<25}{t_pre + ' / ' + t_post:<20}{'Sample size:':<20}{n}",
        _separator("-"),
        _center("Key Statistics"),
        _separator("-"),
        f"{'Severity (S_pre):':<25}{s_pre:<20}{'Kappa:':<20}{kappa}",
        f"{'Decision (\u03c6):':<25}{phi_label:<20}{'Threshold (M):':<20}{threshold_m}",
        _separator("-"),
        _center("Confidence Interval"),
        _separator("-"),
        f"{'Point estimate (\u03b4\u0304):':<25}{delta_bar}",
        f"{'CI half-width:':<25}{ci_half}",
        f"{ci_pct + ' CI:':<25}[{ci_lower}, {ci_upper}]",
        f"{'CI available:':<25}{ci_available}",
        _separator("="),
    ]
    return "\n".join(lines)


def simulation_coverage_str(obj: Any) -> str:
    """Text summary for SimulationCoverageResult."""
    lines = [
        _separator("="),
        _center("Coverage Simulation Result"),
        _separator("="),
        f"{'Replications:':<40}{_fmt_int(obj.replications)}",
        f"{'Pass count:':<40}{_fmt_int(obj.pass_count)}",
        f"{'Pass rate:':<40}{_fmt_pct(obj.pass_rate)}",
        _separator("-"),
        _center("Conditional Coverage (Proposed CI)"),
        _separator("-"),
        f"{'Coverage | pass:':<40}{_fmt_pct(obj.conditional_coverage)}",
        f"{'Valid reporting rate:':<40}{_fmt_pct(obj.valid_reporting_rate)}",
        f"{'Mean CI width (passed):':<40}{_fmt_float(obj.mean_ci_width_when_passed)}",
    ]
    if obj.conditional_coverage_standard_error is not None:
        lines.append(f"{'Coverage SE:':<40}{_fmt_float(obj.conditional_coverage_standard_error)}")
    if obj.valid_reporting_rate_standard_error is not None:
        lines.append(f"{'Valid reporting SE:':<40}{_fmt_float(obj.valid_reporting_rate_standard_error)}")

    lines.extend([
        _separator("-"),
        _center("Conventional CI Benchmark"),
        _separator("-"),
        f"{'Coverage | pass (conv.):':<40}{_fmt_pct(obj.conventional_conditional_coverage)}",
        f"{'Valid reporting rate (conv.):':<40}{_fmt_pct(obj.conventional_valid_reporting_rate)}",
        f"{'Mean conv. CI width (passed):':<40}{_fmt_float(obj.mean_conventional_ci_width_when_passed)}",
    ])
    if obj.conventional_conditional_coverage_standard_error is not None:
        lines.append(f"{'Conv. coverage SE:':<40}{_fmt_float(obj.conventional_conditional_coverage_standard_error)}")

    if obj.critical_value is not None:
        lines.extend([
            _separator("-"),
            f"{'Critical value (f_alpha):':<40}{_fmt_float(obj.critical_value)}",
        ])

    lines.append(_separator("="))
    return "\n".join(lines)


def m_sensitivity_str(obj: Any) -> str:
    """Text summary for MSensitivityResult."""
    lines = [
        _separator("="),
        _center("M-Sensitivity Analysis"),
        _separator("="),
        f"{'Breakdown point (M*):':<30}{_fmt_float(obj.breakdown_point)}",
        f"{'S_pre_hat:':<30}{_fmt_float(obj.s_pre_hat)}",
        f"{'Sample size (n):':<30}{_fmt_int(obj.n)}",
        f"{'Alpha:':<30}{_fmt_float(obj.alpha, 4)}",
        _separator("-"),
        _center("Confidence Interval"),
        _separator("-"),
        f"{'CI half-width:':<30}{_fmt_float(obj.ci_half_width)}",
        f"{'CI lower:':<30}{_fmt_float(obj.ci_lower)}",
        f"{'CI upper:':<30}{_fmt_float(obj.ci_upper)}",
        _separator("-"),
        _center("Sensitivity Table"),
        _separator("-"),
        f"{'M':<14}{'phi(M)':<12}{'Can Report':<12}",
        _separator("-"),
    ]
    # Show up to 20 rows; truncate with ellipsis
    n_rows = len(obj.m_values)
    show = min(n_rows, 20)
    for i in range(show):
        m = _fmt_float(obj.m_values[i])
        phi = str(obj.phi_values[i])
        can = "Yes" if obj.can_report[i] else "No"
        lines.append(f"{m:<14}{phi:<12}{can:<12}")
    if n_rows > show:
        lines.append(f"  ... ({n_rows - show} more rows)")
    lines.append(_separator("="))
    return "\n".join(lines)


def monte_carlo_str(obj: Any) -> str:
    """Text summary for MonteCarloResult."""
    lines = [
        _separator("="),
        _center("Monte Carlo Coverage Result"),
        _separator("="),
        f"{'Replications:':<35}{_fmt_int(obj.replications)}",
        f"{'Mode:':<35}{obj.mode}",
        f"{'Threshold M:':<35}{_fmt_float(obj.threshold_m)}",
        f"{'Alpha:':<35}{_fmt_float(obj.alpha, 4)}",
        f"{'p-norm:':<35}{_fmt_float(obj.p_norm, 3)}",
        _separator("-"),
        _center("Pass / Coverage Statistics"),
        _separator("-"),
        f"{'Pass count:':<35}{_fmt_int(obj.pass_count)}",
        f"{'Pass rate:':<35}{_fmt_pct(obj.pass_rate)}",
        f"{'Covered count:':<35}{_fmt_int(obj.covered_count)}",
        f"{'Conditional coverage:':<35}{_fmt_pct(obj.conditional_coverage)}",
        f"{'Valid reporting rate:':<35}{_fmt_pct(obj.valid_reporting_rate)}",
        _separator("-"),
        _center("Severity & CI Width"),
        _separator("-"),
        f"{'Mean S_pre:':<35}{_fmt_float(obj.mean_s_pre)}",
        f"{'Std S_pre:':<35}{_fmt_float(obj.std_s_pre)}",
        f"{'Mean CI width:':<35}{_fmt_float(obj.mean_ci_width)}",
        _separator("="),
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML report builders
# ---------------------------------------------------------------------------

_HTML_STYLE = (
    "style='border-collapse:collapse;font-family:monospace;font-size:13px;"
    "margin:8px 0'"
)
_TH_STYLE = (
    "style='background:#f0f0f0;padding:6px 12px;border:1px solid #ddd;"
    "text-align:left'"
)
_TD_LABEL_STYLE = (
    "style='padding:6px 12px;border:1px solid #ddd;text-align:left;"
    "font-weight:bold'"
)
_TD_VALUE_STYLE = (
    "style='padding:6px 12px;border:1px solid #ddd;text-align:right'"
)
_SECTION_STYLE = (
    "style='background:#f8f8f8;padding:6px 12px;border:1px solid #ddd;"
    "text-align:center;font-weight:bold'"
)


def _html_header(title: str) -> str:
    return (
        f"<div style='margin:8px 0'>"
        f"<h4 style='margin:4px 0;font-family:sans-serif'>{title}</h4>"
    )


def _html_row(label: str, value: str, *, row_idx: int = 0) -> str:
    bg = "background:#fafafa;" if row_idx % 2 == 1 else ""
    td_l = f"style='{bg}padding:6px 12px;border:1px solid #ddd;text-align:left;font-weight:bold'"
    td_v = f"style='{bg}padding:6px 12px;border:1px solid #ddd;text-align:right'"
    return f"<tr><td {td_l}>{label}</td><td {td_v}>{value}</td></tr>"


def _html_section_row(title: str) -> str:
    return f"<tr><td colspan='2' {_SECTION_STYLE}>{title}</td></tr>"


def _html_table_open() -> str:
    return f"<table {_HTML_STYLE}>"


def _html_table_close() -> str:
    return "</table></div>"


def pretest_result_html(obj: Any) -> str:
    """HTML representation for PretestResultSnapshot."""
    summary = obj.reporting_summary()
    scalars = obj.canonical.get("scalars", {})

    mode = summary.get("mode", _NA)
    alpha = _fmt_float(scalars.get("alpha"), 4)
    n = _fmt_int(scalars.get("n"))
    t_pre = _fmt_int(scalars.get("T_pre"))
    t_post = _fmt_int(scalars.get("T_post"))
    s_pre = _fmt_float(summary.get("S_pre"))
    kappa = _fmt_float(scalars.get("kappa"))
    phi = summary.get("phi")
    phi_label = "Pass (0)" if phi == 0 else "Fail (1)" if phi == 1 else _NA
    threshold_m = _fmt_float(summary.get("threshold"))
    delta_bar = _fmt_float(summary.get("delta_bar"))

    ci = summary.get("conditional_interval")
    if ci is not None:
        ci_lower = _fmt_float(ci[0])
        ci_upper = _fmt_float(ci[1])
        ci_half = _fmt_float((ci[1] - ci[0]) / 2.0)
        ci_available = "Yes"
    else:
        ci_lower = _NA
        ci_upper = _NA
        ci_half = _NA
        ci_available = "No"

    ci_level = scalars.get("alpha")
    if ci_level is not None:
        try:
            ci_pct = f"{(1 - float(ci_level)) * 100:.0f}%"
        except (TypeError, ValueError):
            ci_pct = "95%"
    else:
        ci_pct = "95%"

    rows: list[str] = []
    rows.append(_html_section_row("General Info"))
    rows.append(_html_row("Mode", mode, row_idx=0))
    rows.append(_html_row("Alpha", alpha, row_idx=1))
    rows.append(_html_row("Periods (pre / post)", f"{t_pre} / {t_post}", row_idx=2))
    rows.append(_html_row("Sample size (n)", n, row_idx=3))
    rows.append(_html_section_row("Key Statistics"))
    rows.append(_html_row("Severity (S_pre)", s_pre, row_idx=4))
    rows.append(_html_row("Kappa", kappa, row_idx=5))
    rows.append(_html_row("Decision (\u03c6)", phi_label, row_idx=6))
    rows.append(_html_row("Threshold (M)", threshold_m, row_idx=7))
    rows.append(_html_section_row("Confidence Interval"))
    rows.append(_html_row("Point estimate (\u03b4\u0304)", delta_bar, row_idx=8))
    rows.append(_html_row("CI half-width", ci_half, row_idx=9))
    rows.append(_html_row(f"{ci_pct} CI", f"[{ci_lower}, {ci_upper}]", row_idx=10))
    rows.append(_html_row("CI available", ci_available, row_idx=11))

    return (
        _html_header("Pretest Result Summary")
        + _html_table_open()
        + "\n".join(rows)
        + _html_table_close()
    )


def simulation_coverage_html(obj: Any) -> str:
    """HTML representation for SimulationCoverageResult."""
    rows: list[str] = []
    idx = 0

    rows.append(_html_section_row("Simulation Setup"))
    rows.append(_html_row("Replications", _fmt_int(obj.replications), row_idx=idx)); idx += 1
    rows.append(_html_row("Pass count", _fmt_int(obj.pass_count), row_idx=idx)); idx += 1
    rows.append(_html_row("Pass rate", _fmt_pct(obj.pass_rate), row_idx=idx)); idx += 1
    if obj.critical_value is not None:
        rows.append(_html_row("Critical value (f_alpha)", _fmt_float(obj.critical_value), row_idx=idx)); idx += 1

    rows.append(_html_section_row("Proposed CI Coverage"))
    rows.append(_html_row("Conditional coverage", _fmt_pct(obj.conditional_coverage), row_idx=idx)); idx += 1
    rows.append(_html_row("Valid reporting rate", _fmt_pct(obj.valid_reporting_rate), row_idx=idx)); idx += 1
    rows.append(_html_row("Mean CI width (passed)", _fmt_float(obj.mean_ci_width_when_passed), row_idx=idx)); idx += 1
    if obj.conditional_coverage_standard_error is not None:
        rows.append(_html_row("Coverage SE", _fmt_float(obj.conditional_coverage_standard_error), row_idx=idx)); idx += 1
    if obj.valid_reporting_rate_standard_error is not None:
        rows.append(_html_row("Valid reporting SE", _fmt_float(obj.valid_reporting_rate_standard_error), row_idx=idx)); idx += 1

    rows.append(_html_section_row("Conventional CI Benchmark"))
    rows.append(_html_row("Conv. conditional coverage", _fmt_pct(obj.conventional_conditional_coverage), row_idx=idx)); idx += 1
    rows.append(_html_row("Conv. valid reporting rate", _fmt_pct(obj.conventional_valid_reporting_rate), row_idx=idx)); idx += 1
    rows.append(_html_row("Mean conv. CI width (passed)", _fmt_float(obj.mean_conventional_ci_width_when_passed), row_idx=idx)); idx += 1

    return (
        _html_header("Coverage Simulation Result")
        + _html_table_open()
        + "\n".join(rows)
        + _html_table_close()
    )


def m_sensitivity_html(obj: Any) -> str:
    """HTML representation for MSensitivityResult."""
    rows: list[str] = []
    idx = 0

    rows.append(_html_section_row("Summary"))
    rows.append(_html_row("Breakdown point (M*)", _fmt_float(obj.breakdown_point), row_idx=idx)); idx += 1
    rows.append(_html_row("S_pre_hat", _fmt_float(obj.s_pre_hat), row_idx=idx)); idx += 1
    rows.append(_html_row("Sample size (n)", _fmt_int(obj.n), row_idx=idx)); idx += 1
    rows.append(_html_row("Alpha", _fmt_float(obj.alpha, 4), row_idx=idx)); idx += 1
    rows.append(_html_row("CI half-width", _fmt_float(obj.ci_half_width), row_idx=idx)); idx += 1
    rows.append(_html_row("CI lower", _fmt_float(obj.ci_lower), row_idx=idx)); idx += 1
    rows.append(_html_row("CI upper", _fmt_float(obj.ci_upper), row_idx=idx)); idx += 1

    # Sensitivity table (multi-column)
    th_style = "style='background:#f0f0f0;padding:6px 12px;border:1px solid #ddd;text-align:center'"
    td_center = "style='padding:6px 8px;border:1px solid #ddd;text-align:right'"
    table_rows = [
        f"<tr><th {th_style}>M</th><th {th_style}>\u03c6(M)</th><th {th_style}>Can Report</th></tr>"
    ]
    n_rows = len(obj.m_values)
    show = min(n_rows, 20)
    for i in range(show):
        bg = "background:#fafafa;" if i % 2 == 1 else ""
        td_s = f"style='{bg}padding:6px 8px;border:1px solid #ddd;text-align:right'"
        m = _fmt_float(obj.m_values[i])
        phi = str(obj.phi_values[i])
        can = "Yes" if obj.can_report[i] else "No"
        table_rows.append(f"<tr><td {td_s}>{m}</td><td {td_s}>{phi}</td><td {td_s}>{can}</td></tr>")
    if n_rows > show:
        table_rows.append(
            f"<tr><td colspan='3' style='padding:6px;border:1px solid #ddd;text-align:center;"
            f"font-style:italic'>... {n_rows - show} more rows</td></tr>"
        )

    sensitivity_table = (
        f"<table {_HTML_STYLE}>"
        + "\n".join(table_rows)
        + "</table>"
    )

    return (
        _html_header("M-Sensitivity Analysis")
        + _html_table_open()
        + "\n".join(rows)
        + _html_table_close()
        + "<h5 style='margin:8px 0 4px;font-family:sans-serif'>Sensitivity Table</h5>"
        + sensitivity_table
        + "</div>"
    )


def monte_carlo_html(obj: Any) -> str:
    """HTML representation for MonteCarloResult."""
    rows: list[str] = []
    idx = 0

    rows.append(_html_section_row("Configuration"))
    rows.append(_html_row("Replications", _fmt_int(obj.replications), row_idx=idx)); idx += 1
    rows.append(_html_row("Mode", obj.mode, row_idx=idx)); idx += 1
    rows.append(_html_row("Threshold M", _fmt_float(obj.threshold_m), row_idx=idx)); idx += 1
    rows.append(_html_row("Alpha", _fmt_float(obj.alpha, 4), row_idx=idx)); idx += 1
    rows.append(_html_row("p-norm", _fmt_float(obj.p_norm, 3), row_idx=idx)); idx += 1

    rows.append(_html_section_row("Pass / Coverage"))
    rows.append(_html_row("Pass count", _fmt_int(obj.pass_count), row_idx=idx)); idx += 1
    rows.append(_html_row("Pass rate", _fmt_pct(obj.pass_rate), row_idx=idx)); idx += 1
    rows.append(_html_row("Covered count", _fmt_int(obj.covered_count), row_idx=idx)); idx += 1
    rows.append(_html_row("Conditional coverage", _fmt_pct(obj.conditional_coverage), row_idx=idx)); idx += 1
    rows.append(_html_row("Valid reporting rate", _fmt_pct(obj.valid_reporting_rate), row_idx=idx)); idx += 1

    rows.append(_html_section_row("Severity & CI Width"))
    rows.append(_html_row("Mean S_pre", _fmt_float(obj.mean_s_pre), row_idx=idx)); idx += 1
    rows.append(_html_row("Std S_pre", _fmt_float(obj.std_s_pre), row_idx=idx)); idx += 1
    rows.append(_html_row("Mean CI width", _fmt_float(obj.mean_ci_width), row_idx=idx)); idx += 1

    return (
        _html_header("Monte Carlo Coverage Result")
        + _html_table_open()
        + "\n".join(rows)
        + _html_table_close()
    )
