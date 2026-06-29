from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Sequence

import yaml

from . import __version__
from .api import parse_stata_command
from .data_estimators import (
    build_prop99_python_handoff_summary,
    build_prop99_window_iter_deterministic_split_capture_evidence,
    build_prop99_window_iter_parity_summary,
    load_prop99_window_iter_records_from_csv,
)
from .plotting import render_event_study_svg
from .replay_summary import (
    load_prop99_capture_ready_overall_bundles,
    load_prop99_nonoverall_split_capture_inventory,
    load_prop99_overall_auxiliary_scaffold,
    load_prop99_replay_scaffold,
    load_prop99_replay_story_packet,
    load_prop99_window_iter_stata_split_capture_evidence,
    load_capture_ready_overall_bundles_from_paths,
    load_stata_split_capture_evidence_from_paths,
    materialize_prop99_replay_summary,
    materialize_replay_summary_from_scaffold,
    materialize_replay_summary_from_paths,
)
from .result_schema import seed_result_snapshot

_SOURCE_TREE_HELPERS_ENV = "PRETEST_ENABLE_SOURCE_TREE_HELPERS"
_SOURCE_TREE_HELPER_COMMANDS = {
    "prop99-capture-ready-overall-bundles",
    "prop99-nonoverall-split-capture-inventory",
    "prop99-overall-auxiliary-scaffold",
    "prop99-replay-scaffold",
    "prop99-replay-story-packet",
    "prop99-replay-summary",
    "prop99-graph-preview-svg",
    "prop99-window-iter-deterministic-split-capture-evidence",
    "prop99-window-iter-parity-summary",
    "prop99-window-iter-stata-split-capture-evidence",
}

_USAGE = "\n".join(
    [
        "usage: pretest 'pretest depvar, treatment(...) time(...) threshold(...) [options]'",
        "       pretest replay-summary --driver PATH --template PATH [...]",
        "       pretest replay-summary-from-scaffold --scaffold PATH",
        "       pretest capture-ready-overall-bundles --case-id CASE_ID --driver PATH --template PATH [...]",
        "       pretest stata-split-capture-evidence --case-id CASE_ID --driver PATH --template PATH --stata-stdout PATH --stata-stored-results PATH",
        "       pretest prop99-python-handoff-summary --records-csv PATH",
        "",
        "subcommands:",
        "  replay-summary                 materialize the canonical replay summary JSON document",
        "  replay-summary-from-scaffold   materialize a replay summary JSON document from a scaffold file",
        "  capture-ready-overall-bundles  emit the committed overall-case Stata/Python bundle pair",
        "  stata-split-capture-evidence   emit Stata-only split-doc evidence for a non-overall replay case",
        "  prop99-python-handoff-summary  compute the Prop99 records-to-snapshot Python workflow from caller-supplied records",
        "",
        "Source-checkout reference helpers are not part of the public wheel CLI contract.",
        f"Set {_SOURCE_TREE_HELPERS_ENV}=1 in a source checkout to run local reference helpers.",
    ]
)
_REPLAY_SUMMARY_USAGE = (
    "usage: pretest replay-summary --driver PATH --template PATH "
    "[--stata-bundle CASE_ID=PATH] [--python-bundle CASE_ID=PATH] "
    "[--overall-capture-packet CASE_ID=PATH] "
    "[--overall-capture-verifier-input CASE_ID=PATH] "
    "[--precapture-contract CASE_ID=PATH] [--capture-metadata CASE_ID=PATH]"
)
_REPLAY_SUMMARY_FROM_SCAFFOLD_USAGE = (
    "usage: pretest replay-summary-from-scaffold --scaffold PATH|-"
)
_CAPTURE_READY_OVERALL_BUNDLES_USAGE = (
    "usage: pretest capture-ready-overall-bundles --case-id CASE_ID "
    "--driver PATH --template PATH --overall-capture-packet PATH "
    "--overall-capture-verifier-input PATH --precapture-contract PATH "
    "--capture-metadata PATH [--promote-authoritative-fields]"
)
_STATA_SPLIT_CAPTURE_EVIDENCE_USAGE = (
    "usage: pretest stata-split-capture-evidence --case-id CASE_ID "
    "--driver PATH --template PATH --stata-stdout PATH --stata-stored-results PATH"
)
_PROP99_REPLAY_SUMMARY_USAGE = (
    "usage: pretest prop99-replay-summary [--format json|text]"
)
_PROP99_GRAPH_PREVIEW_SVG_USAGE = (
    "usage: pretest prop99-graph-preview-svg [--output PATH|-]"
)
_PROP99_OVERALL_AUXILIARY_SCAFFOLD_USAGE = (
    "usage: pretest prop99-overall-auxiliary-scaffold"
)
_PROP99_REPLAY_SCAFFOLD_USAGE = "usage: pretest prop99-replay-scaffold"
_PROP99_REPLAY_STORY_PACKET_USAGE = "usage: pretest prop99-replay-story-packet"
_PROP99_CAPTURE_READY_OVERALL_BUNDLES_USAGE = (
    "usage: pretest prop99-capture-ready-overall-bundles "
    "[--promote-authoritative-fields]"
)
_PROP99_NONOVERALL_SPLIT_CAPTURE_INVENTORY_USAGE = (
    "usage: pretest prop99-nonoverall-split-capture-inventory [--format json|text]"
)
_PROP99_WINDOW_ITER_STATA_SPLIT_CAPTURE_EVIDENCE_USAGE = (
    "usage: pretest prop99-window-iter-stata-split-capture-evidence"
)
_PROP99_WINDOW_ITER_DETERMINISTIC_SPLIT_CAPTURE_EVIDENCE_USAGE = (
    "usage: pretest prop99-window-iter-deterministic-split-capture-evidence"
)
_PROP99_WINDOW_ITER_PARITY_SUMMARY_USAGE = (
    "usage: pretest prop99-window-iter-parity-summary [--format json|text]"
)
_PROP99_PYTHON_HANDOFF_SUMMARY_USAGE = (
    "usage: pretest prop99-python-handoff-summary "
    "--records-csv PATH [--format json|text]"
)


def _split_inline_option_token(
    token: str,
    *,
    recognized_flags: set[str],
) -> tuple[str, str | None]:
    if token in recognized_flags or "=" not in token:
        return token, None
    flag, value = token.split("=", 1)
    if flag in recognized_flags:
        return flag, value
    return token, None


