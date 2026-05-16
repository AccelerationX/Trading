from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from trading_system.config.paths import CONFIGS_DIR


class SourceTier(str, Enum):
    A = "A"
    B = "B"
    C = "C"


class TrustLevel(str, Enum):
    S = "S"
    A = "A"
    B = "B"
    C = "C"


class StructureLevel(str, Enum):
    STRUCTURED = "structured"
    SEMI_STRUCTURED = "semi_structured"
    TEXT = "text"


class Timeliness(str, Enum):
    DAILY = "daily"
    INTRADAY = "intraday"
    EVENT_DRIVEN = "event_driven"
    LOW_FREQUENCY = "low_frequency"
    USER_DEFINED = "user_defined"


class LLMDependency(str, Enum):
    NONE = "none"
    SUMMARY_ONLY = "summary_only"
    REQUIRED = "required"


@dataclass(frozen=True)
class SourceDefinition:
    id: str
    name: str
    family: str
    tier: SourceTier
    trust_level: TrustLevel
    structure_level: StructureLevel
    timeliness: Timeliness
    llm_dependency: LLMDependency
    purpose: tuple[str, ...]
    required_fields: tuple[str, ...]
    output_objects: tuple[str, ...]


def _registry_path() -> Path:
    return CONFIGS_DIR / "source_registry.json"


def load_source_registry(path: Path | None = None) -> list[SourceDefinition]:
    registry_path = path or _registry_path()
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    return [
        SourceDefinition(
            id=item["id"],
            name=item["name"],
            family=item["family"],
            tier=SourceTier(item["tier"]),
            trust_level=TrustLevel(item["trust_level"]),
            structure_level=StructureLevel(item["structure_level"]),
            timeliness=Timeliness(item["timeliness"]),
            llm_dependency=LLMDependency(item["llm_dependency"]),
            purpose=tuple(item["purpose"]),
            required_fields=tuple(item["required_fields"]),
            output_objects=tuple(item["output_objects"]),
        )
        for item in payload["sources"]
    ]


def group_sources_by_tier(path: Path | None = None) -> dict[SourceTier, list[SourceDefinition]]:
    grouped: dict[SourceTier, list[SourceDefinition]] = {tier: [] for tier in SourceTier}
    for source in load_source_registry(path):
        grouped[source.tier].append(source)
    return grouped
