from __future__ import annotations

from dataclasses import dataclass, field

from trading_system.context.cards import MarketRegimeSnapshot


SETUP_TYPES: tuple[str, ...] = (
    "leader_acceleration",
    "dip_to_consensus",
    "event_ignition",
    "ice_point_reversal",
    "trend_follow_thrust",
    "defensive_only",
)


@dataclass(frozen=True)
class SetupClassification:
    setup_type: str
    confidence: float
    notes: tuple[str, ...] = field(default_factory=tuple)


def _clamp_score(value: float, *, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def classify_candidate_setup(
    *,
    snapshot: MarketRegimeSnapshot,
    candidate_source: str,
    technical_state: str,
    event_support_score: float,
    theme_alignment_score: float,
    module_score: float,
    market_fit_score: float,
) -> SetupClassification:
    notes: list[str] = []

    if technical_state == "defensive_scan_only":
        confidence = 0.30 + market_fit_score * 0.20
        notes.append("defensive_state")
        return SetupClassification("defensive_only", round(_clamp_score(confidence), 3), tuple(notes))

    if (
        candidate_source in {"full_resonance", "event_theme_resonance", "module_event_resonance"}
        and event_support_score >= 0.64
        and theme_alignment_score >= 0.60
        and module_score >= 0.42
        and technical_state in {"event_theme_resonance", "event_breakout_watch"}
    ):
        confidence = 0.42 + event_support_score * 0.22 + theme_alignment_score * 0.18 + module_score * 0.14
        if snapshot.theme_concentration == "high":
            confidence += 0.04
            notes.append("theme_concentrated")
        return SetupClassification("leader_acceleration", round(_clamp_score(confidence), 3), tuple(notes))

    if technical_state == "selective_repair_watch" and event_support_score >= 0.52:
        confidence = 0.34 + event_support_score * 0.24 + module_score * 0.14 + market_fit_score * 0.12
        if snapshot.sentiment_cycle == "contraction":
            confidence += 0.04
            notes.append("contraction_repair")
        return SetupClassification("dip_to_consensus", round(_clamp_score(confidence), 3), tuple(notes))

    if event_support_score >= 0.68 and theme_alignment_score < 0.58:
        confidence = 0.35 + event_support_score * 0.28 + module_score * 0.10 + market_fit_score * 0.12
        notes.append("event_first_then_theme")
        return SetupClassification("event_ignition", round(_clamp_score(confidence), 3), tuple(notes))

    if technical_state == "selective_repair_watch" and snapshot.sentiment_cycle == "contraction":
        confidence = 0.30 + event_support_score * 0.16 + module_score * 0.18 + market_fit_score * 0.14
        notes.append("sentiment_reversal_attempt")
        return SetupClassification("ice_point_reversal", round(_clamp_score(confidence), 3), tuple(notes))

    if module_score >= 0.55 and theme_alignment_score >= 0.50:
        confidence = 0.32 + module_score * 0.20 + theme_alignment_score * 0.16 + market_fit_score * 0.12
        if snapshot.trend_strength_score is not None:
            confidence += max(0.0, snapshot.trend_strength_score - 0.5) * 0.20
        notes.append("trend_following_bias")
        return SetupClassification("trend_follow_thrust", round(_clamp_score(confidence), 3), tuple(notes))

    confidence = 0.24 + max(event_support_score, theme_alignment_score, module_score) * 0.18
    notes.append("fallback_defensive")
    return SetupClassification("defensive_only", round(_clamp_score(confidence), 3), tuple(notes))
