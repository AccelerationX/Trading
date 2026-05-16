from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_system.integrations.llm_contracts import LLMWorkPacket
from trading_system.integrations.llm_provider_registry import LLMProviderConfig, load_llm_provider_registry, resolve_llm_execution_routes


class LLMProviderRegistryTest(unittest.TestCase):
    def test_load_provider_registry(self) -> None:
        providers = load_llm_provider_registry()
        provider_ids = [provider.provider_id for provider in providers]
        self.assertGreaterEqual(len(providers), 2)
        self.assertEqual(providers[0].provider_id, "ollama_local_primary")
        self.assertIn("moonshot_kimi_primary", provider_ids)

    def test_resolve_routes_without_credentials(self) -> None:
        packets = [
            LLMWorkPacket(
                packet_id="p1",
                trade_date="2026-05-06",
                agent_id="trade_plan_refine_agent",
                task_id="trade_plan_drafting",
                priority="high",
                target_object_type="trade_plan_card",
                target_object_id="plan1",
                prompt_file="prompts/tasks/trade_plan_drafting.md",
                expected_output_contract="trade_plan_refinement",
            )
        ]
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "providers.json"
            path.write_text(
                """
{
  "providers": [
    {
      "provider_id": "openai_like",
      "enabled": true,
      "provider_type": "openai_compatible",
      "default_model": "gpt-test",
      "api_key_env": "OPENAI_API_KEY",
      "api_base_env": "OPENAI_BASE_URL",
      "api_base_default": "",
      "timeout_seconds": 60,
      "max_retries": 2,
      "supports_json_mode": true,
      "agent_overrides": [],
      "agent_allowlist": []
    }
  ]
}
                """.strip(),
                encoding="utf-8",
            )
            providers = load_llm_provider_registry(path)
        routes = resolve_llm_execution_routes(packets, providers, environ={})
        self.assertEqual(routes[0].status, "missing_credentials")
        self.assertEqual(routes[0].model, "gpt-test")

    def test_resolve_routes_with_credentials(self) -> None:
        packets = [
            LLMWorkPacket(
                packet_id="p1",
                trade_date="2026-05-06",
                agent_id="trade_plan_refine_agent",
                task_id="trade_plan_drafting",
                priority="high",
                target_object_type="trade_plan_card",
                target_object_id="plan1",
                prompt_file="prompts/tasks/trade_plan_drafting.md",
                expected_output_contract="trade_plan_refinement",
            )
        ]
        providers = [
            LLMProviderConfig(
                provider_id="openai_like",
                enabled=True,
                provider_type="openai_compatible",
                default_model="gpt-ready",
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
        routes = resolve_llm_execution_routes(
            packets,
            providers,
            environ={"OPENAI_API_KEY": "test-key", "OPENAI_BASE_URL": "https://example.com/v1"},
        )
        self.assertEqual(routes[0].status, "ready")
        self.assertEqual(routes[0].model, "gpt-ready")
        self.assertEqual(routes[0].provider_type, "openai_compatible")

    def test_manual_provider_route_is_ready_without_credentials(self) -> None:
        packets = [
            LLMWorkPacket(
                packet_id="p1",
                trade_date="2026-05-06",
                agent_id="trade_plan_refine_agent",
                task_id="trade_plan_drafting",
                priority="high",
                target_object_type="trade_plan_card",
                target_object_id="plan1",
                prompt_file="prompts/tasks/trade_plan_drafting.md",
                expected_output_contract="trade_plan_refinement",
            )
        ]
        providers = [
            LLMProviderConfig(
                provider_id="manual_workspace_stub",
                enabled=True,
                provider_type="manual_workspace",
                default_model="manual-review",
                api_key_env="",
                api_base_env="",
                api_base_default="",
                timeout_seconds=0,
                max_retries=0,
                supports_json_mode=False,
                agent_overrides=(),
                agent_allowlist=(),
            )
        ]
        routes = resolve_llm_execution_routes(packets, providers, environ={})
        self.assertEqual(routes[0].status, "ready")
        self.assertIn("no_api_key_required", routes[0].notes)

    def test_agent_allowlist_routes_packet_to_local_provider(self) -> None:
        packets = [
            LLMWorkPacket(
                packet_id="p1",
                trade_date="2026-05-06",
                agent_id="event_deepening_agent",
                task_id="event_analysis",
                priority="high",
                target_object_type="event_card",
                target_object_id="event1",
                prompt_file="prompts/tasks/event_analysis.md",
                expected_output_contract="event_card_enrichment",
            )
        ]
        providers = [
            LLMProviderConfig(
                provider_id="ollama_local_primary",
                enabled=True,
                provider_type="ollama_chat",
                default_model="gpt-oss:20b",
                api_key_env="",
                api_base_env="OLLAMA_BASE_URL",
                api_base_default="http://127.0.0.1:11434",
                timeout_seconds=120,
                max_retries=1,
                supports_json_mode=True,
                agent_overrides=(),
                agent_allowlist=("event_deepening_agent",),
            ),
            LLMProviderConfig(
                provider_id="moonshot_kimi_primary",
                enabled=True,
                provider_type="openai_compatible",
                default_model="kimi-k2.5",
                api_key_env="MOONSHOT_API_KEY",
                api_base_env="MOONSHOT_BASE_URL",
                api_base_default="https://api.moonshot.cn/v1",
                timeout_seconds=90,
                max_retries=2,
                supports_json_mode=True,
                agent_overrides=(),
                agent_allowlist=("trade_plan_refine_agent",),
            ),
        ]
        routes = resolve_llm_execution_routes(packets, providers, environ={})
        self.assertEqual(routes[0].provider_id, "ollama_local_primary")
        self.assertEqual(routes[0].provider_type, "ollama_chat")


if __name__ == "__main__":
    unittest.main()
