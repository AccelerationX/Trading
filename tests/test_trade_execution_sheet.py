from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_system.reporting.trade_execution_sheet import (
    build_trade_execution_payload,
    render_trade_execution_markdown,
)


class TradeExecutionSheetTest(unittest.TestCase):
    def test_build_trade_execution_payload_generates_buy_and_sell_orders(self) -> None:
        preopen_payload = {
            "trade_date": "2026-05-15",
            "data_basis": {"market_close_date": "2026-05-15"},
            "account_view": {"profile_name": "acct", "capital_total": 43300.0},
            "action_summary": {"preferred_posture": "small_probe", "posture_note": "Only act on confirmed names."},
            "portfolio": {"cash_cny": 21000.0},
            "top_new_ideas": [
                {
                    "stock_code": "603986.SH",
                    "stock_name": "兆易创新",
                    "action": "buy_pilot",
                    "setup_type": "leader_acceleration",
                    "theme_context": {"theme_name": "算力"},
                    "trade_instruction": {
                        "instruction": "Leader setup confirmed.",
                        "pilot_shares": 200,
                        "max_shares": 400,
                        "buy_zone": "120.00 - 121.50",
                        "stop_loss": "116.40",
                        "take_profit": "124.80 - 129.60",
                    },
                    "candidate_diagnosis": "Strong confirmation.",
                }
            ],
            "holding_assessments": [
                {
                    "stock_code": "600000.SH",
                    "stock_name": "浦发银行",
                    "shares": 1000,
                    "available_shares": 1000,
                    "summary_action": "reduce_or_exit_review",
                    "recommendation": "System support is gone.",
                    "rationale": "Trend failed.",
                    "unrealized_return_pct": -0.062,
                    "risk_notes": ["unrealized_drawdown_alert"],
                }
            ],
        }
        account_payload = {"preferred_holding_horizon_days": 3}

        payload = build_trade_execution_payload(preopen_payload, account_payload)

        self.assertTrue(payload["actionable"])
        self.assertEqual(payload["buy_count"], 1)
        self.assertEqual(payload["sell_count"], 1)
        self.assertEqual(payload["buy_orders"][0]["target_shares"], 200)
        self.assertEqual(payload["sell_orders"][0]["target_shares"], 1000)

    def test_render_trade_execution_markdown_handles_no_action(self) -> None:
        payload = {
            "trade_date": "2026-05-15",
            "market_close_date": "2026-05-15",
            "profile_name": "acct",
            "capital_total": 43300.0,
            "cash_cny": 43300.0,
            "preferred_posture": "defensive_wait",
            "posture_note": "Stay defensive.",
            "overall_instruction": "今日无明确买卖机会，建议不操作，保持空仓观察。",
            "actionable": False,
            "buy_orders": [],
            "sell_orders": [],
            "hold_orders": [],
        }

        markdown = render_trade_execution_markdown(payload)

        self.assertIn("# 今日交易指令 - 2026-05-15", markdown)
        self.assertIn("无明确买入指令", markdown)
        self.assertIn("无明确卖出指令", markdown)
        self.assertIn("不操作", markdown)


if __name__ == "__main__":
    unittest.main()
