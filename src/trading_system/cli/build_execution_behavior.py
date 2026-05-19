from __future__ import annotations

import argparse
import json
from pathlib import Path

from trading_system.config.paths import OUTPUTS_DIR, PROCESSED_DATA_DIR
from trading_system.decision.live_trade_state import default_trade_log_path, load_system_trade_log
from trading_system.evaluation.execution_behavior import build_execution_behavior
from trading_system.reporting.execution_behavior_reports import render_execution_behavior_markdown


def execution_behavior_output_dir() -> Path:
    directory = OUTPUTS_DIR / "execution_behavior"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def build_execution_behavior_cli(trade_date: str, *, trade_log_path: Path | None = None) -> tuple[Path, Path]:
    records = load_system_trade_log(trade_log_path or default_trade_log_path())
    payload = build_execution_behavior(records)
    json_path = PROCESSED_DATA_DIR / "evaluation" / f"execution_behavior_{trade_date}.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path = execution_behavior_output_dir() / f"execution_behavior_{trade_date}.md"
    md_path.write_text(render_execution_behavior_markdown(trade_date, payload), encoding="utf-8")
    return json_path, md_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Trade date in YYYY-MM-DD format.")
    parser.add_argument("--trade-log-path", default=str(default_trade_log_path()), help="System trade log JSON path.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    json_path, md_path = build_execution_behavior_cli(args.date, trade_log_path=Path(args.trade_log_path))
    print(f"execution_behavior_json={json_path}")
    print(f"execution_behavior_md={md_path}")


if __name__ == "__main__":
    main()
