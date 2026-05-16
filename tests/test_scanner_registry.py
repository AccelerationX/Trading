from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import trading_system.signal.scanners.registry as scanner_registry


class _DummyScannerA:
    @property
    def module_id(self) -> str:
        return "TMX"

    def is_available(self, trade_date: str) -> bool:
        return True

    def scan(self, trade_date: str, market_regime, account=None, universe=None):
        return []


class _DummyScannerB(_DummyScannerA):
    pass


class _ConfigAwareScanner(_DummyScannerA):
    def __init__(self, config: dict | None = None) -> None:
        self.config = config or {}


class ScannerRegistryTest(unittest.TestCase):
    def test_duplicate_registration_keeps_first_factory(self) -> None:
        original = dict(scanner_registry._SCANNER_FACTORIES)
        try:
            scanner_registry._SCANNER_FACTORIES.clear()
            scanner_registry.register_scanner("TMX", _DummyScannerA)
            scanner_registry.register_scanner("TMX", _DummyScannerB)
            self.assertIs(scanner_registry._SCANNER_FACTORIES["TMX"], _DummyScannerA)
        finally:
            scanner_registry._SCANNER_FACTORIES.clear()
            scanner_registry._SCANNER_FACTORIES.update(original)

    def test_build_scanner_passes_config_when_factory_accepts_argument(self) -> None:
        scanner = scanner_registry._build_scanner(_ConfigAwareScanner, {"top_n": 12})
        self.assertIsInstance(scanner, _ConfigAwareScanner)
        self.assertEqual(scanner.config["top_n"], 12)


if __name__ == "__main__":
    unittest.main()
