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
import trading_system.cli.plan_llm_execution as plan_cli
from trading_system.integrations.llm_provider_registry import LLMProviderConfig
from trading_system.reporting.llm_execution_reports import render_llm_execution_plan_markdown


class LLMExecutionPlanTest(unittest.TestCase):
    def setUp(self) -> None:
        self.original_processed_dir = workpack_cli.PROCESSED_DATA_DIR

    def tearDown(self) -> None:
        workpack_cli.PROCESSED_DATA_DIR = self.original_processed_dir

    def test_render_execution_plan_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            processed = Path(tmp_dir)
            for name in ("events", "themes", "capital", "candidates", "trade_plans", "context", "memory"):
                (processed / name).mkdir(parents=True, exist_ok=True)

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
            for name, payload in (
                ("themes/theme_cards_2026-05-06.json", []),
                ("capital/capital_behavior_cards_2026-05-06.json", []),
                ("candidates/candidate_cards_2026-05-06.json", []),
                ("trade_plans/trade_plan_cards_2026-05-06.json", []),
                ("memory/review_memory_entries.json", []),
            ):
                (processed / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
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

            workpack_cli.PROCESSED_DATA_DIR = processed
            packets = workpack_cli.build_llm_workpacks("2026-05-06")
            providers = [
                LLMProviderConfig(
                    provider_id="openai_like",
                    enabled=True,
                    provider_type="openai_compatible",
                    default_model="gpt-test",
                    api_key_env="OPENAI_API_KEY",
                    api_base_env="OPENAI_BASE_URL",
                    api_base_default="",
                    timeout_seconds=60,
                    max_retries=2,
                    supports_json_mode=True,
                    agent_overrides=(),
                    agent_allowlist=(),
                )
            ]
            routes = plan_cli.resolve_llm_execution_routes(packets, providers, environ={})
            markdown = render_llm_execution_plan_markdown("2026-05-06", routes)
            self.assertIn("LLM Execution Plan - 2026-05-06", markdown)
            self.assertIn("missing_credentials", markdown)


if __name__ == "__main__":
    unittest.main()
