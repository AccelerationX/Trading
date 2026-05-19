from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import json
import tempfile
from unittest.mock import patch

from trading_system.context.candidate_cards import build_candidate_cards
from trading_system.context.cards import EventCard, MacroEventCard, MarketRegimeSnapshot, ThemeCard
from trading_system.decision.account import AccountConstraints
from trading_system.reporting.candidate_reports import render_candidate_cards_markdown
from trading_system.signal.scanners.base import ModuleSignal
from trading_system.signal.technical_modules import recommend_modules_for_regime


class CandidateCardsTest(unittest.TestCase):
    def test_build_candidate_cards_from_event_and_theme_inputs(self) -> None:
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
            confidence=0.78,
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
        modules = recommend_modules_for_regime(snapshot, can_watch_intraday=account.can_watch_intraday)
        cards = build_candidate_cards(
            "2026-05-06",
            market_regime=snapshot,
            account=account,
            technical_modules=modules,
            event_cards=[
                EventCard(
                    event_id="e1",
                    event_type="earnings_preannouncement",
                    event_title="positive earnings",
                    stock_codes=["000001.SZ"],
                    bullish_bearish="bullish",
                    impact_horizon="multi_day",
                    event_strength=0.8,
                    is_official=True,
                ),
                EventCard(
                    event_id="e2",
                    event_type="share_reduction",
                    event_title="share reduction",
                    stock_codes=["600001.SH"],
                    bullish_bearish="bearish",
                    impact_horizon="multi_day",
                    event_strength=0.7,
                    is_official=True,
                ),
            ],
            theme_cards=[
                ThemeCard(
                    theme_id="t1",
                    theme_name="robotics",
                    trigger_type="policy:ministry",
                    trigger_time="2026-05-06 18:00:00",
                    priority_stocks=["000001.SZ", "000002.SZ"],
                    continuation_guess="multi_day",
                )
            ],
            text_watch_records=[
                {
                    "source_id": "exchange_filings",
                    "priority_score": 108,
                    "publish_time": "2026-05-06 20:00:00",
                    "title": "300001.SZ 回购进展公告",
                    "stock_code": "000001.SZ",
                    "related_industries": ["robotics"],
                    "related_stocks": ["000001.SZ"],
                    "source_url": "https://example.com/300001",
                    "summary_text": "公司发布回购进展",
                }
            ],
        )
        stock_codes = [card.stock_code for card in cards]
        self.assertEqual(stock_codes, ["000001.SZ", "000002.SZ"])
        self.assertEqual(cards[0].candidate_source, "event_theme_resonance")
        self.assertGreater(cards[0].candidate_score or 0.0, cards[1].candidate_score or 0.0)
        self.assertTrue(cards[0].active_module_ids)
        self.assertIn("text_signal_score=", cards[0].candidate_rationale)
        self.assertEqual(cards[0].fusion_verdict, "actionable")
        self.assertEqual(cards[0].dominant_driver, "event")
        self.assertIsNotNone(cards[0].market_permission_score)
        self.assertIsNotNone(cards[0].technical_confirmation_score)

    def test_markdown_render(self) -> None:
        snapshot = MarketRegimeSnapshot(
            snapshot_id="s1",
            trade_date="2026-05-06",
            market_bias="mixed",
            risk_mode="selective",
            breadth_strength="mixed",
            limit_up_temperature="neutral",
            turnover_regime="normal",
            style_lead="mixed",
            theme_concentration="normal",
            confidence=0.55,
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
            can_watch_intraday=False,
            preopen_available=True,
            midday_available=False,
            close_available=True,
            avoid_chasing_limit_up=True,
            avoid_low_liquidity=True,
        )
        modules = recommend_modules_for_regime(snapshot, can_watch_intraday=account.can_watch_intraday)
        cards = build_candidate_cards(
            "2026-05-06",
            market_regime=snapshot,
            account=account,
            technical_modules=modules,
            event_cards=[
                EventCard(
                    event_id="e1",
                    event_type="major_contract",
                    event_title="contract win",
                    stock_codes=["000001.SZ"],
                    bullish_bearish="bullish",
                    impact_horizon="multi_day_to_medium_term",
                    event_strength=0.7,
                    is_official=True,
                )
            ],
            theme_cards=[],
        )
        markdown = render_candidate_cards_markdown("2026-05-06", cards)
        self.assertIn("Candidate Cards - 2026-05-06", markdown)
        self.assertIn("000001.SZ", markdown)

    def test_negative_text_watch_adds_risk_flag(self) -> None:
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
            confidence=0.78,
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
        modules = recommend_modules_for_regime(snapshot, can_watch_intraday=account.can_watch_intraday)
        cards = build_candidate_cards(
            "2026-05-06",
            market_regime=snapshot,
            account=account,
            technical_modules=modules,
            event_cards=[
                EventCard(
                    event_id="e1",
                    event_type="major_contract",
                    event_title="contract win",
                    stock_codes=["000001.SZ"],
                    bullish_bearish="bullish",
                    impact_horizon="multi_day",
                    event_strength=0.75,
                    is_official=True,
                )
            ],
            theme_cards=[],
            text_watch_records=[
                {
                    "source_id": "exchange_filings",
                    "priority_score": 103,
                    "publish_time": "2026-05-06 20:00:00",
                    "title": "000001.SZ 股票交易风险提示公告",
                    "stock_code": "000001.SZ",
                    "related_industries": [],
                    "related_stocks": ["000001.SZ"],
                    "source_url": "https://example.com/risk",
                    "summary_text": "风险提示与异常波动说明",
                }
            ],
        )
        self.assertIn("text_watch_risk_overhang", cards[0].disqualify_flags)

    def test_overlay_only_module_signal_does_not_create_direct_candidate(self) -> None:
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
            confidence=0.78,
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
        modules = recommend_modules_for_regime(snapshot, can_watch_intraday=account.can_watch_intraday)
        cards = build_candidate_cards(
            "2026-05-06",
            market_regime=snapshot,
            account=account,
            technical_modules=modules,
            event_cards=[],
            theme_cards=[],
            module_signals=[
                ModuleSignal(
                    module_id="TM601_capital_flow_overlay",
                    stock_code="000001.SZ",
                    trade_date="2026-05-06",
                    signal_type="strong",
                    strength=0.85,
                    technical_state="high_capital_inflow",
                    confidence=0.8,
                )
            ],
        )
        self.assertEqual(cards, [])

    def test_only_enabled_modules_appear_in_active_module_ids(self) -> None:
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
            confidence=0.78,
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
        modules = recommend_modules_for_regime(snapshot, can_watch_intraday=account.can_watch_intraday)
        cards = build_candidate_cards(
            "2026-05-06",
            market_regime=snapshot,
            account=account,
            technical_modules=modules,
            event_cards=[
                EventCard(
                    event_id="e1",
                    event_type="earnings_preannouncement",
                    event_title="positive earnings",
                    stock_codes=["000001.SZ"],
                    bullish_bearish="bullish",
                    impact_horizon="multi_day",
                    event_strength=0.8,
                    is_official=True,
                )
            ],
            theme_cards=[],
            available_module_ids={"TM001_line_a_trend_continuation", "TM002_breakout_and_relative_strength"},
        )
        self.assertTrue(cards)
        self.assertTrue(set(cards[0].active_module_ids).issubset({"TM001_line_a_trend_continuation", "TM002_breakout_and_relative_strength"}))

    def test_candidate_card_includes_tradeability_diagnosis(self) -> None:
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
            confidence=0.78,
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
        modules = recommend_modules_for_regime(snapshot, can_watch_intraday=account.can_watch_intraday)
        with tempfile.TemporaryDirectory() as tmp_dir:
            inbox = Path(tmp_dir)
            (inbox / "market_equity_daily").mkdir(parents=True, exist_ok=True)
            (inbox / "market_equity_daily" / "market_equity_daily_20260506.csv").write_text(
                "stock_code,trade_date,close,amount\n603986.SH,20260506,350.0,1500000000\n",
                encoding="utf-8",
            )
            with patch("trading_system.context.candidate_cards.INBOX_DIR", inbox):
                cards = build_candidate_cards(
                    "2026-05-06",
                    market_regime=snapshot,
                    account=account,
                    technical_modules=modules,
                    event_cards=[
                        EventCard(
                            event_id="e1",
                            event_type="share_repurchase",
                            event_title="股份回购进展：预案",
                            stock_codes=["603986.SH"],
                            bullish_bearish="bullish",
                            impact_horizon="multi_day",
                            event_strength=0.8,
                            is_official=True,
                        )
                    ],
                    theme_cards=[],
                )
        self.assertTrue(cards)
        self.assertEqual(cards[0].tradeability_verdict, "too_concentrated")
        self.assertIn("高价股导致仓位过度集中", cards[0].diagnostic_risk_notes)


    def test_event_driven_candidate_ranks_above_module_only_candidate(self) -> None:
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
            sentiment_cycle="expansion",
            leader_stability="stable_leaders",
            event_driven_bias="theme_momentum",
            confidence=0.78,
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
        modules = recommend_modules_for_regime(snapshot, can_watch_intraday=account.can_watch_intraday)
        cards = build_candidate_cards(
            "2026-05-06",
            market_regime=snapshot,
            account=account,
            technical_modules=modules,
            event_cards=[
                EventCard(
                    event_id="e1",
                    event_type="major_contract",
                    event_title="重大合同",
                    stock_codes=["000001.SZ"],
                    bullish_bearish="bullish",
                    impact_horizon="multi_day",
                    event_strength=0.85,
                    is_official=True,
                )
            ],
            theme_cards=[],
            module_signals=[
                ModuleSignal(
                    module_id="TM001_line_a_trend_continuation",
                    stock_code="000001.SZ",
                    trade_date="2026-05-06",
                    signal_type="strong",
                    strength=0.82,
                    technical_state="event_breakout_watch",
                    confidence=0.8,
                ),
                ModuleSignal(
                    module_id="TM001_line_a_trend_continuation",
                    stock_code="000002.SZ",
                    trade_date="2026-05-06",
                    signal_type="strong",
                    strength=0.9,
                    technical_state="event_breakout_watch",
                    confidence=0.85,
                ),
            ],
        )
        self.assertEqual(cards[0].stock_code, "000001.SZ")
        self.assertEqual(cards[0].candidate_source, "module_event_resonance")
        self.assertEqual(cards[1].candidate_source, "module_direct")
        self.assertGreater(cards[0].information_edge_score or 0.0, cards[1].information_edge_score or 0.0)
        self.assertGreater(cards[0].candidate_score or 0.0, cards[1].candidate_score or 0.0)
        self.assertEqual(cards[1].fusion_verdict, "watch")

    def test_macro_alignment_boosts_matching_candidate(self) -> None:
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
            confidence=0.78,
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
        modules = recommend_modules_for_regime(snapshot, can_watch_intraday=account.can_watch_intraday)
        cards = build_candidate_cards(
            "2026-05-06",
            market_regime=snapshot,
            account=account,
            technical_modules=modules,
            event_cards=[],
            theme_cards=[
                ThemeCard(
                    theme_id="t1",
                    theme_name="AI hardware",
                    trigger_type="policy:ministry",
                    trigger_time="2026-05-06 18:00:00",
                    priority_stocks=["000001.SZ"],
                    priority_industries=["consumer_electronics", "semiconductor"],
                    continuation_guess="multi_day",
                )
            ],
            macro_event_cards=[
                MacroEventCard(
                    macro_event_id="m1",
                    event_type="cross_border_diplomacy",
                    title="Trump visit opens trade talks",
                    bias="bullish",
                    impact_scope="macro_cross_border",
                    confidence=0.85,
                    beneficiary_industries=["consumer_electronics", "new_energy_vehicle"],
                    risk_industries=["military"],
                )
            ],
        )
        self.assertTrue(cards)
        self.assertGreater(cards[0].macro_alignment_score or 0.0, 0.6)
        self.assertIn("m1", cards[0].supporting_macro_events)
        self.assertIn("macro_alignment_score=", cards[0].candidate_rationale)

    def test_candidate_cards_assign_setup_and_market_gate(self) -> None:
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
            confidence=0.78,
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
        modules = recommend_modules_for_regime(snapshot, can_watch_intraday=account.can_watch_intraday)
        cards = build_candidate_cards(
            "2026-05-06",
            market_regime=snapshot,
            account=account,
            technical_modules=modules,
            event_cards=[
                EventCard(
                    event_id="e1",
                    event_type="major_contract",
                    event_title="major contract",
                    stock_codes=["000001.SZ"],
                    bullish_bearish="bullish",
                    impact_horizon="multi_day",
                    event_strength=0.85,
                    is_official=True,
                )
            ],
            theme_cards=[
                ThemeCard(
                    theme_id="t1",
                    theme_name="robotics",
                    trigger_type="policy",
                    trigger_time="2026-05-06 08:00:00",
                    priority_stocks=["000001.SZ"],
                    continuation_guess="multi_day",
                )
            ],
            module_signals=[
                ModuleSignal(
                    module_id="TM001_line_a_trend_continuation",
                    stock_code="000001.SZ",
                    trade_date="2026-05-06",
                    signal_type="strong",
                    strength=0.82,
                    technical_state="event_theme_resonance",
                    confidence=0.8,
                )
            ],
        )
        self.assertEqual(cards[0].setup_type, "leader_acceleration")
        self.assertTrue(cards[0].market_gate_pass)
        self.assertIn("setup_type=leader_acceleration", cards[0].candidate_rationale)

    def test_risk_off_market_blocks_leader_acceleration_setup(self) -> None:
        snapshot = MarketRegimeSnapshot(
            snapshot_id="s1",
            trade_date="2026-05-06",
            market_bias="bearish",
            risk_mode="risk_off",
            breadth_strength="weak",
            limit_up_temperature="cool",
            turnover_regime="low",
            style_lead="small_cap_lead",
            theme_concentration="high",
            confidence=0.78,
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
        modules = recommend_modules_for_regime(snapshot, can_watch_intraday=account.can_watch_intraday)
        cards = build_candidate_cards(
            "2026-05-06",
            market_regime=snapshot,
            account=account,
            technical_modules=modules,
            event_cards=[
                EventCard(
                    event_id="e1",
                    event_type="major_contract",
                    event_title="major contract",
                    stock_codes=["000001.SZ"],
                    bullish_bearish="bullish",
                    impact_horizon="multi_day",
                    event_strength=0.85,
                    is_official=True,
                )
            ],
            theme_cards=[
                ThemeCard(
                    theme_id="t1",
                    theme_name="robotics",
                    trigger_type="policy",
                    trigger_time="2026-05-06 08:00:00",
                    priority_stocks=["000001.SZ"],
                    continuation_guess="multi_day",
                )
            ],
            module_signals=[
                ModuleSignal(
                    module_id="TM001_line_a_trend_continuation",
                    stock_code="000001.SZ",
                    trade_date="2026-05-06",
                    signal_type="strong",
                    strength=0.82,
                    technical_state="event_theme_resonance",
                    confidence=0.8,
                )
            ],
        )
        self.assertEqual(cards[0].setup_type, "leader_acceleration")
        self.assertFalse(cards[0].market_gate_pass)
        self.assertEqual(cards[0].fusion_verdict, "avoid")
        self.assertEqual(cards[0].market_gate_reason, "blocked_setup:leader_acceleration")

    def test_setup_policy_disabled_caps_candidate(self) -> None:
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
            confidence=0.78,
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
        modules = recommend_modules_for_regime(snapshot, can_watch_intraday=account.can_watch_intraday)
        cards = build_candidate_cards(
            "2026-05-06",
            market_regime=snapshot,
            account=account,
            technical_modules=modules,
            event_cards=[
                EventCard(
                    event_id="e1",
                    event_type="major_contract",
                    event_title="major contract",
                    stock_codes=["000001.SZ"],
                    bullish_bearish="bullish",
                    impact_horizon="multi_day",
                    event_strength=0.85,
                    is_official=True,
                )
            ],
            theme_cards=[
                ThemeCard(
                    theme_id="t1",
                    theme_name="robotics",
                    trigger_type="policy",
                    trigger_time="2026-05-06 08:00:00",
                    priority_stocks=["000001.SZ"],
                    continuation_guess="multi_day",
                )
            ],
            module_signals=[
                ModuleSignal(
                    module_id="TM001_line_a_trend_continuation",
                    stock_code="000001.SZ",
                    trade_date="2026-05-06",
                    signal_type="strong",
                    strength=0.82,
                    technical_state="event_theme_resonance",
                    confidence=0.8,
                )
            ],
            setup_policy={
                "leader_acceleration": type(
                    "Policy",
                    (),
                    {
                        "status": "disabled",
                        "score_multiplier": 0.72,
                        "verdict_cap": "watch",
                        "action_score_floor": 1.0,
                        "position_cap_multiplier": 0.0,
                        "notes": ("historical_underperformance",),
                    },
                )()
            },
        )
        self.assertEqual(cards[0].setup_policy_status, "disabled")
        self.assertEqual(cards[0].fusion_verdict, "watch")
        self.assertIn("setup_policy_disabled", cards[0].disqualify_flags)
        self.assertEqual(cards[0].setup_action_floor, 1.0)
        self.assertEqual(cards[0].setup_position_cap_multiplier, 0.0)

    def test_setup_policy_favored_boosts_candidate_score(self) -> None:
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
            confidence=0.78,
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
        modules = recommend_modules_for_regime(snapshot, can_watch_intraday=account.can_watch_intraday)
        baseline = build_candidate_cards(
            "2026-05-06",
            market_regime=snapshot,
            account=account,
            technical_modules=modules,
            event_cards=[
                EventCard(
                    event_id="e1",
                    event_type="major_contract",
                    event_title="major contract",
                    stock_codes=["000001.SZ"],
                    bullish_bearish="bullish",
                    impact_horizon="multi_day",
                    event_strength=0.85,
                    is_official=True,
                )
            ],
            theme_cards=[],
            module_signals=[
                ModuleSignal(
                    module_id="TM001_line_a_trend_continuation",
                    stock_code="000001.SZ",
                    trade_date="2026-05-06",
                    signal_type="strong",
                    strength=0.82,
                    technical_state="event_breakout_watch",
                    confidence=0.8,
                )
            ],
        )[0]
        favored = build_candidate_cards(
            "2026-05-06",
            market_regime=snapshot,
            account=account,
            technical_modules=modules,
            event_cards=[
                EventCard(
                    event_id="e1",
                    event_type="major_contract",
                    event_title="major contract",
                    stock_codes=["000001.SZ"],
                    bullish_bearish="bullish",
                    impact_horizon="multi_day",
                    event_strength=0.85,
                    is_official=True,
                )
            ],
            theme_cards=[],
            module_signals=[
                ModuleSignal(
                    module_id="TM001_line_a_trend_continuation",
                    stock_code="000001.SZ",
                    trade_date="2026-05-06",
                    signal_type="strong",
                    strength=0.82,
                    technical_state="event_breakout_watch",
                    confidence=0.8,
                )
            ],
            setup_policy={
                "event_ignition": type(
                    "Policy",
                    (),
                    {
                        "status": "favored",
                        "score_multiplier": 1.08,
                        "verdict_cap": "actionable",
                        "action_score_floor": 0.56,
                        "position_cap_multiplier": 1.15,
                        "notes": ("historical_edge_positive",),
                    },
                )()
            },
        )[0]
        self.assertEqual(favored.setup_policy_status, "favored")
        self.assertGreater(favored.candidate_score or 0.0, baseline.candidate_score or 0.0)
        self.assertEqual(favored.setup_action_floor, 0.56)
        self.assertEqual(favored.setup_position_cap_multiplier, 1.15)


if __name__ == "__main__":
    unittest.main()
