from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import trading_system.integrations.llm_runtime as runtime_mod
from trading_system.integrations.llm_contracts import LLMWorkPacket
from trading_system.integrations.llm_provider_registry import LLMExecutionRoute, LLMProviderConfig


class LLMOpenAICompatibleRuntimeTest(unittest.TestCase):
    def test_normalize_enrichment_result(self) -> None:
        packet = LLMWorkPacket(
            packet_id="p1",
            trade_date="2026-05-06",
            agent_id="trade_plan_refine_agent",
            task_id="trade_plan_drafting",
            priority="high",
            target_object_type="trade_plan_card",
            target_object_id="tp1",
            prompt_file="prompts/tasks/trade_plan_drafting.md",
            expected_output_contract="trade_plan_refinement",
        )
        result = runtime_mod._normalize_enrichment_result(
            packet,
            {
                "summary": "Keep pilot size small.",
                "confidence": 0.77,
                "structured_payload": {"execution_watchpoints": ["opening breadth"]},
                "citations": ["candidate_card"],
                "warnings": ["watch liquidity"],
            },
        )
        self.assertEqual(result.target_object_id, "tp1")
        self.assertIn("opening breadth", result.structured_payload["execution_watchpoints"])

    def test_openai_compatible_call_parses_json_response(self) -> None:
        packet = LLMWorkPacket(
            packet_id="p1",
            trade_date="2026-05-06",
            agent_id="event_deepening_agent",
            task_id="event_analysis",
            priority="high",
            target_object_type="event_card",
            target_object_id="e1",
            prompt_file="prompts/tasks/event_analysis.md",
            context_payload={"stock_codes": ["000001.SZ"]},
            expected_output_contract="event_card_enrichment",
        )
        route = LLMExecutionRoute(
            packet_id="p1",
            agent_id="event_deepening_agent",
            provider_id="moonshot_kimi_primary",
            provider_type="openai_compatible",
            model="kimi-k2-turbo-preview",
            status="ready",
            api_key_env="MOONSHOT_API_KEY",
            api_key_present=True,
            api_base_env="MOONSHOT_BASE_URL",
            api_base_present=False,
            api_base_default="https://api.moonshot.cn/v1",
            timeout_seconds=30,
            max_retries=1,
            output_mode="json_contract",
            notes=(),
        )
        provider = LLMProviderConfig(
            provider_id="moonshot_kimi_primary",
            enabled=True,
            provider_type="openai_compatible",
            default_model="kimi-k2-turbo-preview",
            api_key_env="MOONSHOT_API_KEY",
            api_base_env="MOONSHOT_BASE_URL",
            api_base_default="https://api.moonshot.cn/v1",
            timeout_seconds=30,
            max_retries=1,
            supports_json_mode=True,
            agent_overrides=(),
            agent_allowlist=(),
        )

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self) -> bytes:
                payload = {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "summary": "Real catalyst but needs confirmation.",
                                        "confidence": 0.72,
                                        "structured_payload": {
                                            "sentiment_verdict": "constructive",
                                            "beneficiary_stocks": ["000001.SZ"],
                                            "risk_notes": ["watch follow-through"],
                                        },
                                        "citations": ["official_announcement"],
                                        "warnings": [],
                                    },
                                    ensure_ascii=False,
                                )
                            }
                        }
                    ]
                }
                return json.dumps(payload, ensure_ascii=False).encode("utf-8")

        original_urlopen = runtime_mod.request.urlopen
        try:
            runtime_mod.request.urlopen = lambda req, timeout=0: FakeResponse()
            result = runtime_mod._call_openai_compatible_provider(
                packet,
                route,
                provider,
                {"MOONSHOT_API_KEY": "test-key"},
            )
        finally:
            runtime_mod.request.urlopen = original_urlopen

        self.assertEqual(result.target_object_type, "event_card")
        self.assertEqual(result.structured_payload["sentiment_verdict"], "constructive")

    def test_openai_compatible_call_falls_back_on_non_json(self) -> None:
        packet = LLMWorkPacket(
            packet_id="p2",
            trade_date="2026-05-06",
            agent_id="event_deepening_agent",
            task_id="event_analysis",
            priority="high",
            target_object_type="event_card",
            target_object_id="e2",
            prompt_file="prompts/tasks/event_analysis.md",
            context_payload={"stock_codes": ["000002.SZ"]},
            expected_output_contract="event_card_enrichment",
        )
        route = LLMExecutionRoute(
            packet_id="p2",
            agent_id="event_deepening_agent",
            provider_id="moonshot_kimi_primary",
            provider_type="openai_compatible",
            model="kimi-k2.5",
            status="ready",
            api_key_env="MOONSHOT_API_KEY",
            api_key_present=True,
            api_base_env="MOONSHOT_BASE_URL",
            api_base_present=False,
            api_base_default="https://api.moonshot.cn/v1",
            timeout_seconds=30,
            max_retries=1,
            output_mode="json_contract",
            notes=(),
        )
        provider = LLMProviderConfig(
            provider_id="moonshot_kimi_primary",
            enabled=True,
            provider_type="openai_compatible",
            default_model="kimi-k2.5",
            api_key_env="MOONSHOT_API_KEY",
            api_base_env="MOONSHOT_BASE_URL",
            api_base_default="https://api.moonshot.cn/v1",
            timeout_seconds=30,
            max_retries=1,
            supports_json_mode=True,
            agent_overrides=(),
            agent_allowlist=(),
        )

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self) -> bytes:
                payload = {
                    "choices": [
                        {
                            "message": {
                                "content": "这是一条普通文本，不是 JSON。"
                            }
                        }
                    ]
                }
                return json.dumps(payload, ensure_ascii=False).encode("utf-8")

        original_urlopen = runtime_mod.request.urlopen
        try:
            runtime_mod.request.urlopen = lambda req, timeout=0: FakeResponse()
            result = runtime_mod._call_openai_compatible_provider(
                packet,
                route,
                provider,
                {"MOONSHOT_API_KEY": "test-key"},
            )
        finally:
            runtime_mod.request.urlopen = original_urlopen

        self.assertEqual(result.summary, "这是一条普通文本，不是 JSON。")
        self.assertIn("non_json_response_fallback", result.warnings)


if __name__ == "__main__":
    unittest.main()
