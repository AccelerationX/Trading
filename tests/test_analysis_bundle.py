from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_system.context.cards import CapitalBehaviorCard, EventCard, MarketRegimeSnapshot, ThemeCard
from trading_system.decision.account import AccountConstraints
from trading_system.reporting.analysis_bundle import render_analysis_bundle_markdown
from trading_system.signal.technical_modules import recommend_modules_for_regime


class AnalysisBundleTest(unittest.TestCase):
    def test_markdown_render(self) -> None:
        market_regime = MarketRegimeSnapshot(
            snapshot_id="s1",
            trade_date="2026-05-06",
            market_bias="bullish",
            risk_mode="risk_on",
            breadth_strength="strong",
            limit_up_temperature="hot",
            turnover_regime="high",
            style_lead="small_cap_lead",
            theme_concentration="high",
            confidence=0.75,
            supporting_evidence=[],
        )
        account = AccountConstraints(
            profile_name="acct",
            capital_total=100000.0,
            capital_liquid_ratio_min=0.1,
            single_position_max_pct=0.2,
            single_trade_capital_max=30000.0,
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
        modules = recommend_modules_for_regime(market_regime, can_watch_intraday=account.can_watch_intraday)
        md = render_analysis_bundle_markdown(
            trade_date="2026-05-06",
            market_regime=market_regime,
            account=account,
            technical_modules=modules,
            event_cards=[
                EventCard(
                    event_id="e1",
                    event_type="earnings_preannouncement",
                    event_title="earnings beat",
                    stock_codes=["000001.SZ"],
                    bullish_bearish="bullish",
                    impact_horizon="multi_day",
                )
            ],
            theme_cards=[
                ThemeCard(
                    theme_id="t1",
                    theme_name="commercial aerospace",
                    trigger_type="policy:ministry",
                    trigger_time="2026-05-06 18:00:00",
                )
            ],
            macro_event_cards=[],
            capital_behavior_cards=[
                CapitalBehaviorCard(
                    card_id="c1",
                    stock_code="300001.SZ",
                    trade_date="2026-05-06",
                    capital_signal_type="dragon_tiger_board",
                    participation_strength="high",
                    consistency_score=0.8,
                    suspected_style="institutional_active",
                    support_or_distribution="support",
                )
            ],
        )
        self.assertIn("Assistant Analysis Bundle", md)
        self.assertIn("earnings beat", md)
        self.assertIn("commercial aerospace", md)
        self.assertIn("300001.SZ", md)


if __name__ == "__main__":
    unittest.main()
