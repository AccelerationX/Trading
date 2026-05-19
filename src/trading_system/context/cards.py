from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class MarketRegimeSnapshot:
    snapshot_id: str
    trade_date: str
    market_bias: str
    risk_mode: str
    breadth_strength: str
    limit_up_temperature: str
    turnover_regime: str
    style_lead: str = ""
    theme_concentration: str = ""
    sentiment_cycle: str = ""
    leader_stability: str = ""
    event_driven_bias: str = ""
    index_trend_state: str = ""
    index_alignment: str = ""
    trend_strength_score: float | None = None
    speculative_heat_score: float | None = None
    sentiment_pressure_score: float | None = None
    breakout_failure_rate: float | None = None
    opening_risk_note: str = ""
    confidence: float | None = None
    supporting_evidence: list[str] = field(default_factory=list)


@dataclass(slots=True)
class EventCard:
    event_id: str
    event_type: str
    event_title: str
    stock_codes: list[str]
    industry_tags: list[str] = field(default_factory=list)
    publish_time: str = ""
    bullish_bearish: str = ""
    impact_horizon: str = ""
    event_strength: float | None = None
    novelty_score: float | None = None
    is_official: bool = False
    core_claim: str = ""
    risk_flags: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    llm_summary: str = ""
    llm_sentiment_verdict: str = ""
    llm_confidence: float | None = None
    llm_beneficiary_stocks: list[str] = field(default_factory=list)
    llm_risk_notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ThemeCard:
    theme_id: str
    theme_name: str
    trigger_type: str
    trigger_time: str
    beneficiary_chain: list[str] = field(default_factory=list)
    priority_industries: list[str] = field(default_factory=list)
    priority_stocks: list[str] = field(default_factory=list)
    continuation_guess: str = ""
    market_confirmation_needed: list[str] = field(default_factory=list)
    contra_risks: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    llm_summary: str = ""
    llm_focus_industries: list[str] = field(default_factory=list)
    llm_focus_stocks: list[str] = field(default_factory=list)
    llm_tradeability_verdict: str = ""
    llm_confidence: float | None = None


@dataclass(slots=True)
class MacroEventCard:
    macro_event_id: str
    event_type: str
    title: str
    publish_time: str = ""
    source_name: str = ""
    source_url: str = ""
    source_kind: str = ""
    bias: str = ""
    impact_scope: str = ""
    confidence: float | None = None
    beneficiary_industries: list[str] = field(default_factory=list)
    risk_industries: list[str] = field(default_factory=list)
    related_markets: list[str] = field(default_factory=list)
    confirmation_signals: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    summary: str = ""
    source_refs: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CapitalBehaviorCard:
    card_id: str
    stock_code: str
    trade_date: str
    capital_signal_type: str
    participation_strength: str = ""
    consistency_score: float | None = None
    suspected_style: str = ""
    support_or_distribution: str = ""
    warning_flags: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    llm_summary: str = ""
    llm_interpretation: str = ""
    llm_confidence: float | None = None


@dataclass(slots=True)
class CandidateCard:
    candidate_id: str
    stock_code: str
    trade_date: str
    candidate_source: str
    candidate_score: float | None = None
    fusion_score: float | None = None
    fusion_verdict: str = ""
    setup_type: str = ""
    setup_confidence: float | None = None
    setup_policy_status: str = ""
    setup_policy_score: float | None = None
    setup_action_floor: float | None = None
    setup_position_cap_multiplier: float | None = None
    market_gate_pass: bool = False
    market_gate_reason: str = ""
    dominant_driver: str = ""
    technical_state: str = ""
    market_permission_score: float | None = None
    driver_conviction_score: float | None = None
    thesis_quality_score: float | None = None
    technical_confirmation_score: float | None = None
    execution_readiness_score: float | None = None
    event_support_score: float | None = None
    theme_alignment_score: float | None = None
    macro_alignment_score: float | None = None
    capital_confirmation_score: float | None = None
    information_edge_score: float | None = None
    market_fit_score: float | None = None
    account_fit_score: float | None = None
    active_module_ids: list[str] = field(default_factory=list)
    disqualify_flags: list[str] = field(default_factory=list)
    supporting_cards: list[str] = field(default_factory=list)
    supporting_macro_events: list[str] = field(default_factory=list)
    candidate_rationale: str = ""
    last_close_price: float | None = None
    board_lot_size: int = 100
    estimated_min_lot_cost: float | None = None
    account_tradeability_score: float | None = None
    tradeability_verdict: str = ""
    diagnostic_summary: str = ""
    diagnostic_risk_notes: list[str] = field(default_factory=list)
    fusion_notes: list[str] = field(default_factory=list)
    llm_diagnostic_summary: str = ""
    llm_tradeability_verdict: str = ""
    llm_focus_points: list[str] = field(default_factory=list)
    llm_risk_notes: list[str] = field(default_factory=list)
    llm_confidence: float | None = None


@dataclass(slots=True)
class TradePlanCard:
    plan_id: str
    trade_date: str
    stock_code: str
    action: str
    priority_rank: int
    rationale: str
    entry_condition: str
    setup_type: str = ""
    setup_policy_status: str = ""
    market_gate_reason: str = ""
    entry_zone: str = ""
    position_size_rule: str = ""
    max_position_pct: float | None = None
    add_reduce_rule: str = ""
    invalidation_rule: str = ""
    exit_rule_hint: str = ""
    holding_horizon: str = ""
    risk_notes: list[str] = field(default_factory=list)
    supporting_cards: list[str] = field(default_factory=list)
    llm_refined_plan: str = ""
    llm_execution_watchpoints: list[str] = field(default_factory=list)
    llm_confidence: float | None = None
