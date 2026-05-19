from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_system.decision.live_trade_state import (
    load_system_trade_log,
    sync_trade_execution_payload_to_live_state,
)


class LiveTradeStateTest(unittest.TestCase):
    def test_sync_buy_order_updates_holdings_and_trade_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            holdings_path = Path(tmp_dir) / "current_holdings.json"
            trade_log_path = Path(tmp_dir) / "system_trade_log.json"
            holdings_path.write_text(
                json.dumps(
                    {
                        "as_of": "2026-05-17",
                        "broker": "",
                        "cash_cny": 43300.0,
                        "positions": [],
                        "applied_system_record_ids": [],
                        "notes": "",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            payload = {
                "trade_date": "2026-05-18",
                "market_close_date": "2026-05-16",
                "profile_name": "acct",
                "preferred_posture": "small_probe",
                "buy_orders": [
                    {
                        "stock_code": "600000.SH",
                        "stock_name": "Test Bank",
                        "target_shares": 1000,
                        "buy_zone": "10.00 - 10.20",
                        "stop_loss": "9.70",
                        "take_profit": "10.60 - 11.00",
                        "price_reference": 10.1,
                        "suggested_holding_days": 3,
                        "reason": "test buy",
                        "setup_type": "event_ignition",
                        "theme_name": "finance",
                    }
                ],
                "sell_orders": [],
            }

            sync_trade_execution_payload_to_live_state(
                payload,
                holdings_path=holdings_path,
                trade_log_path=trade_log_path,
                source_trade_execution_path="trade_execution_2026-05-18.json",
            )

            holdings = json.loads(holdings_path.read_text(encoding="utf-8"))
            records = load_system_trade_log(trade_log_path)

        self.assertEqual(holdings["as_of"], "2026-05-18")
        self.assertEqual(len(holdings["positions"]), 1)
        self.assertEqual(holdings["positions"][0]["stock_code"], "600000.SH")
        self.assertEqual(holdings["positions"][0]["shares"], 1000)
        self.assertEqual(holdings["positions"][0]["execution_status"], "pending_fill")
        self.assertAlmostEqual(holdings["cash_cny"], 33200.0)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].order_action, "buy")
        self.assertEqual(records[0].execution_status, "pending_fill")

    def test_sync_is_idempotent_for_same_trade_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            holdings_path = Path(tmp_dir) / "current_holdings.json"
            trade_log_path = Path(tmp_dir) / "system_trade_log.json"
            holdings_path.write_text(
                json.dumps(
                    {
                        "as_of": "2026-05-17",
                        "broker": "",
                        "cash_cny": 43300.0,
                        "positions": [],
                        "applied_system_record_ids": [],
                        "notes": "",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            payload = {
                "trade_date": "2026-05-18",
                "buy_orders": [
                    {
                        "stock_code": "600000.SH",
                        "stock_name": "Test Bank",
                        "target_shares": 1000,
                        "buy_zone": "10.00 - 10.20",
                        "price_reference": 10.1,
                    }
                ],
                "sell_orders": [],
            }

            sync_trade_execution_payload_to_live_state(payload, holdings_path=holdings_path, trade_log_path=trade_log_path)
            sync_trade_execution_payload_to_live_state(payload, holdings_path=holdings_path, trade_log_path=trade_log_path)

            holdings = json.loads(holdings_path.read_text(encoding="utf-8"))
            records = json.loads(trade_log_path.read_text(encoding="utf-8"))

        self.assertEqual(len(holdings["positions"]), 1)
        self.assertEqual(holdings["positions"][0]["shares"], 1000)
        self.assertEqual(len(records), 1)

    def test_sync_sell_order_reduces_existing_position(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            holdings_path = Path(tmp_dir) / "current_holdings.json"
            trade_log_path = Path(tmp_dir) / "system_trade_log.json"
            holdings_path.write_text(
                json.dumps(
                    {
                        "as_of": "2026-05-17",
                        "broker": "",
                        "cash_cny": 1000.0,
                        "positions": [
                            {
                                "stock_code": "600000.SH",
                                "stock_name": "Test Bank",
                                "shares": 800,
                                "available_shares": 800,
                                "cost_basis": 9.8,
                            }
                        ],
                        "applied_system_record_ids": [],
                        "notes": "",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            payload = {
                "trade_date": "2026-05-18",
                "buy_orders": [],
                "sell_orders": [
                    {
                        "stock_code": "600000.SH",
                        "stock_name": "Test Bank",
                        "target_shares": 800,
                        "sell_scope": "full_available",
                        "price_reference": 12.0,
                        "reason": "exit",
                    }
                ],
            }

            sync_trade_execution_payload_to_live_state(payload, holdings_path=holdings_path, trade_log_path=trade_log_path)
            holdings = json.loads(holdings_path.read_text(encoding="utf-8"))
            records = load_system_trade_log(trade_log_path)

        self.assertEqual(holdings["positions"], [])
        self.assertAlmostEqual(holdings["cash_cny"], 10600.0)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].order_action, "sell")

    def test_trade_log_serialization_groups_editable_fill_form(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            holdings_path = Path(tmp_dir) / "current_holdings.json"
            trade_log_path = Path(tmp_dir) / "system_trade_log.json"
            holdings_path.write_text(
                json.dumps(
                    {
                        "as_of": "2026-05-17",
                        "broker": "",
                        "cash_cny": 43300.0,
                        "positions": [],
                        "applied_system_record_ids": [],
                        "notes": "",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            payload = {
                "trade_date": "2026-05-18",
                "buy_orders": [
                    {
                        "stock_code": "600000.SH",
                        "stock_name": "Test Bank",
                        "target_shares": 1000,
                        "buy_zone": "10.00 - 10.20",
                        "price_reference": 10.1,
                    }
                ],
                "sell_orders": [],
            }

            sync_trade_execution_payload_to_live_state(payload, holdings_path=holdings_path, trade_log_path=trade_log_path)
            raw_records = json.loads(trade_log_path.read_text(encoding="utf-8"))

        self.assertEqual(len(raw_records), 1)
        self.assertIn("fill_form", raw_records[0])
        self.assertIn("editable_fields", raw_records[0])
        self.assertEqual(raw_records[0]["fill_form"]["execution_status"], "pending_fill")


if __name__ == "__main__":
    unittest.main()
