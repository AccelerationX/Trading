from __future__ import annotations

from dataclasses import dataclass, field

from trading_system.context.cards import MarketRegimeSnapshot
from trading_system.decision.account import AccountConstraints, is_small_capital_aggressive
from trading_system.decision.market_gate import evaluate_market_gate, market_gate_verdict
from trading_system.decision.setup_types import classify_candidate_setup


def _clamp_score(value: float, *, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


@dataclass(frozen=True)
class CandidateFusionInput:
    candidate_source: str
    technical_state: str
    event_support_score: float
    theme_alignment_score: float
    information_edge_score: float
    module_score: float
    capital_confirmation_score: float | None
    market_fit_score: float
    account_fit_score: float
    tradeability_score: float | None
    tradeability_verdict: str
    text_signal_score: float | None
    has_bearish_event: bool
    active_module_count: int


@dataclass(frozen=True)
class CandidateFusionResult:
    setup_type: str
    setup_confidence: float
    market_gate_pass: bool
    market_gate_reason: str
    dominant_driver: str
    market_permission_score: float
    driver_conviction_score: float
    thesis_quality_score: float
    technical_confirmation_score: float
    execution_readiness_score: float
    fusion_score: float
    fusion_verdict: str
    fusion_notes: tuple[str, ...] = field(default_factory=tuple)


def _is_aggressive_small_cap_profile(account: AccountConstraints) -> bool:
    return is_small_capital_aggressive(account)


def _dominant_driver(fusion_input: CandidateFusionInput) -> str:
    source = fusion_input.candidate_source
    if source == "full_resonance":
        return "event_theme_technical"
    if source in {"event_theme_resonance", "module_event_resonance"}:
        return "event"
    if source == "module_theme_resonance":
        return "theme"
    if source == "theme_priority":
        return "theme"
    if source == "module_direct":
        return "technical"
    return "event"


def _market_permission_score(
    snapshot: MarketRegimeSnapshot,
    fusion_input: CandidateFusionInput,
    *,
    dominant_driver: str,
) -> float:
    if snapshot.risk_mode == "risk_on":
        score = 0.82
    elif snapshot.risk_mode == "selective":
        score = 0.56
    else:
        score = 0.18

    if dominant_driver in {"theme", "event_theme_technical"} and snapshot.style_lead == "small_cap_lead":
        score += 0.05
    if dominant_driver == "event" and snapshot.style_lead == "large_cap_lead":
        score += 0.04
    if snapshot.theme_concentration == "high" and fusion_input.theme_alignment_score >= 0.6:
        score += 0.05
    if snapshot.sentiment_cycle == "contraction":
        score -= 0.10
    if snapshot.leader_stability == "fragile_leaders":
        score -= 0.07
    if snapshot.index_alignment == "broadly_aligned_up":
        score += 0.05
    elif snapshot.index_alignment == "broadly_aligned_down":
        score -= 0.08
    if snapshot.index_trend_state == "broad_uptrend":
        score += 0.06
    elif snapshot.index_trend_state == "broad_downtrend":
        score -= 0.10
    if snapshot.trend_strength_score is not None:
        score += (snapshot.trend_strength_score - 0.5) * 0.18
    if snapshot.sentiment_pressure_score is not None and snapshot.sentiment_pressure_score >= 0.65:
        score -= 0.10
    if fusion_input.market_fit_score >= 0.7:
        score += 0.04
    return round(_clamp_score(score), 3)


def _driver_conviction_score(fusion_input: CandidateFusionInput) -> float:
    score = max(
        fusion_input.event_support_score,
        fusion_input.theme_alignment_score,
        fusion_input.module_score,
    )
    source = fusion_input.candidate_source
    if source == "full_resonance":
        score += 0.12
    elif source in {"event_theme_resonance", "module_event_resonance", "module_theme_resonance"}:
        score += 0.08
    elif source in {"event_direct", "theme_priority"}:
        score += 0.03
    if fusion_input.capital_confirmation_score is not None and fusion_input.capital_confirmation_score >= 0.75:
        score += 0.05
    if fusion_input.text_signal_score is not None and fusion_input.text_signal_score >= 0.62:
        score += 0.04
    return round(_clamp_score(score), 3)


def _thesis_quality_score(fusion_input: CandidateFusionInput) -> float:
    score = (
        fusion_input.event_support_score * 0.34
        + fusion_input.theme_alignment_score * 0.16
        + fusion_input.information_edge_score * 0.24
        + fusion_input.market_fit_score * 0.10
    )
    total_weight = 0.84
    if fusion_input.capital_confirmation_score is not None:
        score += fusion_input.capital_confirmation_score * 0.10
        total_weight += 0.10
    if fusion_input.text_signal_score is not None:
        score += fusion_input.text_signal_score * 0.06
        total_weight += 0.06
    score = score / total_weight
    if fusion_input.candidate_source == "module_direct":
        score = min(score, 0.52)
    if fusion_input.has_bearish_event:
        score -= 0.24
    return round(_clamp_score(score), 3)


def _technical_confirmation_score(fusion_input: CandidateFusionInput) -> float:
    score = 0.18 + fusion_input.module_score * 0.72
    if fusion_input.technical_state in {"event_theme_resonance", "event_breakout_watch"}:
        score += 0.08
    elif fusion_input.technical_state in {"theme_rotation_watch", "selective_repair_watch"}:
        score += 0.05
    elif fusion_input.technical_state == "defensive_scan_only":
        score -= 0.28
    if fusion_input.active_module_count <= 0:
        score = min(score, 0.42 if fusion_input.candidate_source.startswith("event") else 0.36)
    return round(_clamp_score(score), 3)


def _execution_readiness_score(account: AccountConstraints, fusion_input: CandidateFusionInput) -> float:
    tradeability_score = fusion_input.tradeability_score if fusion_input.tradeability_score is not None else fusion_input.account_fit_score
    score = fusion_input.account_fit_score * 0.56 + tradeability_score * 0.44
    if fusion_input.tradeability_verdict in {"blocked_by_budget", "too_concentrated"}:
        score = min(score, 0.18)
    elif fusion_input.tradeability_verdict == "stretched":
        score = min(score, 0.48)
    elif fusion_input.tradeability_verdict == "liquidity_caution":
        score = min(score, 0.42)

    if _is_aggressive_small_cap_profile(account):
        if fusion_input.tradeability_verdict == "stretched":
            score += 0.04
        if fusion_input.candidate_source in {"event_theme_resonance", "module_event_resonance", "full_resonance"}:
            score += 0.03
    return round(_clamp_score(score), 3)


def evaluate_candidate_fusion(
    *,
    snapshot: MarketRegimeSnapshot,
    account: AccountConstraints,
    fusion_input: CandidateFusionInput,
) -> CandidateFusionResult:
    dominant_driver = _dominant_driver(fusion_input)
    setup = classify_candidate_setup(
        snapshot=snapshot,
        candidate_source=fusion_input.candidate_source,
        technical_state=fusion_input.technical_state,
        event_support_score=fusion_input.event_support_score,
        theme_alignment_score=fusion_input.theme_alignment_score,
        module_score=fusion_input.module_score,
        market_fit_score=fusion_input.market_fit_score,
    )
    gate = evaluate_market_gate(snapshot, account)
    market_gate_pass, market_gate_reason = market_gate_verdict(gate, setup.setup_type)
    market_permission_score = _market_permission_score(snapshot, fusion_input, dominant_driver=dominant_driver)
    driver_conviction_score = _driver_conviction_score(fusion_input)
    thesis_quality_score = _thesis_quality_score(fusion_input)
    technical_confirmation_score = _technical_confirmation_score(fusion_input)
    execution_readiness_score = _execution_readiness_score(account, fusion_input)

    weighted_score = (
        market_permission_score * 0.16
        + driver_conviction_score * 0.20
        + thesis_quality_score * 0.24
        + technical_confirmation_score * 0.22
        + execution_readiness_score * 0.18
    )
    fusion_score = weighted_score + (setup.confidence - 0.5) * 0.08
    fusion_notes: list[str] = list(setup.notes)

    if not market_gate_pass:
        market_permission_score = round(_clamp_score(min(market_permission_score, 0.24)), 3)
        fusion_score = min(fusion_score, 0.40)
        fusion_notes.append(market_gate_reason)
    elif gate.only_core_allowed and setup.setup_type in {"event_ignition", "trend_follow_thrust"}:
        fusion_score = min(fusion_score, 0.62)
        fusion_notes.append("market_core_only")

    if market_permission_score < 0.28:
        fusion_score = min(fusion_score, 0.36)
        fusion_notes.append("market_not_permissive")
    elif market_permission_score < 0.50:
        fusion_score = min(fusion_score, 0.62)
        fusion_notes.append("market_confirmation_needed")

    if thesis_quality_score < 0.40:
        fusion_score = min(fusion_score, 0.46)
        fusion_notes.append("thesis_too_weak")

    if technical_confirmation_score < 0.35:
        fusion_score = min(fusion_score, 0.52)
        fusion_notes.append("technical_not_confirmed")
    elif technical_confirmation_score < 0.50:
        fusion_score = min(fusion_score, 0.66)
        fusion_notes.append("technical_confirmation_pending")

    if execution_readiness_score < 0.22:
        fusion_score = min(fusion_score, 0.28)
        fusion_notes.append("execution_blocked")
    elif execution_readiness_score < 0.40:
        fusion_score = min(fusion_score, 0.58)
        fusion_notes.append("account_caution")

    fusion_score = round(_clamp_score(fusion_score), 3)
    if (
        "execution_blocked" in fusion_notes
        or not market_gate_pass
        or market_permission_score < 0.20
        or (fusion_input.has_bearish_event and thesis_quality_score < 0.34)
    ):
        fusion_verdict = "avoid"
    elif (
        fusion_score >= 0.64
        and market_permission_score >= 0.50
        and thesis_quality_score >= 0.52
        and technical_confirmation_score >= 0.44
        and execution_readiness_score >= 0.38
    ):
        fusion_verdict = "actionable"
    else:
        fusion_verdict = "watch"

    return CandidateFusionResult(
        setup_type=setup.setup_type,
        setup_confidence=setup.confidence,
        market_gate_pass=market_gate_pass,
        market_gate_reason=market_gate_reason,
        dominant_driver=dominant_driver,
        market_permission_score=market_permission_score,
        driver_conviction_score=driver_conviction_score,
        thesis_quality_score=thesis_quality_score,
        technical_confirmation_score=technical_confirmation_score,
        execution_readiness_score=execution_readiness_score,
        fusion_score=fusion_score,
        fusion_verdict=fusion_verdict,
        fusion_notes=tuple(dict.fromkeys(fusion_notes)),
    )
