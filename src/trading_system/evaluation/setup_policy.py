from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SetupPolicySignal:
    setup_type: str
    status: str
    score_multiplier: float
    verdict_cap: str
    action_score_floor: float
    position_cap_multiplier: float
    sample_count: int
    buy_pilot_count: int
    avg_return_3d: float | None = None
    win_rate_3d: float | None = None
    hit_rate_3pct_3d: float | None = None
    execution_closed_trade_count: int = 0
    execution_avg_return: float | None = None
    execution_win_rate: float | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


def _derive_from_setup_performance(payload: dict | None) -> dict[str, SetupPolicySignal]:
    if not payload:
        return {}
    result: dict[str, SetupPolicySignal] = {}
    for item in list(payload.get("setup_summary", [])):
        setup_type = str(item.get("setup_type", "")).strip()
        if not setup_type:
            continue

        buy_pilot = dict(item.get("buy_pilot_horizons", {})).get("3d", {})
        sample_count = int(item.get("sample_count", 0) or 0)
        buy_pilot_count = int(item.get("buy_pilot_count", 0) or 0)
        avg_return = buy_pilot.get("avg_return")
        win_rate = buy_pilot.get("win_rate")
        hit_rate = buy_pilot.get("hit_rate_3pct")
        notes: list[str] = []

        status = "neutral"
        score_multiplier = 1.0
        verdict_cap = "actionable"
        action_score_floor = 0.60
        position_cap_multiplier = 1.0

        if buy_pilot_count < 2:
            status = "insufficient_sample"
            action_score_floor = 0.62
            position_cap_multiplier = 0.90
            notes.append("insufficient_buy_pilot_history")
        elif avg_return is not None and win_rate is not None and hit_rate is not None:
            avg_return = float(avg_return)
            win_rate = float(win_rate)
            hit_rate = float(hit_rate)
            if avg_return <= -0.02 or win_rate <= 0.35:
                status = "disabled"
                score_multiplier = 0.72
                verdict_cap = "watch"
                action_score_floor = 1.00
                position_cap_multiplier = 0.0
                notes.append("historical_underperformance")
            elif avg_return <= 0.0 or hit_rate < 0.20:
                status = "cautious"
                score_multiplier = 0.88
                verdict_cap = "watch"
                action_score_floor = 0.68
                position_cap_multiplier = 0.75
                notes.append("historical_edge_weak")
            elif avg_return >= 0.04 and hit_rate >= 0.45 and win_rate >= 0.50:
                status = "favored"
                score_multiplier = 1.08
                action_score_floor = 0.56
                position_cap_multiplier = 1.15
                notes.append("historical_edge_positive")
            else:
                status = "neutral"
                notes.append("historical_edge_mixed")

        result[setup_type] = SetupPolicySignal(
            setup_type=setup_type,
            status=status,
            score_multiplier=score_multiplier,
            verdict_cap=verdict_cap,
            action_score_floor=action_score_floor,
            position_cap_multiplier=position_cap_multiplier,
            sample_count=sample_count,
            buy_pilot_count=buy_pilot_count,
            avg_return_3d=float(avg_return) if avg_return is not None else None,
            win_rate_3d=float(win_rate) if win_rate is not None else None,
            hit_rate_3pct_3d=float(hit_rate) if hit_rate is not None else None,
            execution_closed_trade_count=0,
            execution_avg_return=None,
            execution_win_rate=None,
            notes=tuple(notes),
        )
    return result


def _blend_execution_feedback(
    base: dict[str, SetupPolicySignal],
    execution_feedback: dict | None,
) -> dict[str, SetupPolicySignal]:
    if not execution_feedback:
        return base

    feedback_map = {
        str(item.get("setup_type", "")).strip(): dict(item)
        for item in list(execution_feedback.get("setup_summary", []))
        if str(item.get("setup_type", "")).strip()
    }
    result = dict(base)
    for setup_type, item in feedback_map.items():
        closed_trade_count = int(item.get("closed_trade_count", 0) or 0)
        avg_return = item.get("avg_realized_return")
        win_rate = item.get("win_rate")

        signal = result.get(
            setup_type,
            SetupPolicySignal(
                setup_type=setup_type,
                status="insufficient_sample",
                score_multiplier=1.0,
                verdict_cap="actionable",
                action_score_floor=0.62,
                position_cap_multiplier=0.90,
                sample_count=0,
                buy_pilot_count=0,
                notes=(),
            ),
        )
        status = signal.status
        score_multiplier = signal.score_multiplier
        verdict_cap = signal.verdict_cap
        action_score_floor = signal.action_score_floor
        position_cap_multiplier = signal.position_cap_multiplier
        notes = list(signal.notes)

        if closed_trade_count >= 2 and avg_return is not None and win_rate is not None:
            avg_return = float(avg_return)
            win_rate = float(win_rate)
            if avg_return <= -0.03 or win_rate <= 0.34:
                status = "disabled"
                score_multiplier = min(score_multiplier, 0.68)
                verdict_cap = "watch"
                action_score_floor = max(action_score_floor, 1.00)
                position_cap_multiplier = 0.0
                notes.append("execution_feedback_underperformance")
            elif avg_return <= 0.0 or win_rate < 0.45:
                if status != "disabled":
                    status = "cautious"
                    score_multiplier = min(score_multiplier, 0.85)
                    verdict_cap = "watch"
                    action_score_floor = max(action_score_floor, 0.70)
                    position_cap_multiplier = min(position_cap_multiplier, 0.72)
                    notes.append("execution_feedback_weak")
            elif avg_return >= 0.035 and win_rate >= 0.55:
                if status not in {"disabled", "cautious"}:
                    status = "favored"
                score_multiplier = max(score_multiplier, 1.10)
                action_score_floor = min(action_score_floor, 0.54)
                position_cap_multiplier = max(position_cap_multiplier, 1.18)
                notes.append("execution_feedback_positive")
        elif closed_trade_count == 1:
            notes.append("execution_feedback_sample_thin")

        result[setup_type] = SetupPolicySignal(
            setup_type=signal.setup_type,
            status=status,
            score_multiplier=score_multiplier,
            verdict_cap=verdict_cap,
            action_score_floor=action_score_floor,
            position_cap_multiplier=position_cap_multiplier,
            sample_count=signal.sample_count,
            buy_pilot_count=signal.buy_pilot_count,
            avg_return_3d=signal.avg_return_3d,
            win_rate_3d=signal.win_rate_3d,
            hit_rate_3pct_3d=signal.hit_rate_3pct_3d,
            execution_closed_trade_count=closed_trade_count,
            execution_avg_return=float(avg_return) if avg_return is not None else None,
            execution_win_rate=float(win_rate) if win_rate is not None else None,
            notes=tuple(dict.fromkeys(notes)),
        )
    return result


