from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date

from trading_system.decision.live_trade_state import SystemTradeRecord


@dataclass(slots=True)
class OpenLot:
    trade_date: str
    stock_code: str
    setup_type: str
    shares: int
    price: float


def _usable_status(record: SystemTradeRecord) -> bool:
    return record.execution_status in {"filled", "partial"} and record.actual_shares not in (None, 0) and record.actual_price not in (None, 0)


def _holding_days(entry_date: str, exit_date: str) -> int | None:
    try:
        return max(0, (date.fromisoformat(exit_date) - date.fromisoformat(entry_date)).days)
    except ValueError:
        return None


def build_execution_feedback(records: list[SystemTradeRecord]) -> dict:
    ordered_records = sorted(records, key=lambda item: (item.trade_date, item.order_action, item.stock_code, item.record_id))
    open_lots: dict[str, deque[OpenLot]] = defaultdict(deque)
    closed_rows: list[dict] = []

    for record in ordered_records:
        if not _usable_status(record):
            continue
        shares = int(record.actual_shares or 0)
        price = float(record.actual_price or 0.0)
        if shares <= 0 or price <= 0:
            continue

        if record.order_action == "buy":
            open_lots[record.stock_code].append(
                OpenLot(
                    trade_date=record.trade_date,
                    stock_code=record.stock_code,
                    setup_type=record.setup_type or "unknown",
                    shares=shares,
                    price=price,
                )
            )
            continue

        if record.order_action != "sell":
            continue

        remaining = shares
        lot_queue = open_lots.get(record.stock_code, deque())
        while remaining > 0 and lot_queue:
            lot = lot_queue[0]
            matched_shares = min(remaining, lot.shares)
            realized_return = round((price / lot.price) - 1.0, 4)
            closed_rows.append(
                {
                    "stock_code": record.stock_code,
                    "setup_type": lot.setup_type,
                    "entry_trade_date": lot.trade_date,
                    "exit_trade_date": record.trade_date,
                    "holding_days": _holding_days(lot.trade_date, record.trade_date),
                    "matched_shares": matched_shares,
                    "entry_price": lot.price,
                    "exit_price": price,
                    "realized_return": realized_return,
                }
            )
            lot.shares -= matched_shares
            remaining -= matched_shares
            if lot.shares <= 0:
                lot_queue.popleft()

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in closed_rows:
        grouped[row["setup_type"]].append(row)

    summary: list[dict] = []
    for setup_type, rows in grouped.items():
        returns = [float(row["realized_return"]) for row in rows]
        holding_days = [row["holding_days"] for row in rows if row["holding_days"] is not None]
        summary.append(
            {
                "setup_type": setup_type,
                "closed_trade_count": len(rows),
                "matched_share_total": sum(int(row["matched_shares"]) for row in rows),
                "avg_realized_return": round(sum(returns) / len(returns), 4) if returns else None,
                "win_rate": round(sum(1 for value in returns if value > 0) / len(returns), 4) if returns else None,
                "avg_holding_days": round(sum(holding_days) / len(holding_days), 2) if holding_days else None,
            }
        )
    summary.sort(key=lambda item: (-(item.get("avg_realized_return") or -999), -item["closed_trade_count"], item["setup_type"]))

    return {
        "closed_trade_count": len(closed_rows),
        "setup_count": len(summary),
        "setup_summary": summary,
        "closed_trades": closed_rows,
    }
