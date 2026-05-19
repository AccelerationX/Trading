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

from trading_system.integrations.llm_contracts import LLMWorkPacket
from trading_system.integrations.llm_provider_registry import LLMExecutionRoute
import trading_system.integrations.llm_runtime as runtime_mod
from trading_system.reporting.llm_runtime_reports import render_llm_runtime_markdown


class LLMRuntimeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.original_outputs_dir = runtime_mod.OUTPUTS_DIR
        self.original_workspace_dir = runtime_mod.WORKSPACE_DIR
        self.original_prompts_dir = runtime_mod.PROMPTS_DIR

    def tearDown(self) -> None:
        runtime_mod.OUTPUTS_DIR = self.original_outputs_dir
        runtime_mod.WORKSPACE_DIR = self.original_workspace_dir
        runtime_mod.PROMPTS_DIR = self.original_prompts_dir

    def test_manual_workspace_runtime_exports_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            runtime_mod.OUTPUTS_DIR = root / "outputs"
            runtime_mod.WORKSPACE_DIR = root / "workspace"
            runtime_mod.PROMPTS_DIR = root / "prompts"
            (runtime_mod.PROMPTS_DIR / "tasks").mkdir(parents=True, exist_ok=True)
            (runtime_mod.PROMPTS_DIR / "tasks" / "trade_plan_drafting.md").write_text("prompt body", encoding="utf-8")

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
            routes = [
                LLMExecutionRoute(
                    packet_id="p1",
                    agent_id="trade_plan_refine_agent",
                    provider_id="manual_workspace_stub",
                    provider_type="manual_workspace",
                    model="manual-review",
                    status="ready",
                    api_key_env="",
                    api_key_present=False,
                    api_base_env="",
                    api_base_present=False,
                    api_base_default="",
                    timeout_seconds=0,
                    max_retries=0,
                    output_mode="text_contract",
                    notes=("no_api_key_required",),
                )
            ]
            json_path, md_path, records = runtime_mod.execute_llm_runtime_with_inputs("2026-05-06", packets, routes)
            md_path.write_text(render_llm_runtime_markdown("2026-05-06", records), encoding="utf-8")

            self.assertTrue(Path(json_path).exists())
            self.assertTrue(Path(md_path).exists())
            batch_path = root / "workspace" / "llm_requests" / "llm_request_batch_2026-05-06_manual_workspace_stub.json"
            self.assertTrue(batch_path.exists())
            batch_payload = json.loads(batch_path.read_text(encoding="utf-8"))
            self.assertEqual(batch_payload[0]["prompt_text"], "prompt body")
            self.assertEqual(records[0].status, "exported_for_manual")

    def test_mock_contract_runtime_writes_enrichment_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            runtime_mod.OUTPUTS_DIR = root / "outputs"
            runtime_mod.WORKSPACE_DIR = root / "workspace"
            runtime_mod.PROMPTS_DIR = root / "prompts"
            (runtime_mod.PROMPTS_DIR / "tasks").mkdir(parents=True, exist_ok=True)
            (runtime_mod.PROMPTS_DIR / "tasks" / "event_analysis.md").write_text("event prompt", encoding="utf-8")

            packets = [
                LLMWorkPacket(
                    packet_id="e1_packet",
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
            ]
            routes = [
                LLMExecutionRoute(
                    packet_id="e1_packet",
                    agent_id="event_deepening_agent",
                    provider_id="mock_contract_stub",
                    provider_type="mock_contract",
                    model="mock-contract-v1",
                    status="ready",
                    api_key_env="",
                    api_key_present=False,
                    api_base_env="",
                    api_base_present=False,
                    api_base_default="",
                    timeout_seconds=0,
                    max_retries=0,
                    output_mode="json_contract",
                    notes=("no_api_key_required",),
                )
            ]
            json_path, md_path, records = runtime_mod.execute_llm_runtime_with_inputs("2026-05-06", packets, routes)
            md_path.write_text(render_llm_runtime_markdown("2026-05-06", records), encoding="utf-8")

            response_path = root / "workspace" / "llm_responses" / "llm_enrichments_2026-05-06_mock_contract_stub.json"
            self.assertTrue(response_path.exists())
            payload = json.loads(response_path.read_text(encoding="utf-8"))
            self.assertEqual(payload[0]["target_object_type"], "event_card")
            self.assertEqual(records[0].status, "completed")

    def test_ollama_runtime_writes_enrichment_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            runtime_mod.OUTPUTS_DIR = root / "outputs"
            runtime_mod.WORKSPACE_DIR = root / "workspace"
            runtime_mod.PROMPTS_DIR = root / "prompts"
            (runtime_mod.PROMPTS_DIR / "tasks").mkdir(parents=True, exist_ok=True)
            (runtime_mod.PROMPTS_DIR / "tasks" / "event_analysis.md").write_text("event prompt", encoding="utf-8")

            packets = [
                LLMWorkPacket(
                    packet_id="e2_packet",
                    trade_date="2026-05-06",
                    agent_id="event_deepening_agent",
                    task_id="event_analysis",
                    priority="high",
                    target_object_type="event_card",
                    target_object_id="e2",
                    prompt_file="prompts/tasks/event_analysis.md",
                    context_payload={"stock_codes": ["000625.SZ"]},
                    expected_output_contract="event_card_enrichment",
                )
            ]
            routes = [
                LLMExecutionRoute(
                    packet_id="e2_packet",
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
                    notes=("no_api_key_required",),
                )
            ]

            original_provider_map = runtime_mod._provider_map
            original_urlopen = runtime_mod.request.urlopen

            class FakeResponse:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self) -> bytes:
                    payload = {
                        "message": {
                            "content": json.dumps(
                                {
                                    "summary": "Local model review.",
                                    "confidence": 0.66,
                                    "structured_payload": {
                                        "sentiment_verdict": "constructive",
                                        "beneficiary_stocks": ["000625.SZ"],
                                        "risk_notes": ["watch follow-through"],
                                    },
                                    "citations": ["local_ollama"],
                                    "warnings": [],
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                    return json.dumps(payload, ensure_ascii=False).encode("utf-8")

            try:
                runtime_mod._provider_map = lambda: {
                    "ollama_local_primary": runtime_mod.LLMProviderConfig(
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
                    )
                }
                runtime_mod.request.urlopen = lambda req, timeout=0: FakeResponse()
                json_path, md_path, records = runtime_mod.execute_llm_runtime_with_inputs("2026-05-06", packets, routes)
            finally:
                runtime_mod._provider_map = original_provider_map
                runtime_mod.request.urlopen = original_urlopen

            self.assertTrue(Path(json_path).exists())
            self.assertTrue(Path(md_path).parent.exists())
            response_path = root / "workspace" / "llm_responses" / "llm_enrichments_2026-05-06_ollama_local_primary.json"
            self.assertTrue(response_path.exists())
            payload = json.loads(response_path.read_text(encoding="utf-8"))
            self.assertEqual(payload[0]["structured_payload"]["sentiment_verdict"], "constructive")
            self.assertEqual(records[0].status, "completed")

    def test_runtime_falls_back_to_secondary_provider_after_primary_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            runtime_mod.OUTPUTS_DIR = root / "outputs"
            runtime_mod.WORKSPACE_DIR = root / "workspace"
            runtime_mod.PROMPTS_DIR = root / "prompts"
            (runtime_mod.PROMPTS_DIR / "tasks").mkdir(parents=True, exist_ok=True)
            (runtime_mod.PROMPTS_DIR / "tasks" / "trade_plan_drafting.md").write_text("plan prompt", encoding="utf-8")

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
            routes = [
                LLMExecutionRoute(
                    packet_id="p1",
                    agent_id="trade_plan_refine_agent",
                    provider_id="moonshot_kimi_primary",
                    provider_type="openai_compatible",
                    model="kimi-k2.5",
                    status="ready",
                    api_key_env="MOONSHOT_API_KEY",
                    api_key_present=True,
                    api_base_env="MOONSHOT_BASE_URL",
                    api_base_present=True,
                    api_base_default="https://api.moonshot.cn/v1",
                    timeout_seconds=30,
                    max_retries=0,
                    output_mode="text_contract",
                    notes=(),
                )
            ]

            original_provider_map = runtime_mod._provider_map
            original_openai = runtime_mod._call_openai_compatible_provider
            original_ollama = runtime_mod._call_ollama_provider

            try:
                runtime_mod._provider_map = lambda: {
                    "moonshot_kimi_primary": runtime_mod.LLMProviderConfig(
                        provider_id="moonshot_kimi_primary",
                        enabled=True,
                        provider_type="openai_compatible",
                        default_model="kimi-k2.5",
                        api_key_env="MOONSHOT_API_KEY",
                        api_base_env="MOONSHOT_BASE_URL",
                        api_base_default="https://api.moonshot.cn/v1",
                        timeout_seconds=30,
                        max_retries=0,
                        supports_json_mode=False,
                        agent_overrides=(),
                        agent_allowlist=("trade_plan_refine_agent",),
                    ),
                    "ollama_local_primary": runtime_mod.LLMProviderConfig(
                        provider_id="ollama_local_primary",
                        enabled=True,
                        provider_type="ollama_chat",
                        default_model="gpt-oss:20b",
                        api_key_env="",
                        api_base_env="OLLAMA_BASE_URL",
                        api_base_default="http://127.0.0.1:11434",
                        timeout_seconds=30,
                        max_retries=0,
                        supports_json_mode=True,
                        agent_overrides=(),
                        agent_allowlist=("trade_plan_refine_agent",),
                    ),
                }
                runtime_mod._call_openai_compatible_provider = lambda *args, **kwargs: (_ for _ in ()).throw(
                    RuntimeError("remote_down")
                )
                runtime_mod._call_ollama_provider = lambda *args, **kwargs: runtime_mod.LLMEnrichmentResult(
                    trade_date="2026-05-06",
                    packet_id="p1",
                    agent_id="trade_plan_refine_agent",
                    target_object_type="trade_plan_card",
                    target_object_id="plan1",
                    contract_type="trade_plan_refinement",
                    summary="fallback local success",
                    confidence=0.7,
                    structured_payload={"execution_watchpoints": ["open strength"]},
                    citations=["fallback_local"],
                    warnings=[],
                )
                json_path, _, records = runtime_mod.execute_llm_runtime_with_inputs(
                    "2026-05-06",
                    packets,
                    routes,
                    allowed_provider_ids={"moonshot_kimi_primary", "ollama_local_primary"},
                )
            finally:
                runtime_mod._provider_map = original_provider_map
                runtime_mod._call_openai_compatible_provider = original_openai
                runtime_mod._call_ollama_provider = original_ollama

            self.assertTrue(Path(json_path).exists())
            self.assertEqual(records[0].status, "completed")
            self.assertEqual(records[0].provider_id, "ollama_local_primary")
            self.assertIn("fallback_from=moonshot_kimi_primary", records[0].notes)


if __name__ == "__main__":
    unittest.main()
