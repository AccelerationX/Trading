from __future__ import annotations

from collections import defaultdict

from trading_system.decision.live_trade_state import SystemTradeRecord


FINAL_STATUSES = {"filled", "partial", "cancelled", "skipped"}


def _safe_avg(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def build_execution_behavior(records: list[SystemTradeRecord]) -> dict:
    grouped: dict[str, list[SystemTradeRecord]] = defaultdict(list)
    for record in records:
        setup_type = record.setup_type or "unknown"
        grouped[setup_type].append(record)

    summary: list[dict] = []
    for setup_type, setup_records in grouped.items():
        finalized = [record for record in setup_records if record.execution_status in FINAL_STATUSES]
        filled_like = [record for record in finalized if record.execution_status in {"filled", "partial"}]
        partial = [record for record in finalized if record.execution_status == "partial"]
        skipped_like = [record for record in finalized if record.execution_status in {"cancelled", "skipped"}]
        buy_records = [record for record in filled_like if record.order_action == "buy"]

        fill_ratios = [
            min(1.0, max(0.0, float(record.actual_shares or 0) / float(record.suggested_shares or 1)))
            for record in filled_like
            if record.suggested_shares not in (None, 0)
        ]
        buy_slippage = [
            (float(record.actual_price) / float(record.suggested_price_reference)) - 1.0
            for record in buy_records
            if record.actual_price not in (None, 0) and record.suggested_price_reference not in (None, 0)
        ]
        sell_slippage = [
            (float(record.actual_price) / float(record.suggested_price_reference)) - 1.0
            for record in filled_like
            if record.order_action == "sell"
            and record.actual_price not in (None, 0)
            and record.suggested_price_reference not in (None, 0)
        ]

        finalized_count = len(finalized)
        fill_rate = None if finalized_count == 0 else round(len(filled_like) / finalized_count, 4)
        skip_rate = None if finalized_count == 0 else round(len(skipped_like) / finalized_count, 4)
        partial_rate = None if finalized_count == 0 else round(len(partial) / finalized_count, 4)

        notes: list[str] = []
        if finalized_count >= 2:
            if skip_rate is not None and skip_rate >= 0.5:
                notes.append("frequent_skip_or_cancel")
            if partial_rate is not None and partial_rate >= 0.4:
                notes.append("partial_fill_common")
            if buy_slippage and _safe_avg(buy_slippage) is not None and (_safe_avg(buy_slippage) or 0.0) >= 0.02:
                notes.append("buy_slippage_high")
            if fill_rate is not None and fill_rate >= 0.8 and (not buy_slippage or (abs(_safe_avg(buy_slippage) or 0.0) <= 0.005)):
                notes.append("execution_followthrough_good")

        summary.append(
            {
                "setup_type": setup_type,
                "record_count": len(setup_records),
                "finalized_count": finalized_count,
                "fill_rate": fill_rate,
                "skip_rate": skip_rate,
                "partial_rate": partial_rate,
                "avg_fill_ratio": _safe_avg(fill_ratios),
                "avg_buy_slippage_pct": _safe_avg(buy_slippage),
                "avg_sell_slippage_pct": _safe_avg(sell_slippage),
                "notes": notes,
            }
        )

    summary.sort(key=lambda item: (-item["finalized_count"], item["setup_type"]))
    finalized_total = sum(int(item["finalized_count"]) for item in summary)
    return {
        "record_count": len(records),
        "setup_count": len(summary),
        "finalized_count": finalized_total,
        "setup_summary": summary,
    }
