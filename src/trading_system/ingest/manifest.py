from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(slots=True)
class SourceManifestEntry:
    source_id: str
    connector_kind: str
    status: str
    required: bool
    input_path: str
    discovered_files: list[str] = field(default_factory=list)
    copied_files: list[str] = field(default_factory=list)
    file_count: int = 0
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DailyIntakeManifest:
    run_name: str
    run_date: str
    snapshot_dir: str
    required_sources: list[str]
    optional_sources: list[str]
    entries: list[SourceManifestEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "run_name": self.run_name,
            "run_date": self.run_date,
            "snapshot_dir": self.snapshot_dir,
            "required_sources": self.required_sources,
            "optional_sources": self.optional_sources,
            "entries": [asdict(entry) for entry in self.entries],
        }


def write_manifest(manifest: DailyIntakeManifest, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
