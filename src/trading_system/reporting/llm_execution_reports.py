from __future__ import annotations

from collections import Counter

from trading_system.integrations.llm_provider_registry import LLMExecutionRoute


def render_llm_execution_plan_markdown(trade_date: str, routes: list[LLMExecutionRoute]) -> str:
    lines = [f"# LLM Execution Plan - {trade_date}", ""]
    if not routes:
        lines.append("No LLM routes generated.")
        return "\n".join(lines)

    status_counts = Counter(route.status for route in routes)
    lines.extend(
        [
            "## Summary",
            "",
            f"- total_routes: {len(routes)}",
            f"- ready: {status_counts.get('ready', 0)}",
            f"- missing_credentials: {status_counts.get('missing_credentials', 0)}",
            f"- disabled: {status_counts.get('disabled', 0)}",
            "",
            "## Routes",
            "",
        ]
    )
    for route in routes:
        lines.append(f"### {route.packet_id}")
        lines.append(f"- agent_id: {route.agent_id}")
        lines.append(f"- provider_id: {route.provider_id or 'unbound'}")
        lines.append(f"- provider_type: {route.provider_type or 'unset'}")
        lines.append(f"- model: {route.model or 'unset'}")
        lines.append(f"- status: {route.status}")
        lines.append(f"- output_mode: {route.output_mode}")
        lines.append(f"- api_key_env: {route.api_key_env or 'n/a'}")
        lines.append(f"- api_key_present: {'yes' if route.api_key_present else 'no'}")
        lines.append(f"- api_base_env: {route.api_base_env or 'n/a'}")
        lines.append(f"- api_base_present: {'yes' if route.api_base_present else 'no'}")
        lines.append(f"- api_base_default: {route.api_base_default or 'n/a'}")
        lines.append(f"- timeout_seconds: {route.timeout_seconds}")
        lines.append(f"- max_retries: {route.max_retries}")
        if route.notes:
            lines.append(f"- notes: {', '.join(route.notes)}")
        lines.append("")
    return "\n".join(lines)
