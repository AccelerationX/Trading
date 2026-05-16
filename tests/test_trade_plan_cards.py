from __future__ import annotations

import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_system.context.cards import CandidateCard, MarketRegimeSnapshot
from trading_system.cli.build_trade_plan_cards import _apply_supporting_card_labels, _load_supporting_card_labels
from trading_system.decision.account import AccountConstraints
from trading_system.decision.trade_plan_cards import build_trade_plan_cards
from trading_system.reporting.trade_plan_reports import render_trade_plan_markdown


class TradePlanCardsTest(unittest.TestCase):
    def test_build_trade_plan_cards(self) -> None:
        snapshot = MarketRegimeSnapshot(
            snapshot_id="s1",
            trade_date="2026-05-06",
            market_bias="bullish",
            risk_mode="risk_on",
            breadth_strength="strong",
            limit_up_temperature="warm",
            turnover_regime="high",
            style_lead="small_cap_lead",
            theme_concentration="high",
            opening_risk_note="Need confirmation.",
            confidence=0.8,
            supporting_evidence=[],
        )
        account = AccountConstraints(
            profile_name="acct",
            capital_total=200000.0,
            capital_liquid_ratio_min=0.1,
            single_position_max_pct=0.2,
            single_trade_capital_max=50000.0,
            max_holdings=5,
            max_new_positions_per_day=1,
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
        plans = build_trade_plan_cards(
            "2026-05-06",
            market_regime=snapshot,
            account=account,
            candidate_cards=[
                CandidateCard(
                    candidate_id="c1",
                    stock_code="000001.SZ",
                    trade_date="2026-05-06",
                    candidate_source="event_theme_resonance",
                    candidate_score=0.82,
                    technical_state="event_theme_resonance",
                    active_module_ids=["TM501_market_state_dynamic", "TM201_group_rotation_repair"],
                    supporting_cards=["e1", "t1"],
                ),
                CandidateCard(
                    candidate_id="c2",
                    stock_code="000002.SZ",
                    trade_date="2026-05-06",
                    candidate_source="theme_priority",
                    candidate_score=0.58,
                    technical_state="theme_rotation_watch",
                    supporting_cards=["t1"],
                ),
            ],
            text_watch_records=[
                {
                    "source_id": "exchange_filings",
                    "priority_score": 107,
                    "publish_time": "2026-05-06 20:10:00",
                    "title": "300001.SZ 回购进展公告",
                    "stock_code": "000001.SZ",
                    "related_industries": [],
                    "related_stocks": ["000001.SZ"],
                    "source_url": "https://example.com/300001",
                    "summary_text": "回购进展",
                }
            ],
        )
        self.assertEqual(plans[0].action, "buy_pilot")
        self.assertEqual(plans[1].action, "watch_only")
        self.assertIsNotNone(plans[0].max_position_pct)
        self.assertTrue(any("text_watch_focus" in note for note in plans[0].risk_notes))

    def test_render_trade_plan_markdown(self) -> None:
        markdown = render_trade_plan_markdown(
            "2026-05-06",
            plans=[],
        )
        self.assertIn("Trade Plan Draft - 2026-05-06", markdown)

    def test_negative_text_watch_forces_avoid(self) -> None:
        snapshot = MarketRegimeSnapshot(
            snapshot_id="s1",
            trade_date="2026-05-06",
            market_bias="bullish",
            risk_mode="risk_on",
            breadth_strength="strong",
            limit_up_temperature="warm",
            turnover_regime="high",
            style_lead="small_cap_lead",
            theme_concentration="high",
            confidence=0.8,
            supporting_evidence=[],
        )
        account = AccountConstraints(
            profile_name="acct",
            capital_total=200000.0,
            capital_liquid_ratio_min=0.1,
            single_position_max_pct=0.2,
            single_trade_capital_max=50000.0,
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
        plans = build_trade_plan_cards(
            "2026-05-06",
            market_regime=snapshot,
            account=account,
            candidate_cards=[
                CandidateCard(
                    candidate_id="c1",
                    stock_code="000001.SZ",
                    trade_date="2026-05-06",
                    candidate_source="event_theme_resonance",
                    candidate_score=0.82,
                    technical_state="event_theme_resonance",
                    disqualify_flags=["text_watch_risk_overhang"],
                    supporting_cards=["e1"],
                )
            ],
            text_watch_records=[
                {
                    "source_id": "exchange_filings",
                    "priority_score": 111,
                    "publish_time": "2026-05-06 20:10:00",
                    "title": "300001.SZ 股票交易风险提示公告",
                    "stock_code": "000001.SZ",
                    "related_industries": [],
                    "related_stocks": ["300001.SZ"],
                    "source_url": "https://example.com/risk",
                    "summary_text": "风险提示",
                }
            ],
        )
        self.assertEqual(plans[0].action, "avoid")

    def test_trade_plan_cards_are_capped_for_manual_review(self) -> None:
        snapshot = MarketRegimeSnapshot(
            snapshot_id="s1",
            trade_date="2026-05-06",
            market_bias="bullish",
            risk_mode="risk_on",
            breadth_strength="strong",
            limit_up_temperature="warm",
            turnover_regime="high",
            style_lead="small_cap_lead",
            theme_concentration="high",
            confidence=0.8,
            supporting_evidence=[],
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
                candidate_id=f"c{i}",
                stock_code=f"000{i:03d}.SZ",
                trade_date="2026-05-06",
                candidate_source="event_direct",
                candidate_score=0.80 - i * 0.01,
                technical_state="event_breakout_watch",
            )
            for i in range(1, 15)
        ]
        plans = build_trade_plan_cards(
            "2026-05-06",
            market_regime=snapshot,
            account=account,
            candidate_cards=candidates,
            text_watch_records=[],
        )
        self.assertEqual(len(plans), 10)
        self.assertEqual(plans[0].action, "buy_pilot")
        self.assertEqual(plans[1].action, "buy_pilot")
        self.assertTrue(all(plan.priority_rank <= 10 for plan in plans))

    def test_high_price_concentrated_candidate_is_not_buy_pilot(self) -> None:
        snapshot = MarketRegimeSnapshot(
            snapshot_id="s1",
            trade_date="2026-05-06",
            market_bias="bullish",
            risk_mode="risk_on",
            breadth_strength="strong",
            limit_up_temperature="warm",
            turnover_regime="high",
            style_lead="large_cap_lead",
            theme_concentration="high",
            confidence=0.8,
            supporting_evidence=[],
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
        plans = build_trade_plan_cards(
            "2026-05-06",
            market_regime=snapshot,
            account=account,
            candidate_cards=[
                CandidateCard(
                    candidate_id="c1",
                    stock_code="603986.SH",
                    trade_date="2026-05-06",
                    candidate_source="event_direct",
                    candidate_score=0.82,
                    technical_state="event_breakout_watch",
                    estimated_min_lot_cost=35000.0,
                    last_close_price=350.0,
                    tradeability_verdict="too_concentrated",
                    disqualify_flags=["min_lot_too_concentrated"],
                    diagnostic_summary="最小一手成本约3.5万元，占总资金比例过高。",
                )
            ],
            text_watch_records=[],
        )
        self.assertEqual(plans[0].action, "watch_only")

    def test_supporting_card_labels_are_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            processed = Path(tmp_dir)
            (processed / "events").mkdir(parents=True, exist_ok=True)
            (processed / "themes").mkdir(parents=True, exist_ok=True)
            (processed / "capital").mkdir(parents=True, exist_ok=True)

            (processed / "events" / "event_cards_2026-05-06.json").write_text(
                json.dumps(
                    [
                        {
                            "event_id": "e1",
                            "event_type": "share_repurchase",
                            "event_title": "股份回购进展：实施",
                            "stock_codes": ["000001.SZ"],
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (processed / "themes" / "theme_cards_2026-05-06.json").write_text(
                json.dumps(
                    [
                        {
                            "theme_id": "t1",
                            "theme_name": "算力基础设施",
                            "trigger_type": "policy:ministry",
                            "trigger_time": "2026-05-06 09:00:00",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch("trading_system.cli.build_trade_plan_cards.PROCESSED_DATA_DIR", processed):
                label_map = _load_supporting_card_labels("2026-05-06")

            resolved = _apply_supporting_card_labels(
                [
                    build_trade_plan_cards(
                        "2026-05-06",
                        market_regime=MarketRegimeSnapshot(
                            snapshot_id="s1",
                            trade_date="2026-05-06",
                            market_bias="bullish",
                            risk_mode="risk_on",
                            breadth_strength="strong",
                            limit_up_temperature="warm",
                            turnover_regime="high",
                        ),
                        account=AccountConstraints(
                            profile_name="acct",
                            capital_total=200000.0,
                            capital_liquid_ratio_min=0.1,
                            single_position_max_pct=0.2,
                            single_trade_capital_max=50000.0,
                            max_holdings=5,
                            max_new_positions_per_day=1,
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
                        ),
                        candidate_cards=[
                            CandidateCard(
                                candidate_id="c1",
                                stock_code="000001.SZ",
                                trade_date="2026-05-06",
                                candidate_source="event_direct",
                                candidate_score=0.8,
                                technical_state="event_breakout_watch",
                                supporting_cards=["e1", "t1"],
                            )
                        ],
                        text_watch_records=[],
                    )[0]
                ],
                label_map,
            )
            self.assertEqual(resolved[0].supporting_cards, ["股份回购进展：实施", "算力基础设施"])


if __name__ == "__main__":
    unittest.main()
