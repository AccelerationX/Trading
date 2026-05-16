from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from trading_system.config.paths import INBOX_DIR, PROCESSED_DATA_DIR
from trading_system.context.cards import MarketRegimeSnapshot
from trading_system.ingest.simple_tabular import read_records


def market_processed_dir() -> Path:
    directory = PROCESSED_DATA_DIR / "context"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _latest_matching_file(directory: Path) -> Path:
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
        raise FileNotFoundError(f"No supported input files found in {directory}")
    return candidates[0]


def _as_float(record: dict, key: str, default: float = 0.0) -> float:
    value = record.get(key, default)
    try:
        if value in ("", None):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _load_market_breadth_record(path: Path | None = None) -> dict:
    source_path = path or _latest_matching_file(INBOX_DIR / "market_breadth_and_limit_structure")
    records = read_records(source_path)
    if not records:
        raise ValueError(f"No records found in {source_path}")
    return records[-1]


def _load_index_records(path: Path | None = None) -> list[dict]:
    source_path = path or _latest_matching_file(INBOX_DIR / "market_index_daily")
    records = read_records(source_path)
    if not records:
        raise ValueError(f"No index records found in {source_path}")
    return records


def _infer_style_lead(index_records: list[dict]) -> str:
    scores: list[tuple[str, float]] = []
    for record in index_records:
        name = str(record.get("index_name") or record.get("index_code") or "").lower()
        close_val = _as_float(record, "close", 0.0)
        prev_close_val = _as_float(record, "prev_close", 0.0)
        open_val = _as_float(record, "open", prev_close_val)
        if prev_close_val > 0:
            change_pct = close_val / prev_close_val - 1.0
        elif open_val > 0:
            change_pct = close_val / open_val - 1.0
        else:
            change_pct = 0.0
        scores.append((name, change_pct))

    if not scores:
        return "unknown"

    small_keywords = ("small", "micro", "创业", "中证1000", "中证2000", "2000", "1000")
    large_keywords = ("沪深300", "上证50", "50", "300", "blue")

    small_score = max((score for name, score in scores if any(key in name for key in small_keywords)), default=0.0)
    large_score = max((score for name, score in scores if any(key in name for key in large_keywords)), default=0.0)

    if small_score - large_score > 0.005:
        return "small_cap_lead"
    if large_score - small_score > 0.005:
        return "large_cap_lead"
    return "mixed"


def _infer_sentiment_cycle(
    *,
    breadth_strength: str,
    limit_up_count: float,
    broken_limit_up_count: float,
    limit_down_count: float,
    max_board_height: float,
) -> str:
    broken_ratio = broken_limit_up_count / max(limit_up_count, 1.0)
    if breadth_strength in {"strong", "positive"} and limit_up_count >= 35 and max_board_height >= 4 and broken_ratio <= 0.25:
        return "expansion"
    if breadth_strength in {"strong", "positive"} and limit_up_count >= 18 and broken_ratio <= 0.45:
        return "active_rotation"
    if breadth_strength == "weak" or limit_down_count >= 10 or broken_ratio >= 0.55:
        return "contraction"
    return "mixed_transition"


def _infer_leader_stability(*, limit_up_count: float, broken_limit_up_count: float, max_board_height: float) -> str:
    broken_ratio = broken_limit_up_count / max(limit_up_count, 1.0)
    if max_board_height >= 4 and broken_ratio <= 0.25:
        return "stable_leaders"
    if broken_ratio <= 0.45:
        return "mixed_leaders"
    return "fragile_leaders"


def _infer_event_driven_bias(
    *,
    risk_mode: str,
    style_lead: str,
    theme_concentration: str,
    max_board_height: float,
    limit_up_count: float,
) -> str:
    if risk_mode == "risk_off":
        return "defensive"
    if theme_concentration == "high" and max_board_height >= 4 and limit_up_count >= 20:
        return "theme_momentum"
    if style_lead == "large_cap_lead":
        return "institutional_trend"
    if style_lead == "small_cap_lead":
        return "speculative_rotation"
    return "mixed"


