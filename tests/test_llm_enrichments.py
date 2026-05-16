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

import trading_system.cli.apply_llm_enrichments as apply_cli
import trading_system.integrations.llm_enrichments as enrichment_mod


class LLMEnrichmentApplyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.original_processed_dir = apply_cli.PROCESSED_DATA_DIR
        self.original_workspace_dir = enrichment_mod.WORKSPACE_DIR
        self.original_outputs_dir = apply_cli.OUTPUTS_DIR

    def tearDown(self) -> None:
        apply_cli.PROCESSED_DATA_DIR = self.original_processed_dir
        enrichment_mod.WORKSPACE_DIR = self.original_workspace_dir
        apply_cli.OUTPUTS_DIR = self.original_outputs_dir

    def test_apply_llm_enrichments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            processed = root / "processed"
            workspace = root / "workspace"
            outputs = root / "outputs"
            for name in ("events", "themes", "capital", "candidates", "trade_plans", "memory", "llm"):
                (processed / name).mkdir(parents=True, exist_ok=True)
            (workspace / "llm_responses").mkdir(parents=True, exist_ok=True)
            outputs.mkdir(parents=True, exist_ok=True)

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
                            "supporting_cards": ["e1"]
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (processed / "events" / "event_cards_2026-05-06.json").write_text(
                json.dumps(
                    [
                        {
                            "event_id": "e1",
                            "event_type": "major_contract",
                            "event_title": "contract win",
                            "stock_codes": ["000001.SZ"],
                            "industry_tags": [],
                            "publish_time": "",
                            "bullish_bearish": "bullish",
                            "impact_horizon": "",
                            "event_strength": 0.7,
                            "novelty_score": 0.6,
                            "is_official": True,
                            "core_claim": "new order",
                            "risk_flags": [],
                            "source_refs": [],
                            "llm_summary": ""
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
                            "supporting_cards": []
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (processed / "memory" / "review_memory_entries.json").write_text(json.dumps([], ensure_ascii=False, indent=2), encoding="utf-8")
            (processed / "themes" / "theme_cards_2026-05-06.json").write_text(json.dumps([], ensure_ascii=False, indent=2), encoding="utf-8")
            (processed / "capital" / "capital_behavior_cards_2026-05-06.json").write_text(json.dumps([], ensure_ascii=False, indent=2), encoding="utf-8")

            (workspace / "llm_responses" / "llm_enrichments_2026-05-06.json").write_text(
                json.dumps(
                    [
                        {
                            "trade_date": "2026-05-06",
                            "packet_id": "packet_e1",
                            "agent_id": "event_deepening_agent",
                            "target_object_type": "event_card",
                            "target_object_id": "e1",
                            "contract_type": "event_card_enrichment",
                            "summary": "real catalyst but needs sector confirmation",
                            "confidence": 0.75,
                            "structured_payload": {
                                "sentiment_verdict": "constructive",
                                "beneficiary_stocks": ["000001.SZ"],
                                "risk_notes": ["confirm sector breadth"]
                            },
                            "citations": ["official_announcement"],
                            "warnings": []
                        },
                        {
                            "trade_date": "2026-05-06",
                            "packet_id": "packet_c1",
                            "agent_id": "candidate_diagnosis_agent",
                            "target_object_type": "candidate_card",
                            "target_object_id": "cand1",
                            "contract_type": "candidate_card_diagnosis",
                            "summary": "This candidate is technically interesting but should be watched for confirmation first.",
                            "confidence": 0.69,
                            "structured_payload": {
                                "tradeability_verdict": "watch_only",
                                "focus_points": ["opening strength", "event follow-through"],
                                "risk_notes": ["confirmation still needed"]
                            },
                            "citations": ["candidate_card"],
                            "warnings": []
                        },
                        {
                            "trade_date": "2026-05-06",
                            "packet_id": "packet_p1",
                            "agent_id": "trade_plan_refine_agent",
                            "target_object_type": "trade_plan_card",
                            "target_object_id": "p1",
                            "contract_type": "trade_plan_refinement",
                            "summary": "Pilot only. Add only after theme follow-through.",
                            "confidence": 0.71,
                            "structured_payload": {
                                "execution_watchpoints": ["opening breadth", "leader follow-through"]
                            },
                            "citations": [],
                            "warnings": []
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            apply_cli.PROCESSED_DATA_DIR = processed
            enrichment_mod.WORKSPACE_DIR = workspace
            apply_cli.OUTPUTS_DIR = outputs

            json_path, md_path = apply_cli.apply_llm_enrichments("2026-05-06")
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())

            event_payload = json.loads((processed / "events" / "event_cards_2026-05-06.json").read_text(encoding="utf-8"))
            self.assertEqual(event_payload[0]["llm_sentiment_verdict"], "constructive")
            self.assertIn("000001.SZ", event_payload[0]["llm_beneficiary_stocks"])

            candidate_payload = json.loads((processed / "candidates" / "candidate_cards_2026-05-06.json").read_text(encoding="utf-8"))
            self.assertIn("technically interesting", candidate_payload[0]["llm_diagnostic_summary"])
            self.assertEqual(candidate_payload[0]["llm_tradeability_verdict"], "watch_only")

            plan_payload = json.loads((processed / "trade_plans" / "trade_plan_cards_2026-05-06.json").read_text(encoding="utf-8"))
            self.assertIn("Pilot only", plan_payload[0]["llm_refined_plan"])
            self.assertIn("leader follow-through", plan_payload[0]["llm_execution_watchpoints"])

    def test_apply_llm_enrichments_to_output_trade_plan_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            processed = root / "processed"
            workspace = root / "workspace"
            outputs = root / "outputs"
            for name in ("events", "themes", "capital", "memory", "llm"):
                (processed / name).mkdir(parents=True, exist_ok=True)
            (outputs / "trade_plans").mkdir(parents=True, exist_ok=True)
            (workspace / "llm_responses").mkdir(parents=True, exist_ok=True)

            (outputs / "trade_plans" / "trade_plan_cards_2026-05-06.json").write_text(
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
                            "supporting_cards": []
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (processed / "memory" / "review_memory_entries.json").write_text(json.dumps([], ensure_ascii=False, indent=2), encoding="utf-8")
            (processed / "events" / "event_cards_2026-05-06.json").write_text(json.dumps([], ensure_ascii=False, indent=2), encoding="utf-8")
            (processed / "themes" / "theme_cards_2026-05-06.json").write_text(json.dumps([], ensure_ascii=False, indent=2), encoding="utf-8")
            (processed / "capital" / "capital_behavior_cards_2026-05-06.json").write_text(json.dumps([], ensure_ascii=False, indent=2), encoding="utf-8")

            (workspace / "llm_responses" / "llm_enrichments_2026-05-06.json").write_text(
                json.dumps(
                    [
                        {
                            "trade_date": "2026-05-06",
                            "packet_id": "packet_p1",
                            "agent_id": "trade_plan_refine_agent",
                            "target_object_type": "trade_plan_card",
                            "target_object_id": "p1",
                            "contract_type": "trade_plan_refinement",
                            "summary": "Use a small pilot only.",
                            "confidence": 0.7,
                            "structured_payload": {
                                "execution_watchpoints": ["watch opening breadth"]
                            },
                            "citations": [],
                            "warnings": []
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            apply_cli.PROCESSED_DATA_DIR = processed
            enrichment_mod.WORKSPACE_DIR = workspace
            apply_cli.OUTPUTS_DIR = outputs

            json_path, md_path = apply_cli.apply_llm_enrichments("2026-05-06")
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())

            plan_payload = json.loads((outputs / "trade_plans" / "trade_plan_cards_2026-05-06.json").read_text(encoding="utf-8"))
            self.assertIn("Use a small pilot only.", plan_payload[0]["llm_refined_plan"])
            self.assertIn("watch opening breadth", plan_payload[0]["llm_execution_watchpoints"])


if __name__ == "__main__":
    unittest.main()
