from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from trading_system.config.paths import OUTPUTS_DIR, PROCESSED_DATA_DIR
from trading_system.context.cards import CandidateCard, MarketRegimeSnapshot, TradePlanCard
from trading_system.decision.account import AccountConstraints
from trading_system.evaluation.module_signal_evaluation import build_module_signal_evaluation
from trading_system.reporting.module_evaluation_reports import render_module_evaluation_markdown
from trading_system.signal.legacy.data_loader import load_stock_history
from trading_system.signal.scanners.base import ModuleSignal


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return json.loads(path.read_text(encoding="utf-8-sig"))


def _processed_dir() -> Path:
    directory = PROCESSED_DATA_DIR / "evaluation"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _analysis_dir() -> Path:
    directory = OUTPUTS_DIR / "analysis"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _load_market_regime(trade_date: str) -> MarketRegimeSnapshot:
    path = PROCESSED_DATA_DIR / "context" / f"market_regime_{trade_date}.json"
    return MarketRegimeSnapshot(**dict(_load_json(path)))


def _load_module_signals(trade_date: str) -> list[ModuleSignal]:
    path = PROCESSED_DATA_DIR / "module_signals" / f"module_signals_{trade_date}.json"
    payload = list(_load_json(path))
    return [ModuleSignal(**item) for item in payload]


def _load_candidate_cards(trade_date: str) -> list[CandidateCard]:
    path = PROCESSED_DATA_DIR / "candidates" / f"candidate_cards_{trade_date}.json"
    if not path.exists():
        return []
    payload = list(_load_json(path))
    return [CandidateCard(**item) for item in payload]


def _load_trade_plan_cards(trade_date: str) -> list[TradePlanCard]:
    preferred = PROCESSED_DATA_DIR / "trade_plans" / f"trade_plan_cards_{trade_date}.json"
    fallback = OUTPUTS_DIR / "trade_plans" / f"trade_plan_cards_{trade_date}.json"
    path = preferred if preferred.exists() else fallback
    if not path.exists():
        return []
    payload = list(_load_json(path))
    return [TradePlanCard(**item) for item in payload]


def build_module_evaluation_cli(trade_date: str) -> tuple[Path, Path]:
    market_regime = _load_market_regime(trade_date)
    module_signals = _load_module_signals(trade_date)
    candidate_cards = _load_candidate_cards(trade_date)
    trade_plan_cards = _load_trade_plan_cards(trade_date)
    history = load_stock_history(r"D:\TradingSystem\data\raw\stock_history")

    payload = build_module_signal_evaluation(
        trade_date,
        module_signals=module_signals,
        history=history,
        market_regime=market_regime,
        candidate_cards=candidate_cards,
        trade_plan_cards=trade_plan_cards,
    )

    json_path = _processed_dir() / f"module_evaluation_{trade_date}.json"
    md_path = _analysis_dir() / f"module_evaluation_{trade_date}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_module_evaluation_markdown(trade_date, payload), encoding="utf-8")
    return json_path, md_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Trade date in YYYY-MM-DD format.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    json_path, md_path = build_module_evaluation_cli(args.date)
    print(f"module_evaluation_json={json_path}")
    print(f"module_evaluation_md={md_path}")


if __name__ == "__main__":
    main()
