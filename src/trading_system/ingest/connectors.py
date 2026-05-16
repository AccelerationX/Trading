from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from trading_system.config.source_inputs import SourceEndpointConfig
from trading_system.ingest.snapshot_store import copy_inputs_to_snapshot


@dataclass(slots=True)
class ConnectorResult:
    source_id: str
    connector_kind: str
    status: str
    discovered_files: list[Path] = field(default_factory=list)
    copied_files: list[Path] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _scan_input_files(config: SourceEndpointConfig) -> list[Path]:
    if not config.input_path.exists():
        return []
    files: list[Path] = []
    for pattern in config.file_patterns:
        files.extend(path for path in config.input_path.glob(pattern) if path.is_file())
    seen: set[Path] = set()
    ordered: list[Path] = []
    for path in sorted(files):
        if path not in seen:
            seen.add(path)
            ordered.append(path)
    return ordered


def run_connector(config: SourceEndpointConfig, run_date: str, copy_to_snapshot: bool) -> ConnectorResult:
    if not config.enabled:
        return ConnectorResult(
            source_id=config.id,
            connector_kind=config.connector_kind,
            status="disabled",
            notes=["source disabled in endpoint config"],
        )

    if not config.input_path.exists():
        return ConnectorResult(
            source_id=config.id,
            connector_kind=config.connector_kind,
            status="missing",
            notes=[f"input path missing: {config.input_path}"],
        )

    discovered_files = _scan_input_files(config)
    if not discovered_files:
        return ConnectorResult(
            source_id=config.id,
            connector_kind=config.connector_kind,
            status="empty",
            notes=["no matching files discovered"],
        )

    copied_files: list[Path] = []
    if copy_to_snapshot:
        copied_files = copy_inputs_to_snapshot(discovered_files, run_date=run_date, source_id=config.id)

    return ConnectorResult(
        source_id=config.id,
        connector_kind=config.connector_kind,
        status="ready",
        discovered_files=discovered_files,
        copied_files=copied_files,
        notes=[f"connector={config.connector_kind}", f"discovered={len(discovered_files)}"],
    )
