from __future__ import annotations

import argparse
import json
from pathlib import Path

from trading_system.config.paths import OUTPUTS_DIR, PROCESSED_DATA_DIR
from trading_system.context.cards import CandidateCard, CapitalBehaviorCard, EventCard, MarketRegimeSnapshot, ThemeCard, TradePlanCard
from trading_system.context.text_signal_support import find_relevant_text_signals, load_text_signal_watch, text_signal_focus_summary
from trading_system.decision.account import AccountConstraints
from trading_system.integrations.llm_contracts import LLMWorkPacket, load_llm_agent_registry, save_llm_workpacks
from trading_system.memory.models import ReviewMemoryEntry
from trading_system.reporting.llm_workpack_reports import render_llm_workpacks_markdown

MAX_EVENT_PACKETS = 120
MAX_THEME_PACKETS = 40
MAX_CAPITAL_PACKETS = 80
MAX_CANDIDATE_PACKETS = 20
MAX_TRADE_PLAN_PACKETS = 20
MAX_REVIEW_MEMORY_PACKETS = 50


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return json.loads(path.read_text(encoding="utf-8-sig"))


def _optional_load_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    payload = _load_json(path)
    return list(payload)


def _load_market_regime(trade_date: str) -> MarketRegimeSnapshot | None:
    path = PROCESSED_DATA_DIR / "context" / f"market_regime_{trade_date}.json"
    if not path.exists():
        return None
    return MarketRegimeSnapshot(**dict(_load_json(path)))


def _load_event_cards(trade_date: str) -> list[EventCard]:
    path = PROCESSED_DATA_DIR / "events" / f"event_cards_{trade_date}.json"
    return [EventCard(**item) for item in _optional_load_list(path)]


def _load_theme_cards(trade_date: str) -> list[ThemeCard]:
    path = PROCESSED_DATA_DIR / "themes" / f"theme_cards_{trade_date}.json"
    return [ThemeCard(**item) for item in _optional_load_list(path)]


def _load_capital_cards(trade_date: str) -> list[CapitalBehaviorCard]:
    path = PROCESSED_DATA_DIR / "capital" / f"capital_behavior_cards_{trade_date}.json"
    return [CapitalBehaviorCard(**item) for item in _optional_load_list(path)]


def _load_candidate_cards(trade_date: str) -> list[CandidateCard]:
    path = PROCESSED_DATA_DIR / "candidates" / f"candidate_cards_{trade_date}.json"
    return [CandidateCard(**item) for item in _optional_load_list(path)]


def _load_trade_plan_cards(trade_date: str) -> list[TradePlanCard]:
    preferred_path = PROCESSED_DATA_DIR / "trade_plans" / f"trade_plan_cards_{trade_date}.json"
    fallback_path = OUTPUTS_DIR / "trade_plans" / f"trade_plan_cards_{trade_date}.json"
    if preferred_path.exists():
        return [TradePlanCard(**item) for item in _optional_load_list(preferred_path)]
    return [TradePlanCard(**item) for item in _optional_load_list(fallback_path)]


def _load_review_memory_entries() -> list[ReviewMemoryEntry]:
    path = PROCESSED_DATA_DIR / "memory" / "review_memory_entries.json"
    return [ReviewMemoryEntry(**item) for item in _optional_load_list(path)]


def _load_account_constraints() -> AccountConstraints | None:
    path = PROCESSED_DATA_DIR / "account" / "active_account_constraints.json"
    if not path.exists():
        return None
    return AccountConstraints(**dict(_load_json(path)))


def _event_packet_rank(card: EventCard) -> tuple[float, float, int]:
    strength = card.event_strength if card.event_strength is not None else 0.0
    novelty = card.novelty_score if card.novelty_score is not None else 0.0
    risk_bonus = 0
    if "negative_event_check" in card.risk_flags:
        risk_bonus += 3
    if "complex_event" in card.risk_flags:
        risk_bonus += 2
    if "proposal_stage" in card.risk_flags:
        risk_bonus += 1
    return (risk_bonus, novelty, strength)


def _theme_packet_rank(card: ThemeCard) -> tuple[int, int, int]:
    missing_industries = 1 if not card.priority_industries else 0
    needs_review = 1 if card.continuation_guess == "needs_review" else 0
    stock_count = len(card.priority_stocks)
    return (missing_industries, needs_review, stock_count)


