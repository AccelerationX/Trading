from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path
from typing import Callable

from trading_system.config.paths import CONFIGS_DIR
from trading_system.signal.scanners.base import ModuleScanner
from trading_system.signal.technical_modules import TechnicalModule


_SCANNER_FACTORIES: dict[str, Callable[..., ModuleScanner]] = {}
_DISCOVERY_LOADED = False


def register_scanner(module_id: str, factory: Callable[..., ModuleScanner]) -> None:
    # Preserve the first registration so later compatibility imports cannot
    # silently replace the scanner implementation for the same module_id.
    if module_id in _SCANNER_FACTORIES:
        return
    _SCANNER_FACTORIES[module_id] = factory


def _ensure_default_scanner_registration() -> None:
    global _DISCOVERY_LOADED
    if _DISCOVERY_LOADED:
        return
    importlib.import_module("trading_system.signal.scanners")
    _DISCOVERY_LOADED = True


def _load_module_registry(path: Path | None = None) -> dict[str, dict]:
    config_path = path or (CONFIGS_DIR / "technical_module_registry.json")
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    return {item["module_id"]: item for item in payload.get("modules", [])}


def _build_scanner(factory: Callable[..., ModuleScanner], config: dict) -> ModuleScanner:
    try:
        signature = inspect.signature(factory)
    except (TypeError, ValueError):
        return factory()

    if len(signature.parameters) == 0:
        return factory()
    return factory(config)


def load_scanners_for_modules(
    modules: list[TechnicalModule],
    registry_path: Path | None = None,
) -> dict[str, ModuleScanner]:
    _ensure_default_scanner_registration()
    registry = _load_module_registry(registry_path)
    result: dict[str, ModuleScanner] = {}
    for module in modules:
        config = registry.get(module.module_id, {})
        scanner_config = config.get("scanner", {})
        if not scanner_config.get("enabled", False):
            continue
        factory = _SCANNER_FACTORIES.get(module.module_id)
        if factory is None:
            continue
        scanner = _build_scanner(factory, scanner_config.get("config", {}))
        if not isinstance(scanner, ModuleScanner):
            continue
        result[module.module_id] = scanner
    return result
