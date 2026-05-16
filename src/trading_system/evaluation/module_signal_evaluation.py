from __future__ import annotations

from collections import defaultdict

import pandas as pd

from trading_system.context.cards import CandidateCard, MarketRegimeSnapshot, TradePlanCard
from trading_system.signal.scanners.base import ModuleSignal


def _prepare_history_index(history: pd.DataFrame) -> dict[str, pd.DataFrame]:
    prepared: dict[str, pd.DataFrame] = {}
    if history.empty:
        return prepared

    frame = history.copy()
    frame["stock_code"] = frame["stock_code"].astype(str).str.strip().str.upper()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce")
    frame = frame.dropna(subset=["stock_code", "trade_date", "close"])
    frame = frame.sort_values(["stock_code", "trade_date"]).reset_index(drop=True)

    for stock_code, group in frame.groupby("stock_code", sort=False):
        prepared[stock_code] = group.reset_index(drop=True)
    return prepared


def _round_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 4)


def _compute_forward_return(group: pd.DataFrame, start_index: int, horizon: int) -> float | None:
    end_index = start_index + horizon
    if end_index >= len(group):
        return None
    entry_close = float(group.iloc[start_index]["close"])
    future_close = float(group.iloc[end_index]["close"])
    if entry_close == 0:
        return None
    return (future_close / entry_close) - 1.0


def _evaluate_signal(
    signal: ModuleSignal,
    history_index: dict[str, pd.DataFrame],
    *,
    horizons: tuple[int, ...],
    candidate_codes: set[str],
    planned_codes: set[str],
) -> dict:
    stock_code = signal.stock_code.strip().upper()
    group = history_index.get(stock_code)
    trade_date = pd.to_datetime(signal.trade_date, errors="coerce")

    result = {
        "module_id": signal.module_id,
        "stock_code": stock_code,
        "trade_date": signal.trade_date,
        "signal_type": signal.signal_type,
        "strength": signal.strength,
        "confidence": signal.confidence,
        "technical_state": signal.technical_state,
        "candidate_selected": stock_code in candidate_codes,
        "trade_plan_selected": stock_code in planned_codes,
        "entry_close": None,
        "forward_returns": {},
    }

    if group is None or pd.isna(trade_date):
        for horizon in horizons:
            result["forward_returns"][f"{horizon}d"] = None
        return result

    matched = group.index[group["trade_date"] == trade_date].tolist()
    if not matched:
        for horizon in horizons:
            result["forward_returns"][f"{horizon}d"] = None
        return result

    start_index = matched[0]
    entry_close = float(group.iloc[start_index]["close"])
    result["entry_close"] = round(entry_close, 4)
    for horizon in horizons:
        result["forward_returns"][f"{horizon}d"] = _round_or_none(
            _compute_forward_return(group, start_index, horizon)
        )
    return result


def _summarize_module(module_id: str, rows: list[dict], horizons: tuple[int, ...]) -> dict:
    signal_type_counts: dict[str, int] = {}
    for row in rows:
        signal_type_counts[row["signal_type"]] = signal_type_counts.get(row["signal_type"], 0) + 1

    horizon_summary: dict[str, dict] = {}
    for horizon in horizons:
        key = f"{horizon}d"
        values = [
            float(row["forward_returns"][key])
            for row in rows
            if row["forward_returns"].get(key) is not None
        ]
        if values:
            avg_return = sum(values) / len(values)
            win_rate = sum(1 for value in values if value > 0) / len(values)
            hit_rate_3pct = sum(1 for value in values if value >= 0.03) / len(values)
            horizon_summary[key] = {
                "sample_count": len(values),
                "avg_return": round(avg_return, 4),
                "win_rate": round(win_rate, 4),
                "hit_rate_3pct": round(hit_rate_3pct, 4),
            }
        else:
            horizon_summary[key] = {
                "sample_count": 0,
                "avg_return": None,
                "win_rate": None,
                "hit_rate_3pct": None,
            }

    return {
        "module_id": module_id,
        "signal_count": len(rows),
        "unique_stock_count": len({row["stock_code"] for row in rows}),
        "candidate_overlap_count": sum(1 for row in rows if row["candidate_selected"]),
        "trade_plan_overlap_count": sum(1 for row in rows if row["trade_plan_selected"]),
        "avg_strength": round(sum(float(row["strength"]) for row in rows) / len(rows), 4) if rows else None,
        "avg_confidence": round(sum(float(row["confidence"]) for row in rows) / len(rows), 4) if rows else None,
        "signal_type_counts": signal_type_counts,
        "horizons": horizon_summary,
    }


def build_module_signal_evaluation(
    trade_date: str,
    module_signals: list[ModuleSignal],
    history: pd.DataFrame,
    *,
    market_regime: MarketRegimeSnapshot | None = None,
    candidate_cards: list[CandidateCard] | None = None,
    trade_plan_cards: list[TradePlanCard] | None = None,
    horizons: tuple[int, ...] = (1, 3, 5),
) -> dict:
    history_index = _prepare_history_index(history)
    candidate_codes = {
        card.stock_code.strip().upper()
        for card in (candidate_cards or [])
    }
    planned_codes = {
        card.stock_code.strip().upper()
        for card in (trade_plan_cards or [])
    }

    evaluations = [
        _evaluate_signal(
            signal,
            history_index,
            horizons=horizons,
            candidate_codes=candidate_codes,
            planned_codes=planned_codes,
        )
        for signal in module_signals
    ]

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in evaluations:
        grouped[row["module_id"]].append(row)

    summary = [
        _summarize_module(module_id, rows, horizons)
        for module_id, rows in grouped.items()
    ]
    summary.sort(key=lambda item: (-item["trade_plan_overlap_count"], -item["signal_count"], item["module_id"]))

    payload = {
        "trade_date": trade_date,
        "signal_count": len(module_signals),
        "module_count": len(summary),
        "candidate_count": len(candidate_codes),
        "trade_plan_count": len(planned_codes),
        "horizons": [f"{horizon}d" for horizon in horizons],
        "market_regime": {
            "risk_mode": market_regime.risk_mode,
            "style_lead": market_regime.style_lead,
            "theme_concentration": market_regime.theme_concentration,
        }
        if market_regime is not None
        else None,
        "module_summary": summary,
        "signal_evaluations": evaluations,
    }
    return payload
