from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_system.signal.scanners.capital_flow_scanner import CapitalFlowScanner


class CapitalFlowScannerTest(unittest.TestCase):
    def test_module_id(self) -> None:
        scanner = CapitalFlowScanner()
        self.assertEqual(scanner.module_id, "TM601_capital_flow_overlay")

    def test_is_available_returns_bool(self) -> None:
        scanner = CapitalFlowScanner()
        self.assertIsInstance(scanner.is_available("2026-05-06"), bool)

    def test_scan_maps_candidates_to_module_signals(self) -> None:
        scanner = CapitalFlowScanner()
        mocked_candidates = pd.DataFrame(
            [
                {
                    "stock_code": "000001.SZ",
                    "capital_signal_type": "northbound_flow",
                    "net_amount": 120000000.0,
                    "rank_pos": 1,
                    "in_entry_top_n": True,
                    "in_keep_zone": True,
                    "signal_type": "strong",
                    "technical_state": "high_capital_inflow",
                    "strength_hint": 0.85,
                }
            ]
        )
        with patch(
            "trading_system.signal.scanners.capital_flow_scanner.scan_capital_flow_candidates",
            return_value=mocked_candidates,
        ):
            signals = scanner.scan("2026-05-06", market_regime=None)

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].signal_type, "strong")
        self.assertEqual(signals[0].technical_state, "high_capital_inflow")
        self.assertEqual(signals[0].metadata["rank_pos"], 1)


if __name__ == "__main__":
    unittest.main()
