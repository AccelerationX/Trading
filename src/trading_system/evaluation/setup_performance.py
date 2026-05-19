from __future__ import annotations

from collections import defaultdict

import pandas as pd

from trading_system.context.cards import CandidateCard, TradePlanCard


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


def _compute_excursion(group: pd.DataFrame, start_index: int, horizon: int) -> tuple[float | None, float | None]:
    end_index = min(start_index + horizon, len(group) - 1)
    if end_index <= start_index:
        return None, None
    entry_close = float(group.iloc[start_index]["close"])
    if entry_close == 0:
        return None, None
    future = group.iloc[start_index + 1 : end_index + 1]
    if future.empty:
        return None, None
    high_series = future["high"] if "high" in future else future["close"]
    low_series = future["low"] if "low" in future else future["close"]
    max_high = pd.to_numeric(high_series, errors="coerce").dropna().max()
    min_low = pd.to_numeric(low_series, errors="coerce").dropna().min()
    mfe = None if pd.isna(max_high) else (float(max_high) / entry_close) - 1.0
    mae = None if pd.isna(min_low) else (float(min_low) / entry_close) - 1.0
    return mfe, mae


def _evaluate_candidate(
    card: CandidateCard,
    plan_map: dict[tuple[str, str], TradePlanCard],
    history_index: dict[str, pd.DataFrame],
    *,
    horizons: tuple[int, ...],
) -> dict:
    stock_code = card.stock_code.strip().upper()
    group = history_index.get(stock_code)
    trade_date = pd.to_datetime(card.trade_date, errors="coerce")
    plan = plan_map.get((card.trade_date, stock_code))
    result = {
        "trade_date": card.trade_date,
        "stock_code": stock_code,
        "setup_type": card.setup_type or "unknown",
        "setup_confidence": card.setup_confidence,
        "candidate_score": card.candidate_score,
        "fusion_score": card.fusion_score,
        "fusion_verdict": card.fusion_verdict,
        "trade_action": plan.action if plan is not None else "none",
        "entry_close": None,
        "forward_returns": {},
        "mfe_5d": None,
        "mae_5d": None,
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
        result["forward_returns"][f"{horizon}d"] = _round_or_none(_compute_forward_return(group, start_index, horizon))
    mfe_5d, mae_5d = _compute_excursion(group, start_index, 5)
    result["mfe_5d"] = _round_or_none(mfe_5d)
    result["mae_5d"] = _round_or_none(mae_5d)
    return result


def _summarize_rows(rows: list[dict], horizons: tuple[int, ...]) -> dict[str, dict]:
    summary: dict[str, dict] = {}
    for horizon in horizons:
        key = f"{horizon}d"
        values = [float(row["forward_returns"][key]) for row in rows if row["forward_returns"].get(key) is not None]
        if values:
            avg_return = sum(values) / len(values)
            win_rate = sum(1 for value in values if value > 0) / len(values)
            hit_rate_3pct = sum(1 for value in values if value >= 0.03) / len(values)
            summary[key] = {
                "sample_count": len(values),
                "avg_return": round(avg_return, 4),
                "win_rate": round(win_rate, 4),
                "hit_rate_3pct": round(hit_rate_3pct, 4),
            }
        else:
            summary[key] = {
                "sample_count": 0,
                "avg_return": None,
                "win_rate": None,
                "hit_rate_3pct": None,
            }
    return summary


def _average(values: list[float | None]) -> float | None:
    usable = [float(value) for value in values if value is not None]
    if not usable:
        return None
    return round(sum(usable) / len(usable), 4)


def _summarize_setup(setup_type: str, rows: list[dict], horizons: tuple[int, ...]) -> dict:
    buy_pilot_rows = [row for row in rows if row["trade_action"] == "buy_pilot"]
    watch_rows = [row for row in rows if row["trade_action"] == "watch_only"]
    actionable_rows = [row for row in rows if row["fusion_verdict"] == "actionable"]
    return {
        "setup_type": setup_type,
        "sample_count": len(rows),
        "buy_pilot_count": len(buy_pilot_rows),
        "watch_only_count": len(watch_rows),
        "actionable_count": len(actionable_rows),
        "avg_candidate_score": _average([row.get("candidate_score") for row in rows]),
        "avg_setup_confidence": _average([row.get("setup_confidence") for row in rows]),
        "avg_mfe_5d": _average([row.get("mfe_5d") for row in rows]),
        "avg_mae_5d": _average([row.get("mae_5d") for row in rows]),
        "all_horizons": _summarize_rows(rows, horizons),
        "buy_pilot_horizons": _summarize_rows(buy_pilot_rows, horizons),
    }


def build_setup_performance(
    label: str,
    candidate_cards: list[CandidateCard],
    trade_plan_cards: list[TradePlanCard],
    history: pd.DataFrame,
    *,
    horizons: tuple[int, ...] = (1, 3, 5),
) -> dict:
    history_index = _prepare_history_index(history)
    plan_map = {
        (plan.trade_date, plan.stock_code.strip().upper()): plan
        for plan in trade_plan_cards
    }
    rows = [
        _evaluate_candidate(card, plan_map, history_index, horizons=horizons)
        for card in candidate_cards
        if card.setup_type
    ]

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["setup_type"]].append(row)

    setup_summary = [_summarize_setup(setup_type, grouped_rows, horizons) for setup_type, grouped_rows in grouped.items()]
    setup_summary.sort(
        key=lambda item: (
            -(item["buy_pilot_horizons"].get("3d", {}).get("avg_return") or -999),
            -item["buy_pilot_count"],
            -item["sample_count"],
            item["setup_type"],
        )
    )

    return {
        "label": label,
        "candidate_count": len(candidate_cards),
        "trade_plan_count": len(trade_plan_cards),
        "evaluated_setup_count": len(rows),
        "setup_count": len(setup_summary),
        "horizons": [f"{horizon}d" for horizon in horizons],
        "setup_summary": setup_summary,
        "setup_evaluations": rows,
    }
