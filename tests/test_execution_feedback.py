from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_system.decision.live_trade_state import SystemTradeRecord
from trading_system.evaluation.execution_behavior import build_execution_behavior
from trading_system.evaluation.execution_feedback import build_execution_feedback


class ExecutionFeedbackTest(unittest.TestCase):
    def test_build_execution_feedback_matches_buy_and_sell_records(self) -> None:
        records = [
            SystemTradeRecord(
                record_id="2026-05-18:buy:600000.SH",
                trade_date="2026-05-18",
                stock_code="600000.SH",
                stock_name="Test Bank",
                order_action="buy",
                actual_shares=1000,
                actual_price=10.0,
                execution_status="filled",
                setup_type="event_ignition",
            ),
            SystemTradeRecord(
                record_id="2026-05-20:sell:600000.SH",
                trade_date="2026-05-20",
                stock_code="600000.SH",
                stock_name="Test Bank",
                order_action="sell",
                actual_shares=1000,
                actual_price=11.0,
                execution_status="filled",
            ),
        ]

        payload = build_execution_feedback(records)

        self.assertEqual(payload["closed_trade_count"], 1)
        self.assertEqual(payload["setup_count"], 1)
        self.assertEqual(payload["setup_summary"][0]["setup_type"], "event_ignition")
        self.assertEqual(payload["setup_summary"][0]["avg_realized_return"], 0.1)

    def test_build_execution_behavior_tracks_fill_and_slippage(self) -> None:
        records = [
            SystemTradeRecord(
                record_id="2026-05-18:buy:600000.SH",
                trade_date="2026-05-18",
                stock_code="600000.SH",
                stock_name="Test Bank",
                order_action="buy",
                suggested_shares=1000,
                actual_shares=1000,
                suggested_price_reference=10.0,
                actual_price=10.3,
                execution_status="filled",
                setup_type="event_ignition",
            ),
            SystemTradeRecord(
                record_id="2026-05-19:buy:600001.SH",
                trade_date="2026-05-19",
                stock_code="600001.SH",
                stock_name="Test Bank 2",
                order_action="buy",
                suggested_shares=1000,
                actual_shares=500,
                suggested_price_reference=10.0,
                actual_price=10.2,
                execution_status="partial",
                setup_type="event_ignition",
            ),
            SystemTradeRecord(
                record_id="2026-05-20:buy:600002.SH",
                trade_date="2026-05-20",
                stock_code="600002.SH",
                stock_name="Test Bank 3",
                order_action="buy",
                suggested_shares=1000,
                execution_status="skipped",
                setup_type="event_ignition",
            ),
        ]

        payload = build_execution_behavior(records)

        self.assertEqual(payload["setup_count"], 1)
        item = payload["setup_summary"][0]
        self.assertEqual(item["finalized_count"], 3)
        self.assertAlmostEqual(item["fill_rate"], 0.6667, places=4)
        self.assertAlmostEqual(item["partial_rate"], 0.3333, places=4)
        self.assertAlmostEqual(item["avg_buy_slippage_pct"], 0.025, places=4)


if __name__ == "__main__":
    unittest.main()
