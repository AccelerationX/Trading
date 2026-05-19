from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from trading_system.config.paths import OUTPUTS_DIR, PROCESSED_DATA_DIR
from trading_system.context.cards import CandidateCard, TradePlanCard
from trading_system.evaluation.setup_performance import build_setup_performance
from trading_system.reporting.setup_performance_reports import render_setup_performance_markdown
from trading_system.signal.legacy.data_loader import load_stock_history


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return json.loads(path.read_text(encoding="utf-8-sig"))


def _evaluation_dir() -> Path:
    directory = PROCESSED_DATA_DIR / "evaluation"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _analysis_dir() -> Path:
    directory = OUTPUTS_DIR / "analysis"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _extract_date(path: Path, prefix: str) -> str | None:
    match = re.match(rf"{re.escape(prefix)}_(\d{{4}}-\d{{2}}-\d{{2}})\.json$", path.name)
    return match.group(1) if match else None


def _load_candidate_cards_for_dates(trade_dates: list[str]) -> list[CandidateCard]:
    cards: list[CandidateCard] = []
    for trade_date in trade_dates:
        path = PROCESSED_DATA_DIR / "candidates" / f"candidate_cards_{trade_date}.json"
        if not path.exists():
            continue
        payload = list(_load_json(path))
        cards.extend(CandidateCard(**item) for item in payload)
    return cards


def _load_trade_plan_cards_for_dates(trade_dates: list[str]) -> list[TradePlanCard]:
    plans: list[TradePlanCard] = []
    for trade_date in trade_dates:
        path = OUTPUTS_DIR / "trade_plans" / f"trade_plan_cards_{trade_date}.json"
        if not path.exists():
            continue
        payload = list(_load_json(path))
        plans.extend(TradePlanCard(**item) for item in payload)
    return plans


def _discover_trade_dates(end_date: str, *, lookback_trade_days: int) -> list[str]:
    candidate_dir = PROCESSED_DATA_DIR / "candidates"
    available = sorted(
        filter(
            None,
            (_extract_date(path, "candidate_cards") for path in candidate_dir.glob("candidate_cards_*.json")),
        )
    )
    filtered = [trade_date for trade_date in available if trade_date <= end_date]
    if lookback_trade_days <= 0:
        return filtered
    return filtered[-lookback_trade_days:]


def build_setup_performance_cli(end_date: str, *, lookback_trade_days: int = 20) -> tuple[Path, Path]:
    trade_dates = _discover_trade_dates(end_date, lookback_trade_days=lookback_trade_days)
    candidate_cards = _load_candidate_cards_for_dates(trade_dates)
    trade_plan_cards = _load_trade_plan_cards_for_dates(trade_dates)
    history = load_stock_history(r"D:\TradingSystem\data\raw\stock_history")
    label = f"{trade_dates[0]}_to_{trade_dates[-1]}" if trade_dates else end_date
    payload = build_setup_performance(label, candidate_cards, trade_plan_cards, history)
    payload["backfill"] = {
        "end_date": end_date,
        "lookback_trade_days": lookback_trade_days,
        "trade_dates": trade_dates,
    }

    json_path = _evaluation_dir() / f"setup_performance_{end_date}.json"
    md_path = _analysis_dir() / f"setup_performance_{end_date}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_setup_performance_markdown(label, payload), encoding="utf-8")
    return json_path, md_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="End date in YYYY-MM-DD format.")
    parser.add_argument("--lookback-trade-days", type=int, default=20, help="How many archived trade dates to include.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    json_path, md_path = build_setup_performance_cli(args.date, lookback_trade_days=args.lookback_trade_days)
    print(f"setup_performance_json={json_path}")
    print(f"setup_performance_md={md_path}")


if __name__ == "__main__":
    main()
