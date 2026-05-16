from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_system.cli.sync_stock_history import sync_stock_history_from_market_daily


def _sample_market_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "stock_code": "000001.SZ",
                "trade_date": "20260506",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.4,
                "prev_close": 10.0,
                "volume": 1000,
                "amount": 5000000.0,
                "turnover_pct": 1.2,
                "turnover_rate_f": 2.3,
                "volume_ratio": 1.1,
                "pe_ttm": 12.5,
                "pb": 1.6,
                "limit_up_price": 11.0,
                "limit_down_price": 9.0,
                "total_share": 100000.0,
                "float_share": 80000.0,
                "free_share": 70000.0,
                "total_mv": 1234567.0,
                "circ_mv": 999999.0,
            }
        ]
    )


def _sample_reference_frame() -> pd.DataFrame:
    return pd.DataFrame([{"stock_code": "000001.SZ", "name": "平安银行"}])


class SyncStockHistoryTest(unittest.TestCase):
    def test_sync_stock_history_from_market_daily(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            inbox = tmp_root / "inbox"
            outputs = tmp_root / "outputs"
            raw = tmp_root / "raw"
            (inbox / "market_equity_daily").mkdir(parents=True, exist_ok=True)
            (inbox / "equity_reference_master").mkdir(parents=True, exist_ok=True)
            outputs.mkdir(parents=True, exist_ok=True)
            raw.mkdir(parents=True, exist_ok=True)

            _sample_market_frame().to_csv(
                inbox / "market_equity_daily" / "market_equity_daily_20260506.csv",
                index=False,
                encoding="utf-8-sig",
            )
            _sample_reference_frame().to_csv(
                inbox / "equity_reference_master" / "equity_reference_master_20260506.csv",
                index=False,
                encoding="utf-8-sig",
            )

            with patch("trading_system.cli.sync_stock_history.INBOX_DIR", inbox), \
                patch("trading_system.cli.sync_stock_history.OUTPUTS_DIR", outputs), \
                patch("trading_system.cli.sync_stock_history.RAW_DATA_DIR", raw):
                json_path, md_path = sync_stock_history_from_market_daily("20260506")

            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            stock_path = raw / "stock_history" / "000001.SZ.csv"
            self.assertTrue(stock_path.exists())
            content = stock_path.read_text(encoding="utf-8-sig")
            self.assertIn("平安银行", content)
            self.assertIn("20260506", content)

    def test_sync_stock_history_repairs_empty_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            inbox = tmp_root / "inbox"
            outputs = tmp_root / "outputs"
            raw = tmp_root / "raw"
            stock_history_dir = raw / "stock_history"
            (inbox / "market_equity_daily").mkdir(parents=True, exist_ok=True)
            (inbox / "equity_reference_master").mkdir(parents=True, exist_ok=True)
            outputs.mkdir(parents=True, exist_ok=True)
            stock_history_dir.mkdir(parents=True, exist_ok=True)

            _sample_market_frame().to_csv(
                inbox / "market_equity_daily" / "market_equity_daily_20260506.csv",
                index=False,
                encoding="utf-8-sig",
            )
            _sample_reference_frame().to_csv(
                inbox / "equity_reference_master" / "equity_reference_master_20260506.csv",
                index=False,
                encoding="utf-8-sig",
            )

            stock_path = stock_history_dir / "000001.SZ.csv"
            stock_path.write_text("", encoding="utf-8")

            with patch("trading_system.cli.sync_stock_history.INBOX_DIR", inbox), \
                patch("trading_system.cli.sync_stock_history.OUTPUTS_DIR", outputs), \
                patch("trading_system.cli.sync_stock_history.RAW_DATA_DIR", raw):
                sync_stock_history_from_market_daily("20260506")

            repaired = pd.read_csv(stock_path, encoding="utf-8-sig")
            self.assertEqual(len(repaired), 1)
            self.assertIn("20260506", repaired.to_csv(index=False))


if __name__ == "__main__":
    unittest.main()
