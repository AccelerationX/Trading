from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_system.context.market_regime import build_market_regime_snapshot


class MarketRegimeTest(unittest.TestCase):
    def test_market_regime_risk_on(self) -> None:
        breadth = {
            "up_count": 3200,
            "down_count": 1200,
            "limit_up_count": 65,
            "limit_down_count": 3,
            "broken_limit_up_count": 10,
            "total_turnover": 1450000000000,
            "max_board_height": 5,
        }
        indexes = [
            {"index_name": "沪深300", "close": 4000, "prev_close": 3980},
            {"index_name": "中证2000", "close": 2200, "prev_close": 2160},
        ]
        snapshot = build_market_regime_snapshot("2026-05-06", breadth_record=breadth, index_records=indexes)
        self.assertEqual(snapshot.risk_mode, "risk_on")
        self.assertEqual(snapshot.market_bias, "bullish")

    def test_market_regime_risk_off(self) -> None:
        breadth = {
            "up_count": 900,
            "down_count": 3400,
            "limit_up_count": 5,
            "limit_down_count": 22,
            "broken_limit_up_count": 4,
            "total_turnover": 650000000000,
            "max_board_height": 2,
        }
        indexes = [
            {"index_name": "沪深300", "close": 3980, "prev_close": 4030},
            {"index_name": "中证2000", "close": 2100, "prev_close": 2200},
        ]
        snapshot = build_market_regime_snapshot("2026-05-06", breadth_record=breadth, index_records=indexes)
        self.assertEqual(snapshot.risk_mode, "risk_off")
        self.assertEqual(snapshot.market_bias, "bearish")


if __name__ == "__main__":
    unittest.main()
