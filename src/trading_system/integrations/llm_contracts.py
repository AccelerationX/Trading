from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from trading_system.config.paths import CONFIGS_DIR, OUTPUTS_DIR


@dataclass(frozen=True)
class LLMTaskAgentSpec:
    agent_id: str
    task_id: str
    role: str
    trigger_object: str
    trigger_rule: str
    input_objects: tuple[str, ...]
    output_contract: str
    priority: str
    prompt_file: str


@dataclass(slots=True)
class LLMWorkPacket:
    packet_id: str
    trade_date: str
    agent_id: str
    task_id: str
    priority: str
    target_object_type: str
    target_object_id: str
    prompt_file: str
    sort_rank: int = 0
    input_refs: list[str] = field(default_factory=list)
    context_payload: dict = field(default_factory=dict)
    expected_output_contract: str = ""
    notes: list[str] = field(default_factory=list)


def load_llm_agent_registry(path: Path | None = None) -> list[LLMTaskAgentSpec]:
    config_path = path or (CONFIGS_DIR / "llm_agent_registry.json")
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    return [
        LLMTaskAgentSpec(
            agent_id=item["agent_id"],
            task_id=item["task_id"],
            role=item["role"],
            trigger_object=item["trigger_object"],
            trigger_rule=item["trigger_rule"],
            input_objects=tuple(item.get("input_objects", [])),
            output_contract=item["output_contract"],
            priority=item["priority"],
            prompt_file=item["prompt_file"],
        )
        for item in payload["agents"]
    ]


def llm_output_dir() -> Path:
    directory = OUTPUTS_DIR / "llm_workpacks"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def save_llm_workpacks(trade_date: str, packets: list[LLMWorkPacket], path: Path | None = None) -> Path:
    output_path = path or (llm_output_dir() / f"llm_workpacks_{trade_date}.json")
    output_path.write_text(json.dumps([asdict(packet) for packet in packets], ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
