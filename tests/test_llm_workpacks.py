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

import trading_system.cli.build_llm_workpacks as workpack_cli
import trading_system.context.text_signal_support as text_watch_support
from trading_system.reporting.llm_workpack_reports import render_llm_workpacks_markdown


class LLMWorkpacksTest(unittest.TestCase):
    def setUp(self) -> None:
        self.original_processed_dir = workpack_cli.PROCESSED_DATA_DIR
        self.original_outputs_dir = text_watch_support.OUTPUTS_DIR

    def tearDown(self) -> None:
        workpack_cli.PROCESSED_DATA_DIR = self.original_processed_dir
        text_watch_support.OUTPUTS_DIR = self.original_outputs_dir

    def test_build_llm_workpacks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            processed = Path(tmp_dir)
            for name in ("events", "themes", "capital", "candidates", "trade_plans", "context", "memory", "account"):
                (processed / name).mkdir(parents=True, exist_ok=True)
            analysis_dir = processed / "outputs" / "analysis"
            analysis_dir.mkdir(parents=True, exist_ok=True)

            (processed / "events" / "event_cards_2026-05-06.json").write_text(
                json.dumps(
                    [
                        {
                            "event_id": "e1",
                            "event_type": "major_contract",
                            "event_title": "contract win",
                            "stock_codes": ["000001.SZ"],
                            "industry_tags": ["ai"],
                            "publish_time": "2026-05-06 20:00:00",
                            "bullish_bearish": "bullish",
                            "impact_horizon": "multi_day",
                            "event_strength": 0.7,
                            "novelty_score": 0.6,
                            "is_official": True,
                            "core_claim": "new order",
                            "risk_flags": ["needs_llm_review"],
                            "source_refs": ["src1"],
                            "llm_summary": ""
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (processed / "themes" / "theme_cards_2026-05-06.json").write_text(
                json.dumps(
                    [
                        {
                            "theme_id": "t1",
                            "theme_name": "commercial aerospace",
                            "trigger_type": "policy:ministry",
                            "trigger_time": "2026-05-06 18:00:00",
                            "beneficiary_chain": [],
                            "priority_industries": [],
                            "priority_stocks": [],
                            "continuation_guess": "needs_review",
                            "market_confirmation_needed": [],
                            "contra_risks": [],
                            "source_refs": ["src2"],
                            "llm_summary": ""
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (processed / "capital" / "capital_behavior_cards_2026-05-06.json").write_text(
                json.dumps(
                    [
                        {
                            "card_id": "c1",
                            "stock_code": "000001.SZ",
                            "trade_date": "2026-05-06",
                            "capital_signal_type": "dragon_tiger_board",
                            "participation_strength": "high",
                            "consistency_score": 0.8,
                            "suspected_style": "institutional_active",
                            "support_or_distribution": "support",
                            "warning_flags": [],
                            "source_refs": ["src3"],
                            "llm_summary": ""
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (processed / "candidates" / "candidate_cards_2026-05-06.json").write_text(
                json.dumps(
                    [
                        {
                            "candidate_id": "cand1",
                            "stock_code": "000001.SZ",
                            "trade_date": "2026-05-06",
                            "candidate_source": "event_direct",
                            "candidate_score": 0.7,
                            "technical_state": "event_breakout_watch",
                            "event_support_score": 0.7,
                            "theme_alignment_score": 0.3,
                            "capital_confirmation_score": 0.8,
                            "market_fit_score": 0.7,
                            "account_fit_score": 0.7,
                            "last_close_price": 10.0,
                            "estimated_min_lot_cost": 1000.0,
                            "account_tradeability_score": 0.8,
                            "tradeability_verdict": "tradable",
                            "diagnostic_summary": "rule diagnosis",
                            "diagnostic_risk_notes": [],
                            "active_module_ids": [],
                            "disqualify_flags": [],
                            "supporting_cards": ["e1"],
                            "candidate_rationale": "ok"
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (processed / "trade_plans" / "trade_plan_cards_2026-05-06.json").write_text(
                json.dumps(
                    [
                        {
                            "plan_id": "p1",
                            "trade_date": "2026-05-06",
                            "stock_code": "000001.SZ",
                            "action": "buy_pilot",
                            "priority_rank": 1,
                            "rationale": "ok",
                            "entry_condition": "confirm",
                            "entry_zone": "",
                            "position_size_rule": "pilot",
                            "max_position_pct": 0.1,
                            "add_reduce_rule": "",
                            "invalidation_rule": "",
                            "exit_rule_hint": "",
                            "holding_horizon": "1_to_3_days",
                            "risk_notes": [],
                            "supporting_cards": ["e1"]
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (processed / "context" / "market_regime_2026-05-06.json").write_text(
                json.dumps(
                    {
                        "snapshot_id": "s1",
                        "trade_date": "2026-05-06",
                        "market_bias": "bullish",
                        "risk_mode": "risk_on",
                        "breadth_strength": "strong",
                        "limit_up_temperature": "warm",
                        "turnover_regime": "high",
                        "style_lead": "small_cap_lead",
                        "theme_concentration": "high",
                        "opening_risk_note": "",
                        "confidence": 0.7,
                        "supporting_evidence": []
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (processed / "memory" / "review_memory_entries.json").write_text(
                json.dumps(
                    [
                        {
                            "memory_id": "m1",
                            "trade_date": "2026-05-05",
                            "stock_code": "000001.SZ",
                            "action": "buy",
                            "outcome_tag": "positive",
                            "setup_tags": ["event_driven"],
                            "lesson_summary": "wait for pullback",
                            "actionable_rule": "wait for pullback",
                            "confidence": 0.8,
                            "retrieval_keys": ["000001.SZ"],
                            "source_refs": ["review1.md"]
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (processed / "account" / "active_account_constraints.json").write_text(
                json.dumps(
                    {
                        "profile_name": "unit_test",
                        "capital_total": 100000.0,
                        "capital_liquid_ratio_min": 0.1,
                        "single_position_max_pct": 0.2,
                        "single_trade_capital_max": 20000.0,
                        "max_holdings": 5,
                        "max_new_positions_per_day": 2,
                        "max_portfolio_turnover_per_day": 0.5,
                        "daily_drawdown_alert_pct": 0.02,
                        "portfolio_drawdown_alert_pct": 0.08,
                        "preferred_holding_horizon_days": 3,
                        "execution_mode": "manual",
                        "can_watch_intraday": True,
                        "preopen_available": True,
                        "midday_available": True,
                        "close_available": True,
                        "avoid_chasing_limit_up": True,
                        "avoid_low_liquidity": True,
                        "notes": "test account"
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (analysis_dir / "text_signal_watch_2026-05-06.json").write_text(
                json.dumps(
                    [
                        {
                            "source_id": "exchange_filings",
                            "priority_score": 108,
                            "publish_time": "2026-05-06 20:00:00",
                            "title": "000001.SZ 回购进展公告",
                            "stock_code": "000001.SZ",
                            "related_industries": ["ai"],
                            "related_stocks": ["000001.SZ"],
                            "source_url": "https://example.com/1",
                            "summary_text": "回购进展",
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            workpack_cli.PROCESSED_DATA_DIR = processed
            text_watch_support.OUTPUTS_DIR = processed / "outputs"
            packets = workpack_cli.build_llm_workpacks("2026-05-06")
            self.assertGreaterEqual(len(packets), 5)
            self.assertTrue(any("text_watch_focus=" in note for packet in packets for note in packet.notes))
            self.assertTrue(any(packet.agent_id == "candidate_diagnosis_agent" for packet in packets))
            self.assertTrue(any(packet.agent_id == "trade_plan_refine_agent" for packet in packets))
            trade_plan_packet = next(packet for packet in packets if packet.agent_id == "trade_plan_refine_agent")
            self.assertIn("candidate", trade_plan_packet.context_payload)
            self.assertIn("market_snapshot", trade_plan_packet.context_payload)
            self.assertIn("account_constraints", trade_plan_packet.context_payload)
            self.assertIn("supporting_events", trade_plan_packet.context_payload)
            self.assertIn("text_watch_records", trade_plan_packet.context_payload)
            candidate_packet = next(packet for packet in packets if packet.agent_id == "candidate_diagnosis_agent")
            self.assertEqual(candidate_packet.target_object_type, "candidate_card")
            self.assertIn("candidate", candidate_packet.context_payload)
            markdown = render_llm_workpacks_markdown("2026-05-06", packets)
            self.assertIn("LLM Workpacks - 2026-05-06", markdown)
            self.assertIn("event_deepening_agent", markdown)
            self.assertIn("packet_family", markdown)
            stable_packets = workpack_cli.build_llm_workpacks("2026-05-06", mode="stable")
            self.assertLess(len(stable_packets), len(packets))
            self.assertFalse(any(packet.packet_family == "review_memory" for packet in stable_packets))
            self.assertTrue(all(packet.packet_id.startswith("2026-05-06_") for packet in stable_packets))


if __name__ == "__main__":
    unittest.main()
