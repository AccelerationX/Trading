from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_system.signal.scanners.behavior_repair_scanner import BehaviorRepairScanner


class BehaviorRepairScannerTest(unittest.TestCase):
    def test_module_id(self) -> None:
        scanner = BehaviorRepairScanner()
        self.assertEqual(scanner.module_id, "TM101_behavior_repair_rebound")

    def test_is_available_checks_local_data_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            scanner = BehaviorRepairScanner(data_dir=tmp_dir)
            self.assertFalse(scanner.is_available("2026-05-06"))
            Path(tmp_dir, "000001.SZ.csv").write_text("x\n1\n", encoding="utf-8")
            self.assertTrue(scanner.is_available("2026-05-06"))

    def test_scan_maps_candidates_to_module_signals(self) -> None:
        scanner = BehaviorRepairScanner(data_dir="D:/unused")
        scanner._df = pd.DataFrame({"trade_date": [pd.Timestamp("2026-05-06")]})
        mocked_candidates = pd.DataFrame(
            [
                {
                    "stock_code": "000001.SZ",
                    "trade_date": pd.Timestamp("2026-05-06"),
                    "signal_type": "strong",
                    "technical_state": "repair_accel",
                    "signal": 0.9,
                    "repair_accel_signal": 1.1,
                    "trend_repair_signal": None,
                    "rank_pos": 1,
                    "in_entry_top_n": True,
                    "in_keep_zone": True,
                }
            ]
        )
        with patch(
            "trading_system.signal.scanners.behavior_repair_scanner.scan_behavior_repair_candidates",
            return_value=mocked_candidates,
        ):
            signals = scanner.scan("2026-05-06", market_regime=None)

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].signal_type, "strong")
        self.assertEqual(signals[0].technical_state, "repair_accel")
        self.assertIn("repair_accel_signal", signals[0].metadata)

    def test_scan_requires_exact_trade_date(self) -> None:
        scanner = BehaviorRepairScanner(data_dir="D:/unused")
        scanner._df = pd.DataFrame({"trade_date": [pd.Timestamp("2026-04-30")]})
        with self.assertRaises(FileNotFoundError):
            scanner.scan("2026-05-06", market_regime=None)


if __name__ == "__main__":
    unittest.main()
