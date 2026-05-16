from __future__ import annotations

from trading_system.context.cards import MarketRegimeSnapshot


def render_market_regime_markdown(snapshot: MarketRegimeSnapshot) -> str:
    lines = [
        f"# Market Regime - {snapshot.trade_date}",
        "",
        "## Summary",
        f"- market_bias: `{snapshot.market_bias}`",
        f"- risk_mode: `{snapshot.risk_mode}`",
        f"- breadth_strength: `{snapshot.breadth_strength}`",
        f"- limit_up_temperature: `{snapshot.limit_up_temperature}`",
        f"- turnover_regime: `{snapshot.turnover_regime}`",
        f"- style_lead: `{snapshot.style_lead}`",
        f"- theme_concentration: `{snapshot.theme_concentration}`",
        f"- sentiment_cycle: `{snapshot.sentiment_cycle}`",
        f"- leader_stability: `{snapshot.leader_stability}`",
        f"- event_driven_bias: `{snapshot.event_driven_bias}`",
        f"- confidence: `{snapshot.confidence}`",
        "",
        "## Opening Note",
        f"- {snapshot.opening_risk_note or 'none'}",
        "",
        "## Evidence",
    ]
    for item in snapshot.supporting_evidence:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"
