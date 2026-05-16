from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path

from trading_system.config.paths import PROCESSED_DATA_DIR, WORKSPACE_DIR
from trading_system.memory.models import ReviewMemoryEntry


def review_workspace_dir() -> Path:
    directory = WORKSPACE_DIR / "reviews"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def memory_processed_dir() -> Path:
    directory = PROCESSED_DATA_DIR / "memory"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _review_files(directory: Path | None = None) -> list[Path]:
    root = directory or review_workspace_dir()
    if not root.exists():
        return []
    return sorted([path for path in root.rglob("*.md") if path.is_file()], key=lambda path: path.name)


def _parse_markdown_bullets(path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("- "):
            continue
        content = line[2:]
        if ":" not in content:
            continue
        key, value = content.split(":", 1)
        mapping[key.strip().lower()] = value.strip()
    return mapping


def _slugify(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "_", text).strip("_")
    return slug[:80] or "review"


def _infer_outcome_tag(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in ("worked", "profit", "good", "有效", "赚钱", "符合")):
        return "positive"
    if any(token in lowered for token in ("failed", "loss", "bad", "错误", "亏损", "失效")):
        return "negative"
    return "mixed"


def _infer_setup_tags(text: str) -> list[str]:
    lowered = text.lower()
    tags: list[str] = []
    keyword_map = {
        "event_driven": ("event", "公告", "news", "policy"),
        "theme_rotation": ("theme", "题材", "sector", "板块"),
        "repair_rebound": ("repair", "rebound", "修复", "反弹"),
        "trend_follow": ("trend", "breakout", "趋势", "突破"),
        "risk_control": ("stop", "risk", "回撤", "止损"),
    }
    for tag, keywords in keyword_map.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            tags.append(tag)
    return tags or ["general_review"]


def _extract_actionable_rule(learned: str, why_executed: str, aftermath: str) -> str:
    if learned:
        return learned
    if aftermath:
        return f"Review similar situations with this reminder: {aftermath}"
    if why_executed:
        return f"Re-check whether this execution logic still holds: {why_executed}"
    return "No clear lesson recorded yet."


def _confidence(mapping: dict[str, str]) -> float:
    filled = sum(1 for key in ("trade date", "stock", "action", "why i executed", "what happened afterward", "what i learned") if mapping.get(key))
    return round(min(0.95, 0.35 + 0.1 * filled), 2)


def build_review_memory_entries(directory: Path | None = None) -> list[ReviewMemoryEntry]:
    entries: list[ReviewMemoryEntry] = []
    for path in _review_files(directory):
        mapping = _parse_markdown_bullets(path)
        trade_date = mapping.get("trade date", "")
        stock_code = mapping.get("stock", "").upper()
        action = mapping.get("action", "")
        why_executed = mapping.get("why i executed", "")
        ignored_system = mapping.get("why i ignored any system suggestion", "")
        aftermath = mapping.get("what happened afterward", "")
        learned = mapping.get("what i learned", "")
        merged_text = " ".join(value for value in (why_executed, ignored_system, aftermath, learned) if value)
        if not trade_date and not stock_code and not merged_text:
            continue

        setup_tags = _infer_setup_tags(merged_text)
        outcome_tag = _infer_outcome_tag(" ".join([action, aftermath, learned]))
        retrieval_keys = [stock_code, action, *setup_tags]
        retrieval_keys = [key for key in retrieval_keys if key]
        entries.append(
            ReviewMemoryEntry(
                memory_id=f"{trade_date or 'unknown'}_{stock_code or 'market'}_{_slugify(path.stem)}",
                trade_date=trade_date,
                stock_code=stock_code,
                action=action,
                outcome_tag=outcome_tag,
                setup_tags=setup_tags,
                lesson_summary=learned or aftermath or why_executed or ignored_system,
                actionable_rule=_extract_actionable_rule(learned, why_executed, aftermath),
                confidence=_confidence(mapping),
                retrieval_keys=list(dict.fromkeys(retrieval_keys)),
                source_refs=[str(path)],
            )
        )

    entries.sort(key=lambda item: (item.trade_date, item.stock_code, item.memory_id), reverse=True)
    return entries


def save_review_memory_entries(entries: list[ReviewMemoryEntry], path: Path | None = None) -> Path:
    output_path = path or (memory_processed_dir() / "review_memory_entries.json")
    output_path.write_text(json.dumps([asdict(entry) for entry in entries], ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path

