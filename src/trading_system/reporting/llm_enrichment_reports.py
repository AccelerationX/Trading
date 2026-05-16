from __future__ import annotations

from collections import Counter

from trading_system.integrations.llm_enrichments import LLMEnrichmentResult


def render_llm_enrichment_apply_markdown(
    trade_date: str,
    results: list[LLMEnrichmentResult],
    applied_counts: dict[str, int],
    skipped: list[str],
) -> str:
    lines = [f"# LLM Enrichment Apply - {trade_date}", ""]
    if not results:
        lines.append("No enrichment results applied.")
        return "\n".join(lines)

    contract_counts = Counter(item.contract_type for item in results)
    lines.extend(
        [
            "## Summary",
            "",
            f"- total_results: {len(results)}",
            f"- contracts: {dict(contract_counts)}",
            f"- applied_counts: {applied_counts}",
            "",
            "## Results",
            "",
        ]
    )
    for item in results:
        lines.append(f"### {item.packet_id}")
        lines.append(f"- agent_id: {item.agent_id}")
        lines.append(f"- target: {item.target_object_type}:{item.target_object_id}")
        lines.append(f"- contract_type: {item.contract_type}")
        lines.append(f"- confidence: {item.confidence if item.confidence is not None else 'n/a'}")
        if item.warnings:
            lines.append(f"- warnings: {', '.join(item.warnings)}")
        if item.citations:
            lines.append(f"- citations: {', '.join(item.citations)}")
        lines.append("")

    lines.extend(["## Skipped", ""])
    if not skipped:
        lines.append("- none")
    else:
        for item in skipped:
            lines.append(f"- {item}")
    return "\n".join(lines)