def _capital_packet_rank(card: CapitalBehaviorCard) -> tuple[int, float, int]:
    warning_score = len(card.warning_flags)
    consistency = card.consistency_score if card.consistency_score is not None else 0.0
    distribution_bonus = 1 if card.support_or_distribution == "distribution" else 0
    return (warning_score + distribution_bonus, consistency, 1 if card.participation_strength == "high" else 0)


def _should_send_event_card(card: EventCard) -> bool:
    if "needs_llm_review" not in card.risk_flags:
        return False
    if "negative_event_check" in card.risk_flags or "complex_event" in card.risk_flags:
        return True
    novelty = card.novelty_score if card.novelty_score is not None else 0.0
    strength = card.event_strength if card.event_strength is not None else 0.0
    return novelty >= 0.6 or strength >= 0.7 or bool(card.industry_tags)


def _event_watch_priority(card: EventCard, text_watch_records: list[dict]) -> int:
    relevant = []
    for stock_code in card.stock_codes:
        relevant.extend(find_relevant_text_signals(text_watch_records, stock_code=stock_code, industry_tags=card.industry_tags, limit=2))
    if not relevant:
        return 0
    return max(int(record.get("priority_score", 0) or 0) for record in relevant)


def _should_send_theme_card(card: ThemeCard) -> bool:
    return card.continuation_guess == "needs_review" or not card.priority_industries or not card.priority_stocks


def _theme_watch_priority(card: ThemeCard, text_watch_records: list[dict]) -> int:
    relevant = []
    for stock_code in card.priority_stocks[:3]:
        relevant.extend(find_relevant_text_signals(text_watch_records, stock_code=stock_code, industry_tags=card.priority_industries, limit=2))
    if not relevant:
        relevant = find_relevant_text_signals(text_watch_records, industry_tags=card.priority_industries, limit=2)
    if not relevant:
        return 0
    return max(int(record.get("priority_score", 0) or 0) for record in relevant)


def _should_send_capital_card(card: CapitalBehaviorCard) -> bool:
    consistency = card.consistency_score if card.consistency_score is not None else 0.0
    if card.warning_flags:
        return True
    if card.participation_strength == "high" and consistency >= 0.85:
        return True
    return card.support_or_distribution == "distribution" and consistency >= 0.75


def _should_send_trade_plan(plan: TradePlanCard, candidate: CandidateCard | None) -> bool:
    if plan.action == "buy_pilot":
        return True
    if plan.action != "watch_only":
        return False
    candidate_score = candidate.candidate_score if candidate and candidate.candidate_score is not None else 0.0
    return plan.priority_rank <= 8 and candidate_score >= 0.65


def _should_send_candidate(candidate: CandidateCard) -> bool:
    score = candidate.candidate_score if candidate.candidate_score is not None else 0.0
    if candidate.tradeability_verdict in {"too_concentrated", "blocked_by_budget"}:
        return True
    if candidate.candidate_source.startswith("module_") and not candidate.supporting_cards:
        return score >= 0.6
    return score >= 0.62


def _candidate_watch_priority(candidate: CandidateCard, text_watch_records: list[dict]) -> int:
    relevant = find_relevant_text_signals(text_watch_records, stock_code=candidate.stock_code, limit=2)
    if not relevant:
        return 0
    return max(int(record.get("priority_score", 0) or 0) for record in relevant)


def _trade_plan_watch_priority(plan: TradePlanCard, text_watch_records: list[dict]) -> int:
    relevant = find_relevant_text_signals(text_watch_records, stock_code=plan.stock_code, limit=2)
    if not relevant:
        return 0
    return max(int(record.get("priority_score", 0) or 0) for record in relevant)


def _event_brief(card: EventCard) -> dict:
    return {
        "event_id": card.event_id,
        "event_title": card.event_title,
        "event_type": card.event_type,
        "bullish_bearish": card.bullish_bearish,
        "event_strength": card.event_strength,
        "industry_tags": list(card.industry_tags),
        "core_claim": card.core_claim,
        "risk_flags": list(card.risk_flags),
        "llm_summary": card.llm_summary,
    }


def _theme_brief(card: ThemeCard) -> dict:
    return {
        "theme_id": card.theme_id,
        "theme_name": card.theme_name,
        "trigger_type": card.trigger_type,
        "priority_industries": list(card.priority_industries),
        "priority_stocks": list(card.priority_stocks[:5]),
        "continuation_guess": card.continuation_guess,
        "market_confirmation_needed": list(card.market_confirmation_needed),
        "contra_risks": list(card.contra_risks),
        "llm_summary": card.llm_summary,
    }


