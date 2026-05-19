from __future__ import annotations

import os
import sys
from pathlib import Path


def _load_env_file(root: Path) -> None:
    env_path = root / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip()


def bootstrap() -> None:
    root = Path(__file__).resolve().parents[1]
    src = root / "src"
    _load_env_file(root)
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
