from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from trading_system.config.paths import OUTPUTS_DIR
from trading_system.context.capital_behavior import build_capital_behavior_cards, save_capital_behavior_cards
from trading_system.reporting.card_reports import render_capital_behavior_cards_markdown


def _analysis_output_dir() -> Path:
    directory = OUTPUTS_DIR / "analysis"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def build_capital_behavior_cards_cli(trade_date: str) -> tuple[Path, Path]:
    cards = build_capital_behavior_cards(trade_date)
    json_path = save_capital_behavior_cards(trade_date, cards)
    md_path = _analysis_output_dir() / f"capital_behavior_cards_{trade_date}.md"
    md_path.write_text(render_capital_behavior_cards_markdown(trade_date, cards), encoding="utf-8")
    return json_path, md_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat(), help="Trade date in YYYY-MM-DD format.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    json_path, md_path = build_capital_behavior_cards_cli(args.date)
    print(f"capital_behavior_cards_json={json_path}")
    print(f"capital_behavior_cards_md={md_path}")


if __name__ == "__main__":
    main()
