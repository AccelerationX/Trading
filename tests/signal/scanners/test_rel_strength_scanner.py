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

from trading_system.signal.scanners.rel_strength_scanner import RelStrengthScanner


class RelStrengthScannerTest(unittest.TestCase):
    def test_module_id(self) -> None:
        scanner = RelStrengthScanner()
        self.assertEqual(scanner.module_id, "TM002_breakout_and_relative_strength")

    def test_is_available_checks_local_data_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            scanner = RelStrengthScanner(data_dir=tmp_dir)
            self.assertFalse(scanner.is_available("2026-05-06"))
            Path(tmp_dir, "000001.SZ.csv").write_text("x\n1\n", encoding="utf-8")
            self.assertTrue(scanner.is_available("2026-05-06"))

    def test_scan_maps_candidates_to_module_signals(self) -> None:
        scanner = RelStrengthScanner(data_dir="D:/unused")
        scanner._df = pd.DataFrame({"trade_date": [pd.Timestamp("2026-05-06")]})
        mocked_candidates = pd.DataFrame(
            [
                {
                    "stock_code": "000001.SZ",
                    "trade_date": pd.Timestamp("2026-05-06"),
                    "rel_strength": 0.8,
                    "rs_zscore": 1.2,
                    "stock_mom": 0.5,
                    "market_mom": 0.1,
                    "rank_pos": 1,
                    "in_top_n": True,
                    "signal_type": "strong",
                },
                {
                    "stock_code": "000002.SZ",
                    "trade_date": pd.Timestamp("2026-05-06"),
                    "rel_strength": 0.6,
                    "rs_zscore": 1.3,
                    "stock_mom": 0.4,
                    "market_mom": 0.1,
                    "rank_pos": 30,
                    "in_top_n": False,
                    "signal_type": "moderate",
                },
                {
                    "stock_code": "000003.SZ",
                    "trade_date": pd.Timestamp("2026-05-06"),
                    "rel_strength": 0.5,
                    "rs_zscore": 0.8,
                    "stock_mom": 0.3,
                    "market_mom": 0.1,
                    "rank_pos": 12,
                    "in_top_n": False,
                    "signal_type": "moderate",
                }
            ]
        )
        with patch(
            "trading_system.signal.scanners.rel_strength_scanner.scan_rel_strength_candidates",
            return_value=mocked_candidates,
        ):
            signals = scanner.scan("2026-05-06", market_regime=None)

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].signal_type, "strong")
        self.assertEqual(signals[0].technical_state, "breakout_confirmed")
        self.assertGreater(signals[0].metadata["rel_strength"], 0)

    def test_scan_requires_exact_trade_date(self) -> None:
        scanner = RelStrengthScanner(data_dir="D:/unused")
        scanner._df = pd.DataFrame({"trade_date": [pd.Timestamp("2026-04-30")]})
        with self.assertRaises(FileNotFoundError):
            scanner.scan("2026-05-06", market_regime=None)


if __name__ == "__main__":
    unittest.main()
