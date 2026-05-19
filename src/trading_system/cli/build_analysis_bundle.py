from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from trading_system.config.paths import OUTPUTS_DIR, PROCESSED_DATA_DIR
from trading_system.context.cards import CapitalBehaviorCard, EventCard, MacroEventCard, MarketRegimeSnapshot, ThemeCard
from trading_system.decision.account import AccountConstraints
from trading_system.reporting.analysis_bundle import render_analysis_bundle_markdown
from trading_system.signal.technical_modules import TechnicalModule, recommend_modules_for_regime


def _analysis_output_dir() -> Path:
    directory = OUTPUTS_DIR / "analysis"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_market_regime(trade_date: str) -> MarketRegimeSnapshot:
    path = PROCESSED_DATA_DIR / "context" / f"market_regime_{trade_date}.json"
    payload = _load_json(path)
    return MarketRegimeSnapshot(**payload)


def _load_account() -> AccountConstraints:
    path = PROCESSED_DATA_DIR / "account" / "active_account_constraints.json"
    payload = _load_json(path)
    return AccountConstraints(**payload)


def _load_event_cards(trade_date: str) -> list[EventCard]:
    path = PROCESSED_DATA_DIR / "events" / f"event_cards_{trade_date}.json"
    if not path.exists():
        return []
    payload = _load_json(path)
    return [EventCard(**item) for item in payload]


def _load_theme_cards(trade_date: str) -> list[ThemeCard]:
    path = PROCESSED_DATA_DIR / "themes" / f"theme_cards_{trade_date}.json"
    if not path.exists():
        return []
    payload = _load_json(path)
    return [ThemeCard(**item) for item in payload]


def _load_macro_event_cards(trade_date: str) -> list[MacroEventCard]:
    path = PROCESSED_DATA_DIR / "macro_events" / f"macro_event_cards_{trade_date}.json"
    if not path.exists():
        return []
    payload = _load_json(path)
    return [MacroEventCard(**item) for item in payload]


def _load_capital_behavior_cards(trade_date: str) -> list[CapitalBehaviorCard]:
    path = PROCESSED_DATA_DIR / "capital" / f"capital_behavior_cards_{trade_date}.json"
    if not path.exists():
        return []
    payload = _load_json(path)
    return [CapitalBehaviorCard(**item) for item in payload]


def build_analysis_bundle(trade_date: str) -> tuple[Path, Path]:
    market_regime = _load_market_regime(trade_date)
    account = _load_account()
    technical_modules = recommend_modules_for_regime(
        market_regime,
        can_watch_intraday=account.can_watch_intraday,
    )
    event_cards = _load_event_cards(trade_date)
    theme_cards = _load_theme_cards(trade_date)
    macro_event_cards = _load_macro_event_cards(trade_date)
    capital_behavior_cards = _load_capital_behavior_cards(trade_date)

    json_path = _analysis_output_dir() / f"assistant_bundle_{trade_date}.json"
    md_path = _analysis_output_dir() / f"assistant_bundle_{trade_date}.md"

    payload = {
        "trade_date": trade_date,
        "market_regime": asdict(market_regime),
        "account_constraints": asdict(account),
        "technical_modules": [asdict(module) for module in technical_modules],
        "event_cards": [asdict(card) for card in event_cards],
        "theme_cards": [asdict(card) for card in theme_cards],
        "macro_event_cards": [asdict(card) for card in macro_event_cards],
        "capital_behavior_cards": [asdict(card) for card in capital_behavior_cards],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(
        render_analysis_bundle_markdown(
            trade_date=trade_date,
            market_regime=market_regime,
            account=account,
            technical_modules=technical_modules,
            event_cards=event_cards,
            theme_cards=theme_cards,
            macro_event_cards=macro_event_cards,
            capital_behavior_cards=capital_behavior_cards,
        ),
        encoding="utf-8",
    )
    return json_path, md_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Trade date in YYYY-MM-DD format.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    json_path, md_path = build_analysis_bundle(args.date)
    print(f"assistant_bundle_json={json_path}")
    print(f"assistant_bundle_md={md_path}")


if __name__ == "__main__":
    main()
