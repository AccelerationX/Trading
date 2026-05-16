from __future__ import annotations

from trading_system.memory.models import ReviewMemoryEntry


def render_review_memory_markdown(entries: list[ReviewMemoryEntry]) -> str:
    lines = [
        "# Review Memory Entries",
        "",
    ]
    if not entries:
        lines.append("- none")
        return "\n".join(lines) + "\n"

    for entry in entries:
        lines.extend(
            [
                f"## {entry.trade_date or 'unknown'} {entry.stock_code or 'market'}",
                f"- action: `{entry.action or 'none'}`",
                f"- outcome_tag: `{entry.outcome_tag}`",
                f"- setup_tags: `{', '.join(entry.setup_tags) if entry.setup_tags else 'none'}`",
                f"- confidence: `{entry.confidence}`",
                f"- actionable_rule: {entry.actionable_rule}",
                f"- lesson_summary: {entry.lesson_summary or 'none'}",
                f"- retrieval_keys: `{', '.join(entry.retrieval_keys) if entry.retrieval_keys else 'none'}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
