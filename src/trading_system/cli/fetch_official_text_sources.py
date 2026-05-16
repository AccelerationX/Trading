from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from trading_system.config.paths import OUTPUTS_DIR
from trading_system.integrations.official_web_sources import fetch_official_web_sources


def _report_dir() -> Path:
    directory = OUTPUTS_DIR / "daily_reports"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def fetch_official_text_sources(trade_date: str) -> tuple[Path, Path]:
    artifacts, warnings = fetch_official_web_sources(trade_date)
    payload = {
        "trade_date": trade_date,
        "artifacts": [{**asdict(item), "path": str(item.path)} for item in artifacts],
        "warnings": warnings,
    }
    json_path = _report_dir() / f"official_text_source_fetch_{trade_date}.json"
    md_path = _report_dir() / f"official_text_source_fetch_{trade_date}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [f"# Official Text Source Fetch - {trade_date}", ""]
    for artifact in artifacts:
        lines.append(f"- {artifact.source_id}: `{artifact.row_count}` -> {artifact.path}")
        for note in artifact.notes:
            lines.append(f"  - {note}")
    lines.extend(["", "## Warnings"])
    if not warnings:
        lines.append("- none")
    else:
        for warning in warnings:
            lines.append(f"- {warning}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().strftime("%Y%m%d"), help="Trade date in YYYYMMDD format.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    json_path, md_path = fetch_official_text_sources(args.date)
    print(f"official_text_fetch_json={json_path}")
    print(f"official_text_fetch_md={md_path}")


if __name__ == "__main__":
    main()