def _handle_no_arg_subcommand_tokens(
    tokens: Sequence[str],
    *,
    usage: str,
    command_name: str,
) -> bool:
    token_list = list(tokens)
    if token_list and token_list[0] in {"--help", "-h"}:
        print(usage)
        return False
    for raw_token in token_list:
        if raw_token.startswith("-"):
            raise ValueError(f"Unrecognized {command_name} option: {raw_token}")
        raise ValueError(
            f"{command_name} does not accept positional arguments: {raw_token}"
        )
    return True


def _parse_case_path_entries(
    values: list[str],
    *,
    flag: str,
) -> dict[str, str] | None:
    if not values:
        return None

    parsed: dict[str, str] = {}
    for entry in values:
        case_id, separator, path = entry.partition("=")
        if not separator or not case_id.strip() or not path.strip():
            raise ValueError(f"{flag} must use CASE_ID=PATH entries.")
        normalized_case_id = case_id.strip()
        if normalized_case_id in parsed:
            raise ValueError(f"{flag} must not repeat case_id {normalized_case_id}.")
        parsed[normalized_case_id] = path.strip()
    return parsed


def _parse_replay_summary_args(
    tokens: Sequence[str],
) -> tuple[str, str, dict[str, str] | None, dict[str, str] | None, dict[str, str] | None, dict[str, str] | None, dict[str, str] | None, dict[str, str] | None]:
    driver: str | None = None
    template: str | None = None
    repeated_flags: dict[str, list[str]] = {
        "--stata-bundle": [],
        "--python-bundle": [],
        "--overall-capture-packet": [],
        "--overall-capture-verifier-input": [],
        "--precapture-contract": [],
        "--capture-metadata": [],
    }
    single_flags = {"--driver", "--template"}
    recognized_flags = set(repeated_flags) | single_flags | {"--help", "-h"}

    def parse_single_use_path(flag: str, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError(f"{flag} must not be blank.")
        return normalized_value

    index = 0
    token_list = list(tokens)
    while index < len(token_list):
        token, inline_value = _split_inline_option_token(
            token_list[index],
            recognized_flags=recognized_flags,
        )
        if token in {"--help", "-h"}:
            print(_REPLAY_SUMMARY_USAGE)
            raise SystemExit(0)
        if token not in recognized_flags:
            raise ValueError(f"Unrecognized replay-summary option: {token}")
        if inline_value is not None:
            value = inline_value
            step = 1
        elif index + 1 >= len(token_list):
            raise ValueError(f"{token} requires a value.")
        else:
            value = token_list[index + 1]
            if value in recognized_flags:
                raise ValueError(f"{token} requires a value.")
            step = 2
        if token == "--driver":
            if driver is not None:
                raise ValueError("--driver may only be provided once.")
            driver = parse_single_use_path(token, value)
        elif token == "--template":
            if template is not None:
                raise ValueError("--template may only be provided once.")
            template = parse_single_use_path(token, value)
        else:
            repeated_flags[token].append(value)
        index += step

    if driver is None:
        raise ValueError("--driver is required.")
    if template is None:
        raise ValueError("--template is required.")

    return (
        driver,
        template,
        _parse_case_path_entries(repeated_flags["--stata-bundle"], flag="--stata-bundle"),
        _parse_case_path_entries(
            repeated_flags["--python-bundle"],
            flag="--python-bundle",
        ),
        _parse_case_path_entries(
            repeated_flags["--overall-capture-packet"],
            flag="--overall-capture-packet",
        ),
        _parse_case_path_entries(
            repeated_flags["--overall-capture-verifier-input"],
            flag="--overall-capture-verifier-input",
        ),
        _parse_case_path_entries(
            repeated_flags["--precapture-contract"],
            flag="--precapture-contract",
        ),
        _parse_case_path_entries(
            repeated_flags["--capture-metadata"],
            flag="--capture-metadata",
        ),
    )


def _parse_capture_ready_overall_bundles_args(
    tokens: Sequence[str],
) -> tuple[str, str, str, str, str, str, str, bool]:
    parsed: dict[str, str | None] = {
        "--case-id": None,
        "--driver": None,
        "--template": None,
        "--overall-capture-packet": None,
        "--overall-capture-verifier-input": None,
        "--precapture-contract": None,
        "--capture-metadata": None,
    }
    promote_authoritative_fields = False
    recognized_flags = set(parsed) | {
        "--help",
        "-h",
        "--promote-authoritative-fields",
    }

    def parse_single_use_value(flag: str, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError(f"{flag} must not be blank.")
        return normalized_value

    index = 0
    token_list = list(tokens)
    while index < len(token_list):
        token, inline_value = _split_inline_option_token(
            token_list[index],
            recognized_flags=recognized_flags,
        )
        if token in {"--help", "-h"}:
            print(_CAPTURE_READY_OVERALL_BUNDLES_USAGE)
            raise SystemExit(0)
        if token == "--promote-authoritative-fields":
            if inline_value is not None:
                raise ValueError(
                    "--promote-authoritative-fields does not accept a value."
                )
            if promote_authoritative_fields:
                raise ValueError("--promote-authoritative-fields may only be provided once.")
            promote_authoritative_fields = True
            index += 1
            continue
        if token not in recognized_flags:
            raise ValueError(
                f"Unrecognized capture-ready-overall-bundles option: {token}"
            )
        if inline_value is not None:
            value = inline_value
            step = 1
        elif index + 1 >= len(token_list):
            raise ValueError(f"{token} requires a value.")
        else:
            value = token_list[index + 1]
            if value in recognized_flags:
                raise ValueError(f"{token} requires a value.")
            step = 2
        if parsed[token] is not None:
            raise ValueError(f"{token} may only be provided once.")
        parsed[token] = parse_single_use_value(token, value)
        index += step

    for flag, value in parsed.items():
        if value is None:
            raise ValueError(f"{flag} is required.")

    return (
        parsed["--case-id"],
        parsed["--driver"],
        parsed["--template"],
        parsed["--overall-capture-packet"],
        parsed["--overall-capture-verifier-input"],
        parsed["--precapture-contract"],
        parsed["--capture-metadata"],
        promote_authoritative_fields,
    )


def _parse_stata_split_capture_evidence_args(
    tokens: Sequence[str],
) -> tuple[str, str, str, str, str]:
    parsed: dict[str, str | None] = {
        "--case-id": None,
        "--driver": None,
        "--template": None,
        "--stata-stdout": None,
        "--stata-stored-results": None,
    }
    recognized_flags = set(parsed) | {"--help", "-h"}

    def parse_single_use_value(flag: str, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError(f"{flag} must not be blank.")
        return normalized_value

    index = 0
    token_list = list(tokens)
    while index < len(token_list):
        token, inline_value = _split_inline_option_token(
            token_list[index],
            recognized_flags=recognized_flags,
        )
        if token in {"--help", "-h"}:
            print(_STATA_SPLIT_CAPTURE_EVIDENCE_USAGE)
            raise SystemExit(0)
        if token not in recognized_flags:
            raise ValueError(
                f"Unrecognized stata-split-capture-evidence option: {token}"
            )
        if inline_value is not None:
            value = inline_value
            step = 1
        elif index + 1 >= len(token_list):
            raise ValueError(f"{token} requires a value.")
        else:
            value = token_list[index + 1]
            if value in recognized_flags:
                raise ValueError(f"{token} requires a value.")
            step = 2
        if parsed[token] is not None:
            raise ValueError(f"{token} may only be provided once.")
        parsed[token] = parse_single_use_value(token, value)
        index += step

    for flag, value in parsed.items():
        if value is None:
            raise ValueError(f"{flag} is required.")

    return (
        parsed["--case-id"],
        parsed["--driver"],
        parsed["--template"],
        parsed["--stata-stdout"],
        parsed["--stata-stored-results"],
    )


def _run_replay_summary_cli(tokens: Sequence[str]) -> int:
    (
        driver,
        template,
        stata_bundle_paths,
        python_bundle_paths,
        overall_capture_packet_paths,
        overall_capture_verifier_input_paths,
        precapture_contract_paths_by_case,
        capture_metadata_paths_by_case,
    ) = _parse_replay_summary_args(tokens)
    summary = materialize_replay_summary_from_paths(
        driver,
        template,
        stata_bundle_paths=stata_bundle_paths,
        python_bundle_paths=python_bundle_paths,
        overall_capture_packet_paths=overall_capture_packet_paths,
        overall_capture_verifier_input_paths=overall_capture_verifier_input_paths,
        precapture_contract_paths_by_case=precapture_contract_paths_by_case,
        capture_metadata_paths_by_case=capture_metadata_paths_by_case,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _parse_replay_summary_from_scaffold_args(tokens: Sequence[str]) -> str:
    token_list = list(tokens)
    recognized_flags = {"--scaffold", "--help", "-h"}
    scaffold_path: str | None = None

    index = 0
    while index < len(token_list):
        raw_token = token_list[index]
        token, inline_value = _split_inline_option_token(
            raw_token,
            recognized_flags=recognized_flags,
        )
        if token in {"--help", "-h"}:
            print(_REPLAY_SUMMARY_FROM_SCAFFOLD_USAGE)
            raise SystemExit(0)
        if token not in recognized_flags:
            if raw_token.startswith("-"):
                raise ValueError(
                    "Unrecognized replay-summary-from-scaffold option: "
                    f"{raw_token}"
                )
            raise ValueError(
                "replay-summary-from-scaffold does not accept positional arguments: "
                f"{raw_token}"
            )
        if scaffold_path is not None:
            raise ValueError("--scaffold may only be provided once.")
        if inline_value is not None:
            value = inline_value
            step = 1
        elif index + 1 >= len(token_list):
            raise ValueError("--scaffold requires a value.")
        else:
            value = token_list[index + 1]
            if value in recognized_flags:
                raise ValueError("--scaffold requires a value.")
            step = 2
        scaffold_path = value.strip()
        index += step

    if scaffold_path is None:
        raise ValueError("--scaffold is required.")
    if not scaffold_path:
        raise ValueError("--scaffold must not be blank.")
    return scaffold_path


def _run_replay_summary_from_scaffold_cli(tokens: Sequence[str]) -> int:
    scaffold_path = _parse_replay_summary_from_scaffold_args(tokens)
    try:
        raw_text = (
            sys.stdin.read()
            if scaffold_path == "-"
            else Path(scaffold_path).read_text(encoding="utf-8")
        )
    except FileNotFoundError as exc:
        raise ValueError(f"--scaffold path does not exist: {scaffold_path}") from exc
    except OSError as exc:
        raise ValueError(f"--scaffold could not be read: {scaffold_path}") from exc

    try:
        scaffold = json.loads(raw_text)
    except json.JSONDecodeError:
        try:
            scaffold = yaml.safe_load(raw_text)
        except yaml.YAMLError as exc:
            raise ValueError(
                f"--scaffold must contain valid JSON or YAML: {scaffold_path}"
            ) from exc

    if not isinstance(scaffold, dict):
        raise ValueError(
            f"--scaffold must contain a JSON or YAML object at the root: {scaffold_path}"
        )

    summary = materialize_replay_summary_from_scaffold(scaffold)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _run_capture_ready_overall_bundles_cli(tokens: Sequence[str]) -> int:
    (
        case_id,
        driver,
        template,
        overall_capture_packet_path,
        overall_capture_verifier_input_path,
        precapture_contract_path,
        capture_metadata_path,
        promote_authoritative_fields,
    ) = _parse_capture_ready_overall_bundles_args(tokens)
    bundle_pair = load_capture_ready_overall_bundles_from_paths(
        driver,
        template,
        case_id=case_id,
        overall_capture_packet_path=overall_capture_packet_path,
        overall_capture_verifier_input_path=overall_capture_verifier_input_path,
        precapture_contract_path=precapture_contract_path,
        capture_metadata_path=capture_metadata_path,
        promote_authoritative_fields=promote_authoritative_fields,
    )
    print(json.dumps(bundle_pair, indent=2, sort_keys=True))
    return 0


def _run_stata_split_capture_evidence_cli(tokens: Sequence[str]) -> int:
    (
        case_id,
        driver,
        template,
        stata_stdout_path,
        stata_stored_results_path,
    ) = _parse_stata_split_capture_evidence_args(tokens)
    evidence = load_stata_split_capture_evidence_from_paths(
        driver,
        template,
        case_id=case_id,
        stata_stdout_path=stata_stdout_path,
        stata_stored_results_path=stata_stored_results_path,
    )
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


def _parse_no_arg_format_subcommand(
    tokens: Sequence[str],
    *,
    usage: str,
    command_name: str,
) -> str:
    output_format = "json"
    seen_format = False
    recognized_flags = {"--help", "-h", "--format"}
    token_list = list(tokens)
    index = 0
    while index < len(token_list):
        raw_token = token_list[index]
        token, inline_value = _split_inline_option_token(
            raw_token,
            recognized_flags=recognized_flags,
        )
        if token in {"--help", "-h"}:
            print(usage)
            raise SystemExit(0)
        if token not in recognized_flags:
            if raw_token.startswith("-"):
                raise ValueError(f"Unrecognized {command_name} option: {raw_token}")
            raise ValueError(
                f"{command_name} does not accept positional arguments: {raw_token}"
            )
        if seen_format:
            raise ValueError("--format may only be provided once.")
        seen_format = True
        if inline_value is not None:
            value = inline_value
            step = 1
        elif index + 1 >= len(token_list):
            raise ValueError("--format requires a value.")
        else:
            value = token_list[index + 1]
            if value in recognized_flags:
                raise ValueError("--format requires a value.")
            step = 2
        normalized_value = value.strip().lower()
        if normalized_value not in {"json", "text"}:
            raise ValueError("--format must be json or text.")
        output_format = normalized_value
        index += step
    return output_format


def _parse_prop99_python_handoff_summary_args(
    tokens: Sequence[str],
) -> tuple[str, str]:
    output_format = "json"
    records_csv: str | None = None
    seen_format = False
    recognized_flags = {"--help", "-h", "--format", "--records-csv"}
    token_list = list(tokens)
    index = 0
    while index < len(token_list):
        raw_token = token_list[index]
        token, inline_value = _split_inline_option_token(
            raw_token,
            recognized_flags=recognized_flags,
        )
        if token in {"--help", "-h"}:
            print(_PROP99_PYTHON_HANDOFF_SUMMARY_USAGE)
            raise SystemExit(0)
        if token not in recognized_flags:
            if raw_token.startswith("-"):
                raise ValueError(
                    f"Unrecognized prop99-python-handoff-summary option: {raw_token}"
                )
            raise ValueError(
                "prop99-python-handoff-summary does not accept positional "
                f"arguments: {raw_token}"
            )
        if token == "--format":
            if seen_format:
                raise ValueError("--format may only be provided once.")
            seen_format = True
            if inline_value is not None:
                value = inline_value
                step = 1
            elif index + 1 >= len(token_list):
                raise ValueError("--format requires a value.")
            else:
                value = token_list[index + 1]
                if value in recognized_flags:
                    raise ValueError("--format requires a value.")
                step = 2
            normalized_value = value.strip().lower()
            if normalized_value not in {"json", "text"}:
                raise ValueError("--format must be json or text.")
            output_format = normalized_value
            index += step
            continue
        if token == "--records-csv":
            if records_csv is not None:
                raise ValueError("--records-csv may only be provided once.")
            if inline_value is not None:
                value = inline_value
                step = 1
            elif index + 1 >= len(token_list):
                raise ValueError("--records-csv requires a value.")
            else:
                value = token_list[index + 1]
                if value in recognized_flags:
                    raise ValueError("--records-csv requires a value.")
                step = 2
            normalized_value = value.strip()
            if not normalized_value:
                raise ValueError("--records-csv must not be blank.")
            records_csv = normalized_value
            index += step
            continue
        raise ValueError(
            f"Unrecognized prop99-python-handoff-summary option: {raw_token}"
        )
    if records_csv is None:
        raise ValueError(
            "prop99-python-handoff-summary requires --records-csv PATH. "
            "Regenerate the reduced Proposition 99 records with the manuscript "
            "replication route or provide an equivalent CSV with columns "
            "cigsale, treated, and year."
        )
    return output_format, records_csv


def _format_count_mapping(mapping: dict[str, object], keys: Sequence[str]) -> str:
    return ", ".join(f"{key}={mapping.get(key, 0)}" for key in keys)


def _render_case_list(case_ids: object) -> str:
    if not isinstance(case_ids, list) or not case_ids:
        return "none"
    return ", ".join(str(case_id) for case_id in case_ids)


def _format_optional_metric(value: object) -> object:
    if value is None:
        return "n/a"
    return value


def _text_report_title(title: str) -> list[str]:
    return [title, "=" * len(title)]


def _append_text_report_section(lines: list[str], title: str) -> None:
    lines.extend(["", title, "-" * len(title)])


def _render_graph_preview_point(point: object, *, label: str) -> str:
    if not isinstance(point, dict):
        raise ValueError(f"{label} graph preview point must be a mapping")
    return (
        f"    {label:<4} "
        f"{point.get('period'):>3} "
        f"{_format_float(point.get('estimate')):>11} "
        f"{_format_float(point.get('ci_lower')):>11} "
        f"{_format_float(point.get('ci_upper')):>11}"
    )


def _append_graph_preview_table(
    lines: list[str],
    *,
    pre_preview: list[object],
    post_preview: list[object],
) -> None:
    lines.append("  graph preview points (stored-results reconstruction):")
    lines.append("    type rel   estimate    ci_lower    ci_upper")
    for point in pre_preview:
        lines.append(_render_graph_preview_point(point, label="pre"))
    for point in post_preview:
        lines.append(_render_graph_preview_point(point, label="post"))


def _render_prop99_replay_summary_text(summary: dict[str, object]) -> str:
    document_summary = summary["document_summary"]
    cases = summary["cases"]
    if not isinstance(document_summary, dict):
        raise ValueError("document_summary must be a mapping")
    if not isinstance(cases, list):
        raise ValueError("cases must be a list")
    case_totals = document_summary["case_totals"]
    graph_totals = document_summary["graph_status_totals"]
    graph_readiness_totals = document_summary["graph_readiness_totals"]
    oracle_totals = document_summary["oracle_capture_totals"]
    verdict_cases = document_summary["case_ids_by_verdict"]
    graph_cases = document_summary["case_ids_by_graph_status"]
    graph_readiness_cases = document_summary["case_ids_by_graph_readiness"]
    oracle_cases = document_summary["case_ids_by_oracle_capture"]
    bucket_totals = document_summary["bucket_totals"]
    for field, value in (
        ("case_totals", case_totals),
        ("graph_status_totals", graph_totals),
        ("graph_readiness_totals", graph_readiness_totals),
        ("oracle_capture_totals", oracle_totals),
        ("case_ids_by_verdict", verdict_cases),
        ("case_ids_by_graph_status", graph_cases),
        ("case_ids_by_graph_readiness", graph_readiness_cases),
        ("case_ids_by_oracle_capture", oracle_cases),
        ("bucket_totals", bucket_totals),
    ):
        if not isinstance(value, dict):
            raise ValueError(f"document_summary.{field} must be a mapping")

    lines = _text_report_title("Prop99 replay summary") + [
        f"Cases: {summary['case_count']}",
        "Verdicts: "
        + _format_count_mapping(
            case_totals,
            (
                "matched",
                "mismatch",
                "pending",
            ),
        ),
        f"Oracle capture: {_format_count_mapping(oracle_totals, ('capture_ready', 'captured_not_ready', 'blocked', 'not_applicable'))}",
        f"Graph status: {_format_count_mapping(graph_totals, ('matches_driver', 'mismatches_driver', 'pending'))}",
        f"Graph readiness: {_format_count_mapping(graph_readiness_totals, ('publication_ready', 'status_matched_not_publishable', 'status_mismatch', 'pending_capture'))}",
    ]
    _append_text_report_section(lines, "Case status")
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("cases entries must be mappings")
        details = [f"verdict={case.get('verdict')}"]
        if case.get("python_parity_status") is not None:
            details.append(f"python={case.get('python_parity_status')}")
        if case.get("capture_status") is not None:
            details.append(f"capture={case.get('capture_status')}")
        if case.get("graph_status") is not None:
            details.append(f"graph={case.get('graph_status')}")
        oracle_summary = case.get("oracle_capture_summary")
        graph_status_summary = case.get("graph_status_summary")
        if isinstance(oracle_summary, dict):
            metadata_status = oracle_summary.get("capture_metadata_status")
            if isinstance(metadata_status, dict):
                details.append(
                    "oracle_capture="
                    + ("ready" if metadata_status.get("capture_ready") is True else "not-ready")
                )
                graph_status = metadata_status.get("graph_status")
                if graph_status is not None and case.get("graph_status") is None:
                    details.append(f"graph={graph_status}")
        lines.append(f"- {case.get('case_id')}: " + "; ".join(details))
        if isinstance(graph_status_summary, dict):
            graph_readiness_summary = case.get("graph_readiness_summary")
            graph_publication_ready = False
            if isinstance(graph_readiness_summary, dict):
                graph_publication_ready = (
                    graph_readiness_summary.get("publication_ready") is True
                )
            graph_status = graph_status_summary.get("stata")
            if (
                graph_status_summary.get("stata") is None
                and graph_status_summary.get("python") is None
                and graph_status_summary.get("matches_driver") is None
            ):
                lines.append(
                    "  graph data: "
                    f"expected={graph_status_summary.get('expected')}; "
                    "capture=pending; publication_ready=no"
                )
            else:
                lines.append(
                    "  graph data: "
                    f"expected={graph_status_summary.get('expected')}; "
                    f"stata={graph_status_summary.get('stata')}; "
                    f"python={graph_status_summary.get('python')}; "
                    f"matches_driver={_format_bool(graph_status_summary.get('matches_driver'))}; "
                    f"publication_ready={_format_bool(graph_publication_ready)}"
                )
            if graph_status == "graph-attempted-but-error-198":
                lines.append(
                    "  graph boundary: graph status matches the replay driver, "
                    "but captured graph series are unavailable after Stata error 198"
                )
            elif isinstance(graph_readiness_summary, dict):
                reason = graph_readiness_summary.get("reason")
                if isinstance(reason, str) and reason.strip():
                    lines.append(f"  graph boundary: {reason}")
            graph_data_summary = case.get("graph_data_summary")
            if isinstance(graph_data_summary, dict):
                lines.append(
                    "  graph series: "
                    f"pre={graph_data_summary.get('pre_treatment_points_observed')}/"
                    f"{graph_data_summary.get('pre_treatment_points_expected')}; "
                    f"post={graph_data_summary.get('post_treatment_points_observed')}/"
                    f"{graph_data_summary.get('post_treatment_points_expected')}; "
                    f"complete={_format_bool(graph_data_summary.get('series_complete'))}"
                )
                graph_preview = graph_data_summary.get("derived_event_study_preview")
                if isinstance(graph_preview, dict):
                    pre_preview = graph_preview.get("pre_treatment_series")
                    post_preview = graph_preview.get("post_treatment_series")
                    if isinstance(pre_preview, list) and isinstance(post_preview, list):
                        lines.append(
                            "  graph preview: "
                            f"derived_pre={len(pre_preview)}; "
                            f"derived_post={len(post_preview)}; "
                            f"source={graph_preview.get('source')}"
                        )
                        _append_graph_preview_table(
                            lines,
                            pre_preview=pre_preview,
                            post_preview=post_preview,
                        )
                graph_comparison = graph_data_summary.get("series_comparison")
                if isinstance(graph_comparison, dict):
                    lines.append(
                        "  graph comparison: "
                        f"status={graph_comparison.get('status')}; "
                        f"pre_max_abs_diff={_format_optional_metric(graph_comparison.get('pre_max_abs_diff'))}; "
                        f"post_max_abs_diff={_format_optional_metric(graph_comparison.get('post_max_abs_diff'))}; "
                        f"tolerance={graph_comparison.get('tolerance')}"
                    )

    stdout_buckets = bucket_totals["stdout_summary"]
    stored_buckets = bucket_totals["stored_results_summary"]
    if not isinstance(stdout_buckets, dict) or not isinstance(stored_buckets, dict):
        raise ValueError("document_summary.bucket_totals summaries must be mappings")
    _append_text_report_section(lines, "Drilldown")
    lines.extend(
        [
            f"Pending cases: {_render_case_list(verdict_cases.get('pending'))}",
            f"Graph pending: {_render_case_list(graph_cases.get('pending'))}",
            f"Graph matched driver: {_render_case_list(graph_cases.get('matches_driver'))}",
            f"Graph publication-ready: {_render_case_list(graph_readiness_cases.get('publication_ready'))}",
            f"Graph not publishable: {_render_case_list(graph_readiness_cases.get('status_matched_not_publishable'))}",
            f"Oracle capture-ready: {_render_case_list(oracle_cases.get('capture_ready'))}",
            f"Oracle not applicable: {_render_case_list(oracle_cases.get('not_applicable'))}",
        ]
    )
    _append_text_report_section(lines, "Planned comparison fields")
    lines.extend(
        [
            f"stdout exact={stdout_buckets['exact']['planned_fields']}, display-rounded={stdout_buckets['display_rounded']['planned_fields']}, exact-absence={stdout_buckets['exact_absence']['planned_fields']}",
            f"stored-results exact={stored_buckets['exact']['planned_fields']}, display-rounded={stored_buckets['display_rounded']['planned_fields']}, exact-absence={stored_buckets['exact_absence']['planned_fields']}",
        ]
    )
    return "\n".join(lines)


def _run_prop99_replay_summary_cli(tokens: Sequence[str]) -> int:
    output_format = _parse_no_arg_format_subcommand(
        tokens,
        usage=_PROP99_REPLAY_SUMMARY_USAGE,
        command_name="prop99-replay-summary",
    )
    summary = materialize_prop99_replay_summary()

    if output_format == "text":
        print(_render_prop99_replay_summary_text(summary))
        return 0

    print(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _parse_prop99_graph_preview_svg_args(tokens: Sequence[str]) -> str | None:
    output_path: str | None = None
    recognized_flags = {"--help", "-h", "--output"}
    token_list = list(tokens)
    index = 0
    while index < len(token_list):
        raw_token = token_list[index]
        token, inline_value = _split_inline_option_token(
            raw_token,
            recognized_flags=recognized_flags,
        )
        if token in {"--help", "-h"}:
            print(_PROP99_GRAPH_PREVIEW_SVG_USAGE)
            raise SystemExit(0)
        if token not in recognized_flags:
            if raw_token.startswith("-"):
                raise ValueError(f"Unrecognized prop99-graph-preview-svg option: {raw_token}")
            raise ValueError(
                f"prop99-graph-preview-svg does not accept positional arguments: {raw_token}"
            )
        if output_path is not None:
            raise ValueError("--output may only be provided once.")
        if inline_value is not None:
            value = inline_value
            step = 1
        elif index + 1 >= len(token_list):
            raise ValueError("--output requires a value.")
        else:
            value = token_list[index + 1]
            if value in recognized_flags:
                raise ValueError("--output requires a value.")
            step = 2
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("--output must not be blank.")
        output_path = normalized_value
        index += step
    return output_path


def _prop99_overall_graph_data_summary() -> dict[str, object]:
    summary = materialize_prop99_replay_summary()
    cases = summary.get("cases")
    if not isinstance(cases, list):
        raise ValueError("prop99 replay summary cases must be a list")
    for case in cases:
        if (
            isinstance(case, dict)
            and case.get("case_id") == "PROP99-WINDOW-1985-1995-M5-OVERALL"
        ):
            graph_data_summary = case.get("graph_data_summary")
            if not isinstance(graph_data_summary, dict):
                raise ValueError("Prop99 overall case missing graph_data_summary")
            return graph_data_summary
    raise ValueError("Prop99 overall replay summary case is missing")


def _run_prop99_graph_preview_svg_cli(tokens: Sequence[str]) -> int:
    output_path = _parse_prop99_graph_preview_svg_args(tokens)
    svg = render_event_study_svg(_prop99_overall_graph_data_summary())
    if output_path is None or output_path == "-":
        sys.stdout.write(svg)
        return 0
    Path(output_path).write_text(svg, encoding="utf-8")
    return 0


def _run_prop99_replay_scaffold_cli(tokens: Sequence[str]) -> int:
    if not _handle_no_arg_subcommand_tokens(
        tokens,
        usage=_PROP99_REPLAY_SCAFFOLD_USAGE,
        command_name="prop99-replay-scaffold",
    ):
        return 0

    print(
        json.dumps(
            load_prop99_replay_scaffold(),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _run_prop99_overall_auxiliary_scaffold_cli(tokens: Sequence[str]) -> int:
    if not _handle_no_arg_subcommand_tokens(
        tokens,
        usage=_PROP99_OVERALL_AUXILIARY_SCAFFOLD_USAGE,
        command_name="prop99-overall-auxiliary-scaffold",
    ):
        return 0

    print(
        json.dumps(
            load_prop99_overall_auxiliary_scaffold(),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _run_prop99_replay_story_packet_cli(tokens: Sequence[str]) -> int:
    if not _handle_no_arg_subcommand_tokens(
        tokens,
        usage=_PROP99_REPLAY_STORY_PACKET_USAGE,
        command_name="prop99-replay-story-packet",
    ):
        return 0

    print(
        json.dumps(
            load_prop99_replay_story_packet(),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _run_prop99_capture_ready_overall_bundles_cli(tokens: Sequence[str]) -> int:
    token_list = list(tokens)
    promote_authoritative_fields = True
    saw_promote_authoritative_fields = False
    recognized_flags = {"--help", "-h", "--promote-authoritative-fields"}
    for raw_token in token_list:
        token, inline_value = _split_inline_option_token(
            raw_token,
            recognized_flags=recognized_flags,
        )
        if token in {"--help", "-h"}:
            print(_PROP99_CAPTURE_READY_OVERALL_BUNDLES_USAGE)
            return 0
        if token == "--promote-authoritative-fields":
            if inline_value is not None:
                raise ValueError(
                    "--promote-authoritative-fields does not accept a value."
                )
            if saw_promote_authoritative_fields:
                raise ValueError(
                    "--promote-authoritative-fields may only be provided once."
                )
            saw_promote_authoritative_fields = True
            promote_authoritative_fields = True
            continue
        if raw_token.startswith("-"):
            raise ValueError(
                "Unrecognized prop99-capture-ready-overall-bundles option: "
                f"{raw_token}"
            )
        raise ValueError(
            "prop99-capture-ready-overall-bundles does not accept positional "
            f"arguments: {raw_token}"
        )

    print(
        json.dumps(
            load_prop99_capture_ready_overall_bundles(
                promote_authoritative_fields=promote_authoritative_fields
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _render_prop99_nonoverall_split_capture_inventory_text(
    inventory: dict[str, object],
) -> str:
    totals = inventory["totals"]
    cases = inventory["cases"]
    if not isinstance(totals, dict):
        raise ValueError("totals must be a mapping")
    if not isinstance(cases, list):
        raise ValueError("cases must be a list")

    lines = _text_report_title("Prop99 non-overall split-capture inventory") + [
        f"Cases: {inventory['case_count']}",
        (
            "Readiness: "
            f"python_blocked={totals['python_blocked']}, "
            f"python_loadable={totals['python_loadable']}, "
            f"stata_loadable={totals['stata_loadable']}, "
            f"stata_pending={totals['stata_pending']}"
        ),
    ]
    _append_text_report_section(lines, "Case status")
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("cases entries must be mappings")
        payload_status = case["payload_status"]
        capture_status = case["capture_status"]
        sample_window = case["sample_window"]
        if not isinstance(payload_status, dict):
            raise ValueError("case payload_status must be a mapping")
        if not isinstance(capture_status, dict):
            raise ValueError("case capture_status must be a mapping")
        if not isinstance(sample_window, list) or len(sample_window) != 2:
            raise ValueError("case sample_window must be a two-element list")
        lines.extend(
            [
                f"- {case['case_id']} ({sample_window[0]}-{sample_window[1]}, {case['mode']}):",
                f"  comparison={case['comparison_status']}; stata_contract={case['stata_contract_status']}",
                (
                    "  payloads: "
                    f"stata_stdout={_format_bool(payload_status['stata_stdout_loadable'])}, "
                    f"stata_stored={_format_bool(payload_status['stata_stored_results_loadable'])}, "
                    f"python_stdout={_format_bool(payload_status['python_stdout_loadable'])}, "
                    f"python_stored={_format_bool(payload_status['python_stored_results_loadable'])}, "
                    f"stata_exact={_format_bool(payload_status['stata_exact_scalar_contract_verified'])}"
                ),
                (
                    "  capture: "
                    f"stata_stdout={capture_status['stata_stdout']}; "
                    f"stata_stored={capture_status['stata_stored_results']}; "
                    f"python_stdout={capture_status['python_stdout']}; "
                    f"python_stored={capture_status['python_stored_results']}"
                ),
                f"  boundary: {case['comparison_pending_reason']}",
            ]
        )
    return "\n".join(lines)


def _run_prop99_nonoverall_split_capture_inventory_cli(tokens: Sequence[str]) -> int:
    output_format = _parse_no_arg_format_subcommand(
        tokens,
        usage=_PROP99_NONOVERALL_SPLIT_CAPTURE_INVENTORY_USAGE,
        command_name="prop99-nonoverall-split-capture-inventory",
    )
    inventory = load_prop99_nonoverall_split_capture_inventory()

    if output_format == "text":
        print(_render_prop99_nonoverall_split_capture_inventory_text(inventory))
        return 0

    print(
        json.dumps(
            inventory,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _run_prop99_window_iter_stata_split_capture_evidence_cli(
    tokens: Sequence[str],
) -> int:
    if not _handle_no_arg_subcommand_tokens(
        tokens,
        usage=_PROP99_WINDOW_ITER_STATA_SPLIT_CAPTURE_EVIDENCE_USAGE,
        command_name="prop99-window-iter-stata-split-capture-evidence",
    ):
        return 0

    print(
        json.dumps(
            load_prop99_window_iter_stata_split_capture_evidence(),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _run_prop99_window_iter_deterministic_split_capture_evidence_cli(
    tokens: Sequence[str],
) -> int:
    if not _handle_no_arg_subcommand_tokens(
        tokens,
        usage=_PROP99_WINDOW_ITER_DETERMINISTIC_SPLIT_CAPTURE_EVIDENCE_USAGE,
        command_name="prop99-window-iter-deterministic-split-capture-evidence",
    ):
        return 0

    print(
        json.dumps(
            build_prop99_window_iter_deterministic_split_capture_evidence(),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _parse_prop99_window_iter_parity_summary_args(tokens: Sequence[str]) -> str:
    return _parse_no_arg_format_subcommand(
        tokens,
        usage=_PROP99_WINDOW_ITER_PARITY_SUMMARY_USAGE,
        command_name="prop99-window-iter-parity-summary",
    )


def _format_bool(value: object) -> str:
    return "yes" if value is True else "no" if value is False else str(value)


def _format_float(value: object, *, digits: int = 6) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{float(value):.{digits}f}"
    return str(value)


def _render_prop99_window_iter_parity_summary_text(
    summary: dict[str, object],
) -> str:
    records = summary["records_dimension_summary"]
    coordinates = summary["coordinate_metadata"]
    covariance = summary["covariance_estimator"]
    probe = summary["critical_value_probe_summary"]
    if not isinstance(records, dict):
        raise ValueError("records_dimension_summary must be a mapping")
    if not isinstance(coordinates, dict):
        raise ValueError("coordinate_metadata must be a mapping")
    if not isinstance(covariance, dict):
        raise ValueError("covariance_estimator must be a mapping")
    if not isinstance(probe, dict):
        raise ValueError("critical_value_probe_summary must be a mapping")

    lines = _text_report_title("Prop99 window iterative parity summary") + [
        f"Case: {summary['case_id']}",
        f"Status: {summary['comparison_status']}",
        f"Deterministic fields: {summary['deterministic_fields_checked']} checked, all match: {_format_bool(summary['deterministic_all_match'])}",
        f"Replay promotion excluded: {', '.join(summary['excluded_from_deterministic_replay_promotion'])}",
    ]
    _append_text_report_section(lines, "Design")
    lines.extend(
        [
        f"Records: {records['records_count']} rows across {records['year_count']} years ({records['pre_year_count']} pre, {records['post_year_count']} post)",
        f"Cells: {records['per_year_treated_count']} treated and {records['per_year_control_count']} controls per year",
        f"Coordinates: mode={coordinates['mode']}, covariance={coordinates['covariance_form']}, pre-violations={coordinates['pre_violations_form']}, T_pre={coordinates['t_pre']}, T_post={coordinates['t_post']}, p={coordinates['p_norm']}, alpha={coordinates['alpha']}",
        f"Estimator: {covariance['target']}; {covariance['sample_design']}; denominator {covariance['covariance_denominator']}",
        ]
    )
    _append_text_report_section(lines, "Critical value")
    lines.extend(
        [
        f"Python f_alpha:    {_format_float(summary['python_f_alpha'])}",
        f"Reference f_alpha: {_format_float(summary['reference_f_alpha'])}",
        f"Absolute gap:      {_format_float(summary['f_alpha_abs_diff'])}",
        f"Attribution:       {summary['critical_value_mismatch_attribution']} ({summary['critical_value_mismatch_status']})",
        ]
    )
    _append_text_report_section(lines, "Probe checks")
    lines.extend(
        [
        f"RNG streams match:      {_format_bool(probe['rng_stream_matches'])}; max |diff|={_format_float(probe['rng_stream_max_abs_diff'])}",
        f"Transform matches:      {_format_bool(probe['transform_matches'])}; max |diff|={_format_float(probe['transform_max_abs_diff'], digits=12)}",
        f"Psi matches:            {_format_bool(probe['psi_matches'])}; |diff|={_format_float(probe['psi_abs_diff'], digits=12)}",
        f"Order statistic:        index {probe['order_statistic_quantile_idx']} / expected {probe['order_statistic_expected_quantile_idx']}; tail {probe['order_statistic_tail_at_f_alpha']} / limit {probe['order_statistic_expected_tail_limit']}",
        f"Regularization effect:  {_format_float(probe['regularized_minus_unregularized'], digits=12)}; residual gap {_format_float(probe['regularization_abs_diff'])}",
        ]
    )
    return "\n".join(lines)


def _render_prop99_python_handoff_summary_text(summary: dict[str, object]) -> str:
    records = summary["records"]
    kernel_inputs = summary["kernel_inputs"]
    critical_value = summary["critical_value"]
    snapshot = summary["snapshot"]
    for field, value in (
        ("records", records),
        ("kernel_inputs", kernel_inputs),
        ("critical_value", critical_value),
        ("snapshot", snapshot),
    ):
        if not isinstance(value, dict):
            raise ValueError(f"{field} must be a mapping")

    lines = _text_report_title("Prop99 Python handoff summary") + [
        f"Case: {summary['case_id']}",
        f"Workflow: {summary['workflow']}",
        f"Record source: {summary['records_source']}",
        (
            "Records: "
            f"{records['rows']} rows across {len(records['years'])} years"
        ),
        (
            "Design: "
            f"T_pre={kernel_inputs['T_pre']}, "
            f"T_post={kernel_inputs['T_post']}, "
            f"mode={kernel_inputs['mode']}, "
            f"p={_format_float(kernel_inputs['p_norm'])}"
        ),
    ]
    _append_text_report_section(lines, "Pre-test")
    lines.extend(
        [
            f"S_pre:     {_format_float(snapshot['S_pre'])}",
            f"Threshold: {_format_float(snapshot['threshold'])}",
            f"Phi:       {snapshot['phi']}",
            f"Pass:      {snapshot['pretest_pass']}",
        ]
    )
    _append_text_report_section(lines, "Critical value")
    lines.extend(
        [
            f"f_alpha:     {_format_float(critical_value['f_alpha'])}",
            f"Simulations: {critical_value['simulations']}",
            f"Seed:        {critical_value['seed']}",
        ]
    )
    _append_text_report_section(lines, "Intervals")
    lines.extend(
        [
            f"delta_bar:        {_format_float(snapshot['delta_bar'])}",
            (
                "conditional CI:  "
                f"[{_format_float(snapshot['ci_lower'])}, "
                f"{_format_float(snapshot['ci_upper'])}]"
            ),
            (
                "conventional CI: "
                f"[{_format_float(snapshot['ci_conv_lower'])}, "
                f"{_format_float(snapshot['ci_conv_upper'])}]"
            ),
        ]
    )
    return "\n".join(lines)


def _run_prop99_python_handoff_summary_cli(tokens: Sequence[str]) -> int:
    output_format, records_csv = _parse_prop99_python_handoff_summary_args(tokens)
    records = load_prop99_window_iter_records_from_csv(records_csv)
    summary = build_prop99_python_handoff_summary(
        records,
        records_source=f"csv:{records_csv}",
    )

    if output_format == "text":
        print(_render_prop99_python_handoff_summary_text(summary))
        return 0

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _run_prop99_window_iter_parity_summary_cli(tokens: Sequence[str]) -> int:
    output_format = _parse_prop99_window_iter_parity_summary_args(tokens)
    summary = build_prop99_window_iter_parity_summary()

    if output_format == "text":
        print(_render_prop99_window_iter_parity_summary_text(summary))
        return 0

    print(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _source_tree_helpers_enabled() -> bool:
    return os.environ.get(_SOURCE_TREE_HELPERS_ENV, "").strip() == "1"


def _reject_source_tree_helper_command(command: str) -> int:
    print(
        (
            f"{command} is a source-checkout reference helper, not a public-wheel CLI "
            "contract. Use prop99-python-handoff-summary --records-csv PATH for "
            "the public Prop99 handoff, or set "
            f"{_SOURCE_TREE_HELPERS_ENV}=1 in a source checkout."
        ),
        file=sys.stderr,
    )
    return 2


def main(argv: Sequence[str] | None = None) -> int:
    tokens = list(sys.argv[1:] if argv is None else argv)
    if not tokens:
        print(_USAGE)
        return 0
    if tokens[0] in _SOURCE_TREE_HELPER_COMMANDS and not _source_tree_helpers_enabled():
        return _reject_source_tree_helper_command(tokens[0])
    if tokens[0] == "replay-summary":
        try:
            return _run_replay_summary_cli(tokens[1:])
        except SystemExit as exc:
            return int(exc.code)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    if tokens[0] == "replay-summary-from-scaffold":
        try:
            return _run_replay_summary_from_scaffold_cli(tokens[1:])
        except SystemExit as exc:
            return int(exc.code)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    if tokens[0] == "capture-ready-overall-bundles":
        try:
            return _run_capture_ready_overall_bundles_cli(tokens[1:])
        except SystemExit as exc:
            return int(exc.code)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    if tokens[0] == "stata-split-capture-evidence":
        try:
            return _run_stata_split_capture_evidence_cli(tokens[1:])
        except SystemExit as exc:
            return int(exc.code)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    if tokens[0] == "prop99-replay-summary":
        try:
            return _run_prop99_replay_summary_cli(tokens[1:])
        except SystemExit as exc:
            return int(exc.code)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    if tokens[0] == "prop99-graph-preview-svg":
        try:
            return _run_prop99_graph_preview_svg_cli(tokens[1:])
        except SystemExit as exc:
            return int(exc.code)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    if tokens[0] == "prop99-replay-scaffold":
        try:
            return _run_prop99_replay_scaffold_cli(tokens[1:])
        except SystemExit as exc:
            return int(exc.code)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    if tokens[0] == "prop99-overall-auxiliary-scaffold":
        try:
            return _run_prop99_overall_auxiliary_scaffold_cli(tokens[1:])
        except SystemExit as exc:
            return int(exc.code)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    if tokens[0] == "prop99-python-handoff-summary":
        try:
            return _run_prop99_python_handoff_summary_cli(tokens[1:])
        except SystemExit as exc:
            return int(exc.code)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    if tokens[0] == "prop99-replay-story-packet":
        try:
            return _run_prop99_replay_story_packet_cli(tokens[1:])
        except SystemExit as exc:
            return int(exc.code)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    if tokens[0] == "prop99-capture-ready-overall-bundles":
        try:
            return _run_prop99_capture_ready_overall_bundles_cli(tokens[1:])
        except SystemExit as exc:
            return int(exc.code)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    if tokens[0] == "prop99-nonoverall-split-capture-inventory":
        try:
            return _run_prop99_nonoverall_split_capture_inventory_cli(tokens[1:])
        except SystemExit as exc:
            return int(exc.code)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    if tokens[0] == "prop99-window-iter-stata-split-capture-evidence":
        try:
            return _run_prop99_window_iter_stata_split_capture_evidence_cli(tokens[1:])
        except SystemExit as exc:
            return int(exc.code)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    if tokens[0] == "prop99-window-iter-deterministic-split-capture-evidence":
        try:
            return _run_prop99_window_iter_deterministic_split_capture_evidence_cli(
                tokens[1:]
            )
        except SystemExit as exc:
            return int(exc.code)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    if tokens[0] == "prop99-window-iter-parity-summary":
        try:
            return _run_prop99_window_iter_parity_summary_cli(tokens[1:])
        except SystemExit as exc:
            return int(exc.code)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    if len(tokens) == 1 and tokens[0] in {"--help", "-h"}:
        print(_USAGE)
        return 0
    if len(tokens) == 1 and tokens[0] in {"--version", "-V"}:
        print(__version__)
        return 0

    command = " ".join(tokens)
    if not command.lower().startswith("pretest "):
        command = f"pretest {command}"

    try:
        snapshot = seed_result_snapshot(parse_stata_command(command))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(snapshot.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
