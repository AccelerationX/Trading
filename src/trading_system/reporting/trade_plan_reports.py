from __future__ import annotations

from trading_system.context.cards import TradePlanCard


def render_trade_plan_markdown(trade_date: str, plans: list[TradePlanCard]) -> str:
    action_counts: dict[str, int] = {}
    for plan in plans:
        action_counts[plan.action] = action_counts.get(plan.action, 0) + 1
    lines = [
        f"# Trade Plan Draft - {trade_date}",
        "",
    ]
    if not plans:
        lines.append("- none")
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            f"- total_plans: `{len(plans)}`",
            f"- buy_pilot: `{action_counts.get('buy_pilot', 0)}`",
            f"- watch_only: `{action_counts.get('watch_only', 0)}`",
            f"- avoid: `{action_counts.get('avoid', 0)}`",
            "",
        ]
    )

    for plan in plans:
        lines.extend(
            [
                f"## {plan.priority_rank}. {plan.stock_code}",
                f"- action: `{plan.action}`",
                f"- setup_type: `{plan.setup_type or 'none'}`",
                f"- setup_policy_status: `{plan.setup_policy_status or 'none'}`",
                f"- market_gate_reason: `{plan.market_gate_reason or 'none'}`",
                f"- rationale: {plan.rationale}",
                f"- entry_condition: {plan.entry_condition}",
                f"- entry_zone: {plan.entry_zone or 'none'}",
                f"- position_size_rule: {plan.position_size_rule}",
                f"- max_position_pct: `{plan.max_position_pct}`",
                f"- add_reduce_rule: {plan.add_reduce_rule}",
                f"- invalidation_rule: {plan.invalidation_rule}",
                f"- exit_rule_hint: {plan.exit_rule_hint}",
                f"- holding_horizon: `{plan.holding_horizon}`",
                f"- risk_notes: `{', '.join(plan.risk_notes) if plan.risk_notes else 'none'}`",
                f"- supporting_cards: `{', '.join(plan.supporting_cards) if plan.supporting_cards else 'none'}`",
                "",
            ]
        )

    return "\n".join(lines)
