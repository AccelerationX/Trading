from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_system.cli.execute_llm_runtime import _apply_route_limit
from trading_system.integrations.llm_provider_registry import LLMExecutionRoute


class ExecuteLLMRuntimeTest(unittest.TestCase):
    def test_limit_caps_each_provider_independently(self) -> None:
        routes = [
            LLMExecutionRoute(
                packet_id="local1",
                agent_id="event_deepening_agent",
                provider_id="ollama_local_primary",
                provider_type="ollama_chat",
                model="gpt-oss:20b",
                status="ready",
                api_key_env="",
                api_key_present=False,
                api_base_env="OLLAMA_BASE_URL",
                api_base_present=False,
                api_base_default="http://127.0.0.1:11434",
                timeout_seconds=120,
                max_retries=1,
                output_mode="json_contract",
                notes=(),
            ),
            LLMExecutionRoute(
                packet_id="local2",
                agent_id="theme_deepening_agent",
                provider_id="ollama_local_primary",
                provider_type="ollama_chat",
                model="gpt-oss:20b",
                status="ready",
                api_key_env="",
                api_key_present=False,
                api_base_env="OLLAMA_BASE_URL",
                api_base_present=False,
                api_base_default="http://127.0.0.1:11434",
                timeout_seconds=120,
                max_retries=1,
                output_mode="json_contract",
                notes=(),
            ),
            LLMExecutionRoute(
                packet_id="remote1",
                agent_id="trade_plan_refine_agent",
                provider_id="moonshot_kimi_primary",
                provider_type="openai_compatible",
                model="kimi-k2.6",
                status="ready",
                api_key_env="MOONSHOT_API_KEY",
                api_key_present=True,
                api_base_env="MOONSHOT_BASE_URL",
                api_base_present=False,
                api_base_default="https://api.moonshot.cn/v1",
                timeout_seconds=90,
                max_retries=2,
                output_mode="json_contract",
                notes=(),
            ),
            LLMExecutionRoute(
                packet_id="remote2",
                agent_id="trade_plan_refine_agent",
                provider_id="moonshot_kimi_primary",
                provider_type="openai_compatible",
                model="kimi-k2.6",
                status="ready",
                api_key_env="MOONSHOT_API_KEY",
                api_key_present=True,
                api_base_env="MOONSHOT_BASE_URL",
                api_base_present=False,
                api_base_default="https://api.moonshot.cn/v1",
                timeout_seconds=90,
                max_retries=2,
                output_mode="json_contract",
                notes=(),
            ),
        ]
        limited = _apply_route_limit(routes, limit=1, include_remote_providers=True)
        self.assertEqual(len(limited), 2)
        self.assertEqual(sum(1 for route in limited if route.provider_type == "ollama_chat"), 1)
        self.assertEqual(sum(1 for route in limited if route.provider_type == "openai_compatible"), 1)


if __name__ == "__main__":
    unittest.main()