def build_market_regime_snapshot(
    trade_date: str,
    breadth_record: dict | None = None,
    index_records: list[dict] | None = None,
) -> MarketRegimeSnapshot:
    breadth = breadth_record or _load_market_breadth_record()
    indexes = index_records or _load_index_records()

    up_count = _as_float(breadth, "up_count", 0.0)
    down_count = _as_float(breadth, "down_count", 0.0)
    limit_up_count = _as_float(breadth, "limit_up_count", 0.0)
    limit_down_count = _as_float(breadth, "limit_down_count", 0.0)
    broken_limit_up_count = _as_float(breadth, "broken_limit_up_count", 0.0)
    total_turnover = _as_float(breadth, "total_turnover", 0.0)
    max_board_height = _as_float(breadth, "max_board_height", 0.0)

    breadth_ratio = (up_count + 1.0) / (down_count + 1.0)
    if breadth_ratio >= 1.8:
        breadth_strength = "strong"
    elif breadth_ratio >= 1.2:
        breadth_strength = "positive"
    elif breadth_ratio <= 0.7:
        breadth_strength = "weak"
    else:
        breadth_strength = "mixed"

    if limit_up_count >= 50 and broken_limit_up_count <= limit_up_count * 0.25:
        limit_up_temperature = "hot"
    elif limit_up_count >= 20:
        limit_up_temperature = "warm"
    elif limit_up_count <= 8 and limit_down_count >= 10:
        limit_up_temperature = "cold"
    else:
        limit_up_temperature = "neutral"

    if total_turnover >= 1500000000000:
        turnover_regime = "very_high"
    elif total_turnover >= 1000000000000:
        turnover_regime = "high"
    elif total_turnover >= 700000000000:
        turnover_regime = "normal"
    else:
        turnover_regime = "low"

    if breadth_strength in {"strong", "positive"} and limit_up_temperature in {"hot", "warm"}:
        market_bias = "bullish"
        risk_mode = "risk_on"
    elif breadth_strength == "weak" and limit_down_count >= 10:
        market_bias = "bearish"
        risk_mode = "risk_off"
    else:
        market_bias = "mixed"
        risk_mode = "selective"

    theme_concentration = "high" if max_board_height >= 4 and limit_up_count >= 20 else "normal"
    style_lead = _infer_style_lead(indexes)
    sentiment_cycle = _infer_sentiment_cycle(
        breadth_strength=breadth_strength,
        limit_up_count=limit_up_count,
        broken_limit_up_count=broken_limit_up_count,
        limit_down_count=limit_down_count,
        max_board_height=max_board_height,
    )
    leader_stability = _infer_leader_stability(
        limit_up_count=limit_up_count,
        broken_limit_up_count=broken_limit_up_count,
        max_board_height=max_board_height,
    )
    event_driven_bias = _infer_event_driven_bias(
        risk_mode=risk_mode,
        style_lead=style_lead,
        theme_concentration=theme_concentration,
        max_board_height=max_board_height,
        limit_up_count=limit_up_count,
    )

    opening_risk_note = ""
    if sentiment_cycle == "contraction":
        opening_risk_note = "Speculation is contracting. Prioritize defense, avoid weak follow-through, and treat rebounds skeptically."
    elif leader_stability == "fragile_leaders":
        opening_risk_note = "Leaders are fragile. Prefer only high-conviction names with clear event support and stable breadth."
    elif turnover_regime == "low" and risk_mode != "risk_on":
        opening_risk_note = "Liquidity is weak. Avoid overtrading and low-conviction breakouts."
    elif limit_up_temperature == "hot" and broken_limit_up_count > limit_up_count * 0.35:
        opening_risk_note = "Speculation is active but unstable. Watch for failed breakouts and intraday reversals."
    elif risk_mode == "risk_on":
        opening_risk_note = "Market supports offensive setups, but still require theme and liquidity confirmation."

    supporting_evidence = [
        f"up_count={int(up_count)}",
        f"down_count={int(down_count)}",
        f"limit_up_count={int(limit_up_count)}",
        f"limit_down_count={int(limit_down_count)}",
        f"broken_limit_up_count={int(broken_limit_up_count)}",
        f"total_turnover={total_turnover:.0f}",
        f"max_board_height={int(max_board_height)}",
        f"sentiment_cycle={sentiment_cycle}",
        f"leader_stability={leader_stability}",
        f"event_driven_bias={event_driven_bias}",
    ]

    if risk_mode == "risk_on":
        confidence = 0.75
    elif risk_mode == "risk_off":
        confidence = 0.7
    else:
        confidence = 0.55

    return MarketRegimeSnapshot(
        snapshot_id=f"market_regime_{trade_date}",
        trade_date=trade_date,
        market_bias=market_bias,
        risk_mode=risk_mode,
        breadth_strength=breadth_strength,
        limit_up_temperature=limit_up_temperature,
        turnover_regime=turnover_regime,
        style_lead=style_lead,
        theme_concentration=theme_concentration,
        sentiment_cycle=sentiment_cycle,
        leader_stability=leader_stability,
        event_driven_bias=event_driven_bias,
        opening_risk_note=opening_risk_note,
        confidence=confidence,
        supporting_evidence=supporting_evidence,
    )


def save_market_regime_snapshot(snapshot: MarketRegimeSnapshot, path: Path | None = None) -> Path:
    output_path = path or (market_processed_dir() / f"{snapshot.snapshot_id}.json")
    output_path.write_text(json.dumps(asdict(snapshot), ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
