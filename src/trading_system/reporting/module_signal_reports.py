from __future__ import annotations

from collections import defaultdict

from trading_system.signal.scanners.base import ModuleSignal


def render_module_signals_markdown(trade_date: str, signals: list[ModuleSignal]) -> str:
    lines = [
        f"# Module Signals - {trade_date}",
        "",
    ]
    if not signals:
        lines.append("- none")
        return "\n".join(lines) + "\n"

    by_module: dict[str, list[ModuleSignal]] = defaultdict(list)
    for signal in signals:
        by_module[signal.module_id].append(signal)

    for module_id in sorted(by_module):
        module_signals = sorted(
            by_module[module_id],
            key=lambda item: (-item.strength, -item.confidence, item.stock_code),
        )
        lines.append(f"## {module_id}")
        lines.append(f"- signal_count: `{len(module_signals)}`")
        lines.append("")
        for signal in module_signals[:20]:
            lines.extend(
                [
                    f"### {signal.stock_code}",
                    f"- signal_type: `{signal.signal_type}`",
                    f"- strength: `{signal.strength}`",
                    f"- confidence: `{signal.confidence}`",
                    f"- technical_state: `{signal.technical_state}`",
                    f"- invalidation_hint: {signal.invalidation_hint or 'none'}",
                    f"- source_refs: `{', '.join(signal.source_refs) if signal.source_refs else 'none'}`",
                    "",
                ]
            )
    return "\n".join(lines) + "\n"
