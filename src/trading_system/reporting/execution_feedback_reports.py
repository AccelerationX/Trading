from __future__ import annotations


def _safe_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2%}"


def render_execution_feedback_markdown(trade_date: str, payload: dict) -> str:
    lines = [
        f"# Execution Feedback - {trade_date}",
        "",
        f"- closed_trade_count: `{payload.get('closed_trade_count', 0)}`",
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
                    f"- closed_trade_count: `{item.get('closed_trade_count', 0)}`",
                    f"- matched_share_total: `{item.get('matched_share_total', 0)}`",
                    f"- avg_realized_return: `{_safe_pct(item.get('avg_realized_return'))}`",
                    f"- win_rate: `{_safe_pct(item.get('win_rate'))}`",
                    f"- avg_holding_days: `{item.get('avg_holding_days', 'n/a')}`",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"
