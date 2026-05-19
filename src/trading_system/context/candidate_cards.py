from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from trading_system.config.paths import INBOX_DIR, PROCESSED_DATA_DIR
from trading_system.context.cards import CandidateCard, CapitalBehaviorCard, EventCard, MacroEventCard, MarketRegimeSnapshot, ThemeCard
from trading_system.context.text_signal_support import (
    find_relevant_text_signals,
    load_text_signal_watch,
    text_signal_bias,
    text_signal_focus_summary,
)
from trading_system.decision.account import AccountConstraints, is_small_capital_aggressive
from trading_system.decision.fusion_engine import CandidateFusionInput, evaluate_candidate_fusion
from trading_system.evaluation.setup_policy import SetupPolicySignal
from trading_system.ingest.simple_tabular import read_records
from trading_system.signal.technical_modules import TechnicalModule
from trading_system.signal.scanners.merging import aggregate_module_signals, compute_module_score, merge_signals_for_stock
from trading_system.signal.scanners.base import ModuleSignal
from trading_system.utils.main_board import is_main_board


def candidate_processed_dir() -> Path:
    directory = PROCESSED_DATA_DIR / "candidates"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _clamp_score(value: float, *, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _normalize_stock_code(stock_code: str) -> str:
    return stock_code.strip().upper()


def _load_market_quote_map(trade_date: str) -> dict[str, dict]:
    trade_date_compact = trade_date.replace("-", "")
    path = INBOX_DIR / "market_equity_daily" / f"market_equity_daily_{trade_date_compact}.csv"
    if not path.exists():
        return {}
    records = read_records(path)
    quote_map: dict[str, dict] = {}
    for record in records:
        stock_code = _normalize_stock_code(str(record.get("stock_code", "")))
        if not stock_code:
            continue
        quote_map[stock_code] = record
    return quote_map


def _event_score(events: list[EventCard]) -> float:
    if not events:
        return 0.3

    score = 0.35
    for event in events:
        strength = event.event_strength if event.event_strength is not None else 0.5
        if event.bullish_bearish == "bullish":
            score += 0.35 * strength
            if event.is_official:
                score += 0.05
        elif event.bullish_bearish == "bearish":
            score -= 0.45 * strength
        else:
            score += 0.08
    return round(_clamp_score(score), 3)


def _theme_score(
    stock_code: str,
    direct_themes: list[ThemeCard],
    event_cards: list[EventCard],
    all_themes: list[ThemeCard],
) -> float:
    score = 0.2
    if direct_themes:
        score += min(0.55, 0.25 + 0.2 * len(direct_themes))

    event_industries = {
        tag.strip().lower()
        for event in event_cards
        for tag in event.industry_tags
        if tag.strip()
    }
    if event_industries:
        industry_matches = 0
        for theme in all_themes:
            theme_industries = {tag.strip().lower() for tag in theme.priority_industries if tag.strip()}
            if theme_industries & event_industries:
                industry_matches += 1
        if industry_matches:
            score += min(0.25, 0.1 + 0.08 * industry_matches)

    continuation_bonus = 0.0
    for theme in direct_themes:
        lowered = theme.continuation_guess.lower()
        if any(token in lowered for token in ("multi_day", "medium", "continue", "sustain")):
            continuation_bonus += 0.06
    score += min(0.12, continuation_bonus)
    return round(_clamp_score(score), 3)


def _capital_score(stock_code: str, capital_cards: list[CapitalBehaviorCard] | None) -> float | None:
    if not capital_cards:
        return None
    related = [card for card in capital_cards if _normalize_stock_code(card.stock_code) == stock_code]
    if not related:
        return None

    best = 0.45
    for card in related:
        score = card.consistency_score if card.consistency_score is not None else 0.5
        if card.support_or_distribution == "support":
            score += 0.15
        if card.support_or_distribution == "distribution":
            score -= 0.2
        if card.participation_strength == "high":
            score += 0.1
        if card.warning_flags:
            score -= 0.1
        best = max(best, score)
    return round(_clamp_score(best), 3)


def _information_edge_score(
    *,
    related_events: list[EventCard],
    related_themes: list[ThemeCard],
    macro_alignment_score: float | None,
    text_signal_score: float | None,
) -> float:
    score = 0.18
    official_bullish = 0
    bearish_count = 0
    for event in related_events:
        strength = event.event_strength if event.event_strength is not None else 0.5
        if event.is_official and event.bullish_bearish == "bullish":
            official_bullish += 1
            score += 0.16 * strength
        elif event.bullish_bearish == "bullish":
            score += 0.08 * strength
        elif event.bullish_bearish == "bearish":
            bearish_count += 1
            score -= 0.18 * strength

    for theme in related_themes:
        score += 0.08
        if theme.continuation_guess in {"multi_day", "multi_day_follow_up", "medium_term_policy_line"}:
            score += 0.06
        if theme.priority_stocks:
            score += 0.03

    if macro_alignment_score is not None:
        score += (macro_alignment_score - 0.5) * 0.24

    if text_signal_score is not None:
        score += (text_signal_score - 0.5) * 0.18

    if official_bullish and related_themes:
        score += 0.08
    if bearish_count and not official_bullish:
        score -= 0.08
    return round(_clamp_score(score), 3)


def _market_fit_score(
    snapshot: MarketRegimeSnapshot,
    *,
    candidate_source: str,
    event_support_score: float,
    theme_alignment_score: float,
    macro_alignment_score: float | None,
) -> float:
    if snapshot.risk_mode == "risk_on":
        score = 0.72
    elif snapshot.risk_mode == "selective":
        score = 0.54
    else:
        score = 0.22

    if candidate_source == "event_theme_resonance":
        score += 0.12
    elif candidate_source == "event_direct":
        score += 0.06
    elif candidate_source == "theme_priority":
        score += 0.05

    if snapshot.style_lead == "small_cap_lead" and theme_alignment_score >= 0.6:
        score += 0.05
    if snapshot.style_lead == "large_cap_lead" and event_support_score >= 0.65:
        score += 0.04
    if snapshot.theme_concentration == "high" and theme_alignment_score >= 0.6:
        score += 0.05
    if macro_alignment_score is not None and macro_alignment_score >= 0.62:
        score += 0.06
    elif macro_alignment_score is not None and macro_alignment_score <= 0.38:
        score -= 0.08

    return round(_clamp_score(score), 3)


def _macro_alignment_score(
    *,
    industry_tags: list[str],
    macro_event_cards: list[MacroEventCard] | None,
) -> tuple[float | None, list[MacroEventCard]]:
    if not macro_event_cards or not industry_tags:
        return None, []

    normalized_tags = {tag.strip().lower() for tag in industry_tags if tag.strip()}
    relevant: list[MacroEventCard] = []
    score = 0.5

    for card in macro_event_cards:
        beneficiary_tags = {tag.strip().lower() for tag in card.beneficiary_industries if tag.strip()}
        risk_tags = {tag.strip().lower() for tag in card.risk_industries if tag.strip()}
        if not (normalized_tags & beneficiary_tags or normalized_tags & risk_tags):
            continue
        relevant.append(card)
        confidence = card.confidence if card.confidence is not None else 0.6
        if normalized_tags & beneficiary_tags:
            if card.bias == "bullish":
                score += 0.22 * confidence
            elif card.bias == "bearish":
                score -= 0.14 * confidence
            else:
                score += 0.04 * confidence
        if normalized_tags & risk_tags:
            if card.bias == "bearish":
                score -= 0.24 * confidence
            elif card.bias == "bullish":
                score += 0.03 * confidence
            else:
                score -= 0.06 * confidence
    if not relevant:
        return None, []
    return round(_clamp_score(score), 3), relevant[:3]


def _account_fit_score(
    account: AccountConstraints,
    *,
    technical_modules: list[TechnicalModule],
    candidate_source: str,
    tradeability_score: float | None = None,
) -> float:
    aggressive = is_small_capital_aggressive(account)
    score = 0.75
    if account.single_position_max_pct < 0.1:
        score -= 0.15
    if account.max_new_positions_per_day <= 1:
        score -= 0.08
    if account.max_holdings <= 3:
        score -= 0.07
    if account.single_trade_capital_max <= 0 or account.capital_total <= 0:
        score = 0.0
    if candidate_source == "event_theme_resonance" and account.avoid_chasing_limit_up:
        score -= 0.06
    if any(module.needs_intraday for module in technical_modules) and not account.can_watch_intraday:
        score -= 0.2
    if aggressive:
        if candidate_source in {"full_resonance", "event_theme_resonance", "module_event_resonance"}:
            score += 0.08
        if account.allow_high_volatility_entries:
            score += 0.04
        if account.max_new_positions_per_day <= 2:
            score += 0.03
    if tradeability_score is not None:
        score = min(score, tradeability_score)
    return round(_clamp_score(score), 3)


def _tradeability_assessment(
    account: AccountConstraints,
    stock_code: str,
    quote_record: dict | None,
) -> tuple[float | None, float | None, float | None, str, list[str]]:
    if not quote_record:
        return None, None, 0.45, "unknown_quote", ["missing_latest_quote"]

    last_close = quote_record.get("close")
    amount = quote_record.get("amount")
    close_price = float(last_close) if last_close not in ("", None) else None
    amount_value = float(amount) if amount not in ("", None) else None
    if close_price is None or close_price <= 0:
        return None, None, 0.35, "unknown_quote", ["missing_last_close_price"]

    board_lot_size = max(1, int(account.board_lot_size or 100))
    min_lot_cost = round(close_price * board_lot_size, 2)
    capital_total = max(1.0, float(account.capital_total or 0.0))
    concentration_ratio = min_lot_cost / capital_total
    executable_cap = min(
        float(account.single_trade_capital_max or capital_total),
        capital_total * max(0.0, 1.0 - float(account.capital_liquid_ratio_min or 0.0)),
    )

    verdict = "tradable"
    risk_notes: list[str] = []
    score = 0.82
    if min_lot_cost > executable_cap:
        verdict = "blocked_by_budget"
        score = 0.02
        risk_notes.append("min_lot_exceeds_trade_budget")
    elif concentration_ratio >= account.single_lot_block_capital_pct:
        verdict = "too_concentrated"
        score = 0.18
        risk_notes.append("min_lot_too_concentrated")
    elif concentration_ratio >= account.single_lot_alert_capital_pct:
        verdict = "stretched"
        score = 0.42
        risk_notes.append("min_lot_stretches_positioning")

    if account.avoid_low_liquidity and amount_value is not None and amount_value < 80_000_000:
        score = min(score, 0.45)
        verdict = "liquidity_caution" if verdict == "tradable" else verdict
        risk_notes.append("low_daily_turnover")

    if is_small_capital_aggressive(account):
        if verdict == "stretched":
            score = min(0.56, max(score, 0.48))
        if verdict == "tradable" and concentration_ratio >= account.position_concentration_limit * 0.5:
            risk_notes.append("position_concentration_high")

    return close_price, min_lot_cost, round(_clamp_score(score), 3), verdict, list(dict.fromkeys(risk_notes))


def _diagnostic_summary(
    *,
    stock_code: str,
    candidate_source: str,
    technical_state: str,
    related_events: list[EventCard],
    related_themes: list[ThemeCard],
    module_agg: dict,
    capital_confirmation_score: float | None,
    market_regime: MarketRegimeSnapshot,
    tradeability_verdict: str,
    min_lot_cost: float | None,
    capital_total: float,
) -> tuple[str, list[str]]:
    risk_notes: list[str] = []
    event_part = "无明确事件催化"
    if related_events:
        event_titles = [event.event_title for event in related_events[:2]]
        event_part = f"事件面以{' / '.join(event_titles)}为主"
        if any(event.bullish_bearish == "bearish" for event in related_events):
            risk_notes.append("存在负面或冲突事件")

    theme_part = "题材映射一般"
    if related_themes:
        theme_names = [theme.theme_name for theme in related_themes[:2]]
        theme_part = f"题材侧对应{' / '.join(theme_names)}"

    module_part = "技术模块未形成强共振"
    if module_agg.get("active_module_ids"):
        module_part = f"技术上由{', '.join(module_agg['active_module_ids'][:3])}共振支撑"

    capital_part = "资金确认一般"
    if capital_confirmation_score is not None:
        if capital_confirmation_score >= 0.8:
            capital_part = "资金面有明显确认"
        elif capital_confirmation_score >= 0.6:
            capital_part = "资金面偏支持"

    tradeability_part = "账户可交易性正常"
    if tradeability_verdict == "blocked_by_budget":
        tradeability_part = "最小一手成本超过当前可执行预算"
        risk_notes.append("最小一手买入超预算")
    elif tradeability_verdict == "too_concentrated":
        tradeability_part = f"最小一手约{min_lot_cost:.0f}元，占总资金比例过高"
        risk_notes.append("高价股导致仓位过度集中")
    elif tradeability_verdict == "stretched":
        tradeability_part = f"最小一手约{min_lot_cost:.0f}元，会明显挤压你的正常试仓空间"
        risk_notes.append("试仓成本偏高")
    elif tradeability_verdict == "liquidity_caution":
        tradeability_part = "价格可做，但成交额偏低，需要控制交易冲击"
        risk_notes.append("流动性一般")
    elif tradeability_verdict == "unknown_quote":
        tradeability_part = "缺少最新价格，账户适配性只能粗判"
        risk_notes.append("缺少最新行情快照")

    summary = (
        f"{stock_code} 当前归类为 {technical_state}，{module_part}；{event_part}；{theme_part}；"
        f"{capital_part}；市场环境属于 {market_regime.risk_mode} / {market_regime.style_lead}；{tradeability_part}。"
    )
    if candidate_source.startswith("module_") and not related_events:
        risk_notes.append("偏技术驱动，基本面支撑不足")
    if candidate_source == "event_direct" and not module_agg.get("active_module_ids"):
        risk_notes.append("事件驱动为主，技术确认不足")
    return summary, list(dict.fromkeys(risk_notes))


def _diagnostic_summary_clean(
    *,
    stock_code: str,
    candidate_source: str,
    technical_state: str,
    related_events: list[EventCard],
    related_themes: list[ThemeCard],
    module_agg: dict,
    capital_confirmation_score: float | None,
    market_regime: MarketRegimeSnapshot,
    tradeability_verdict: str,
    min_lot_cost: float | None,
    capital_total: float,
) -> tuple[str, list[str]]:
    del capital_total
    risk_notes: list[str] = []

    event_part = "暂无明确事件催化"
    if related_events:
        event_titles = [event.event_title for event in related_events[:2]]
        event_part = f"事件面以{' / '.join(event_titles)}为主"
        if any(event.bullish_bearish == "bearish" for event in related_events):
            risk_notes.append("存在负面或冲突事件")

    theme_part = "题材映射一般"
    if related_themes:
        theme_names = [theme.theme_name for theme in related_themes[:2]]
        theme_part = f"题材侧对应{' / '.join(theme_names)}"

    module_part = "技术模块尚未形成强共振"
    if module_agg.get("active_module_ids"):
        module_part = f"技术上由{', '.join(module_agg['active_module_ids'][:3])}共振支撑"

    capital_part = "资金确认一般"
    if capital_confirmation_score is not None:
        if capital_confirmation_score >= 0.8:
            capital_part = "资金面有明显确认"
        elif capital_confirmation_score >= 0.6:
            capital_part = "资金面偏支持"

    tradeability_part = "账户可交易性正常"
    if tradeability_verdict == "blocked_by_budget":
        tradeability_part = "最小一手成本超过当前可执行预算"
        risk_notes.append("最小一手买入超过预算")
    elif tradeability_verdict == "too_concentrated":
        tradeability_part = f"最小一手约{min_lot_cost:.0f}元，占总资金比例过高"
        risk_notes.append("高价股导致仓位过度集中")
    elif tradeability_verdict == "stretched":
        tradeability_part = f"最小一手约{min_lot_cost:.0f}元，会明显挤压你的正常试仓空间"
        risk_notes.append("试仓成本偏高")
    elif tradeability_verdict == "liquidity_caution":
        tradeability_part = "价格可做，但成交额偏低，需要控制交易冲击"
        risk_notes.append("流动性一般")
    elif tradeability_verdict == "unknown_quote":
        tradeability_part = "缺少最新价格，账户适配性只能粗判"
        risk_notes.append("缺少最新行情快照")

    summary = (
        f"{stock_code} 当前归类为{technical_state}；{module_part}；{event_part}；{theme_part}；"
        f"{capital_part}；市场环境属于{market_regime.risk_mode} / {market_regime.style_lead}；{tradeability_part}。"
    )
    if candidate_source.startswith("module_") and not related_events:
        risk_notes.append("偏技术驱动，基本面支撑不足")
    if candidate_source == "event_direct" and not module_agg.get("active_module_ids"):
        risk_notes.append("事件驱动为主，技术确认不足")
    return summary, list(dict.fromkeys(risk_notes))


def _pick_modules_for_candidate(
    snapshot: MarketRegimeSnapshot,
    recommended_modules: list[TechnicalModule],
    *,
    event_support_score: float,
    theme_alignment_score: float,
    account: AccountConstraints,
) -> list[str]:
    selected: list[str] = []

    for module in recommended_modules:
        if module.role == "environment_filter" and module.module_id not in selected:
            selected.append(module.module_id)
            break

    if snapshot.risk_mode == "selective":
        for module in recommended_modules:
            if module.family.startswith("repair") or module.family == "group_rotation":
                if module.module_id not in selected:
                    selected.append(module.module_id)
                if len(selected) >= 5:
                    return selected
    else:
        for module in recommended_modules:
            if module.role == "candidate_generator" and module.module_id not in selected:
                selected.append(module.module_id)
                break

    if theme_alignment_score >= 0.6:
        for module in recommended_modules:
            if module.role == "theme_mapper" or module.family == "group_rotation":
                if module.module_id not in selected:
                    selected.append(module.module_id)
                if len(selected) >= 5:
                    return selected

    if event_support_score >= 0.65:
        for module in recommended_modules:
            if module.role in {"technical_confirmer", "entry_timing", "intraday_confirmer"}:
                if module.module_id not in selected:
                    selected.append(module.module_id)
                if len(selected) >= 5:
                    return selected

    if account.avoid_chasing_limit_up or account.avoid_low_liquidity:
        for module in recommended_modules:
            if module.role == "risk_filter" and module.module_id not in selected:
                selected.append(module.module_id)
                if len(selected) >= 5:
                    return selected

    return selected[:5]


def _infer_technical_state(
    snapshot: MarketRegimeSnapshot,
    *,
    candidate_source: str,
    event_support_score: float,
    theme_alignment_score: float,
) -> str:
    if snapshot.risk_mode == "risk_off":
        return "defensive_scan_only"
    if candidate_source == "event_theme_resonance" and event_support_score >= 0.65 and theme_alignment_score >= 0.6:
        return "event_theme_resonance"
    if snapshot.risk_mode == "selective" and event_support_score >= 0.55:
        return "selective_repair_watch"
    if theme_alignment_score >= 0.65:
        return "theme_rotation_watch"
    if event_support_score >= 0.65:
        return "event_breakout_watch"
    return "ranked_watchlist"


def _text_signal_score(stock_code: str, industry_tags: list[str], text_watch_records: list[dict]) -> tuple[float | None, list[dict]]:
    relevant_records = find_relevant_text_signals(
        text_watch_records,
        stock_code=stock_code,
        industry_tags=industry_tags,
        limit=3,
    )
    if not relevant_records:
        return None, []

    bias = text_signal_bias(relevant_records)
    direct_match = any(_normalize_stock_code(record.get("stock_code", "")) == stock_code for record in relevant_records)
    max_priority = max(int(record.get("priority_score", 0) or 0) for record in relevant_records)
    score = 0.5 + bias * 0.25
    if direct_match:
        score += 0.08
    score += min(0.12, max_priority / 120.0)
    return round(_clamp_score(score), 3), relevant_records


def _is_actionable_module_signal(signal: ModuleSignal, module_role_map: dict[str, str]) -> bool:
    role = module_role_map.get(signal.module_id, "")
    if signal.signal_type not in {"strong", "moderate"}:
        return False
    return role in {
        "candidate_generator",
        "candidate_compressor",
        "watchlist_builder",
    }


def build_candidate_cards(
    trade_date: str,
    market_regime: MarketRegimeSnapshot,
    account: AccountConstraints,
    technical_modules: list[TechnicalModule],
    event_cards: list[EventCard],
    theme_cards: list[ThemeCard],
    macro_event_cards: list[MacroEventCard] | None = None,
    capital_cards: list[CapitalBehaviorCard] | None = None,
    text_watch_records: list[dict] | None = None,
    module_signals: list[ModuleSignal] | None = None,
    available_module_ids: set[str] | None = None,
    setup_policy: dict[str, SetupPolicySignal] | None = None,
) -> list[CandidateCard]:
    text_watch_records = text_watch_records if text_watch_records is not None else load_text_signal_watch(trade_date)
    quote_map = _load_market_quote_map(trade_date)
    enabled_module_ids = set(available_module_ids) if available_module_ids is not None else {module.module_id for module in technical_modules}
    module_role_map = {module.module_id: module.role for module in technical_modules}
    event_map: dict[str, list[EventCard]] = {}
    theme_map: dict[str, list[ThemeCard]] = {}

    for event in event_cards:
        for stock_code in event.stock_codes:
            normalized = _normalize_stock_code(stock_code)
            if not normalized:
                continue
            event_map.setdefault(normalized, []).append(event)

    for theme in theme_cards:
        for stock_code in theme.priority_stocks:
            normalized = _normalize_stock_code(stock_code)
            if not normalized:
                continue
            theme_map.setdefault(normalized, []).append(theme)

    # 聚合模块信号
    module_map: dict[str, list[ModuleSignal]] = {}
    if module_signals:
        module_map = aggregate_module_signals(module_signals)

    candidate_universe = sorted(set(event_map) | set(theme_map) | set(module_map))
    if account.main_board_only:
        candidate_universe = [code for code in candidate_universe if is_main_board(code)]
    cards: list[CandidateCard] = []

    for stock_code in candidate_universe:
        related_events = event_map.get(stock_code, [])
        related_themes = theme_map.get(stock_code, [])
        related_module_signals = module_map.get(stock_code, [])
        actionable_module_signals = [
            signal
            for signal in related_module_signals
            if _is_actionable_module_signal(signal, module_role_map)
        ]

        positive_signal = (
            any(card.bullish_bearish == "bullish" for card in related_events)
            or bool(related_themes)
            or bool(actionable_module_signals)
        )
        if not positive_signal:
            continue

        has_event = bool(related_events)
        has_theme = bool(related_themes)
        has_module = bool(actionable_module_signals)

        if has_event and has_theme and has_module:
            candidate_source = "full_resonance"
        elif has_event and has_theme:
            candidate_source = "event_theme_resonance"
        elif has_event and has_module:
            candidate_source = "module_event_resonance"
        elif has_theme and has_module:
            candidate_source = "module_theme_resonance"
        elif has_module:
            candidate_source = "module_direct"
        elif has_event:
            candidate_source = "event_direct"
        else:
            candidate_source = "theme_priority"

        event_support_score = _event_score(related_events)
        theme_alignment_score = _theme_score(stock_code, related_themes, related_events, theme_cards)
        module_score = compute_module_score(related_module_signals)
        module_agg = merge_signals_for_stock(related_module_signals)
        capital_confirmation_score = _capital_score(stock_code, capital_cards)
        industry_tags = list(
            {
                tag.strip()
                for event in related_events
                for tag in event.industry_tags
                if tag.strip()
            }
            | {
                tag.strip()
                for theme in related_themes
                for tag in theme.priority_industries
                if tag.strip()
            }
        )
        macro_alignment_score, related_macro_events = _macro_alignment_score(
            industry_tags=industry_tags,
            macro_event_cards=macro_event_cards,
        )
        text_signal_score, relevant_text_signals = _text_signal_score(stock_code, industry_tags, text_watch_records)
        information_edge_score = _information_edge_score(
            related_events=related_events,
            related_themes=related_themes,
            macro_alignment_score=macro_alignment_score,
            text_signal_score=text_signal_score,
        )
        last_close_price, min_lot_cost, tradeability_score, tradeability_verdict, tradeability_risks = _tradeability_assessment(
            account,
            stock_code,
            quote_map.get(stock_code),
        )
        market_fit_score = _market_fit_score(
            market_regime,
            candidate_source=candidate_source,
            event_support_score=event_support_score,
            theme_alignment_score=theme_alignment_score,
            macro_alignment_score=macro_alignment_score,
        )

        # active_module_ids 合并规则推荐 + 模块信号实际产出
        rule_module_ids = _pick_modules_for_candidate(
            market_regime,
            [module for module in technical_modules if module.module_id in enabled_module_ids],
            event_support_score=event_support_score,
            theme_alignment_score=theme_alignment_score,
            account=account,
        )
        active_module_ids = list(dict.fromkeys(rule_module_ids + module_agg["active_module_ids"]))[:5]

        active_modules = [module for module in technical_modules if module.module_id in active_module_ids]
        account_fit_score = _account_fit_score(
            account,
            technical_modules=active_modules,
            candidate_source=candidate_source,
            tradeability_score=tradeability_score,
        )

        # technical_state 优先使用模块聚合结果，若无为规则推断
        if module_agg["technical_state"]:
            technical_state = module_agg["technical_state"]
        else:
            technical_state = _infer_technical_state(
                market_regime,
                candidate_source=candidate_source,
                event_support_score=event_support_score,
                theme_alignment_score=theme_alignment_score,
            )

        disqualify_flags: list[str] = []
        if market_regime.risk_mode == "risk_off":
            disqualify_flags.append("risk_off_market")
        if any(card.bullish_bearish == "bearish" for card in related_events):
            disqualify_flags.append("bearish_event_overhang")
        if account.max_new_positions_per_day <= 0:
            disqualify_flags.append("account_blocks_new_positions")
        if account.capital_total <= 0 or account.single_trade_capital_max <= 0:
            disqualify_flags.append("no_trade_budget")
        if market_regime.limit_up_temperature == "hot" and account.avoid_chasing_limit_up:
            disqualify_flags.append("avoid_chasing_limit_up")
        if text_signal_score is not None and text_signal_bias(relevant_text_signals) <= -0.35:
            disqualify_flags.append("text_watch_risk_overhang")
        if macro_alignment_score is not None and macro_alignment_score <= 0.35:
            disqualify_flags.append("macro_headwind")
        if module_agg.get("has_avoid"):
            disqualify_flags.append("module_avoid_signal")
        disqualify_flags.extend(tradeability_risks)

        fusion_result = evaluate_candidate_fusion(
            snapshot=market_regime,
            account=account,
            fusion_input=CandidateFusionInput(
                candidate_source=candidate_source,
                technical_state=technical_state,
                event_support_score=event_support_score,
                theme_alignment_score=theme_alignment_score,
                information_edge_score=information_edge_score,
                module_score=module_score,
                capital_confirmation_score=capital_confirmation_score,
                market_fit_score=market_fit_score,
                account_fit_score=account_fit_score,
                tradeability_score=tradeability_score,
                tradeability_verdict=tradeability_verdict,
                text_signal_score=text_signal_score,
                has_bearish_event=any(card.bullish_bearish == "bearish" for card in related_events),
                active_module_count=len(active_module_ids),
            ),
        )
        policy_signal = (setup_policy or {}).get(fusion_result.setup_type)
        policy_status = policy_signal.status if policy_signal is not None else "neutral"
        policy_score = policy_signal.score_multiplier if policy_signal is not None else 1.0
        policy_action_floor = policy_signal.action_score_floor if policy_signal is not None else 0.60
        policy_position_multiplier = policy_signal.position_cap_multiplier if policy_signal is not None else 1.0
        if policy_signal is not None:
            candidate_score = round(_clamp_score(fusion_result.fusion_score * policy_signal.score_multiplier), 3)
            if policy_signal.status == "disabled":
                disqualify_flags.append("setup_policy_disabled")
                if fusion_result.fusion_verdict == "actionable":
                    fusion_verdict = "watch"
                else:
                    fusion_verdict = fusion_result.fusion_verdict
            elif policy_signal.status == "cautious":
                disqualify_flags.append("setup_policy_cautious")
                fusion_verdict = "watch" if fusion_result.fusion_verdict == "actionable" else fusion_result.fusion_verdict
            else:
                fusion_verdict = fusion_result.fusion_verdict
            disqualify_flags.extend(policy_signal.notes)
        else:
            candidate_score = fusion_result.fusion_score
            fusion_verdict = fusion_result.fusion_verdict
        disqualify_flags.extend(fusion_result.fusion_notes)
        if fusion_verdict == "avoid":
            disqualify_flags.append("fusion_avoid")

        diagnostic_summary, diagnostic_risk_notes = _diagnostic_summary_clean(
            stock_code=stock_code,
            candidate_source=candidate_source,
            technical_state=technical_state,
            related_events=related_events,
            related_themes=related_themes,
            module_agg=module_agg,
            capital_confirmation_score=capital_confirmation_score,
            market_regime=market_regime,
            tradeability_verdict=tradeability_verdict,
            min_lot_cost=min_lot_cost,
            capital_total=account.capital_total,
        )

        supporting_cards = [card.event_id for card in related_events] + [card.theme_id for card in related_themes]
        rationale_parts = [
            f"source={candidate_source}",
            f"setup_type={fusion_result.setup_type}",
            f"setup_confidence={fusion_result.setup_confidence:.2f}",
            f"setup_policy={policy_status}",
            f"setup_policy_score={policy_score:.2f}",
            f"setup_action_floor={policy_action_floor:.2f}",
            f"setup_position_multiplier={policy_position_multiplier:.2f}",
            f"market_gate={fusion_result.market_gate_reason}",
            f"dominant_driver={fusion_result.dominant_driver}",
            f"market={market_regime.risk_mode}/{market_regime.style_lead}",
            f"fusion_verdict={fusion_verdict}",
            f"fusion_score={candidate_score:.2f}",
            f"market_permission={fusion_result.market_permission_score:.2f}",
            f"driver_conviction={fusion_result.driver_conviction_score:.2f}",
            f"thesis_quality={fusion_result.thesis_quality_score:.2f}",
            f"technical_confirmation={fusion_result.technical_confirmation_score:.2f}",
            f"execution_readiness={fusion_result.execution_readiness_score:.2f}",
            f"event_score={event_support_score:.2f}",
            f"theme_score={theme_alignment_score:.2f}",
            f"info_edge={information_edge_score:.2f}",
            f"module_score={module_score:.2f}",
            f"account_score={account_fit_score:.2f}",
        ]
        if capital_confirmation_score is not None:
            rationale_parts.append(f"capital_score={capital_confirmation_score:.2f}")
        if text_signal_score is not None:
            rationale_parts.append(f"text_signal_score={text_signal_score:.2f}")
            rationale_parts.append(f"text_signal_focus={text_signal_focus_summary(relevant_text_signals)}")
        if macro_alignment_score is not None:
            rationale_parts.append(f"macro_alignment_score={macro_alignment_score:.2f}")
        if related_macro_events:
            rationale_parts.append(
                "macro_events=" + ", ".join(card.title for card in related_macro_events[:2])
            )
        if active_module_ids:
            rationale_parts.append(f"modules={', '.join(active_module_ids)}")
        if last_close_price is not None:
            rationale_parts.append(f"last_close={last_close_price:.2f}")
        if min_lot_cost is not None:
            rationale_parts.append(f"min_lot_cost={min_lot_cost:.0f}")
        if tradeability_score is not None:
            rationale_parts.append(f"tradeability_score={tradeability_score:.2f}")
            rationale_parts.append(f"tradeability={tradeability_verdict}")
        if disqualify_flags:
            rationale_parts.append(f"flags={', '.join(disqualify_flags)}")

        cards.append(
            CandidateCard(
                candidate_id=f"candidate_{trade_date}_{stock_code.replace('.', '_')}",
                stock_code=stock_code,
                trade_date=trade_date,
                candidate_source=candidate_source,
                candidate_score=candidate_score,
                fusion_score=candidate_score,
                fusion_verdict=fusion_verdict,
                setup_type=fusion_result.setup_type,
                setup_confidence=fusion_result.setup_confidence,
                setup_policy_status=policy_status,
                setup_policy_score=policy_score,
                setup_action_floor=policy_action_floor,
                setup_position_cap_multiplier=policy_position_multiplier,
                market_gate_pass=fusion_result.market_gate_pass,
                market_gate_reason=fusion_result.market_gate_reason,
                dominant_driver=fusion_result.dominant_driver,
                technical_state=technical_state,
                market_permission_score=fusion_result.market_permission_score,
                driver_conviction_score=fusion_result.driver_conviction_score,
                thesis_quality_score=fusion_result.thesis_quality_score,
                technical_confirmation_score=fusion_result.technical_confirmation_score,
                execution_readiness_score=fusion_result.execution_readiness_score,
                event_support_score=event_support_score,
                theme_alignment_score=theme_alignment_score,
                macro_alignment_score=macro_alignment_score,
                capital_confirmation_score=capital_confirmation_score,
                information_edge_score=information_edge_score,
                market_fit_score=market_fit_score,
                account_fit_score=account_fit_score,
                active_module_ids=active_module_ids,
                disqualify_flags=list(dict.fromkeys(disqualify_flags)),
                supporting_cards=supporting_cards,
                supporting_macro_events=[card.macro_event_id for card in related_macro_events],
                candidate_rationale="; ".join(rationale_parts),
                last_close_price=last_close_price,
                board_lot_size=account.board_lot_size,
                estimated_min_lot_cost=min_lot_cost,
                account_tradeability_score=tradeability_score,
                tradeability_verdict=tradeability_verdict,
                diagnostic_summary=diagnostic_summary,
                diagnostic_risk_notes=diagnostic_risk_notes,
                fusion_notes=list(fusion_result.fusion_notes),
            )
        )

    cards.sort(
        key=lambda card: (
            0 if card.market_gate_pass else 1,
            -(card.setup_confidence if card.setup_confidence is not None else 0.0),
            -(card.candidate_score if card.candidate_score is not None else 0.0),
            len(card.disqualify_flags),
            card.stock_code,
        )
    )
    return cards


def save_candidate_cards(trade_date: str, cards: list[CandidateCard], path: Path | None = None) -> Path:
    output_path = path or (candidate_processed_dir() / f"candidate_cards_{trade_date}.json")
    output_path.write_text(json.dumps([asdict(card) for card in cards], ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
