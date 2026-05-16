from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from trading_system.cli.build_analysis_bundle import build_analysis_bundle
from trading_system.config.paths import OUTPUTS_DIR, PROCESSED_DATA_DIR
from trading_system.context.candidate_cards import build_candidate_cards, save_candidate_cards
from trading_system.context.cards import CapitalBehaviorCard, EventCard, MarketRegimeSnapshot, ThemeCard
from trading_system.context.text_signal_support import load_text_signal_watch
from trading_system.decision.account import AccountConstraints
from trading_system.reporting.candidate_reports import render_candidate_cards_markdown
from trading_system.reporting.module_signal_reports import render_module_signals_markdown
from trading_system.signal.scanners.base import ModuleSignal
from trading_system.signal.scanners.registry import load_scanners_for_modules
from trading_system.signal.technical_modules import TechnicalModule


def _analysis_output_dir() -> Path:
    directory = OUTPUTS_DIR / "analysis"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _module_signal_processed_dir() -> Path:
    directory = PROCESSED_DATA_DIR / "module_signals"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_assistant_bundle(trade_date: str) -> dict:
    path = _analysis_output_dir() / f"assistant_bundle_{trade_date}.json"
    return dict(_load_json(path))


def _save_module_signals(trade_date: str, module_signals: list[ModuleSignal]) -> tuple[Path, Path]:
    json_path = _module_signal_processed_dir() / f"module_signals_{trade_date}.json"
    md_path = _analysis_output_dir() / f"module_signals_{trade_date}.md"
    json_path.write_text(
        json.dumps([asdict(signal) for signal in module_signals], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(render_module_signals_markdown(trade_date, module_signals), encoding="utf-8")
    return json_path, md_path


def build_candidate_cards_from_bundle(
    trade_date: str,
    *,
    refresh_bundle: bool = True,
) -> tuple[Path, Path, Path, Path, list[str]]:
    warnings: list[str] = []
    if refresh_bundle:
        build_analysis_bundle(trade_date)

    payload = _load_assistant_bundle(trade_date)
    market_regime = MarketRegimeSnapshot(**payload["market_regime"])
    account = AccountConstraints(**payload["account_constraints"])
    technical_modules = [TechnicalModule(**item) for item in payload.get("technical_modules", [])]
    event_cards = [EventCard(**item) for item in payload.get("event_cards", [])]
    theme_cards = [ThemeCard(**item) for item in payload.get("theme_cards", [])]
    capital_cards = [CapitalBehaviorCard(**item) for item in payload.get("capital_behavior_cards", [])]
    text_watch_records = load_text_signal_watch(trade_date)

    module_signals = []
    scanners = load_scanners_for_modules(technical_modules)

    for module_id, scanner in scanners.items():
        if not scanner.is_available(trade_date):
            warnings.append(f"scanner_unavailable: {module_id} for {trade_date}")
            continue
        try:
            signals = scanner.scan(trade_date, market_regime, account=account)
        except Exception as exc:
            warnings.append(f"scanner_failed: {module_id}: {exc.__class__.__name__}: {exc}")
            continue
        module_signals.extend(signals)

    module_signal_json, module_signal_md = _save_module_signals(trade_date, module_signals)

    cards = build_candidate_cards(
        trade_date,
        market_regime=market_regime,
        account=account,
        technical_modules=technical_modules,
        event_cards=event_cards,
        theme_cards=theme_cards,
        capital_cards=capital_cards,
        text_watch_records=text_watch_records,
        module_signals=module_signals,
        available_module_ids=set(scanners),
    )
    json_path = save_candidate_cards(trade_date, cards)
    md_path = _analysis_output_dir() / f"candidate_cards_{trade_date}.md"
    md_path.write_text(render_candidate_cards_markdown(trade_date, cards), encoding="utf-8")
    return json_path, md_path, module_signal_json, module_signal_md, warnings


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Trade date in YYYY-MM-DD format.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    json_path, md_path, module_signal_json, module_signal_md, warnings = build_candidate_cards_from_bundle(args.date)
    print(f"candidate_cards_json={json_path}")
    print(f"candidate_cards_md={md_path}")
    print(f"module_signals_json={module_signal_json}")
    print(f"module_signals_md={module_signal_md}")
    print(f"candidate_cards_warning_count={len(warnings)}")
    for warning in warnings:
        print(f"candidate_cards_warning={warning}")


if __name__ == "__main__":
    main()
