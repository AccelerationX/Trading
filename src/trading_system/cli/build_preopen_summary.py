from __future__ import annotations

import argparse
import json
from pathlib import Path

from trading_system.config.paths import OUTPUTS_DIR, PROCESSED_DATA_DIR
from trading_system.context.cards import CandidateCard, MacroEventCard, MarketRegimeSnapshot, ThemeCard, TradePlanCard
from trading_system.decision.account import AccountConstraints
from trading_system.decision.holdings import (
    PortfolioSnapshot,
    assess_portfolio_positions,
    load_portfolio_snapshot,
)
from trading_system.reporting.preopen_summary import (
    build_preopen_summary_payload,
    preopen_summary_output_dir,
    render_preopen_summary_markdown,
    save_preopen_summary_payload,
)


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_market_regime(trade_date: str) -> MarketRegimeSnapshot:
    path = PROCESSED_DATA_DIR / "context" / f"market_regime_{trade_date}.json"
    return MarketRegimeSnapshot(**dict(_load_json(path)))


def _load_account() -> AccountConstraints:
    path = PROCESSED_DATA_DIR / "account" / "active_account_constraints.json"
    return AccountConstraints(**dict(_load_json(path)))


def _load_candidates(trade_date: str) -> list[CandidateCard]:
    path = PROCESSED_DATA_DIR / "candidates" / f"candidate_cards_{trade_date}.json"
    payload = list(_load_json(path))
    return [CandidateCard(**item) for item in payload]


def _load_trade_plans(trade_date: str) -> list[TradePlanCard]:
    path = OUTPUTS_DIR / "trade_plans" / f"trade_plan_cards_{trade_date}.json"
    payload = list(_load_json(path))
    return [TradePlanCard(**item) for item in payload]


def _load_themes(trade_date: str) -> list[ThemeCard]:
    path = PROCESSED_DATA_DIR / "themes" / f"theme_cards_{trade_date}.json"
    if not path.exists():
        return []
    payload = list(_load_json(path))
    return [ThemeCard(**item) for item in payload]


def _load_macro_events(trade_date: str) -> list[MacroEventCard]:
    path = PROCESSED_DATA_DIR / "macro_events" / f"macro_event_cards_{trade_date}.json"
    if not path.exists():
        return []
    payload = list(_load_json(path))
    return [MacroEventCard(**item) for item in payload]


def _load_setup_performance(trade_date: str) -> dict | None:
    path = PROCESSED_DATA_DIR / "evaluation" / f"setup_performance_{trade_date}.json"
    if not path.exists():
        return None
    return dict(_load_json(path))


def _load_execution_feedback(trade_date: str) -> dict | None:
    path = PROCESSED_DATA_DIR / "evaluation" / f"execution_feedback_{trade_date}.json"
    if not path.exists():
        return None
    return dict(_load_json(path))


def _load_execution_behavior(trade_date: str) -> dict | None:
    path = PROCESSED_DATA_DIR / "evaluation" / f"execution_behavior_{trade_date}.json"
    if not path.exists():
        return None
    return dict(_load_json(path))


def build_preopen_summary(trade_date: str, portfolio: PortfolioSnapshot | None = None) -> tuple[Path, Path]:
    market_regime = _load_market_regime(trade_date)
    account = _load_account()
    candidates = _load_candidates(trade_date)
    trade_plans = _load_trade_plans(trade_date)
    theme_cards = _load_themes(trade_date)
    macro_event_cards = _load_macro_events(trade_date)
    setup_performance = _load_setup_performance(trade_date)
    execution_feedback = _load_execution_feedback(trade_date)
    execution_behavior = _load_execution_behavior(trade_date)
    portfolio_snapshot = portfolio or load_portfolio_snapshot()
    holding_assessments = assess_portfolio_positions(
        portfolio_snapshot,
        account=account,
        trade_date=trade_date,
        candidate_cards=candidates,
        trade_plans=trade_plans,
    )
    payload = build_preopen_summary_payload(
        trade_date=trade_date,
        market_regime=market_regime,
        account=account,
        portfolio=portfolio_snapshot,
        holding_assessments=holding_assessments,
        candidate_cards=candidates,
        trade_plans=trade_plans,
        theme_cards=theme_cards,
        macro_event_cards=macro_event_cards,
        setup_performance=setup_performance,
        execution_feedback=execution_feedback,
        execution_behavior=execution_behavior,
    )
    json_path = save_preopen_summary_payload(trade_date, payload)
    md_path = preopen_summary_output_dir() / f"preopen_summary_{trade_date}.md"
    md_path.write_text(render_preopen_summary_markdown(payload), encoding="utf-8")
    return json_path, md_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Trade date in YYYY-MM-DD format.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    json_path, md_path = build_preopen_summary(args.date)
    print(f"preopen_summary_json={json_path}")
    print(f"preopen_summary_md={md_path}")


if __name__ == "__main__":
    main()
