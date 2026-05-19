from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from trading_system.config.paths import OUTPUTS_DIR
from trading_system.context.cards import CandidateCard, MarketRegimeSnapshot, TradePlanCard
from trading_system.context.text_signal_support import find_relevant_text_signals, load_text_signal_watch, text_signal_bias, text_signal_focus_summary
from trading_system.decision.account import AccountConstraints, is_small_capital_aggressive
from trading_system.decision.market_gate import evaluate_market_gate
from trading_system.utils.main_board import is_main_board


def trade_plan_output_dir() -> Path:
    directory = OUTPUTS_DIR / "trade_plans"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _entry_condition(card: CandidateCard, snapshot: MarketRegimeSnapshot) -> str:
    mapping = {
        "event_theme_resonance": "Enter only if opening strength holds and the first pullback remains orderly with theme leader confirmation.",
        "selective_repair_watch": "Enter only on a controlled pullback with stable breadth and no early failure pattern.",
        "theme_rotation_watch": "Enter only if the theme remains among the strongest groups after the open.",
        "event_breakout_watch": "Enter only if breakout strength holds with volume confirmation.",
        "defensive_scan_only": "Do not open proactive longs unless market risk improves intraday.",
        "ranked_watchlist": "Enter only after relative-strength confirmation versus the watchlist.",
    }
    default = "Enter only after technical confirmation and stable market breadth."
    if snapshot.risk_mode == "risk_off":
        return "Do not open proactive longs while the market remains risk_off."
    return mapping.get(card.technical_state, default)


def _entry_zone(card: CandidateCard) -> str:
    mapping = {
        "event_theme_resonance": "opening confirmation or first pullback above prior close/VWAP",
        "selective_repair_watch": "pullback near support rather than chasing strength",
        "theme_rotation_watch": "leader confirms and sector breadth expands",
        "event_breakout_watch": "breakout retest or strong opening anchor",
        "defensive_scan_only": "no active entry zone",
        "ranked_watchlist": "watchlist breakout confirmation zone",
    }
    return mapping.get(card.technical_state, "confirmation zone")


def _position_multiplier(snapshot: MarketRegimeSnapshot, card: CandidateCard) -> float:
    if snapshot.risk_mode == "risk_on":
        base = 0.7
    elif snapshot.risk_mode == "selective":
        base = 0.45
    else:
        return 0.0

    score = card.fusion_score if card.fusion_score is not None else card.candidate_score if card.candidate_score is not None else 0.0
    if score >= 0.8:
        base *= 1.0
    elif score >= 0.7:
        base *= 0.8
    else:
        base *= 0.6

    if card.fusion_verdict == "actionable":
        base *= 1.05
    elif card.fusion_verdict == "avoid":
        return 0.0

    if "avoid_chasing_limit_up" in card.disqualify_flags:
        base *= 0.85
    if "bearish_event_overhang" in card.disqualify_flags:
        base *= 0.6
    if card.setup_type == "leader_acceleration":
        base *= 1.05
    elif card.setup_type == "defensive_only":
        base *= 0.65
    return base


def _effective_trade_budget(account: AccountConstraints) -> float:
    liquid_cap = float(account.capital_total or 0.0) * max(0.0, 1.0 - float(account.capital_liquid_ratio_min or 0.0))
    trade_cap = float(account.single_trade_capital_max or 0.0)
    if trade_cap <= 0:
        return max(0.0, liquid_cap)
    return max(0.0, min(liquid_cap, trade_cap))


