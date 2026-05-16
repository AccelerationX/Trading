from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from trading_system.config.paths import PROCESSED_DATA_DIR, WORKSPACE_DIR


@dataclass(slots=True)
class LLMEnrichmentResult:
    trade_date: str
    packet_id: str
    agent_id: str
    target_object_type: str
    target_object_id: str
    contract_type: str
    summary: str = ""
    confidence: float | None = None
    structured_payload: dict = field(default_factory=dict)
    citations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def llm_processed_dir() -> Path:
    directory = PROCESSED_DATA_DIR / "llm"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def llm_response_workspace_dir() -> Path:
    directory = WORKSPACE_DIR / "llm_responses"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return json.loads(path.read_text(encoding="utf-8-sig"))


def load_llm_enrichment_results(trade_date: str, path: Path | None = None) -> list[LLMEnrichmentResult]:
    source_path = path or (llm_response_workspace_dir() / f"llm_enrichments_{trade_date}.json")
    payload = list(_load_json(source_path))
    return [LLMEnrichmentResult(**item) for item in payload]


def save_llm_enrichment_results(trade_date: str, results: list[LLMEnrichmentResult], path: Path | None = None) -> Path:
    output_path = path or (llm_processed_dir() / f"llm_enrichments_{trade_date}.json")
    output_path.write_text(json.dumps([asdict(item) for item in results], ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
