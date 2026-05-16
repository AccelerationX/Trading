from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from trading_system.config.paths import OUTPUTS_DIR
from trading_system.context.market_regime import build_market_regime_snapshot, save_market_regime_snapshot
from trading_system.reporting.market_regime_report import render_market_regime_markdown


def _analysis_output_dir() -> Path:
    directory = OUTPUTS_DIR / "analysis"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def build_market_regime(trade_date: str) -> tuple[Path, Path]:
    snapshot = build_market_regime_snapshot(trade_date=trade_date)
    json_path = save_market_regime_snapshot(snapshot)
    md_path = _analysis_output_dir() / f"market_regime_{trade_date}.md"
    md_path.write_text(render_market_regime_markdown(snapshot), encoding="utf-8")
    return json_path, md_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat(), help="Trade date in YYYY-MM-DD format.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    json_path, md_path = build_market_regime(trade_date=args.date)
    print(f"market_regime_json={json_path}")
    print(f"market_regime_md={md_path}")


if __name__ == "__main__":
    main()
