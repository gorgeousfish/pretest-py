from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import yaml


def _nonempty_case_id(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    if value != value.strip():
        raise ValueError(f"{label} must not contain leading or trailing whitespace")
    return value


def _coerce_path(value: str | Path, *, label: str) -> Path:
    if isinstance(value, Path):
        return value
    if isinstance(value, str) and value.strip():
        return Path(value)
    raise ValueError(f"{label} must be a filesystem path")


def load_replay_yaml(path: str | Path) -> dict[str, object]:
    artifact_path = _coerce_path(path, label="path")
    if not artifact_path.exists():
        raise ValueError(f"{artifact_path} does not exist")
    if not artifact_path.is_file():
        raise ValueError(f"{artifact_path} must be a YAML file path")
    try:
        data = yaml.safe_load(artifact_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"{artifact_path} is not valid YAML") from exc
    if not isinstance(data, Mapping):
        raise ValueError(f"{artifact_path} must contain a YAML mapping at the root")
    return dict(data)


def load_case_payloads(
    case_paths: Mapping[str, str | Path],
    *,
    label: str = "case_paths",
) -> dict[str, dict[str, object]]:
    if not isinstance(case_paths, Mapping):
        raise ValueError(f"{label} must be a mapping keyed by case_id")

    loaded: dict[str, dict[str, object]] = {}
    for raw_case_id, raw_path in case_paths.items():
        case_id = _nonempty_case_id(raw_case_id, label=f"{label} key")
        if case_id in loaded:
            raise ValueError(f"{label} must not contain duplicate case_id keys")
        payload = load_replay_yaml(_coerce_path(raw_path, label=f"{label}[{case_id}]"))
        payload_case_id = payload.get("case_id")
        if payload_case_id is not None:
            normalized_payload_case_id = _nonempty_case_id(
                payload_case_id,
                label=f"{raw_path} case_id",
            )
            if normalized_payload_case_id != case_id:
                raise ValueError(
                    f"{raw_path} defines case_id {normalized_payload_case_id} but was loaded for {case_id}"
                )
        loaded[case_id] = payload
    return loaded
