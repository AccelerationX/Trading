from __future__ import annotations

import argparse
from pathlib import Path

from trading_system.config.paths import OUTPUTS_DIR
from trading_system.decision.holdings import default_holdings_path, save_normalized_portfolio_snapshot, load_portfolio_snapshot
from trading_system.decision.live_trade_state import (
    default_trade_log_path,
    sync_trade_execution_file_to_live_state,
)


def sync_trade_execution_to_live_state(
    trade_date: str,
    *,
    trade_execution_path: Path | None = None,
    holdings_path: Path | None = None,
    trade_log_path: Path | None = None,
) -> tuple[Path, Path, Path]:
    execution_path = trade_execution_path or (OUTPUTS_DIR / "trade_execution" / f"trade_execution_{trade_date}.json")
    holdings_output, trade_log_output = sync_trade_execution_file_to_live_state(
        trade_date,
        trade_execution_path=execution_path,
        holdings_path=holdings_path or default_holdings_path(),
        trade_log_path=trade_log_path or default_trade_log_path(),
    )
    normalized_holdings = save_normalized_portfolio_snapshot(load_portfolio_snapshot(holdings_output))
    return holdings_output, trade_log_output, normalized_holdings


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Trade date in YYYY-MM-DD format.")
    parser.add_argument(
        "--trade-execution-path",
        default="",
        help="Optional explicit trade execution JSON path.",
    )
    parser.add_argument(
        "--holdings-path",
        default=str(default_holdings_path()),
        help="Editable holdings JSON path.",
    )
    parser.add_argument(
        "--trade-log-path",
        default=str(default_trade_log_path()),
        help="System trade log JSON path.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    holdings_output, trade_log_output, normalized_holdings = sync_trade_execution_to_live_state(
        args.date,
        trade_execution_path=Path(args.trade_execution_path) if args.trade_execution_path else None,
        holdings_path=Path(args.holdings_path),
        trade_log_path=Path(args.trade_log_path),
    )
    print(f"auto_holdings_json={holdings_output}")
    print(f"system_trade_log_json={trade_log_output}")
    print(f"holdings_snapshot_json={normalized_holdings}")


if __name__ == "__main__":
    main()
