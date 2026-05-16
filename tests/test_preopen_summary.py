from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_system.context.cards import CandidateCard, MarketRegimeSnapshot, ThemeCard, TradePlanCard
from trading_system.decision.account import AccountConstraints
from trading_system.decision.holdings import HoldingAssessment, PortfolioSnapshot, HoldingPosition
from trading_system.reporting.preopen_summary import (
    _collapse_theme_board,
    build_preopen_summary_payload,
    render_preopen_summary_markdown,
)


class PreopenSummaryTest(unittest.TestCase):
    def test_build_preopen_summary_payload_separates_held_and_new_ideas(self) -> None:
        payload = build_preopen_summary_payload(
            trade_date="2026-05-06",
            market_regime=MarketRegimeSnapshot(
                snapshot_id="s1",
                trade_date="2026-05-06",
                market_bias="bullish",
                risk_mode="risk_on",
                breadth_strength="strong",
                limit_up_temperature="warm",
                turnover_regime="high",
                style_lead="large_cap_lead",
                theme_concentration="high",
                opening_risk_note="Watch opening breadth.",
                supporting_evidence=["breadth stable"],
            ),
            account=AccountConstraints(
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
            ),
            portfolio=PortfolioSnapshot(
                as_of="2026-05-06",
                positions=[HoldingPosition(stock_code="002705.SZ", shares=800, available_shares=800, cost_basis=17.0)],
            ),
            holding_assessments=[
                HoldingAssessment(
                    stock_code="002705.SZ",
                    stock_name="新宝股份",
                    shares=800,
                    available_shares=800,
                    cost_basis=17.0,
                    last_close_price=18.5,
                    market_value=14800.0,
                    unrealized_return_pct=0.0882,
                    portfolio_weight_pct=0.3442,
                    summary_action="hold_or_add",
                    recommendation="已有持仓，确认后再加。",
                    rationale="已有计划",
                )
            ],
            candidate_cards=[
                CandidateCard(
                    candidate_id="c1",
                    stock_code="603986.SH",
                    trade_date="2026-05-06",
                    candidate_source="module_event_resonance",
                    candidate_score=0.8,
                    technical_state="event_breakout_watch",
                    diagnostic_summary="规则诊断A",
                ),
                CandidateCard(
                    candidate_id="c2",
                    stock_code="002705.SZ",
                    trade_date="2026-05-06",
                    candidate_source="full_resonance",
                    candidate_score=0.82,
                    technical_state="event_theme_resonance",
                    diagnostic_summary="规则诊断B",
                    llm_diagnostic_summary="LLM诊断B",
                ),
            ],
            trade_plans=[
                TradePlanCard(
                    plan_id="p1",
                    trade_date="2026-05-06",
                    stock_code="002705.SZ",
                    action="buy_pilot",
                    priority_rank=1,
                    rationale="持仓内计划",
                    entry_condition="确认后处理",
                ),
                TradePlanCard(
                    plan_id="p2",
                    trade_date="2026-05-06",
                    stock_code="603986.SH",
                    action="buy_pilot",
                    priority_rank=2,
                    rationale="新开计划",
                    entry_condition="观察开盘强度",
                    position_size_rule="先试仓一手",
                    supporting_cards=["股份回购进展：预案"],
                ),
            ],
            theme_cards=[
                ThemeCard(
                    theme_id="t1",
                    theme_name="算力基础设施",
                    trigger_type="policy",
                    trigger_time="2026-05-06 09:00:00",
                    priority_industries=["算力", "液冷"],
                    priority_stocks=["603986.SH"],
                    continuation_guess="multi_day",
                )
            ],
        )

        self.assertEqual(len(payload["holding_assessments"]), 1)
        self.assertEqual(len(payload["theme_board"]), 1)
        self.assertIn("action_summary", payload)
        self.assertEqual(payload["action_summary"]["focus_theme"], "算力基础设施")
        grouped_codes = {
            item["stock_code"]
            for key in ("leader_candidates", "core_candidates", "follower_candidates", "avoid_candidates")
            for item in payload["theme_board"][0].get(key, [])
        }
        self.assertIn("603986.SH", grouped_codes)
        self.assertIn("strength_label", payload["theme_board"][0])
        self.assertIn("direct_beneficiaries", payload["theme_board"][0])
        self.assertEqual(len(payload["top_new_ideas"]), 1)
        self.assertEqual(payload["top_new_ideas"][0]["stock_code"], "603986.SH")
        self.assertIn("theme_context", payload["top_new_ideas"][0])
        self.assertIn("beneficiary_note", payload["top_new_ideas"][0])
        self.assertEqual(payload["watchlist"], [])

    def test_render_preopen_summary_markdown(self) -> None:
        payload = {
            "trade_date": "2026-05-06",
            "data_basis": {"market_close_date": "2026-05-06", "description": "test"},
            "market_view": {"risk_mode": "risk_on", "market_bias": "bullish", "style_lead": "large_cap_lead", "breadth_strength": "strong", "theme_concentration": "high", "opening_risk_note": "watch breadth"},
            "account_view": {"capital_total": 43000.0, "single_trade_capital_max": 43000.0, "max_new_positions_per_day": 2, "max_holdings": 5},
            "holding_assessments": [],
            "top_new_ideas": [{"priority_rank": 1, "stock_code": "603986.SH", "action": "buy_pilot", "rationale": "理由", "candidate_diagnosis": "诊断", "entry_condition": "条件", "position_size_rule": "规则", "max_position_pct": 0.5, "supporting_cards": ["支撑1"]}],
            "watchlist": [],
            "focus_themes": [],
        }
        markdown = render_preopen_summary_markdown(payload)
        self.assertIn("盘前摘要 - 2026-05-06", markdown)
        self.assertIn("## 今日结论", markdown)
        self.assertIn("## 今日可试仓", markdown)
        self.assertIn("603986.SH", markdown)

    def test_render_preopen_summary_includes_theme_board(self) -> None:
        payload = {
            "trade_date": "2026-05-06",
            "data_basis": {"market_close_date": "2026-05-06", "description": "test"},
            "market_view": {"risk_mode": "risk_on", "market_bias": "bullish", "style_lead": "large_cap_lead", "breadth_strength": "strong", "theme_concentration": "high", "opening_risk_note": "watch breadth"},
            "account_view": {"capital_total": 43000.0, "single_trade_capital_max": 43000.0, "max_new_positions_per_day": 2, "max_holdings": 5},
            "holding_assessments": [],
            "theme_board": [{"theme_name": "算力基础设施", "conviction": "high", "continuation_guess": "multi_day", "priority_industries": ["算力"], "leader_candidates": [{"stock_code": "603986.SH", "plan_action": "buy_pilot", "candidate_score": 0.8}], "secondary_candidates": [], "avoid_candidates": []}],
            "top_new_ideas": [],
            "watchlist": [],
            "focus_themes": [],
        }
        markdown = render_preopen_summary_markdown(payload)
        self.assertIn("## 可交易主线板", markdown)
        self.assertIn("算力基础设施", markdown)
        self.assertIn("603986.SH", markdown)


    def test_fallback_theme_board_groups_similar_supporting_events(self) -> None:
        payload = build_preopen_summary_payload(
            trade_date="2026-05-06",
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
            ),
            portfolio=PortfolioSnapshot(),
            holding_assessments=[],
            candidate_cards=[
                CandidateCard(
                    candidate_id="c1",
                    stock_code="000425.SZ",
                    trade_date="2026-05-06",
                    candidate_source="event_direct",
                    candidate_score=0.61,
                    information_edge_score=0.41,
                ),
                CandidateCard(
                    candidate_id="c2",
                    stock_code="002120.SZ",
                    trade_date="2026-05-06",
                    candidate_source="event_direct",
                    candidate_score=0.61,
                    information_edge_score=0.41,
                ),
            ],
            trade_plans=[
                TradePlanCard(
                    plan_id="p1",
                    trade_date="2026-05-06",
                    stock_code="000425.SZ",
                    action="buy_pilot",
                    priority_rank=1,
                    rationale="x",
                    entry_condition="x",
                    supporting_cards=["股份回购进展：预案"],
                ),
                TradePlanCard(
                    plan_id="p2",
                    trade_date="2026-05-06",
                    stock_code="002120.SZ",
                    action="watch_only",
                    priority_rank=2,
                    rationale="x",
                    entry_condition="x",
                    supporting_cards=["重要股东增持"],
                ),
            ],
            theme_cards=[],
        )
        self.assertEqual(payload["theme_board"][0]["theme_name"], "股东支持与回购")
        self.assertIn("股份回购进展：预案", payload["theme_board"][0]["trigger_labels"])

    def test_direct_theme_board_collapses_shareholder_support_entries(self) -> None:
        collapsed = _collapse_theme_board(
            [
            {
                "theme_name": "股份回购进展：预案",
                "continuation_guess": "event_follow_up",
                "conviction": "medium",
                "priority_industries": [],
                "leader_candidates": [{"stock_code": "000425.SZ", "plan_action": "buy_pilot", "candidate_score": 0.61, "information_edge_score": 0.41, "tradeability_verdict": "tradable"}],
                "secondary_candidates": [],
                "avoid_candidates": [],
            },
            {
                "theme_name": "重要股东增持",
                "continuation_guess": "event_follow_up",
                "conviction": "medium",
                "priority_industries": [],
                "leader_candidates": [],
                "secondary_candidates": [{"stock_code": "002120.SZ", "plan_action": "watch_only", "candidate_score": 0.61, "information_edge_score": 0.39, "tradeability_verdict": "tradable"}],
                "avoid_candidates": [],
            },
            ]
        )
        self.assertEqual(len(collapsed), 1)
        self.assertEqual(collapsed[0]["theme_name"], "股东支持与回购")
        self.assertIn("股份回购进展：预案", collapsed[0]["trigger_labels"])
        self.assertIn("重要股东增持", collapsed[0]["trigger_labels"])
        self.assertIn("core_candidates", collapsed[0])
        self.assertIn("follower_candidates", collapsed[0])

    def test_render_preopen_summary_includes_theme_roles(self) -> None:
        payload = {
            "trade_date": "2026-05-06",
            "data_basis": {"market_close_date": "2026-05-06", "description": "test"},
            "market_view": {"risk_mode": "risk_on", "market_bias": "bullish", "style_lead": "large_cap_lead", "breadth_strength": "strong", "theme_concentration": "high", "opening_risk_note": "watch breadth"},
            "account_view": {"capital_total": 43000.0, "single_trade_capital_max": 43000.0, "max_new_positions_per_day": 2, "max_holdings": 5},
            "holding_assessments": [],
            "theme_board": [
                {
                    "theme_name": "股东支持与回购",
                    "conviction": "medium",
                    "strength_label": "tradable_branch",
                    "strength_note": "具备交易性，但更适合控制节奏，优先做确认后的前排",
                    "continuation_guess": "event_follow_up",
                    "priority_industries": [],
                    "trigger_labels": ["股份回购进展：预案"],
                    "direct_beneficiaries": ["000425.SZ", "002705.SZ"],
                    "indirect_beneficiaries": ["600388.SH"],
                    "leader_candidates": [{"stock_code": "000425.SZ", "plan_action": "buy_pilot", "candidate_score": 0.61, "role_note": "事件确认较强，可作为前排观察或试仓"}],
                    "core_candidates": [{"stock_code": "002705.SZ", "plan_action": "watch_only", "candidate_score": 0.59, "role_note": "有主线共振，可作为中军或次前排跟踪"}],
                    "follower_candidates": [{"stock_code": "600388.SH", "plan_action": "watch_only", "candidate_score": 0.57, "role_note": "更适合作为跟风观察，不宜抢先出手"}],
                    "secondary_candidates": [],
                    "avoid_candidates": [{"stock_code": "603986.SH", "tradeability_verdict": "too_concentrated", "role_note": "账户约束不匹配"}],
                }
            ],
            "top_new_ideas": [],
            "watchlist": [],
            "focus_themes": [],
        }
        markdown = render_preopen_summary_markdown(payload)
        self.assertIn("- 中军/次前排：", markdown)
        self.assertIn("- 跟风观察：", markdown)
        self.assertIn("账户约束不匹配", markdown)
        self.assertIn("主线强度", markdown)
        self.assertIn("直接受益", markdown)


if __name__ == "__main__":
    unittest.main()
