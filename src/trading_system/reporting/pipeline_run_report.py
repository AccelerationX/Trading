from __future__ import annotations

from pathlib import Path


def render_pipeline_run_report(
    trade_date: str,
    stage_outputs: list[tuple[str, str, list[Path]]],
    warnings: list[str],
) -> str:
    lines = [
        f"# Assistant Pipeline Run - {trade_date}",
        "",
        "## Stage Status",
    ]
    for stage_name, status, paths in stage_outputs:
        lines.append(f"- {stage_name}: `{status}`")
        for path in paths:
            lines.append(f"  - {path}")

    lines.extend(["", "## Warnings"])
    if not warnings:
        lines.append("- none")
    else:
        for warning in warnings:
            lines.append(f"- {warning}")
    return "\n".join(lines) + "\n"
