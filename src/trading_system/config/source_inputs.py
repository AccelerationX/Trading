from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from trading_system.config.paths import CONFIGS_DIR, PROJECT_ROOT


def _resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


@dataclass(frozen=True)
class SourceEndpointConfig:
    id: str
    connector_kind: str
    enabled: bool
    required: bool
    input_path: Path
    file_patterns: tuple[str, ...]
    notes: str = ""


@dataclass(frozen=True)
class DailyIntakePlan:
    run_name: str
    copy_inputs_to_snapshot: bool
    required_source_ids: tuple[str, ...]
    optional_source_ids: tuple[str, ...]
    notes: str = ""


def load_source_endpoints(path: Path | None = None) -> list[SourceEndpointConfig]:
    config_path = path or CONFIGS_DIR / "source_endpoints.template.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    return [
        SourceEndpointConfig(
            id=item["id"],
            connector_kind=item["connector_kind"],
            enabled=bool(item["enabled"]),
            required=bool(item["required"]),
            input_path=_resolve_path(item["input_path"]),
            file_patterns=tuple(item.get("file_patterns", [])),
            notes=item.get("notes", ""),
        )
        for item in payload["sources"]
    ]


def load_daily_intake_plan(path: Path | None = None) -> DailyIntakePlan:
    config_path = path or CONFIGS_DIR / "daily_intake.template.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    return DailyIntakePlan(
        run_name=payload["run_name"],
        copy_inputs_to_snapshot=bool(payload["copy_inputs_to_snapshot"]),
        required_source_ids=tuple(payload.get("required_source_ids", [])),
        optional_source_ids=tuple(payload.get("optional_source_ids", [])),
        notes=payload.get("notes", ""),
    )
