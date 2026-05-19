from __future__ import annotations

from dataclasses import dataclass, field

from trading_system.context.cards import MarketRegimeSnapshot
from trading_system.decision.account import AccountConstraints, is_small_capital_aggressive


ALL_SETUPS: tuple[str, ...] = (
    "leader_acceleration",
    "dip_to_consensus",
    "event_ignition",
    "ice_point_reversal",
    "trend_follow_thrust",
    "defensive_only",
)


@dataclass(frozen=True)
class MarketGateDecision:
    allowed_setups: tuple[str, ...]
    blocked_setups: tuple[str, ...]
    aggression_budget: float
    max_new_positions: int
    chase_allowed: bool
    dip_buy_allowed: bool
    rotation_allowed: bool
    only_core_allowed: bool
    posture: str
    notes: tuple[str, ...] = field(default_factory=tuple)


def evaluate_market_gate(
    snapshot: MarketRegimeSnapshot,
    account: AccountConstraints,
) -> MarketGateDecision:
    aggressive = is_small_capital_aggressive(account)
    notes: list[str] = []
    allowed: list[str]
    blocked: list[str]
    chase_allowed = False
    dip_buy_allowed = False
    rotation_allowed = False
    only_core_allowed = False
    posture = "defensive"
    aggression_budget = 0.15

    sentiment_pressure = snapshot.sentiment_pressure_score if snapshot.sentiment_pressure_score is not None else 0.5
    breakout_failure = snapshot.breakout_failure_rate if snapshot.breakout_failure_rate is not None else 0.4
    trend_strength = snapshot.trend_strength_score if snapshot.trend_strength_score is not None else 0.5

    if snapshot.risk_mode == "risk_off":
        allowed = ["defensive_only"]
        if sentiment_pressure <= 0.60 and breakout_failure <= 0.55:
            allowed.append("ice_point_reversal")
            dip_buy_allowed = True
            notes.append("allow_only_ice_point_reversal")
        blocked = [setup for setup in ALL_SETUPS if setup not in allowed]
        only_core_allowed = True
        aggression_budget = 0.10
        posture = "defensive"
    elif snapshot.risk_mode == "selective":
        allowed = ["defensive_only", "dip_to_consensus", "event_ignition"]
        dip_buy_allowed = True
        if trend_strength >= 0.55 and sentiment_pressure <= 0.55:
            allowed.append("trend_follow_thrust")
            rotation_allowed = True
        if snapshot.sentiment_cycle == "contraction":
            allowed.append("ice_point_reversal")
        if breakout_failure < 0.40 and sentiment_pressure < 0.50 and snapshot.theme_concentration == "high":
            allowed.append("leader_acceleration")
            chase_allowed = True
            notes.append("leader_only_if_theme_is_clean")
        if aggressive and sentiment_pressure < 0.58 and breakout_failure < 0.50:
            if "trend_follow_thrust" not in allowed:
                allowed.append("trend_follow_thrust")
            notes.append("aggressive_profile_selective_extension")
        blocked = [setup for setup in ALL_SETUPS if setup not in allowed]
        only_core_allowed = snapshot.theme_concentration == "high" or sentiment_pressure >= 0.58
        aggression_budget = 0.65 if aggressive else 0.55
        posture = "selective"
    else:
        allowed = ["leader_acceleration", "dip_to_consensus", "event_ignition", "trend_follow_thrust", "defensive_only"]
        chase_allowed = True
        dip_buy_allowed = True
        rotation_allowed = True
        aggression_budget = 1.0 if aggressive else 0.9
        posture = "aggressive"
        if snapshot.sentiment_cycle == "contraction" and sentiment_pressure < 0.65:
            allowed.append("ice_point_reversal")
        if breakout_failure >= 0.55 or sentiment_pressure >= 0.65:
            if "leader_acceleration" in allowed:
                allowed.remove("leader_acceleration")
                notes.append("chase_disabled_by_failure_rate")
            chase_allowed = False
            only_core_allowed = True
        if trend_strength < 0.45 and "trend_follow_thrust" in allowed:
            allowed.remove("trend_follow_thrust")
            rotation_allowed = False
            notes.append("trend_follow_disabled_by_weak_trend")
        blocked = [setup for setup in ALL_SETUPS if setup not in allowed]

    max_slots = max(0, min(account.max_new_positions_per_day, account.max_holdings))
    if snapshot.risk_mode == "risk_off":
        max_new_positions = min(max_slots, 1)
    elif snapshot.risk_mode == "selective":
        max_new_positions = min(max_slots, 2)
    else:
        max_new_positions = min(max_slots, 2 if aggressive else max_slots)
    if only_core_allowed:
        max_new_positions = min(max_new_positions, 2 if snapshot.risk_mode == "risk_on" else 1)

    if aggressive and snapshot.risk_mode != "risk_off":
        notes.append("small_capital_aggressive_mode")

    return MarketGateDecision(
        allowed_setups=tuple(dict.fromkeys(allowed)),
        blocked_setups=tuple(blocked),
        aggression_budget=aggression_budget,
        max_new_positions=max_new_positions,
        chase_allowed=chase_allowed,
        dip_buy_allowed=dip_buy_allowed,
        rotation_allowed=rotation_allowed,
        only_core_allowed=only_core_allowed,
        posture=posture,
        notes=tuple(dict.fromkeys(notes)),
    )


def market_gate_verdict(decision: MarketGateDecision, setup_type: str) -> tuple[bool, str]:
    setup = str(setup_type or "").strip()
    if not setup:
        return False, "missing_setup_type"
    if setup in decision.allowed_setups:
        return True, "allowed"
    if setup in decision.blocked_setups:
        return False, f"blocked_setup:{setup}"
    return False, "setup_not_listed"
