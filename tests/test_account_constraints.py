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

import trading_system.decision.account as account_mod
from trading_system.decision.account import load_active_account_constraints, save_normalized_account_constraints


class AccountConstraintsTest(unittest.TestCase):
    def test_account_constraints_load_and_save(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            profile_path = tmp_root / "account.json"
            profile_path.write_text(
                json.dumps(
                    {
                        "profile_name": "acct_a",
                        "capital_total": 100000,
                        "capital_liquid_ratio_min": 0.1,
                        "single_position_max_pct": 0.2,
                        "single_trade_capital_max": 30000,
                        "max_holdings": 5,
                        "max_new_positions_per_day": 2,
                        "max_portfolio_turnover_per_day": 0.4,
                        "daily_drawdown_alert_pct": 0.03,
                        "portfolio_drawdown_alert_pct": 0.08,
                        "preferred_holding_horizon_days": 3,
                        "execution_mode": "manual",
                        "can_watch_intraday": True,
                        "preopen_available": True,
                        "midday_available": False,
                        "close_available": True,
                        "avoid_chasing_limit_up": True,
                        "avoid_low_liquidity": True,
                        "trading_style": "small_capital_aggressive",
                        "target_return_mode": "asymmetric",
                        "position_concentration_limit": 0.7,
                        "max_setup_exposure": 0.45,
                        "allow_high_volatility_entries": True,
                        "min_expected_upside_pct": 0.06,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            account = load_active_account_constraints(profile_path)
            self.assertEqual(account.profile_name, "acct_a")
            self.assertEqual(account.max_holdings, 5)
            self.assertEqual(account.trading_style, "small_capital_aggressive")
            self.assertTrue(account.allow_high_volatility_entries)
            output_path = tmp_root / "normalized.json"
            saved = save_normalized_account_constraints(account, output_path)
            self.assertTrue(saved.exists())

    def test_account_constraints_fallback_to_runtime_demo(self) -> None:
        original_inbox_dir = account_mod.INBOX_DIR
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_root = Path(tmp_dir)
                account_mod.INBOX_DIR = tmp_root
                (tmp_root / "account_constraints").mkdir(parents=True, exist_ok=True)
                account = load_active_account_constraints()
                self.assertEqual(account.profile_name, "default_runtime_demo")
                self.assertGreater(account.capital_total, 0)
                self.assertGreater(account.single_trade_capital_max, 0)
                self.assertEqual(account.trading_style, "small_capital_aggressive")
        finally:
            account_mod.INBOX_DIR = original_inbox_dir


if __name__ == "__main__":
    unittest.main()
