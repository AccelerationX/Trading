from __future__ import annotations

import argparse
import json
from pathlib import Path

from trading_system.config.paths import OUTPUTS_DIR, PROCESSED_DATA_DIR
from trading_system.reporting.trade_execution_sheet import (
    render_trade_execution_markdown,
    save_trade_execution_payload,
    trade_execution_output_dir,
    build_trade_execution_payload,
)


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return json.loads(path.read_text(encoding="utf-8-sig"))


def build_trade_execution_sheet(trade_date: str) -> tuple[Path, Path]:
    preopen_path = OUTPUTS_DIR / "preopen" / f"preopen_summary_{trade_date}.json"
    account_path = PROCESSED_DATA_DIR / "account" / "active_account_constraints.json"
    preopen_payload = dict(_load_json(preopen_path))
    account_payload = dict(_load_json(account_path))
    payload = build_trade_execution_payload(preopen_payload, account_payload)
    json_path = save_trade_execution_payload(trade_date, payload)
    md_path = trade_execution_output_dir() / f"trade_execution_{trade_date}.md"
    md_path.write_text(render_trade_execution_markdown(payload), encoding="utf-8")
    return json_path, md_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Trade date in YYYY-MM-DD format.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    json_path, md_path = build_trade_execution_sheet(args.date)
    print(f"trade_execution_json={json_path}")
    print(f"trade_execution_md={md_path}")


if __name__ == "__main__":
    main()