def _position_size_rule(account: AccountConstraints, snapshot: MarketRegimeSnapshot, card: CandidateCard) -> tuple[str, float | None]:
    if snapshot.risk_mode == "risk_off":
        return "No new long position while market is risk_off.", None
    aggressive = is_small_capital_aggressive(account)
    multiplier = _position_multiplier(snapshot, card)
    if multiplier <= 0.0:
        return "No new long position under current constraints.", None
    effective_budget = _effective_trade_budget(account)
    if card.estimated_min_lot_cost is not None and card.estimated_min_lot_cost > effective_budget:
        return "One board lot already exceeds the current executable trade budget. Keep it on watch only.", None
    policy_position_multiplier = card.setup_position_cap_multiplier if card.setup_position_cap_multiplier is not None else 1.0
    max_position_cap = account.max_setup_exposure if aggressive else account.single_position_max_pct
    max_position_cap *= policy_position_multiplier
    max_position_pct = round(min(account.single_position_max_pct * multiplier, max_position_cap), 4)
    initial_pct = round(max_position_pct * (0.65 if aggressive else 0.5), 4)
    if card.estimated_min_lot_cost is not None and card.last_close_price is not None:
        initial_budget = float(account.capital_total or 0.0) * initial_pct
        max_budget = float(account.capital_total or 0.0) * max_position_pct
        lot_cost = card.estimated_min_lot_cost
        if lot_cost > initial_budget:
            rule = (
                f"One board lot costs about {lot_cost:.0f} CNY at {card.last_close_price:.2f}. "
                f"A normal pilot would be too small, so wait for stronger confirmation before taking a concentrated first lot."
            )
        else:
            initial_lots = max(1, int(initial_budget // lot_cost))
            max_lots = max(initial_lots, int(max_budget // lot_cost))
            rule = (
                f"Pilot size is about {initial_lots} lot(s) ({initial_lots * account.board_lot_size} shares). "
                f"Do not exceed {max_lots} lot(s) before a second confirmation."
            )
    else:
        rule = (
            f"Start with about {initial_pct:.2%} of portfolio as a pilot. "
            f"Only add toward the {max_position_pct:.2%} cap after confirmation."
        )
    return rule, max_position_pct


def _invalidation_rule(card: CandidateCard, snapshot: MarketRegimeSnapshot) -> str:
    if snapshot.risk_mode == "risk_off":
        return "Abort long idea if market stays risk_off or breadth deteriorates further."
    if card.technical_state == "event_theme_resonance":
        return "Invalidate if the event thesis loses theme confirmation or the opening strength fails quickly."
    if card.technical_state == "selective_repair_watch":
        return "Invalidate if rebound turns into weak follow-through or support breaks."
    if card.technical_state == "theme_rotation_watch":
        return "Invalidate if the theme falls out of the leading groups intraday."
    if card.technical_state == "event_breakout_watch":
        return "Invalidate if breakout cannot hold or volume confirmation disappears."
    return "Invalidate if relative strength fades and market breadth does not confirm."


def _holding_horizon(account: AccountConstraints) -> str:
    days = account.preferred_holding_horizon_days
    if days <= 1:
        return "intraday_to_1_day"
    if days <= 3:
        return "1_to_3_days"
    if days <= 7:
        return "3_to_7_days"
    return f"{days}_day_plus"


def _plan_universe_limit(account: AccountConstraints) -> int:
    aggressive = is_small_capital_aggressive(account)
    action_slots = max(0, min(account.max_new_positions_per_day, account.max_holdings))
    if account.can_watch_intraday:
        hard_cap = 6 if aggressive else 10
    else:
        hard_cap = 4 if aggressive else 6

    base = max(action_slots + 2, account.max_holdings * 2)
    return max(action_slots, min(hard_cap, base))


def _minimum_watch_score(snapshot: MarketRegimeSnapshot) -> float:
    if snapshot.risk_mode == "risk_on":
        return 0.55
    if snapshot.risk_mode == "selective":
        return 0.60
    return 1.0


def _fallback_setup_type(card: CandidateCard) -> str:
    if card.setup_type:
        return card.setup_type
    if card.technical_state == "selective_repair_watch":
        return "dip_to_consensus"
    if card.technical_state == "theme_rotation_watch":
        return "trend_follow_thrust"
    if card.technical_state in {"event_theme_resonance", "event_breakout_watch"}:
        if "theme" in card.candidate_source or card.candidate_source == "full_resonance":
            return "leader_acceleration"
        return "event_ignition"
    return "defensive_only"


def build_trade_plan_cards(
    trade_date: str,
    market_regime: MarketRegimeSnapshot,
    account: AccountConstraints,
    candidate_cards: list[CandidateCard],
    text_watch_records: list[dict] | None = None,
) -> list[TradePlanCard]:
    text_watch_records = text_watch_records if text_watch_records is not None else load_text_signal_watch(trade_date)
    gate = evaluate_market_gate(market_regime, account)
    action_slots = gate.max_new_positions
    plan_universe_limit = _plan_universe_limit(account)
    min_watch_score = _minimum_watch_score(market_regime)
    eligible_candidates = candidate_cards
    if account.main_board_only:
        eligible_candidates = [c for c in eligible_candidates if is_main_board(c.stock_code)]
    if market_regime.risk_mode != "risk_off":
        filtered_candidates: list[CandidateCard] = []
        for index, candidate in enumerate(eligible_candidates, start=1):
            score = candidate.candidate_score if candidate.candidate_score is not None else 0.0
            if index <= action_slots or score >= min_watch_score:
                filtered_candidates.append(candidate)
        eligible_candidates = filtered_candidates
    eligible_candidates = eligible_candidates[:plan_universe_limit]
    plans: list[TradePlanCard] = []

    for rank, card in enumerate(eligible_candidates, start=1):
        setup_type = _fallback_setup_type(card)
        market_gate_pass = card.market_gate_pass if card.setup_type else setup_type in gate.allowed_setups
        market_gate_reason = card.market_gate_reason or ("allowed" if market_gate_pass else f"blocked_setup:{setup_type}")
        severe_flags = {
            "account_blocks_new_positions",
            "no_trade_budget",
            "bearish_event_overhang",
            "text_watch_risk_overhang",
            "min_lot_exceeds_trade_budget",
            "fusion_avoid",
        }
        has_severe_flag = any(flag in severe_flags for flag in card.disqualify_flags)
        score = card.fusion_score if card.fusion_score is not None else card.candidate_score if card.candidate_score is not None else 0.0
        setup_action_floor = card.setup_action_floor if card.setup_action_floor is not None else 0.60
        relevant_text_signals = find_relevant_text_signals(text_watch_records, stock_code=card.stock_code, limit=2)
        text_bias = text_signal_bias(relevant_text_signals)
        concentration_block = "min_lot_too_concentrated" in card.disqualify_flags
        fusion_actionable = card.fusion_verdict == "actionable" or (
            not card.fusion_verdict
            and score >= 0.60
            and (card.market_permission_score if card.market_permission_score is not None else 0.55) >= 0.50
            and (card.technical_confirmation_score if card.technical_confirmation_score is not None else 0.50) >= 0.44
            and (card.execution_readiness_score if card.execution_readiness_score is not None else 0.50) >= 0.38
        )

        if has_severe_flag:
            action = "avoid"
        elif not market_gate_pass:
            action = "watch_only" if setup_type in gate.allowed_setups else "avoid"
        elif market_regime.risk_mode == "risk_off":
            action = "watch_only"
        elif concentration_block:
            action = "watch_only"
        elif card.setup_policy_status == "disabled":
            action = "avoid"
        elif card.setup_policy_status == "cautious":
            action = "watch_only"
        elif (
            fusion_actionable
            and rank <= action_slots
            and score >= setup_action_floor
            and (card.market_permission_score if card.market_permission_score is not None else 0.55) >= 0.50
            and (card.technical_confirmation_score if card.technical_confirmation_score is not None else 0.50) >= 0.44
            and (card.execution_readiness_score if card.execution_readiness_score is not None else 0.50) >= 0.38
            and setup_type in gate.allowed_setups
        ):
            action = "buy_pilot"
        else:
            action = "watch_only"

        if action == "buy_pilot" and gate.only_core_allowed and setup_type in {"event_ignition", "trend_follow_thrust"}:
            action = "watch_only"

        position_size_rule, max_position_pct = _position_size_rule(account, market_regime, card)
        if action != "buy_pilot":
            max_position_pct = None
            if action == "watch_only":
                position_size_rule = "Observe first. Do not allocate until entry conditions are confirmed."
            else:
                position_size_rule = "Do not allocate capital under current constraints."

        rationale_parts = [
            f"candidate_score={score:.2f}",
            f"fusion_verdict={card.fusion_verdict or 'none'}",
            f"setup_type={setup_type or 'none'}",
            f"setup_policy={card.setup_policy_status or 'none'}",
            f"setup_action_floor={setup_action_floor:.2f}",
            f"setup_confidence={(card.setup_confidence if card.setup_confidence is not None else 0.0):.2f}",
            f"market_gate={market_gate_reason}",
            f"dominant_driver={card.dominant_driver or 'none'}",
            f"technical_state={card.technical_state}",
            f"source={card.candidate_source}",
        ]
        if card.market_permission_score is not None:
            rationale_parts.append(f"market_permission={card.market_permission_score:.2f}")
        if card.thesis_quality_score is not None:
            rationale_parts.append(f"thesis_quality={card.thesis_quality_score:.2f}")
        if card.technical_confirmation_score is not None:
            rationale_parts.append(f"technical_confirmation={card.technical_confirmation_score:.2f}")
        if card.execution_readiness_score is not None:
            rationale_parts.append(f"execution_readiness={card.execution_readiness_score:.2f}")
        if card.tradeability_verdict:
            rationale_parts.append(f"tradeability={card.tradeability_verdict}")
        if card.active_module_ids:
            rationale_parts.append(f"modules={', '.join(card.active_module_ids)}")
        if card.disqualify_flags:
            rationale_parts.append(f"flags={', '.join(card.disqualify_flags)}")
        if relevant_text_signals:
            rationale_parts.append(f"text_watch={text_signal_focus_summary(relevant_text_signals)}")
        if card.diagnostic_summary:
            rationale_parts.append(f"diagnosis={card.diagnostic_summary}")
        if card.llm_diagnostic_summary:
            rationale_parts.append(f"llm_diagnosis={card.llm_diagnostic_summary}")

        risk_notes = list(card.disqualify_flags)
        risk_notes.extend(card.diagnostic_risk_notes)
        risk_notes.extend(card.fusion_notes)
        risk_notes.extend(card.llm_risk_notes)
        risk_notes.extend(gate.notes)
        if market_regime.opening_risk_note:
            risk_notes.append(market_regime.opening_risk_note)
        if relevant_text_signals:
            risk_notes.append(f"text_watch_focus: {text_signal_focus_summary(relevant_text_signals)}")
        if text_bias <= -0.35:
            risk_notes.append("text_watch_bias_negative")
        elif text_bias >= 0.35:
            risk_notes.append("text_watch_bias_positive")
        risk_notes = list(dict.fromkeys(risk_notes))

        plans.append(
            TradePlanCard(
                plan_id=f"trade_plan_{trade_date}_{card.stock_code.replace('.', '_')}",
                trade_date=trade_date,
                stock_code=card.stock_code,
                action=action,
                priority_rank=rank,
                rationale="; ".join(rationale_parts),
                entry_condition=_entry_condition(card, market_regime),
                setup_type=setup_type,
                setup_policy_status=card.setup_policy_status,
                market_gate_reason=market_gate_reason,
                entry_zone=_entry_zone(card),
                position_size_rule=position_size_rule,
                max_position_pct=max_position_pct,
                add_reduce_rule="Add only after confirmation. Reduce on failed extension or weak breadth.",
                invalidation_rule=_invalidation_rule(card, market_regime),
                exit_rule_hint="Take partial profit into extension and exit faster if confirmation fails.",
                holding_horizon=_holding_horizon(account),
                risk_notes=risk_notes,
                supporting_cards=list(card.supporting_cards),
            )
        )

    return plans


def save_trade_plan_cards(trade_date: str, plans: list[TradePlanCard], path: Path | None = None) -> Path:
    output_path = path or (trade_plan_output_dir() / f"trade_plan_cards_{trade_date}.json")
    output_path.write_text(json.dumps([asdict(plan) for plan in plans], ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