def _blend_execution_behavior(
    base: dict[str, SetupPolicySignal],
    execution_behavior: dict | None,
) -> dict[str, SetupPolicySignal]:
    if not execution_behavior:
        return base

    behavior_map = {
        str(item.get("setup_type", "")).strip(): dict(item)
        for item in list(execution_behavior.get("setup_summary", []))
        if str(item.get("setup_type", "")).strip()
    }
    result = dict(base)
    for setup_type, item in behavior_map.items():
        signal = result.get(
            setup_type,
            SetupPolicySignal(
                setup_type=setup_type,
                status="insufficient_sample",
                score_multiplier=1.0,
                verdict_cap="actionable",
                action_score_floor=0.62,
                position_cap_multiplier=0.90,
                sample_count=0,
                buy_pilot_count=0,
                notes=(),
            ),
        )
        finalized_count = int(item.get("finalized_count", 0) or 0)
        fill_rate = item.get("fill_rate")
        skip_rate = item.get("skip_rate")
        partial_rate = item.get("partial_rate")
        avg_buy_slippage_pct = item.get("avg_buy_slippage_pct")
        notes = list(signal.notes)

        status = signal.status
        score_multiplier = signal.score_multiplier
        verdict_cap = signal.verdict_cap
        action_score_floor = signal.action_score_floor
        position_cap_multiplier = signal.position_cap_multiplier

        if finalized_count >= 2:
            if skip_rate is not None and float(skip_rate) >= 0.5:
                if status != "disabled":
                    status = "cautious"
                score_multiplier = min(score_multiplier, 0.90)
                verdict_cap = "watch" if status == "cautious" else verdict_cap
                action_score_floor = max(action_score_floor, 0.66)
                position_cap_multiplier = min(position_cap_multiplier, 0.82)
                notes.append("execution_followthrough_weak")
            if partial_rate is not None and float(partial_rate) >= 0.4:
                position_cap_multiplier = min(position_cap_multiplier, 0.85)
                action_score_floor = max(action_score_floor, 0.64)
                notes.append("execution_partial_fill_heavy")
            if avg_buy_slippage_pct is not None and float(avg_buy_slippage_pct) >= 0.02:
                score_multiplier = min(score_multiplier, 0.94)
                action_score_floor = max(action_score_floor, 0.65)
                position_cap_multiplier = min(position_cap_multiplier, 0.88)
                notes.append("execution_buy_slippage_high")
            elif (
                fill_rate is not None
                and float(fill_rate) >= 0.8
                and avg_buy_slippage_pct is not None
                and abs(float(avg_buy_slippage_pct)) <= 0.005
            ):
                score_multiplier = max(score_multiplier, 1.03)
                action_score_floor = min(action_score_floor, 0.58)
                notes.append("execution_followthrough_good")

        result[setup_type] = SetupPolicySignal(
            setup_type=signal.setup_type,
            status=status,
            score_multiplier=score_multiplier,
            verdict_cap=verdict_cap,
            action_score_floor=action_score_floor,
            position_cap_multiplier=position_cap_multiplier,
            sample_count=signal.sample_count,
            buy_pilot_count=signal.buy_pilot_count,
            avg_return_3d=signal.avg_return_3d,
            win_rate_3d=signal.win_rate_3d,
            hit_rate_3pct_3d=signal.hit_rate_3pct_3d,
            execution_closed_trade_count=signal.execution_closed_trade_count,
            execution_avg_return=signal.execution_avg_return,
            execution_win_rate=signal.execution_win_rate,
            notes=tuple(dict.fromkeys(notes)),
        )
    return result


def derive_setup_policy(
    payload: dict | None,
    *,
    execution_feedback: dict | None = None,
    execution_behavior: dict | None = None,
) -> dict[str, SetupPolicySignal]:
    base = _derive_from_setup_performance(payload)
    blended = _blend_execution_feedback(base, execution_feedback)
    return _blend_execution_behavior(blended, execution_behavior)
