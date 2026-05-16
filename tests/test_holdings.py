from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_system.context.cards import CandidateCard, TradePlanCard
from trading_system.decision.account import AccountConstraints
from trading_system.decision.holdings import (
    PortfolioSnapshot,
    HoldingPosition,
    assess_portfolio_positions,
    load_portfolio_snapshot,
)


class HoldingsTest(unittest.TestCase):
    def test_load_portfolio_snapshot_defaults_to_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            snapshot = load_portfolio_snapshot(Path(tmp_dir) / "missing.json")
        self.assertEqual(snapshot.positions, [])
        self.assertEqual(snapshot.broker, "")

    def test_assess_portfolio_positions_marks_held_buy_plan_as_hold_or_add(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inbox = Path(tmp_dir)
            market_dir = inbox / "market_equity_daily"
            market_dir.mkdir(parents=True, exist_ok=True)
            with (market_dir / "market_equity_daily_20260506.csv").open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["stock_code", "stock_name", "close", "amount"])
                writer.writeheader()
                writer.writerow(
                    {
                        "stock_code": "002705.SZ",
                        "stock_name": "新宝股份",
                        "close": "18.5",
                        "amount": "180000000",
                    }
                )

            snapshot = PortfolioSnapshot(
                as_of="2026-05-06",
                positions=[
                    HoldingPosition(
                        stock_code="002705.SZ",
                        stock_name="新宝股份",
                        shares=800,
                        available_shares=800,
                        cost_basis=17.0,
                    )
                ],
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
            candidates = [
                CandidateCard(
                    candidate_id="c1",
                    stock_code="002705.SZ",
                    trade_date="2026-05-06",
                    candidate_source="full_resonance",
                    candidate_score=0.81,
                    technical_state="event_theme_resonance",
                    diagnostic_summary="结构化诊断",
                )
            ]
            trade_plans = [
                TradePlanCard(
                    plan_id="p1",
                    trade_date="2026-05-06",
                    stock_code="002705.SZ",
                    action="buy_pilot",
                    priority_rank=1,
                    rationale="原始计划",
                    entry_condition="开盘确认后处理",
                    position_size_rule="先试仓再加",
                )
            ]

            with patch("trading_system.decision.holdings.INBOX_DIR", inbox):
                assessments = assess_portfolio_positions(
                    snapshot,
                    account=account,
                    trade_date="2026-05-06",
                    candidate_cards=candidates,
                    trade_plans=trade_plans,
                )

        self.assertEqual(len(assessments), 1)
        self.assertEqual(assessments[0].summary_action, "hold_or_add")
        self.assertGreater(assessments[0].market_value or 0, 0)
        self.assertIn("Only consider adding", assessments[0].recommendation)


if __name__ == "__main__":
    unittest.main()
