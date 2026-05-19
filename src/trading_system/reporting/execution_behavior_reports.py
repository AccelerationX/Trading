from __future__ import annotations


def _safe_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2%}"


def render_execution_behavior_markdown(trade_date: str, payload: dict) -> str:
    lines = [
        f"# Execution Behavior - {trade_date}",
        "",
        f"- record_count: `{payload.get('record_count', 0)}`",
        f"- finalized_count: `{payload.get('finalized_count', 0)}`",
        f"- setup_count: `{payload.get('setup_count', 0)}`",
        "",
        "## Setup Summary",
    ]
    summary = list(payload.get("setup_summary", []))
    if not summary:
        lines.append("- none")
    else:
        for item in summary:
            lines.extend(
                [
                    f"### {item.get('setup_type', '')}",
                    f"- finalized_count: `{item.get('finalized_count', 0)}`",
                    f"- fill_rate: `{_safe_pct(item.get('fill_rate'))}`",
                    f"- skip_rate: `{_safe_pct(item.get('skip_rate'))}`",
                    f"- partial_rate: `{_safe_pct(item.get('partial_rate'))}`",
                    f"- avg_fill_ratio: `{_safe_pct(item.get('avg_fill_ratio'))}`",
                    f"- avg_buy_slippage_pct: `{_safe_pct(item.get('avg_buy_slippage_pct'))}`",
                    f"- avg_sell_slippage_pct: `{_safe_pct(item.get('avg_sell_slippage_pct'))}`",
                    f"- notes: `{', '.join(item.get('notes', [])) or 'none'}`",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"
