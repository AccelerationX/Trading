from __future__ import annotations

from collections import Counter

from trading_system.integrations.llm_runtime import LLMRuntimeRecord


def render_llm_runtime_markdown(trade_date: str, records: list[LLMRuntimeRecord]) -> str:
    lines = [f"# LLM Provider Runtime - {trade_date}", ""]
    if not records:
        lines.append("No runtime records generated.")
        return "\n".join(lines)

    status_counts = Counter(record.status for record in records)
    provider_counts = Counter(record.provider_id for record in records)
    lines.extend(
        [
            "## Summary",
            "",
            f"- total_records: {len(records)}",
            f"- completed: {status_counts.get('completed', 0)}",
            f"- exported_for_manual: {status_counts.get('exported_for_manual', 0)}",
            f"- failed: {status_counts.get('failed', 0)}",
            f"- skipped: {status_counts.get('skipped', 0)}",
            "",
            "## Providers",
            "",
        ]
    )
    for provider_id, count in sorted(provider_counts.items()):
        lines.append(f"- {provider_id or 'unbound'}: {count}")
    lines.extend(["", "## Records", ""])

    for record in records:
        lines.append(f"### {record.packet_id}")
        lines.append(f"- provider_id: {record.provider_id}")
        lines.append(f"- provider_type: {record.provider_type}")
        lines.append(f"- status: {record.status}")
        lines.append(f"- target_object_type: {record.target_object_type}")
        lines.append(f"- target_object_id: {record.target_object_id}")
        if record.artifact_paths:
            lines.append(f"- artifact_paths: {', '.join(record.artifact_paths)}")
        if record.notes:
            lines.append(f"- notes: {', '.join(record.notes)}")
        lines.append("")
    return "\n".join(lines)