def _capital_brief(card: CapitalBehaviorCard) -> dict:
    return {
        "card_id": card.card_id,
        "capital_signal_type": card.capital_signal_type,
        "participation_strength": card.participation_strength,
        "consistency_score": card.consistency_score,
        "suspected_style": card.suspected_style,
        "support_or_distribution": card.support_or_distribution,
        "warning_flags": list(card.warning_flags),
        "llm_summary": card.llm_summary,
    }


def _candidate_brief(card: CandidateCard | None) -> dict:
    if card is None:
        return {}
    return {
        "candidate_id": card.candidate_id,
        "candidate_source": card.candidate_source,
        "candidate_score": card.candidate_score,
        "technical_state": card.technical_state,
        "event_support_score": card.event_support_score,
        "theme_alignment_score": card.theme_alignment_score,
        "capital_confirmation_score": card.capital_confirmation_score,
        "market_fit_score": card.market_fit_score,
        "account_fit_score": card.account_fit_score,
        "last_close_price": card.last_close_price,
        "estimated_min_lot_cost": card.estimated_min_lot_cost,
        "account_tradeability_score": card.account_tradeability_score,
        "tradeability_verdict": card.tradeability_verdict,
        "active_module_ids": list(card.active_module_ids),
        "disqualify_flags": list(card.disqualify_flags),
        "candidate_rationale": card.candidate_rationale,
        "diagnostic_summary": card.diagnostic_summary,
        "diagnostic_risk_notes": list(card.diagnostic_risk_notes),
    }


def _account_brief(account: AccountConstraints | None) -> dict:
    if account is None:
        return {}
    return {
        "profile_name": account.profile_name,
        "capital_total": account.capital_total,
        "single_position_max_pct": account.single_position_max_pct,
        "single_trade_capital_max": account.single_trade_capital_max,
        "max_holdings": account.max_holdings,
        "max_new_positions_per_day": account.max_new_positions_per_day,
        "preferred_holding_horizon_days": account.preferred_holding_horizon_days,
        "can_watch_intraday": account.can_watch_intraday,
        "avoid_chasing_limit_up": account.avoid_chasing_limit_up,
        "avoid_low_liquidity": account.avoid_low_liquidity,
        "board_lot_size": account.board_lot_size,
        "single_lot_alert_capital_pct": account.single_lot_alert_capital_pct,
        "single_lot_block_capital_pct": account.single_lot_block_capital_pct,
        "execution_mode": account.execution_mode,
        "notes": account.notes,
    }


def _event_briefs_for_candidate(candidate: CandidateCard, event_cards: list[EventCard]) -> list[dict]:
    event_map = {card.event_id: card for card in event_cards}
    return [_event_brief(event_map[ref]) for ref in candidate.supporting_cards if ref in event_map][:4]


def _theme_briefs_for_candidate(candidate: CandidateCard, theme_cards: list[ThemeCard]) -> list[dict]:
    theme_map = {card.theme_id: card for card in theme_cards}
    return [_theme_brief(theme_map[ref]) for ref in candidate.supporting_cards if ref in theme_map][:3]


def _market_brief(snapshot: MarketRegimeSnapshot | None) -> dict:
    if snapshot is None:
        return {}
    return {
        "market_bias": snapshot.market_bias,
        "risk_mode": snapshot.risk_mode,
        "breadth_strength": snapshot.breadth_strength,
        "limit_up_temperature": snapshot.limit_up_temperature,
        "turnover_regime": snapshot.turnover_regime,
        "style_lead": snapshot.style_lead,
        "theme_concentration": snapshot.theme_concentration,
        "opening_risk_note": snapshot.opening_risk_note,
        "supporting_evidence": list(snapshot.supporting_evidence[:5]),
    }


