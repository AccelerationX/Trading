from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_system.integrations.tushare_client import load_tushare_runtime_config, latest_open_trade_date


class TushareClientTest(unittest.TestCase):
    def test_load_tushare_runtime_config_from_env(self) -> None:
        original = os.environ.get("TUSHARE_TOKEN")
        os.environ["TUSHARE_TOKEN"] = "unit-test-token"
        try:
            config = load_tushare_runtime_config()
            self.assertEqual(config.token, "unit-test-token")
        finally:
            if original is None:
                os.environ.pop("TUSHARE_TOKEN", None)
            else:
                os.environ["TUSHARE_TOKEN"] = original

    def test_latest_open_trade_date_falls_back_to_latest_completed_session(self) -> None:
        class FakePro:
            def trade_cal(self, **kwargs):
                return pd.DataFrame(
                    [
                        {"cal_date": "20260506", "is_open": 1},
                        {"cal_date": "20260507", "is_open": 1},
                        {"cal_date": "20260508", "is_open": 1},
                    ]
                )

            def daily(self, trade_date=None, **kwargs):
                if str(trade_date) == "20260508":
                    return pd.DataFrame()
                return pd.DataFrame([{"ts_code": "000001.SZ", "trade_date": str(trade_date)}])

        resolved = latest_open_trade_date(FakePro(), "20260508")
        self.assertEqual(resolved, "20260507")


if __name__ == "__main__":
    unittest.main()
