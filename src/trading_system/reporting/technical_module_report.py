from __future__ import annotations

from trading_system.context.cards import MarketRegimeSnapshot
from trading_system.signal.technical_modules import TechnicalModule


def render_technical_module_recommendation(
    trade_date: str,
    snapshot: MarketRegimeSnapshot,
    modules: list[TechnicalModule],
) -> str:
    lines = [
        f"# Technical Module Recommendation - {trade_date}",
        "",
        "## Market Context",
        f"- risk_mode: `{snapshot.risk_mode}`",
        f"- market_bias: `{snapshot.market_bias}`",
        f"- style_lead: `{snapshot.style_lead}`",
        f"- theme_concentration: `{snapshot.theme_concentration}`",
        "",
        "## Recommended Modules",
    ]
    if not modules:
        lines.append("- none")
        return "\n".join(lines) + "\n"

    for module in modules:
        lines.extend(
            [
                f"### {module.module_id}",
                f"- family: `{module.family}`",
                f"- role: `{module.role}`",
                f"- priority: `{module.priority}`",
                f"- needs_intraday: `{module.needs_intraday}`",
                f"- description: {module.description}",
            ]
        )
    return "\n".join(lines) + "\n"
