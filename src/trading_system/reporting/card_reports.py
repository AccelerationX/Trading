from __future__ import annotations

from trading_system.context.cards import CapitalBehaviorCard, EventCard, MacroEventCard, ThemeCard


def _cn_macro_value(value: str) -> str:
    mapping = {
        "bullish": "偏多",
        "neutral": "中性",
        "bearish": "偏空",
        "cross_border_diplomacy": "跨境外交",
        "geopolitical_conflict": "地缘冲突",
        "tariff_or_sanction": "关税或制裁",
        "fiscal_or_consumption_stimulus": "财政或消费刺激",
        "monetary_easing": "货币宽松",
        "market_rule_or_reform": "市场规则或改革",
        "macro_cross_border": "跨境宏观影响",
        "global_risk_aversion": "全球风险偏好压制",
        "global_trade_friction": "全球贸易摩擦",
        "domestic_demand": "内需驱动",
        "liquidity": "流动性驱动",
        "market_structure": "市场结构影响",
        "none": "无",
    }
    return mapping.get(str(value or "").strip(), str(value or "").strip())


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


def render_macro_event_cards_markdown(trade_date: str, cards: list[MacroEventCard]) -> str:
    lines = [f"# 宏观事件卡片 - {trade_date}", ""]
    if not cards:
        lines.append("- 无")
        return "\n".join(lines) + "\n"

    for card in cards:
        lines.extend(
            [
                f"## {card.title}",
                f"- 事件编号: `{card.macro_event_id}`",
                f"- 事件类型: `{_cn_macro_value(card.event_type)}`",
                f"- 来源类别: `{card.source_kind}`",
                f"- 发布时间: `{card.publish_time}`",
                f"- 方向判断: `{_cn_macro_value(card.bias)}`",
                f"- 影响范围: `{_cn_macro_value(card.impact_scope)}`",
                f"- 置信度: `{card.confidence}`",
                f"- 受益行业: `{', '.join(card.beneficiary_industries) if card.beneficiary_industries else '无'}`",
                f"- 承压行业: `{', '.join(card.risk_industries) if card.risk_industries else '无'}`",
                f"- 相关市场: `{', '.join(card.related_markets) if card.related_markets else '无'}`",
                f"- 需要确认: `{', '.join(card.confirmation_signals) if card.confirmation_signals else '无'}`",
                f"- 风险标记: `{', '.join(card.risk_flags) if card.risk_flags else '无'}`",
                f"- 摘要: {card.summary}",
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
