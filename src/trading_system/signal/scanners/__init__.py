from __future__ import annotations

from trading_system.signal.scanners.base import ModuleScanner, ModuleSignal
from trading_system.signal.scanners.registry import load_scanners_for_modules, register_scanner

# Import to trigger scanner registration
from trading_system.signal.scanners import line_a_scanner  # noqa: F401
from trading_system.signal.scanners import rel_strength_scanner  # noqa: F401
from trading_system.signal.scanners import behavior_repair_scanner  # noqa: F401
from trading_system.signal.scanners import group_rotation_scanner  # noqa: F401
from trading_system.signal.scanners import capital_flow_scanner  # noqa: F401

__all__ = [
    "ModuleScanner",
    "ModuleSignal",
    "load_scanners_for_modules",
    "register_scanner",
]
