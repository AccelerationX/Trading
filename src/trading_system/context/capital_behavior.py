from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from trading_system.config.paths import INBOX_DIR, PROCESSED_DATA_DIR
from trading_system.context.cards import CapitalBehaviorCard
from trading_system.ingest.simple_tabular import read_records


def _latest_matching_file(directory: Path) -> Path | None:
    candidates = sorted(
        [
            path
            for pattern in ("*.json", "*.csv")
            for path in directory.glob(pattern)
            if path.is_file()
        ],
        key=lambda path: (path.stat().st_mtime, path.name),
        reverse=True,
    )
    if not candidates:
        return None
    return candidates[0]


def _capital_processed_dir() -> Path:
    directory = PROCESSED_DATA_DIR / "capital"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _pick_text(record: dict, *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _pick_float(record: dict, *keys: str) -> float | None:
    for key in keys:
        value = record.get(key)
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _normalize_stock_code(stock_code: str) -> str:
    return stock_code.strip().upper()


def _strength_from_amount(amount: float | None) -> str:
    if amount is None:
        return "medium"
    abs_amount = abs(amount)
    if abs_amount >= 500000000:
        return "high"
    if abs_amount >= 100000000:
        return "medium"
    return "low"


def _support_distribution_from_amount(amount: float | None) -> str:
    if amount is None:
        return "neutral"
    if amount > 0:
        return "support"
    if amount < 0:
        return "distribution"
    return "neutral"


def _consistency_from_amount(amount: float | None) -> float:
    if amount is None:
        return 0.5
    abs_amount = abs(amount)
    if abs_amount >= 500000000:
        return 0.82
    if abs_amount >= 100000000:
        return 0.68
    if abs_amount >= 30000000:
        return 0.58
    return 0.48


def _dragon_tiger_style(record: dict) -> str:
    seat = _pick_text(record, "seat_or_channel", "seat_name", "seat")
    reason = _pick_text(record, "reason", "reason_text")
    text = f"{seat} {reason}".lower()
    if any(token in text for token in ("institution", "机构")):
        return "institutional_active"
    if any(token in text for token in ("hot money", "游资", "营业部")):
        return "hot_money_active"
    return "dragon_tiger_mixed"


def _northbound_style(record: dict) -> str:
    text = f"{_pick_text(record, 'source_name', 'channel')} {_pick_text(record, 'capital_signal_type', 'reason')}".lower()
    if any(token in text for token in ("northbound", "north", "沪股通", "深股通")):
        return "northbound_flow"
    if any(token in text for token in ("margin", "融资", "融券")):
        return "margin_flow"
    return "cross_border_and_margin"


def _block_trade_style(record: dict) -> str:
    premium = _pick_float(record, "premium_pct", "discount_pct")
    abnormal_ratio = _pick_float(record, "abnormal_volume_ratio", "volume_ratio")
    if premium is not None and premium > 0:
        return "block_trade_premium"
    if abnormal_ratio is not None and abnormal_ratio >= 2.0:
        return "abnormal_volume"
    return "block_trade_mixed"


def _build_card(
    *,
    trade_date: str,
    source_id: str,
    stock_code: str,
    signal_type: str,
    participation_strength: str,
    consistency_score: float,
    suspected_style: str,
    support_or_distribution: str,
    warning_flags: list[str],
    source_path: Path,
    llm_summary: str,
) -> CapitalBehaviorCard:
    normalized = _normalize_stock_code(stock_code)
    return CapitalBehaviorCard(
        card_id=f"{trade_date}_{source_id}_{normalized.replace('.', '_')}",
        stock_code=normalized,
        trade_date=trade_date,
        capital_signal_type=signal_type,
        participation_strength=participation_strength,
        consistency_score=round(consistency_score, 3),
        suspected_style=suspected_style,
        support_or_distribution=support_or_distribution,
        warning_flags=warning_flags,
        source_refs=[str(source_path)],
        llm_summary=llm_summary,
    )


def build_capital_behavior_cards_from_dragon_tiger_board(trade_date: str, path: Path | None = None) -> list[CapitalBehaviorCard]:
    source_path = path or _latest_matching_file(INBOX_DIR / "dragon_tiger_board")
    if source_path is None:
        return []

    records = read_records(source_path)
    cards: list[CapitalBehaviorCard] = []
    for record in records:
        stock_code = _pick_text(record, "stock_code", "ts_code", "code")
        if not stock_code:
            continue
        net_amount = _pick_float(record, "net_amount", "net_buy_amount", "net_buy", "buy_sell_diff")
        warning_flags: list[str] = []
        if _pick_text(record, "reason", "reason_text"):
            warning_flags.append("needs_reason_review")
        cards.append(
            _build_card(
                trade_date=trade_date,
                source_id="dragon_tiger_board",
                stock_code=stock_code,
                signal_type="dragon_tiger_board",
                participation_strength=_strength_from_amount(net_amount),
                consistency_score=_consistency_from_amount(net_amount),
                suspected_style=_dragon_tiger_style(record),
                support_or_distribution=_support_distribution_from_amount(net_amount),
                warning_flags=warning_flags,
                source_path=source_path,
                llm_summary="Dragon-tiger board flow draft. Use LLM to interpret seat composition and whether support is sustainable.",
            )
        )
    return cards


def build_capital_behavior_cards_from_northbound_and_margin_flow(trade_date: str, path: Path | None = None) -> list[CapitalBehaviorCard]:
    source_path = path or _latest_matching_file(INBOX_DIR / "northbound_and_margin_flow")
    if source_path is None:
        return []

    records = read_records(source_path)
    cards: list[CapitalBehaviorCard] = []
    for record in records:
        stock_code = _pick_text(record, "stock_code", "ts_code", "code")
        if not stock_code:
            continue
        net_amount = _pick_float(
            record,
            "net_amount",
            "northbound_net_amount",
            "northbound_net_buy",
            "margin_net_amount",
            "margin_change",
        )
        cards.append(
            _build_card(
                trade_date=trade_date,
                source_id="northbound_and_margin_flow",
                stock_code=stock_code,
                signal_type="northbound_and_margin_flow",
                participation_strength=_strength_from_amount(net_amount),
                consistency_score=_consistency_from_amount(net_amount),
                suspected_style=_northbound_style(record),
                support_or_distribution=_support_distribution_from_amount(net_amount),
                warning_flags=[],
                source_path=source_path,
                llm_summary="Northbound or margin flow draft. Use LLM to judge whether the flow confirms medium-risk participation or short-term crowding.",
            )
        )
    return cards


def build_capital_behavior_cards_from_block_trade_and_abnormal_volume(trade_date: str, path: Path | None = None) -> list[CapitalBehaviorCard]:
    source_path = path or _latest_matching_file(INBOX_DIR / "block_trade_and_abnormal_volume")
    if source_path is None:
        return []

    records = read_records(source_path)
    cards: list[CapitalBehaviorCard] = []
    for record in records:
        stock_code = _pick_text(record, "stock_code", "ts_code", "code")
        if not stock_code:
            continue
        premium_pct = _pick_float(record, "premium_pct")
        discount_pct = _pick_float(record, "discount_pct")
        abnormal_ratio = _pick_float(record, "abnormal_volume_ratio", "volume_ratio")
        synthetic_amount = _pick_float(record, "net_amount", "amount", "block_trade_amount")
        support_or_distribution = "neutral"
        warning_flags: list[str] = []
        consistency_score = 0.5
        if premium_pct is not None and premium_pct > 0:
            support_or_distribution = "support"
            consistency_score = 0.62
        elif discount_pct is not None and discount_pct < 0:
            support_or_distribution = "distribution"
            consistency_score = 0.42
        if abnormal_ratio is not None and abnormal_ratio >= 2.0:
            warning_flags.append("abnormal_turnover")
            consistency_score += 0.08
        cards.append(
            _build_card(
                trade_date=trade_date,
                source_id="block_trade_and_abnormal_volume",
                stock_code=stock_code,
                signal_type="block_trade_and_abnormal_volume",
                participation_strength=_strength_from_amount(synthetic_amount),
                consistency_score=consistency_score,
                suspected_style=_block_trade_style(record),
                support_or_distribution=support_or_distribution,
                warning_flags=warning_flags,
                source_path=source_path,
                llm_summary="Block-trade and abnormal-volume draft. Use LLM to judge whether the turnover reflects accumulation, distribution, or pure event noise.",
            )
        )
    return cards


def build_capital_behavior_cards(
    trade_date: str,
    *,
    dragon_tiger_path: Path | None = None,
    northbound_margin_path: Path | None = None,
    block_trade_path: Path | None = None,
) -> list[CapitalBehaviorCard]:
    cards = [
        *build_capital_behavior_cards_from_dragon_tiger_board(trade_date, dragon_tiger_path),
        *build_capital_behavior_cards_from_northbound_and_margin_flow(trade_date, northbound_margin_path),
        *build_capital_behavior_cards_from_block_trade_and_abnormal_volume(trade_date, block_trade_path),
    ]
    cards.sort(key=lambda card: (card.stock_code, card.capital_signal_type, card.card_id))
    return cards


def save_capital_behavior_cards(trade_date: str, cards: list[CapitalBehaviorCard], path: Path | None = None) -> Path:
    output_path = path or (_capital_processed_dir() / f"capital_behavior_cards_{trade_date}.json")
    output_path.write_text(json.dumps([asdict(card) for card in cards], ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
