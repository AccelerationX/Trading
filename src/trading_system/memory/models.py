from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ReviewMemoryEntry:
    memory_id: str
    trade_date: str
    stock_code: str
    action: str
    outcome_tag: str
    setup_tags: list[str] = field(default_factory=list)
    lesson_summary: str = ""
    actionable_rule: str = ""
    confidence: float | None = None
    retrieval_keys: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    llm_pattern_summary: str = ""
    llm_confidence: float | None = None
