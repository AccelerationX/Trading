from __future__ import annotations

from trading_system.integrations.llm_contracts import LLMWorkPacket


def render_llm_workpacks_markdown(trade_date: str, packets: list[LLMWorkPacket], *, mode: str = "full") -> str:
    family_counts: dict[str, int] = {}
    for packet in packets:
        family = packet.packet_family or "unknown"
        family_counts[family] = family_counts.get(family, 0) + 1
    lines = [
        f"# LLM Workpacks - {trade_date}",
        "",
        f"- mode: `{mode}`",
        f"- packet_count: `{len(packets)}`",
        f"- family_counts: `{', '.join(f'{family}={count}' for family, count in sorted(family_counts.items())) or 'none'}`",
        "",
    ]
    if not packets:
        lines.append("- none")
        return "\n".join(lines) + "\n"

    for packet in packets:
        lines.extend(
            [
                f"## {packet.packet_id}",
                f"- agent_id: `{packet.agent_id}`",
                f"- task_id: `{packet.task_id}`",
                f"- priority: `{packet.priority}`",
                f"- packet_family: `{packet.packet_family or 'unknown'}`",
                f"- runtime_tier: `{packet.runtime_tier}`",
                f"- sort_rank: `{packet.sort_rank}`",
                f"- target: `{packet.target_object_type}` / `{packet.target_object_id}`",
                f"- prompt_file: `{packet.prompt_file}`",
                f"- input_refs: `{', '.join(packet.input_refs) if packet.input_refs else 'none'}`",
                f"- expected_output_contract: `{packet.expected_output_contract}`",
                f"- notes: `{', '.join(packet.notes) if packet.notes else 'none'}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
