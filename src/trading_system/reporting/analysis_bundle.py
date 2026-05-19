from __future__ import annotations

from trading_system.context.cards import CapitalBehaviorCard, EventCard, MacroEventCard, MarketRegimeSnapshot, ThemeCard
from trading_system.decision.account import AccountConstraints
from trading_system.signal.technical_modules import TechnicalModule


def render_analysis_bundle_markdown(
    trade_date: str,
    market_regime: MarketRegimeSnapshot,
    account: AccountConstraints,
    technical_modules: list[TechnicalModule],
    event_cards: list[EventCard],
    theme_cards: list[ThemeCard],
    macro_event_cards: list[MacroEventCard],
    capital_behavior_cards: list[CapitalBehaviorCard],
) -> str:
    lines = [
        f"# Assistant Analysis Bundle - {trade_date}",
        "",
        "## Market Regime",
        f"- risk_mode: `{market_regime.risk_mode}`",
        f"- market_bias: `{market_regime.market_bias}`",
        f"- style_lead: `{market_regime.style_lead}`",
        f"- theme_concentration: `{market_regime.theme_concentration}`",
        f"- note: {market_regime.opening_risk_note or 'none'}",
        "",
        "## Account Constraints",
        f"- profile_name: `{account.profile_name}`",
        f"- trading_style: `{account.trading_style}`",
        f"- target_return_mode: `{account.target_return_mode}`",
        f"- capital_total: `{account.capital_total}`",
        f"- single_position_max_pct: `{account.single_position_max_pct}`",
        f"- max_holdings: `{account.max_holdings}`",
        f"- can_watch_intraday: `{account.can_watch_intraday}`",
        "",
        "## Technical Modules",
    ]
    if not technical_modules:
        lines.append("- none")
    else:
        for module in technical_modules:
            lines.append(f"- {module.module_id}: `{module.role}` / `{module.priority}` / {module.description}")

    lines.extend(["", "## Event Cards"])
    if not event_cards:
        lines.append("- none")
    else:
        for card in event_cards:
            lines.append(
                f"- {card.event_title}: `{card.bullish_bearish}` / `{card.impact_horizon}` / stocks `{', '.join(card.stock_codes) if card.stock_codes else 'none'}`"
            )

    lines.extend(["", "## Theme Cards"])
    if not theme_cards:
        lines.append("- none")
    else:
        for card in theme_cards:
            lines.append(
                f"- {card.theme_name}: trigger `{card.trigger_type}`, continuation `{card.continuation_guess}`"
            )

    lines.extend(["", "## Macro Event Cards"])
    if not macro_event_cards:
        lines.append("- none")
    else:
        for card in macro_event_cards:
            lines.append(
                f"- {card.title}: `{card.bias}` / `{card.impact_scope}` / beneficiaries `{', '.join(card.beneficiary_industries) if card.beneficiary_industries else 'none'}`"
            )

    lines.extend(["", "## Capital Behavior Cards"])
    if not capital_behavior_cards:
        lines.append("- none")
    else:
        for card in capital_behavior_cards:
            lines.append(
                f"- {card.stock_code}: `{card.capital_signal_type}` / `{card.support_or_distribution}` / `{card.participation_strength}`"
            )

    return "\n".join(lines) + "\n"
