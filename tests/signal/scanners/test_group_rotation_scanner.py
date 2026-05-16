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

from trading_system.signal.scanners.group_rotation_scanner import GroupRotationScanner


class GroupRotationScannerTest(unittest.TestCase):
    def test_module_id(self) -> None:
        scanner = GroupRotationScanner()
        self.assertEqual(scanner.module_id, "TM201_group_rotation_repair")

    def test_is_available_checks_local_data_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            scanner = GroupRotationScanner(data_dir=tmp_dir)
            self.assertFalse(scanner.is_available("2026-05-06"))
            Path(tmp_dir, "000001.SZ.csv").write_text("x\n1\n", encoding="utf-8")
            self.assertTrue(scanner.is_available("2026-05-06"))

    def test_scan_maps_candidates_to_module_signals(self) -> None:
        scanner = GroupRotationScanner(data_dir="D:/unused")
        scanner._df = pd.DataFrame({"trade_date": [pd.Timestamp("2026-05-06")]})
        mocked_candidates = pd.DataFrame(
            [
                {
                    "stock_code": "000001.SZ",
                    "trade_date": pd.Timestamp("2026-05-06"),
                    "signal_type": "strong",
                    "rotation_repair_signal": 0.88,
                    "latent_group": 2,
                    "rank_pos": 1,
                    "in_entry_top_n": True,
                    "in_keep_zone": True,
                }
            ]
        )
        with patch(
            "trading_system.signal.scanners.group_rotation_scanner.scan_group_rotation_candidates",
            return_value=mocked_candidates,
        ):
            signals = scanner.scan("2026-05-06", market_regime=None)

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].signal_type, "strong")
        self.assertTrue(signals[0].technical_state.startswith("group_"))
        self.assertEqual(signals[0].metadata["latent_group"], 2)

    def test_scan_requires_exact_trade_date(self) -> None:
        scanner = GroupRotationScanner(data_dir="D:/unused")
        scanner._df = pd.DataFrame({"trade_date": [pd.Timestamp("2026-04-30")]})
        with self.assertRaises(FileNotFoundError):
            scanner.scan("2026-05-06", market_regime=None)


if __name__ == "__main__":
    unittest.main()