def build_llm_workpacks(trade_date: str) -> list[LLMWorkPacket]:
    registry = {spec.agent_id: spec for spec in load_llm_agent_registry()}
    market_regime = _load_market_regime(trade_date)
    account_constraints = _load_account_constraints()
    text_watch_records = load_text_signal_watch(trade_date)
    packets: list[LLMWorkPacket] = []

    event_spec = registry["event_deepening_agent"]
    event_cards = [card for card in _load_event_cards(trade_date) if _should_send_event_card(card)]
    event_cards.sort(key=lambda card: (_event_watch_priority(card, text_watch_records), *_event_packet_rank(card)), reverse=True)
    for idx, card in enumerate(event_cards[:MAX_EVENT_PACKETS], start=1):
        watch_records = []
        for stock_code in card.stock_codes:
            watch_records.extend(find_relevant_text_signals(text_watch_records, stock_code=stock_code, industry_tags=card.industry_tags, limit=2))
        packets.append(
            LLMWorkPacket(
                packet_id=f"{trade_date}_{event_spec.agent_id}_{card.event_id}",
                trade_date=trade_date,
                agent_id=event_spec.agent_id,
                task_id=event_spec.task_id,
                priority=event_spec.priority,
                target_object_type="event_card",
                target_object_id=card.event_id,
                prompt_file=event_spec.prompt_file,
                sort_rank=1000 + idx,
                input_refs=[card.event_id, *card.source_refs],
                context_payload={
                    "event_title": card.event_title,
                    "event_type": card.event_type,
                    "stock_codes": card.stock_codes,
                    "industry_tags": card.industry_tags,
                    "publish_time": card.publish_time,
                    "core_claim": card.core_claim,
                    "text_watch_titles": [record.get("title", "") for record in watch_records[:2]],
                },
                expected_output_contract=event_spec.output_contract,
                notes=[
                    "rules_triggered=needs_llm_review",
                    f"text_watch_focus={text_signal_focus_summary(watch_records)}" if watch_records else "text_watch_focus=none",
                ],
            )
        )

    theme_spec = registry["theme_deepening_agent"]
    theme_cards = [card for card in _load_theme_cards(trade_date) if _should_send_theme_card(card)]
    theme_cards.sort(key=lambda card: (_theme_watch_priority(card, text_watch_records), *_theme_packet_rank(card)), reverse=True)
    for idx, card in enumerate(theme_cards[:MAX_THEME_PACKETS], start=1):
        watch_records = []
        for stock_code in card.priority_stocks[:3]:
            watch_records.extend(find_relevant_text_signals(text_watch_records, stock_code=stock_code, industry_tags=card.priority_industries, limit=2))
        if not watch_records:
            watch_records = find_relevant_text_signals(text_watch_records, industry_tags=card.priority_industries, limit=2)
        packets.append(
            LLMWorkPacket(
                packet_id=f"{trade_date}_{theme_spec.agent_id}_{card.theme_id}",
                trade_date=trade_date,
                agent_id=theme_spec.agent_id,
                task_id=theme_spec.task_id,
                priority=theme_spec.priority,
                target_object_type="theme_card",
                target_object_id=card.theme_id,
                prompt_file=theme_spec.prompt_file,
                sort_rank=2000 + idx,
                input_refs=[card.theme_id, *card.source_refs],
                context_payload={
                    "theme_name": card.theme_name,
                    "trigger_type": card.trigger_type,
                    "beneficiary_chain": card.beneficiary_chain,
                    "priority_industries": card.priority_industries,
                    "priority_stocks": card.priority_stocks,
                    "text_watch_titles": [record.get("title", "") for record in watch_records[:2]],
                },
                expected_output_contract=theme_spec.output_contract,
                notes=[
                    "rules_triggered=theme_needs_mapping",
                    f"text_watch_focus={text_signal_focus_summary(watch_records)}" if watch_records else "text_watch_focus=none",
                ],
            )
        )

    capital_spec = registry["capital_interpret_agent"]
    capital_cards = [card for card in _load_capital_cards(trade_date) if _should_send_capital_card(card)]
    capital_cards.sort(key=_capital_packet_rank, reverse=True)
    for idx, card in enumerate(capital_cards[:MAX_CAPITAL_PACKETS], start=1):
        packets.append(
            LLMWorkPacket(
                packet_id=f"{trade_date}_{capital_spec.agent_id}_{card.card_id}",
                trade_date=trade_date,
                agent_id=capital_spec.agent_id,
                task_id=capital_spec.task_id,
                priority=capital_spec.priority,
                target_object_type="capital_behavior_card",
                target_object_id=card.card_id,
                prompt_file=capital_spec.prompt_file,
                sort_rank=3000 + idx,
                input_refs=[card.card_id, *card.source_refs],
                context_payload={
                    "stock_code": card.stock_code,
                    "capital_signal_type": card.capital_signal_type,
                    "participation_strength": card.participation_strength,
                    "suspected_style": card.suspected_style,
                    "support_or_distribution": card.support_or_distribution,
                    "warning_flags": card.warning_flags,
                },
                expected_output_contract=capital_spec.output_contract,
                notes=["rules_triggered=high_strength_or_warning"],
            )
        )

    candidate_map = {card.stock_code: card for card in _load_candidate_cards(trade_date)}
    event_map = {card.event_id: card for card in event_cards}
    theme_map = {card.theme_id: card for card in theme_cards}
    capital_map: dict[str, list[CapitalBehaviorCard]] = {}
    for card in capital_cards:
        capital_map.setdefault(card.stock_code, []).append(card)

    candidate_spec = registry["candidate_diagnosis_agent"]
    selected_candidates = [card for card in candidate_map.values() if _should_send_candidate(card)]
    selected_candidates.sort(
        key=lambda card: (
            0 if card.tradeability_verdict in {"too_concentrated", "blocked_by_budget"} else 1,
            -_candidate_watch_priority(card, text_watch_records),
            -(card.candidate_score if card.candidate_score is not None else 0.0),
            card.stock_code,
        )
    )
    for idx, candidate in enumerate(selected_candidates[:MAX_CANDIDATE_PACKETS], start=1):
        watch_records = find_relevant_text_signals(text_watch_records, stock_code=candidate.stock_code, limit=2)
        packets.append(
            LLMWorkPacket(
                packet_id=f"{trade_date}_{candidate_spec.agent_id}_{candidate.candidate_id}",
                trade_date=trade_date,
                agent_id=candidate_spec.agent_id,
                task_id=candidate_spec.task_id,
                priority=candidate_spec.priority,
                target_object_type="candidate_card",
                target_object_id=candidate.candidate_id,
                prompt_file=candidate_spec.prompt_file,
                sort_rank=idx,
                input_refs=[candidate.candidate_id, *candidate.supporting_cards],
                context_payload={
                    "stock_code": candidate.stock_code,
                    "candidate": _candidate_brief(candidate),
                    "market_snapshot": _market_brief(market_regime),
                    "account_constraints": _account_brief(account_constraints),
                    "supporting_events": _event_briefs_for_candidate(candidate, event_cards),
                    "supporting_themes": _theme_briefs_for_candidate(candidate, theme_cards),
                    "supporting_capital_behavior": [
                        _capital_brief(card) for card in capital_map.get(candidate.stock_code, [])[:3]
                    ],
                    "text_watch_titles": [record.get("title", "") for record in watch_records[:2]],
                    "text_watch_focus": text_signal_focus_summary(watch_records) if watch_records else "",
                },
                expected_output_contract=candidate_spec.output_contract,
                notes=[
                    "rules_triggered=candidate_diagnosis",
                    f"text_watch_focus={text_signal_focus_summary(watch_records)}" if watch_records else "text_watch_focus=none",
                ],
            )
        )
    plan_spec = registry["trade_plan_refine_agent"]
    selected_plans: list[tuple[TradePlanCard, CandidateCard | None]] = []
    for plan in _load_trade_plan_cards(trade_date):
        candidate = candidate_map.get(plan.stock_code)
        if not _should_send_trade_plan(plan, candidate):
            continue
        selected_plans.append((plan, candidate))
    selected_plans.sort(
        key=lambda item: (
            0 if item[0].action == "buy_pilot" else 1,
            -_trade_plan_watch_priority(item[0], text_watch_records),
            item[0].priority_rank,
            -((item[1].candidate_score if item[1] and item[1].candidate_score is not None else 0.0)),
        )
    )
    for idx, (plan, candidate) in enumerate(selected_plans[:MAX_TRADE_PLAN_PACKETS], start=1):
        watch_records = find_relevant_text_signals(text_watch_records, stock_code=plan.stock_code, limit=2)
        supporting_events = [_event_brief(event_map[ref]) for ref in plan.supporting_cards if ref in event_map]
        supporting_themes = [_theme_brief(theme_map[ref]) for ref in plan.supporting_cards if ref in theme_map]
        supporting_capital = [_capital_brief(card) for card in capital_map.get(plan.stock_code, [])[:3]]
        packets.append(
            LLMWorkPacket(
                packet_id=f"{trade_date}_{plan_spec.agent_id}_{plan.plan_id}",
                trade_date=trade_date,
                agent_id=plan_spec.agent_id,
                task_id=plan_spec.task_id,
                priority=plan_spec.priority,
                target_object_type="trade_plan_card",
                target_object_id=plan.plan_id,
                prompt_file=plan_spec.prompt_file,
                sort_rank=4000 + idx,
                input_refs=[plan.plan_id, *(plan.supporting_cards or [])],
                context_payload={
                    "stock_code": plan.stock_code,
                    "action": plan.action,
                    "priority_rank": plan.priority_rank,
                    "plan_rationale": plan.rationale,
                    "entry_condition": plan.entry_condition,
                    "entry_zone": plan.entry_zone,
                    "position_size_rule": plan.position_size_rule,
                    "max_position_pct": plan.max_position_pct,
                    "add_reduce_rule": plan.add_reduce_rule,
                    "invalidation_rule": plan.invalidation_rule,
                    "exit_rule_hint": plan.exit_rule_hint,
                    "holding_horizon": plan.holding_horizon,
                    "risk_notes": list(plan.risk_notes),
                    "candidate": _candidate_brief(candidate),
                    "market_snapshot": _market_brief(market_regime),
                    "account_constraints": _account_brief(account_constraints),
                    "supporting_events": supporting_events[:4],
                    "supporting_themes": supporting_themes[:3],
                    "supporting_capital_behavior": supporting_capital,
                    "text_watch_titles": [record.get("title", "") for record in watch_records[:2]],
                    "text_watch_focus": text_signal_focus_summary(watch_records) if watch_records else "",
                    "text_watch_records": [
                        {
                            "priority_score": record.get("priority_score"),
                            "title": record.get("title", ""),
                            "summary_text": record.get("summary_text", ""),
                            "source_id": record.get("source_id", ""),
                            "publish_time": record.get("publish_time", ""),
                        }
                        for record in watch_records[:2]
                    ],
                },
                expected_output_contract=plan_spec.output_contract,
                notes=[
                    "rules_triggered=tradable_plan_refinement",
                    f"text_watch_focus={text_signal_focus_summary(watch_records)}" if watch_records else "text_watch_focus=none",
                ],
            )
        )

    review_spec = registry["review_memory_agent"]
    review_entries = _load_review_memory_entries()
    review_entries.sort(key=lambda item: ((item.confidence if item.confidence is not None else 0.0), item.trade_date), reverse=True)
    for idx, entry in enumerate(review_entries[:MAX_REVIEW_MEMORY_PACKETS], start=1):
        packets.append(
            LLMWorkPacket(
                packet_id=f"{trade_date}_{review_spec.agent_id}_{entry.memory_id}",
                trade_date=trade_date,
                agent_id=review_spec.agent_id,
                task_id=review_spec.task_id,
                priority=review_spec.priority,
                target_object_type="review_memory_entry",
                target_object_id=entry.memory_id,
                prompt_file=review_spec.prompt_file,
                sort_rank=5000 + idx,
                input_refs=[entry.memory_id, *entry.source_refs],
                context_payload={
                    "stock_code": entry.stock_code,
                    "action": entry.action,
                    "outcome_tag": entry.outcome_tag,
                    "setup_tags": entry.setup_tags,
                    "lesson_summary": entry.lesson_summary,
                },
                expected_output_contract=review_spec.output_contract,
                notes=["rules_triggered=always"],
            )
        )

    priority_order = {"high": 0, "medium": 1, "low": 2}
    packets.sort(key=lambda item: (priority_order.get(item.priority, 9), item.sort_rank, item.agent_id, item.target_object_id))
    return packets


def build_llm_workpacks_cli(trade_date: str) -> tuple[Path, Path]:
    packets = build_llm_workpacks(trade_date)
    json_path = save_llm_workpacks(trade_date, packets)
    md_path = json_path.with_suffix(".md")
    md_path.write_text(render_llm_workpacks_markdown(trade_date, packets), encoding="utf-8")
    return json_path, md_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Trade date in YYYY-MM-DD format.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    json_path, md_path = build_llm_workpacks_cli(args.date)
    print(f"llm_workpacks_json={json_path}")
    print(f"llm_workpacks_md={md_path}")


if __name__ == "__main__":
    main()
