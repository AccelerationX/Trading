from __future__ import annotations

from trading_system.context.cards import CandidateCard


def render_candidate_cards_markdown(trade_date: str, cards: list[CandidateCard]) -> str:
    lines = [
        f"# Candidate Cards - {trade_date}",
        "",
    ]
    if not cards:
        lines.append("- none")
        return "\n".join(lines) + "\n"

    for rank, card in enumerate(cards, start=1):
        lines.extend(
            [
                f"## {rank}. {card.stock_code}",
                f"- source: `{card.candidate_source}`",
                f"- candidate_score: `{card.candidate_score}`",
                f"- fusion_score: `{card.fusion_score}`",
                f"- fusion_verdict: `{card.fusion_verdict or 'none'}`",
                f"- setup_type: `{card.setup_type or 'none'}`",
                f"- setup_confidence: `{card.setup_confidence}`",
                f"- setup_policy_status: `{card.setup_policy_status or 'none'}`",
                f"- setup_policy_score: `{card.setup_policy_score}`",
                f"- setup_action_floor: `{card.setup_action_floor}`",
                f"- setup_position_cap_multiplier: `{card.setup_position_cap_multiplier}`",
                f"- market_gate_pass: `{card.market_gate_pass}`",
                f"- market_gate_reason: `{card.market_gate_reason or 'none'}`",
                f"- dominant_driver: `{card.dominant_driver or 'none'}`",
                f"- technical_state: `{card.technical_state}`",
                f"- market_permission_score: `{card.market_permission_score}`",
                f"- driver_conviction_score: `{card.driver_conviction_score}`",
                f"- thesis_quality_score: `{card.thesis_quality_score}`",
                f"- technical_confirmation_score: `{card.technical_confirmation_score}`",
                f"- execution_readiness_score: `{card.execution_readiness_score}`",
                f"- event_support_score: `{card.event_support_score}`",
                f"- theme_alignment_score: `{card.theme_alignment_score}`",
                f"- macro_alignment_score: `{card.macro_alignment_score}`",
                f"- capital_confirmation_score: `{card.capital_confirmation_score}`",
                f"- information_edge_score: `{card.information_edge_score}`",
                f"- market_fit_score: `{card.market_fit_score}`",
                f"- account_fit_score: `{card.account_fit_score}`",
                f"- last_close_price: `{card.last_close_price}`",
                f"- estimated_min_lot_cost: `{card.estimated_min_lot_cost}`",
                f"- tradeability_verdict: `{card.tradeability_verdict or 'none'}`",
                f"- account_tradeability_score: `{card.account_tradeability_score}`",
                f"- active_modules: `{', '.join(card.active_module_ids) if card.active_module_ids else 'none'}`",
                f"- disqualify_flags: `{', '.join(card.disqualify_flags) if card.disqualify_flags else 'none'}`",
                f"- supporting_cards: `{', '.join(card.supporting_cards) if card.supporting_cards else 'none'}`",
                f"- supporting_macro_events: `{', '.join(card.supporting_macro_events) if card.supporting_macro_events else 'none'}`",
                f"- rationale: {card.candidate_rationale}",
                f"- diagnostic_summary: {card.diagnostic_summary or 'none'}",
                f"- diagnostic_risk_notes: `{', '.join(card.diagnostic_risk_notes) if card.diagnostic_risk_notes else 'none'}`",
                f"- fusion_notes: `{', '.join(card.fusion_notes) if card.fusion_notes else 'none'}`",
                f"- llm_diagnostic_summary: {card.llm_diagnostic_summary or 'none'}",
                f"- llm_tradeability_verdict: `{card.llm_tradeability_verdict or 'none'}`",
                f"- llm_focus_points: `{', '.join(card.llm_focus_points) if card.llm_focus_points else 'none'}`",
                f"- llm_risk_notes: `{', '.join(card.llm_risk_notes) if card.llm_risk_notes else 'none'}`",
                "",
            ]
        )

    return "\n".join(lines)
