from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from trading_system.reporting.text_signal_watch import build_text_signal_watch


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat(), help="Trade date in YYYY-MM-DD format.")
    return parser


def build_text_signal_watch_cli(trade_date: str) -> tuple[Path, Path]:
    return build_text_signal_watch(trade_date)


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    json_path, md_path = build_text_signal_watch_cli(args.date)
    print(f"text_signal_watch_json={json_path}")
    print(f"text_signal_watch_md={md_path}")


if __name__ == "__main__":
    main()
