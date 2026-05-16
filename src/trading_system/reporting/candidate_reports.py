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
                f"- technical_state: `{card.technical_state}`",
                f"- event_support_score: `{card.event_support_score}`",
                f"- theme_alignment_score: `{card.theme_alignment_score}`",
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
                f"- rationale: {card.candidate_rationale}",
                f"- diagnostic_summary: {card.diagnostic_summary or 'none'}",
                f"- diagnostic_risk_notes: `{', '.join(card.diagnostic_risk_notes) if card.diagnostic_risk_notes else 'none'}`",
                f"- llm_diagnostic_summary: {card.llm_diagnostic_summary or 'none'}",
                f"- llm_tradeability_verdict: `{card.llm_tradeability_verdict or 'none'}`",
                f"- llm_focus_points: `{', '.join(card.llm_focus_points) if card.llm_focus_points else 'none'}`",
                f"- llm_risk_notes: `{', '.join(card.llm_risk_notes) if card.llm_risk_notes else 'none'}`",
                "",
            ]
        )

    return "\n".join(lines)
