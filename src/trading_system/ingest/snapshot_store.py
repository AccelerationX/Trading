from __future__ import annotations

import shutil
from pathlib import Path

from trading_system.config.paths import SNAPSHOTS_DIR


def get_snapshot_dir(run_date: str) -> Path:
    snapshot_dir = SNAPSHOTS_DIR / run_date
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    return snapshot_dir


def source_snapshot_dir(run_date: str, source_id: str) -> Path:
    directory = get_snapshot_dir(run_date) / source_id
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def copy_inputs_to_snapshot(files: list[Path], run_date: str, source_id: str) -> list[Path]:
    target_dir = source_snapshot_dir(run_date, source_id)
    copied: list[Path] = []
    for file_path in files:
        if not file_path.exists() or not file_path.is_file():
            continue
        target_path = target_dir / file_path.name
        shutil.copy2(file_path, target_path)
        copied.append(target_path)
    return copied
