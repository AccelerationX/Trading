from __future__ import annotations

import argparse
import json
from pathlib import Path

from trading_system.config.paths import PROCESSED_DATA_DIR
from trading_system.context.cards import CapitalBehaviorCard, CandidateCard, EventCard, MarketRegimeSnapshot, ThemeCard, TradePlanCard
from trading_system.context.text_signal_support import load_text_signal_watch
from trading_system.decision.account import AccountConstraints
from trading_system.decision.trade_plan_cards import build_trade_plan_cards, save_trade_plan_cards, trade_plan_output_dir
from trading_system.reporting.trade_plan_reports import render_trade_plan_markdown


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


def _load_candidate_cards(trade_date: str) -> list[CandidateCard]:
    path = PROCESSED_DATA_DIR / "candidates" / f"candidate_cards_{trade_date}.json"
    payload = list(_load_json(path))
    return [CandidateCard(**item) for item in payload]


def _load_supporting_card_labels(trade_date: str) -> dict[str, str]:
    labels: dict[str, str] = {}

    event_path = PROCESSED_DATA_DIR / "events" / f"event_cards_{trade_date}.json"
    if event_path.exists():
        for item in list(_load_json(event_path)):
            card = EventCard(**item)
            labels[card.event_id] = card.event_title

    theme_path = PROCESSED_DATA_DIR / "themes" / f"theme_cards_{trade_date}.json"
    if theme_path.exists():
        for item in list(_load_json(theme_path)):
            card = ThemeCard(**item)
            labels[card.theme_id] = card.theme_name

    capital_path = PROCESSED_DATA_DIR / "capital" / f"capital_behavior_cards_{trade_date}.json"
    if capital_path.exists():
        for item in list(_load_json(capital_path)):
            card = CapitalBehaviorCard(**item)
            labels[card.card_id] = f"{card.stock_code} {card.capital_signal_type}"

    return labels


def _apply_supporting_card_labels(plans: list[TradePlanCard], label_map: dict[str, str]) -> list[TradePlanCard]:
    resolved_plans: list[TradePlanCard] = []
    for plan in plans:
        labels = [label_map.get(card_id, card_id) for card_id in plan.supporting_cards]
        resolved_plans.append(
            TradePlanCard(
                plan_id=plan.plan_id,
                trade_date=plan.trade_date,
                stock_code=plan.stock_code,
                action=plan.action,
                priority_rank=plan.priority_rank,
                rationale=plan.rationale,
                entry_condition=plan.entry_condition,
                entry_zone=plan.entry_zone,
                position_size_rule=plan.position_size_rule,
                max_position_pct=plan.max_position_pct,
                add_reduce_rule=plan.add_reduce_rule,
                invalidation_rule=plan.invalidation_rule,
                exit_rule_hint=plan.exit_rule_hint,
                holding_horizon=plan.holding_horizon,
                risk_notes=list(plan.risk_notes),
                supporting_cards=labels,
                llm_refined_plan=plan.llm_refined_plan,
                llm_execution_watchpoints=list(plan.llm_execution_watchpoints),
                llm_confidence=plan.llm_confidence,
            )
        )
    return resolved_plans


def build_trade_plan_cards_cli(trade_date: str) -> tuple[Path, Path]:
    market_regime = _load_market_regime(trade_date)
    account = _load_account()
    candidate_cards = _load_candidate_cards(trade_date)
    text_watch_records = load_text_signal_watch(trade_date)
    plans = build_trade_plan_cards(
        trade_date,
        market_regime=market_regime,
        account=account,
        candidate_cards=candidate_cards,
        text_watch_records=text_watch_records,
    )
    plans = _apply_supporting_card_labels(plans, _load_supporting_card_labels(trade_date))
    json_path = save_trade_plan_cards(trade_date, plans)
    md_path = trade_plan_output_dir() / f"trade_plan_cards_{trade_date}.md"
    md_path.write_text(render_trade_plan_markdown(trade_date, plans), encoding="utf-8")
    return json_path, md_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Trade date in YYYY-MM-DD format.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    json_path, md_path = build_trade_plan_cards_cli(args.date)
    print(f"trade_plan_cards_json={json_path}")
    print(f"trade_plan_cards_md={md_path}")


if __name__ == "__main__":
    main()
