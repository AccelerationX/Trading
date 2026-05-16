from __future__ import annotations


def _pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2%}"


def render_module_evaluation_markdown(trade_date: str, payload: dict) -> str:
    lines = [
        f"# Module Evaluation - {trade_date}",
        "",
        f"- signal_count: `{payload.get('signal_count', 0)}`",
        f"- module_count: `{payload.get('module_count', 0)}`",
        f"- candidate_count: `{payload.get('candidate_count', 0)}`",
        f"- trade_plan_count: `{payload.get('trade_plan_count', 0)}`",
    ]
    regime = payload.get("market_regime") or {}
    if regime:
        lines.append(
            f"- market_regime: `{regime.get('risk_mode', '')}` / `{regime.get('style_lead', '')}` / `{regime.get('theme_concentration', '')}`"
        )
    lines.append("")

    summary = payload.get("module_summary") or []
    if not summary:
        lines.append("- none")
        return "\n".join(lines) + "\n"

    for item in summary:
        lines.extend(
            [
                f"## {item['module_id']}",
                f"- signal_count: `{item['signal_count']}`",
                f"- unique_stock_count: `{item['unique_stock_count']}`",
                f"- candidate_overlap_count: `{item['candidate_overlap_count']}`",
                f"- trade_plan_overlap_count: `{item['trade_plan_overlap_count']}`",
                f"- avg_strength: `{item['avg_strength']}`",
                f"- avg_confidence: `{item['avg_confidence']}`",
                f"- signal_type_counts: `{item['signal_type_counts']}`",
            ]
        )
        for horizon, metrics in (item.get("horizons") or {}).items():
            lines.append(
                f"- {horizon}: sample=`{metrics['sample_count']}` avg_return=`{_pct(metrics['avg_return'])}` win_rate=`{_pct(metrics['win_rate'])}` hit_rate_3pct=`{_pct(metrics['hit_rate_3pct'])}`"
            )
        lines.append("")

    return "\n".join(lines)
