from __future__ import annotations

from trading_system.signal.scanners.line_a_scanner import LineAScanner


# Compatibility shim: keep the legacy_adapted import path available without
# re-registering a second implementation for the same module_id.
TM001LineAScanner = LineAScanner

__all__ = ["TM001LineAScanner", "LineAScanner"]
