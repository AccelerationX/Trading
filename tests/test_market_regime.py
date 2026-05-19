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
            {"index_name": "CSI300", "close": 4000, "prev_close": 3980},
            {"index_name": "CSI1000", "close": 2200, "prev_close": 2160},
            {"index_name": "SSE Composite", "close": 3350, "prev_close": 3332},
        ]
        index_history = [
            {"index_code": "000300.SH", "source_trade_date": "20260502", "close": 3920, "prev_close": 3900},
            {"index_code": "000300.SH", "source_trade_date": "20260505", "close": 3980, "prev_close": 3920},
            {"index_code": "000300.SH", "source_trade_date": "20260506", "close": 4000, "prev_close": 3980},
            {"index_code": "000852.SH", "source_trade_date": "20260502", "close": 2100, "prev_close": 2080},
            {"index_code": "000852.SH", "source_trade_date": "20260505", "close": 2160, "prev_close": 2100},
            {"index_code": "000852.SH", "source_trade_date": "20260506", "close": 2200, "prev_close": 2160},
            {"index_code": "000001.SH", "source_trade_date": "20260502", "close": 3290, "prev_close": 3270},
            {"index_code": "000001.SH", "source_trade_date": "20260505", "close": 3332, "prev_close": 3290},
            {"index_code": "000001.SH", "source_trade_date": "20260506", "close": 3350, "prev_close": 3332},
        ]
        snapshot = build_market_regime_snapshot(
            "2026-05-06",
            breadth_record=breadth,
            index_records=indexes,
            index_history_records=index_history,
        )
        self.assertEqual(snapshot.risk_mode, "risk_on")
        self.assertEqual(snapshot.market_bias, "bullish")
        self.assertEqual(snapshot.index_trend_state, "broad_uptrend")
        self.assertEqual(snapshot.index_alignment, "broadly_aligned_up")
        self.assertGreater(snapshot.trend_strength_score or 0.0, 0.7)
        self.assertLess(snapshot.sentiment_pressure_score or 1.0, 0.4)

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
            {"index_name": "CSI300", "close": 3980, "prev_close": 4030},
            {"index_name": "CSI1000", "close": 2100, "prev_close": 2200},
            {"index_name": "SSE Composite", "close": 3280, "prev_close": 3330},
        ]
        index_history = [
            {"index_code": "000300.SH", "source_trade_date": "20260502", "close": 4090, "prev_close": 4110},
            {"index_code": "000300.SH", "source_trade_date": "20260505", "close": 4030, "prev_close": 4090},
            {"index_code": "000300.SH", "source_trade_date": "20260506", "close": 3980, "prev_close": 4030},
            {"index_code": "000852.SH", "source_trade_date": "20260502", "close": 2280, "prev_close": 2300},
            {"index_code": "000852.SH", "source_trade_date": "20260505", "close": 2200, "prev_close": 2280},
            {"index_code": "000852.SH", "source_trade_date": "20260506", "close": 2100, "prev_close": 2200},
            {"index_code": "000001.SH", "source_trade_date": "20260502", "close": 3380, "prev_close": 3400},
            {"index_code": "000001.SH", "source_trade_date": "20260505", "close": 3330, "prev_close": 3380},
            {"index_code": "000001.SH", "source_trade_date": "20260506", "close": 3280, "prev_close": 3330},
        ]
        snapshot = build_market_regime_snapshot(
            "2026-05-06",
            breadth_record=breadth,
            index_records=indexes,
            index_history_records=index_history,
        )
        self.assertEqual(snapshot.risk_mode, "risk_off")
        self.assertEqual(snapshot.market_bias, "bearish")
        self.assertEqual(snapshot.index_trend_state, "broad_downtrend")
        self.assertEqual(snapshot.index_alignment, "broadly_aligned_down")
        self.assertGreater(snapshot.sentiment_pressure_score or 0.0, 0.5)
        self.assertGreater(snapshot.breakout_failure_rate or 0.0, 0.7)


if __name__ == "__main__":
    unittest.main()
