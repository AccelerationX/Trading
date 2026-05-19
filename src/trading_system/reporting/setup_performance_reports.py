from __future__ import annotations


def _pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2%}"


def render_setup_performance_markdown(label: str, payload: dict) -> str:
    lines = [
        f"# Setup Performance - {label}",
        "",
        f"- candidate_count: `{payload.get('candidate_count', 0)}`",
        f"- trade_plan_count: `{payload.get('trade_plan_count', 0)}`",
        f"- evaluated_setup_count: `{payload.get('evaluated_setup_count', 0)}`",
        f"- setup_count: `{payload.get('setup_count', 0)}`",
        "",
    ]

    summary = payload.get("setup_summary") or []
    if not summary:
        lines.append("- none")
        return "\n".join(lines) + "\n"

    for item in summary:
        lines.extend(
            [
                f"## {item['setup_type']}",
                f"- sample_count: `{item['sample_count']}`",
                f"- buy_pilot_count: `{item['buy_pilot_count']}`",
                f"- watch_only_count: `{item['watch_only_count']}`",
                f"- actionable_count: `{item['actionable_count']}`",
                f"- avg_candidate_score: `{item['avg_candidate_score']}`",
                f"- avg_setup_confidence: `{item['avg_setup_confidence']}`",
                f"- avg_mfe_5d: `{_pct(item['avg_mfe_5d'])}`",
                f"- avg_mae_5d: `{_pct(item['avg_mae_5d'])}`",
            ]
        )
        for horizon, metrics in (item.get("buy_pilot_horizons") or {}).items():
            lines.append(
                f"- buy_pilot {horizon}: sample=`{metrics['sample_count']}` avg_return=`{_pct(metrics['avg_return'])}` win_rate=`{_pct(metrics['win_rate'])}` hit_rate_3pct=`{_pct(metrics['hit_rate_3pct'])}`"
            )
        lines.append("")

    return "\n".join(lines)
