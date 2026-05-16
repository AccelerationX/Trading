from __future__ import annotations

import argparse
import json
from pathlib import Path

from trading_system.config.paths import OUTPUTS_DIR, PROCESSED_DATA_DIR
from trading_system.context.cards import MarketRegimeSnapshot
from trading_system.reporting.technical_module_report import render_technical_module_recommendation
from trading_system.signal.technical_modules import recommend_modules_for_regime


def _load_market_regime_snapshot(path: Path) -> MarketRegimeSnapshot:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return MarketRegimeSnapshot(**payload)


def _default_market_regime_path(trade_date: str) -> Path:
    return PROCESSED_DATA_DIR / "context" / f"market_regime_{trade_date}.json"


def _analysis_output_dir() -> Path:
    directory = OUTPUTS_DIR / "analysis"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def recommend_technical_modules_cli(trade_date: str, market_regime_path: Path, can_watch_intraday: bool) -> tuple[Path, Path]:
    snapshot = _load_market_regime_snapshot(market_regime_path)
    modules = recommend_modules_for_regime(snapshot, can_watch_intraday=can_watch_intraday)

    json_path = _analysis_output_dir() / f"technical_modules_{trade_date}.json"
    md_path = _analysis_output_dir() / f"technical_modules_{trade_date}.md"

    json_payload = [
        {
            "module_id": module.module_id,
            "family": module.family,
            "role": module.role,
            "priority": module.priority,
            "needs_intraday": module.needs_intraday,
            "description": module.description,
            "legacy_refs": list(module.legacy_refs),
        }
        for module in modules
    ]
    json_path.write_text(json.dumps(json_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_technical_module_recommendation(trade_date, snapshot, modules), encoding="utf-8")
    return json_path, md_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Trade date in YYYY-MM-DD format.")
    parser.add_argument("--market-regime-path", default="", help="Optional market regime JSON path.")
    parser.add_argument("--can-watch-intraday", action="store_true", default=False, help="Whether intraday modules can be recommended.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    market_regime_path = Path(args.market_regime_path) if args.market_regime_path else _default_market_regime_path(args.date)
    json_path, md_path = recommend_technical_modules_cli(
        trade_date=args.date,
        market_regime_path=market_regime_path,
        can_watch_intraday=args.can_watch_intraday,
    )
    print(f"technical_modules_json={json_path}")
    print(f"technical_modules_md={md_path}")


if __name__ == "__main__":
    main()
