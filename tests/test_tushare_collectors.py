from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import trading_system.integrations.tushare_collectors as collectors


class FakePro:
    def stock_basic(self, **kwargs):
        return pd.DataFrame(
            [
                {
                    "ts_code": "000001.SZ",
                    "symbol": "000001",
                    "name": "PingAn",
                    "area": "SZ",
                    "industry": "bank",
                    "market": "main",
                    "list_date": "19910403",
                    "list_status": "L",
                }
            ]
        )

    def daily(self, trade_date=None, **kwargs):
        date_value = str(trade_date)
        close = 10.9 if date_value == "20260506" else 10.0
        high = 11.0 if date_value == "20260506" else 10.1
        return pd.DataFrame(
            [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": date_value,
                    "open": 10.0,
                    "high": high,
                    "low": 9.9,
                    "close": close,
                    "pre_close": 10.0,
                    "vol": 100000,
                    "amount": 250000,
                }
            ]
        )

    def daily_basic(self, trade_date=None, **kwargs):
        return pd.DataFrame(
            [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": str(trade_date),
                    "turnover_rate": 2.5,
                    "turnover_rate_f": 2.1,
                    "volume_ratio": 1.8,
                    "total_mv": 1000000,
                    "circ_mv": 800000,
                    "float_share": 1000,
                    "free_share": 900,
                    "total_share": 1200,
                }
            ]
        )

    def index_daily(self, ts_code=None, **kwargs):
        return pd.DataFrame(
            [
                {
                    "ts_code": ts_code,
                    "trade_date": "20260506",
                    "open": 100.0,
                    "high": 102.0,
                    "low": 99.0,
                    "close": 101.0,
                    "pre_close": 99.5,
                    "vol": 100000,
                    "amount": 500000,
                }
            ]
        )

    def repurchase(self, **kwargs):
        return pd.DataFrame(
            [
                {
                    "ts_code": "000001.SZ",
                    "ann_date": "20260506",
                    "proc": "board_pass",
                    "amount": 50000000,
                    "vol": 1000000,
                }
            ]
        )

    def stk_holdertrade(self, trade_type=None, **kwargs):
        if trade_type == "IN":
            return pd.DataFrame(
                [
                    {
                        "ts_code": "000001.SZ",
                        "ann_date": "20260506",
                        "holder_name": "major holder",
                        "change_vol": 200000,
                        "change_ratio": 0.5,
                    }
                ]
            )
        return pd.DataFrame()

    def top_list(self, **kwargs):
        return pd.DataFrame(
            [
                {
                    "ts_code": "000001.SZ",
                    "net_amount": 200000000,
                    "buy": 300000000,
                    "sell": 100000000,
                    "reason": "price deviation",
                }
            ]
        )

    def margin_detail(self, **kwargs):
        return pd.DataFrame(
            [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": "20260506",
                    "rzye": 100000000,
                    "rqye": 1000000,
                    "rzmre": 20000000,
                    "rqmcl": 500000,
                }
            ]
        )

    def hk_hold(self, **kwargs):
        return pd.DataFrame(
            [
                {
                    "ts_code": "000001.SZ",
                    "vol": 500000,
                    "ratio": 1.2,
                    "exchange": "SZ",
                }
            ]
        )

    def block_trade(self, **kwargs):
        return pd.DataFrame(
            [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": "20260506",
                    "price": 10.5,
                    "amount": 20000,
                }
            ]
        )


class TushareCollectorsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.original_inbox = collectors.INBOX_DIR
        self.original_load_pro = collectors.load_pro_client
        self.original_latest_trade_date = collectors.latest_open_trade_date
        self.original_load_open_trade_dates = collectors.load_open_trade_dates

    def tearDown(self) -> None:
        collectors.INBOX_DIR = self.original_inbox
        collectors.load_pro_client = self.original_load_pro
        collectors.latest_open_trade_date = self.original_latest_trade_date
        collectors.load_open_trade_dates = self.original_load_open_trade_dates

    def test_collectors_write_normalized_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            collectors.INBOX_DIR = Path(tmp_dir)
            collectors.load_pro_client = lambda: FakePro()
            collectors.latest_open_trade_date = lambda pro, anchor_date: "20260506"
            collectors.load_open_trade_dates = lambda pro, start_date, end_date: ["20260428", "20260429", "20260505", "20260506"]

            reference = collectors.collect_equity_reference_master("2026-05-06")
            market = collectors.collect_market_equity_daily("2026-05-06")
            breadth = collectors.collect_market_breadth_and_limit_structure("2026-05-06")
            events = collectors.collect_company_announcements_structured("2026-05-06")
            capital = collectors.collect_northbound_and_margin_flow("2026-05-06")

            self.assertTrue(reference.path.exists())
            self.assertTrue(market.path.exists())
            self.assertTrue(breadth.path.exists())
            self.assertTrue(events.path.exists())
            self.assertTrue(capital.path.exists())

            market_df = pd.read_csv(market.path, encoding="utf-8-sig")
            self.assertIn("limit_up_price", market_df.columns)

            event_df = pd.read_json(events.path)
            self.assertGreaterEqual(len(event_df), 1)
            self.assertIn("股份回购进展", str(event_df.iloc[0]["title"]))


if __name__ == "__main__":
    unittest.main()
