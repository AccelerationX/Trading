from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from trading_system.config.paths import OUTPUTS_DIR
from trading_system.context.event_cards import (
    build_event_cards_from_structured_announcements,
    build_theme_cards_from_policy_inputs,
    save_event_cards,
    save_theme_cards,
)
from trading_system.context.macro_event_cards import build_macro_event_cards, save_macro_event_cards
from trading_system.reporting.card_reports import (
    render_event_cards_markdown,
    render_macro_event_cards_markdown,
    render_theme_cards_markdown,
)


def _analysis_output_dir() -> Path:
    directory = OUTPUTS_DIR / "analysis"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def build_event_and_theme_cards(trade_date: str) -> tuple[Path | None, Path | None, Path | None, Path, Path, Path]:
    event_cards = build_event_cards_from_structured_announcements(trade_date)
    theme_cards = build_theme_cards_from_policy_inputs(trade_date)
    macro_event_cards = build_macro_event_cards(trade_date)
    event_json = save_event_cards(trade_date, event_cards)
    theme_json = save_theme_cards(trade_date, theme_cards)
    macro_json = save_macro_event_cards(trade_date, macro_event_cards)
    event_md = _analysis_output_dir() / f"event_cards_{trade_date}.md"
    theme_md = _analysis_output_dir() / f"theme_cards_{trade_date}.md"
    macro_md = _analysis_output_dir() / f"macro_event_cards_{trade_date}.md"
    event_md.write_text(render_event_cards_markdown(trade_date, event_cards), encoding="utf-8")
    theme_md.write_text(render_theme_cards_markdown(trade_date, theme_cards), encoding="utf-8")
    macro_md.write_text(render_macro_event_cards_markdown(trade_date, macro_event_cards), encoding="utf-8")
    return event_json, theme_json, macro_json, event_md, theme_md, macro_md


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat(), help="Trade date in YYYY-MM-DD format.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    event_json, theme_json, macro_json, event_md, theme_md, macro_md = build_event_and_theme_cards(args.date)
    print(f"event_cards_json={event_json}")
    print(f"theme_cards_json={theme_json}")
    print(f"macro_event_cards_json={macro_json}")
    print(f"event_cards_md={event_md}")
    print(f"theme_cards_md={theme_md}")
    print(f"macro_event_cards_md={macro_md}")


if __name__ == "__main__":
    main()
