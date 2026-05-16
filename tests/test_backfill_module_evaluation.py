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

from trading_system.cli.backfill_module_evaluation import backfill_module_evaluation
from trading_system.decision.account import AccountConstraints
from trading_system.signal.scanners.base import ModuleSignal
from trading_system.signal.technical_modules import TechnicalModule


class _DummyScanner:
    module_id = "TM001_line_a_trend_continuation"

    def is_available(self, trade_date: str) -> bool:
        return True

    def scan(self, trade_date: str, market_regime, account=None, universe=None):
        return [
            ModuleSignal(
                module_id=self.module_id,
                stock_code="000001.SZ",
                trade_date=trade_date,
                signal_type="strong",
                strength=0.85,
                confidence=0.9,
                technical_state="line_a_top_entry",
            )
        ]


class BackfillModuleEvaluationTest(unittest.TestCase):
    def test_backfill_module_evaluation_writes_outputs(self) -> None:
        history = pd.DataFrame(
            [
                {"stock_code": "000001.SZ", "trade_date": "2026-05-01", "close": 10.0},
                {"stock_code": "000001.SZ", "trade_date": "2026-05-02", "close": 10.2},
                {"stock_code": "000001.SZ", "trade_date": "2026-05-05", "close": 10.4},
                {"stock_code": "000001.SZ", "trade_date": "2026-05-06", "close": 10.5},
                {"stock_code": "000001.SZ", "trade_date": "2026-05-07", "close": 10.7},
                {"stock_code": "000001.SZ", "trade_date": "2026-05-08", "close": 10.8},
                {"stock_code": "000001.SZ", "trade_date": "2026-05-09", "close": 10.9},
                {"stock_code": "000001.SZ", "trade_date": "2026-05-10", "close": 11.0},
                {"stock_code": "000001.SZ", "trade_date": "2026-05-11", "close": 11.1},
            ]
        )
        account = AccountConstraints(
            profile_name="acct",
            capital_total=43000.0,
            capital_liquid_ratio_min=0.1,
            single_position_max_pct=1.0,
            single_trade_capital_max=43000.0,
            max_holdings=5,
            max_new_positions_per_day=2,
            max_portfolio_turnover_per_day=0.4,
            daily_drawdown_alert_pct=0.03,
            portfolio_drawdown_alert_pct=0.08,
            preferred_holding_horizon_days=3,
            execution_mode="manual",
            can_watch_intraday=True,
            preopen_available=True,
            midday_available=True,
            close_available=True,
            avoid_chasing_limit_up=True,
            avoid_low_liquidity=True,
        )
        modules = [
            TechnicalModule(
                module_id="TM001_line_a_trend_continuation",
                family="trend_continuation",
                role="candidate_generator",
                priority="core",
                legacy_refs=(),
                market_regimes=("risk_on", "selective"),
                style_bias=("main_board",),
                needs_intraday=False,
                description="x",
            )
        ]
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            processed = tmp_root / "processed"
            outputs = tmp_root / "outputs"
            processed.mkdir(parents=True, exist_ok=True)
            outputs.mkdir(parents=True, exist_ok=True)
            with patch("trading_system.cli.backfill_module_evaluation.PROCESSED_DATA_DIR", processed), \
                patch("trading_system.cli.backfill_module_evaluation.OUTPUTS_DIR", outputs), \
                patch("trading_system.cli.backfill_module_evaluation.load_stock_history", return_value=history), \
                patch("trading_system.cli.backfill_module_evaluation.load_active_account_constraints", return_value=account), \
                patch("trading_system.cli.backfill_module_evaluation.load_technical_modules", return_value=modules), \
                patch("trading_system.cli.backfill_module_evaluation.load_scanners_for_modules", return_value={"TM001_line_a_trend_continuation": _DummyScanner()}):
                json_path, md_path = backfill_module_evaluation("2026-05-06", lookback_trade_days=3)
                self.assertTrue(json_path.exists())
                self.assertTrue(md_path.exists())


if __name__ == "__main__":
    unittest.main()
