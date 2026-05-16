from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from trading_system.config.paths import OUTPUTS_DIR, PROCESSED_DATA_DIR
from trading_system.context.cards import MarketRegimeSnapshot
from trading_system.decision.account import load_active_account_constraints
from trading_system.evaluation.module_signal_evaluation import build_module_signal_evaluation
from trading_system.reporting.module_evaluation_reports import render_module_evaluation_markdown
from trading_system.signal.legacy.data_loader import load_stock_history
from trading_system.signal.scanners.registry import load_scanners_for_modules
from trading_system.signal.technical_modules import load_technical_modules


def _processed_dir() -> Path:
    directory = PROCESSED_DATA_DIR / "evaluation"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _analysis_dir() -> Path:
    directory = OUTPUTS_DIR / "analysis"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _placeholder_market_regime(trade_date: str) -> MarketRegimeSnapshot:
    return MarketRegimeSnapshot(
        snapshot_id=f"backfill_{trade_date}",
        trade_date=trade_date,
        market_bias="mixed",
        risk_mode="selective",
        breadth_strength="mixed",
        limit_up_temperature="neutral",
        turnover_regime="normal",
        style_lead="mixed",
        theme_concentration="normal",
        supporting_evidence=[],
    )


def _available_trade_dates(history: pd.DataFrame, end_date: str, lookback_trade_days: int) -> list[str]:
    dates = sorted(
        {
            pd.to_datetime(value).strftime("%Y-%m-%d")
            for value in history["trade_date"].dropna().tolist()
            if pd.to_datetime(value) <= pd.to_datetime(end_date)
        }
    )
    if lookback_trade_days <= 0:
        return dates
    return dates[-lookback_trade_days:]


def backfill_module_evaluation(end_date: str, *, lookback_trade_days: int = 10) -> tuple[Path, Path]:
    history = load_stock_history(r"D:\TradingSystem\data\raw\stock_history")
    account = load_active_account_constraints()
    technical_modules = load_technical_modules()
    scanners = load_scanners_for_modules(technical_modules)
    trade_dates = _available_trade_dates(history, end_date, lookback_trade_days)

    all_signals = []
    warnings: list[str] = []
    for trade_date in trade_dates:
        regime = _placeholder_market_regime(trade_date)
        for module_id, scanner in scanners.items():
            if not scanner.is_available(trade_date):
                warnings.append(f"scanner_unavailable: {module_id} for {trade_date}")
                continue
            try:
                signals = scanner.scan(trade_date, regime, account=account)
            except Exception as exc:
                warnings.append(f"scanner_failed: {module_id}: {trade_date}: {exc.__class__.__name__}: {exc}")
                continue
            all_signals.extend(signals)

    label = f"{trade_dates[0]}_to_{trade_dates[-1]}" if trade_dates else end_date
    payload = build_module_signal_evaluation(
        label,
        module_signals=all_signals,
        history=history,
        market_regime=None,
        candidate_cards=[],
        trade_plan_cards=[],
    )
    payload["backfill"] = {
        "end_date": end_date,
        "lookback_trade_days": lookback_trade_days,
        "trade_dates": trade_dates,
        "warnings": warnings,
        "warning_count": len(warnings),
    }

    suffix = f"{end_date}_last{lookback_trade_days}"
    json_path = _processed_dir() / f"module_evaluation_backfill_{suffix}.json"
    md_path = _analysis_dir() / f"module_evaluation_backfill_{suffix}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = render_module_evaluation_markdown(label, payload)
    if warnings:
        markdown += "\n## Backfill Warnings\n" + "\n".join(f"- {warning}" for warning in warnings[:50]) + "\n"
    md_path.write_text(markdown, encoding="utf-8")
    return json_path, md_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="End date in YYYY-MM-DD format.")
    parser.add_argument("--lookback-trade-days", type=int, default=10, help="How many trade dates to evaluate.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    json_path, md_path = backfill_module_evaluation(
        args.date,
        lookback_trade_days=args.lookback_trade_days,
    )
    print(f"module_evaluation_backfill_json={json_path}")
    print(f"module_evaluation_backfill_md={md_path}")


if __name__ == "__main__":
    main()
