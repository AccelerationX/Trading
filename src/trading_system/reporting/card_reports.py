from __future__ import annotations

from trading_system.context.cards import CapitalBehaviorCard, EventCard, ThemeCard


def render_event_cards_markdown(trade_date: str, cards: list[EventCard]) -> str:
    lines = [f"# Event Cards - {trade_date}", ""]
    if not cards:
        lines.append("- none")
        return "\n".join(lines) + "\n"

    for card in cards:
        lines.extend(
            [
                f"## {card.event_title}",
                f"- event_id: `{card.event_id}`",
                f"- event_type: `{card.event_type}`",
                f"- stock_codes: `{', '.join(card.stock_codes) if card.stock_codes else 'none'}`",
                f"- industry_tags: `{', '.join(card.industry_tags) if card.industry_tags else 'none'}`",
                f"- publish_time: `{card.publish_time}`",
                f"- bullish_bearish: `{card.bullish_bearish}`",
                f"- impact_horizon: `{card.impact_horizon}`",
                f"- event_strength: `{card.event_strength}`",
                f"- novelty_score: `{card.novelty_score}`",
                f"- core_claim: {card.core_claim}",
                f"- risk_flags: `{', '.join(card.risk_flags) if card.risk_flags else 'none'}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_theme_cards_markdown(trade_date: str, cards: list[ThemeCard]) -> str:
    lines = [f"# Theme Cards - {trade_date}", ""]
    if not cards:
        lines.append("- none")
        return "\n".join(lines) + "\n"

    for card in cards:
        lines.extend(
            [
                f"## {card.theme_name}",
                f"- theme_id: `{card.theme_id}`",
                f"- trigger_type: `{card.trigger_type}`",
                f"- trigger_time: `{card.trigger_time}`",
                f"- beneficiary_chain: `{', '.join(card.beneficiary_chain) if card.beneficiary_chain else 'none'}`",
                f"- priority_industries: `{', '.join(card.priority_industries) if card.priority_industries else 'none'}`",
                f"- priority_stocks: `{', '.join(card.priority_stocks) if card.priority_stocks else 'none'}`",
                f"- continuation_guess: `{card.continuation_guess}`",
                f"- market_confirmation_needed: `{', '.join(card.market_confirmation_needed) if card.market_confirmation_needed else 'none'}`",
                f"- contra_risks: `{', '.join(card.contra_risks) if card.contra_risks else 'none'}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_capital_behavior_cards_markdown(trade_date: str, cards: list[CapitalBehaviorCard]) -> str:
    lines = [f"# Capital Behavior Cards - {trade_date}", ""]
    if not cards:
        lines.append("- none")
        return "\n".join(lines) + "\n"

    for card in cards:
        lines.extend(
            [
                f"## {card.stock_code}",
                f"- card_id: `{card.card_id}`",
                f"- capital_signal_type: `{card.capital_signal_type}`",
                f"- participation_strength: `{card.participation_strength}`",
                f"- consistency_score: `{card.consistency_score}`",
                f"- suspected_style: `{card.suspected_style}`",
                f"- support_or_distribution: `{card.support_or_distribution}`",
                f"- warning_flags: `{', '.join(card.warning_flags) if card.warning_flags else 'none'}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
