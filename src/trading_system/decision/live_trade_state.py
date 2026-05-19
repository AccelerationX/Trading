from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from trading_system.config.paths import WORKSPACE_DIR
from trading_system.decision.holdings import (
    HoldingPosition,
    PortfolioSnapshot,
    default_holdings_path,
    load_portfolio_snapshot,
)


@dataclass(slots=True)
class SystemTradeRecord:
    record_id: str
    trade_date: str
    market_close_date: str = ""
    stock_code: str = ""
    stock_name: str = ""
    order_action: str = ""
    suggested_shares: int | None = None
    actual_shares: int | None = None
    suggested_price_reference: float | None = None
    actual_price: float | None = None
    execution_status: str = "pending_fill"
    profile_name: str = ""
    preferred_posture: str = ""
    setup_type: str = ""
    theme_name: str = ""
    buy_zone: str = ""
    sell_scope: str = ""
    stop_loss: str = ""
    take_profit: str = ""
    suggested_holding_days: int | None = None
    reason: str = ""
    rationale: str = ""
    risk_notes: list[str] | None = None
    source_trade_execution_path: str = ""
    fill_note: str = ""

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "trade_date": self.trade_date,
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "order_action": self.order_action,
            "fill_form": {
                "execution_status": self.execution_status,
                "actual_shares": self.actual_shares,
                "actual_price": self.actual_price,
                "fill_note": self.fill_note,
            },
            "editable_fields": [
                "fill_form.execution_status",
                "fill_form.actual_shares",
                "fill_form.actual_price",
                "fill_form.fill_note",
            ],
            "fill_hint": "Only edit fill_form.execution_status / actual_shares / actual_price / fill_note.",
            "suggestion": {
                "suggested_shares": self.suggested_shares,
                "suggested_price_reference": self.suggested_price_reference,
                "buy_zone": self.buy_zone,
                "sell_scope": self.sell_scope,
                "stop_loss": self.stop_loss,
                "take_profit": self.take_profit,
                "suggested_holding_days": self.suggested_holding_days,
            },
            "context": {
                "market_close_date": self.market_close_date,
                "profile_name": self.profile_name,
                "preferred_posture": self.preferred_posture,
                "setup_type": self.setup_type,
                "theme_name": self.theme_name,
                "reason": self.reason,
                "rationale": self.rationale,
                "risk_notes": list(self.risk_notes or []),
                "source_trade_execution_path": self.source_trade_execution_path,
            },
        }


def _record_from_payload(item: dict) -> SystemTradeRecord:
    fill_form = dict(item.get("fill_form", {}))
    suggestion = dict(item.get("suggestion", {}))
    context = dict(item.get("context", {}))
    return SystemTradeRecord(
        record_id=str(item.get("record_id", "")).strip(),
        trade_date=str(item.get("trade_date", "")).strip(),
        market_close_date=str(context.get("market_close_date", item.get("market_close_date", ""))).strip(),
        stock_code=str(item.get("stock_code", "")).strip().upper(),
        stock_name=str(item.get("stock_name", "")).strip(),
        order_action=str(item.get("order_action", "")).strip(),
        suggested_shares=int(suggestion["suggested_shares"]) if suggestion.get("suggested_shares") not in ("", None) else int(item["suggested_shares"]) if item.get("suggested_shares") not in ("", None) else None,
        actual_shares=int(fill_form["actual_shares"]) if fill_form.get("actual_shares") not in ("", None) else int(item["actual_shares"]) if item.get("actual_shares") not in ("", None) else None,
        suggested_price_reference=float(suggestion["suggested_price_reference"]) if suggestion.get("suggested_price_reference") not in ("", None) else float(item["suggested_price_reference"]) if item.get("suggested_price_reference") not in ("", None) else None,
        actual_price=float(fill_form["actual_price"]) if fill_form.get("actual_price") not in ("", None) else float(item["actual_price"]) if item.get("actual_price") not in ("", None) else None,
        execution_status=str(fill_form.get("execution_status", item.get("execution_status", "pending_fill"))).strip() or "pending_fill",
        profile_name=str(context.get("profile_name", item.get("profile_name", ""))).strip(),
        preferred_posture=str(context.get("preferred_posture", item.get("preferred_posture", ""))).strip(),
        setup_type=str(context.get("setup_type", item.get("setup_type", ""))).strip(),
        theme_name=str(context.get("theme_name", item.get("theme_name", ""))).strip(),
        buy_zone=str(suggestion.get("buy_zone", item.get("buy_zone", ""))).strip(),
        sell_scope=str(suggestion.get("sell_scope", item.get("sell_scope", ""))).strip(),
        stop_loss=str(suggestion.get("stop_loss", item.get("stop_loss", ""))).strip(),
        take_profit=str(suggestion.get("take_profit", item.get("take_profit", ""))).strip(),
        suggested_holding_days=int(suggestion["suggested_holding_days"]) if suggestion.get("suggested_holding_days") not in ("", None) else int(item["suggested_holding_days"]) if item.get("suggested_holding_days") not in ("", None) else None,
        reason=str(context.get("reason", item.get("reason", ""))).strip(),
        rationale=str(context.get("rationale", item.get("rationale", ""))).strip(),
        risk_notes=[str(note).strip() for note in list(context.get("risk_notes", item.get("risk_notes", []))) if str(note).strip()],
        source_trade_execution_path=str(context.get("source_trade_execution_path", item.get("source_trade_execution_path", ""))).strip(),
        fill_note=str(fill_form.get("fill_note", item.get("fill_note", ""))).strip(),
    )


def portfolio_workspace_dir() -> Path:
    directory = WORKSPACE_DIR / "portfolio"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def default_trade_log_path() -> Path:
    return portfolio_workspace_dir() / "system_trade_log.json"


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return json.loads(path.read_text(encoding="utf-8-sig"))


def load_system_trade_log(path: Path | None = None) -> list[SystemTradeRecord]:
    log_path = path or default_trade_log_path()
    if not log_path.exists():
        return []
    payload = _read_json(log_path)
    if not isinstance(payload, list):
        return []
    records: list[SystemTradeRecord] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        records.append(_record_from_payload(item))
    return [record for record in records if record.record_id]


def save_system_trade_log(records: list[SystemTradeRecord], path: Path | None = None) -> Path:
    log_path = path or default_trade_log_path()
    log_path.write_text(
        json.dumps([record.to_dict() for record in records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return log_path


def _record_id(trade_date: str, action: str, stock_code: str) -> str:
    return f"{trade_date}:{action}:{stock_code.strip().upper()}"


def _extract_reference_price(text: str) -> float | None:
    numbers = [float(match) for match in re.findall(r"\d+(?:\.\d+)?", str(text or ""))]
    if len(numbers) >= 2:
        return round((numbers[0] + numbers[1]) / 2.0, 4)
    if numbers:
        return round(numbers[0], 4)
    return None


def _buy_record(payload: dict, order: dict, *, source_trade_execution_path: str) -> SystemTradeRecord:
    return SystemTradeRecord(
        record_id=_record_id(str(payload.get("trade_date", "")).strip(), "buy", str(order.get("stock_code", ""))),
        trade_date=str(payload.get("trade_date", "")).strip(),
        market_close_date=str(payload.get("market_close_date", "")).strip(),
        stock_code=str(order.get("stock_code", "")).strip().upper(),
        stock_name=str(order.get("stock_name", "")).strip(),
        order_action="buy",
        suggested_shares=int(order["target_shares"]) if order.get("target_shares") not in ("", None) else None,
        suggested_price_reference=float(order["price_reference"]) if order.get("price_reference") not in ("", None) else _extract_reference_price(order.get("buy_zone", "")),
        execution_status="pending_fill",
        profile_name=str(payload.get("profile_name", "")).strip(),
        preferred_posture=str(payload.get("preferred_posture", "")).strip(),
        setup_type=str(order.get("setup_type", "")).strip(),
        theme_name=str(order.get("theme_name", "")).strip(),
        buy_zone=str(order.get("buy_zone", "")).strip(),
        stop_loss=str(order.get("stop_loss", "")).strip(),
        take_profit=str(order.get("take_profit", "")).strip(),
        suggested_holding_days=int(order["suggested_holding_days"]) if order.get("suggested_holding_days") not in ("", None) else None,
        reason=str(order.get("reason", "")).strip(),
        source_trade_execution_path=source_trade_execution_path,
    )


def _sell_record(payload: dict, order: dict, *, source_trade_execution_path: str) -> SystemTradeRecord:
    return SystemTradeRecord(
        record_id=_record_id(str(payload.get("trade_date", "")).strip(), "sell", str(order.get("stock_code", ""))),
        trade_date=str(payload.get("trade_date", "")).strip(),
        market_close_date=str(payload.get("market_close_date", "")).strip(),
        stock_code=str(order.get("stock_code", "")).strip().upper(),
        stock_name=str(order.get("stock_name", "")).strip(),
        order_action="sell",
        suggested_shares=int(order["target_shares"]) if order.get("target_shares") not in ("", None) else None,
        suggested_price_reference=float(order["price_reference"]) if order.get("price_reference") not in ("", None) else None,
        execution_status="pending_fill",
        profile_name=str(payload.get("profile_name", "")).strip(),
        preferred_posture=str(payload.get("preferred_posture", "")).strip(),
        sell_scope=str(order.get("sell_scope", "")).strip(),
        reason=str(order.get("reason", "")).strip(),
        rationale=str(order.get("rationale", "")).strip(),
        risk_notes=[str(note).strip() for note in list(order.get("risk_notes", [])) if str(note).strip()],
        source_trade_execution_path=source_trade_execution_path,
    )


def _upsert_records(existing: list[SystemTradeRecord], new_records: list[SystemTradeRecord]) -> list[SystemTradeRecord]:
    record_map = {record.record_id: record for record in existing}
    for record in new_records:
        if record.record_id in record_map:
            current = record_map[record.record_id]
            if current.execution_status not in {"cancelled", "skipped", "partial", "filled"}:
                current.suggested_shares = record.suggested_shares
                current.suggested_price_reference = record.suggested_price_reference
                current.profile_name = record.profile_name
                current.preferred_posture = record.preferred_posture
                current.setup_type = record.setup_type
                current.theme_name = record.theme_name
                current.buy_zone = record.buy_zone
                current.sell_scope = record.sell_scope
                current.stop_loss = record.stop_loss
                current.take_profit = record.take_profit
                current.suggested_holding_days = record.suggested_holding_days
                current.reason = record.reason
                current.rationale = record.rationale
                current.risk_notes = list(record.risk_notes or [])
                current.source_trade_execution_path = record.source_trade_execution_path
        else:
            record_map[record.record_id] = record
    records = list(record_map.values())
    status_rank = {
        "pending_fill": 0,
        "partial": 1,
        "filled": 2,
        "cancelled": 3,
        "skipped": 4,
    }
    records.sort(
        key=lambda item: (
            status_rank.get(item.execution_status, 9),
            -int(item.trade_date.replace("-", "") or 0),
            item.order_action,
            item.stock_code,
            item.record_id,
        )
    )
    return records


def _find_position(snapshot: PortfolioSnapshot, stock_code: str) -> HoldingPosition | None:
    normalized = stock_code.strip().upper()
    for position in snapshot.positions:
        if position.stock_code == normalized:
            return position
    return None


def _append_note(existing: str, extra: str) -> str:
    parts = [part.strip() for part in (existing, extra) if str(part or "").strip()]
    return " | ".join(dict.fromkeys(parts))


def _apply_buy_to_snapshot(snapshot: PortfolioSnapshot, record: SystemTradeRecord) -> None:
    if not record.suggested_shares or record.suggested_shares <= 0:
        return
    position = _find_position(snapshot, record.stock_code)
    if position is None:
        snapshot.positions.append(
            HoldingPosition(
                stock_code=record.stock_code,
                stock_name=record.stock_name,
                shares=record.suggested_shares,
                available_shares=record.suggested_shares,
                cost_basis=None,
                execution_status=record.execution_status,
                planned_trade_date=record.trade_date,
                source_record_id=record.record_id,
                notes=f"system_auto_buy:{record.trade_date}",
            )
        )
    else:
        position.shares += record.suggested_shares
        position.available_shares += record.suggested_shares
        position.execution_status = record.execution_status or position.execution_status
        position.planned_trade_date = record.trade_date or position.planned_trade_date
        position.source_record_id = record.record_id or position.source_record_id
        position.notes = _append_note(position.notes, f"system_auto_buy:{record.trade_date}")

    if snapshot.cash_cny is not None and record.suggested_price_reference is not None:
        snapshot.cash_cny = round(float(snapshot.cash_cny) - record.suggested_shares * record.suggested_price_reference, 2)


def _apply_sell_to_snapshot(snapshot: PortfolioSnapshot, record: SystemTradeRecord) -> None:
    if not record.suggested_shares or record.suggested_shares <= 0:
        return
    position = _find_position(snapshot, record.stock_code)
    if position is None:
        return

    remaining_shares = max(0, position.shares - record.suggested_shares)
    remaining_available = max(0, position.available_shares - min(position.available_shares, record.suggested_shares))
    if remaining_shares == 0:
        snapshot.positions = [item for item in snapshot.positions if item.stock_code != position.stock_code]
    else:
        position.shares = remaining_shares
        position.available_shares = min(remaining_available, remaining_shares)
        position.execution_status = record.execution_status or position.execution_status
        position.planned_trade_date = record.trade_date or position.planned_trade_date
        position.source_record_id = record.record_id or position.source_record_id
        position.notes = _append_note(position.notes, f"system_auto_sell:{record.trade_date}")

    if snapshot.cash_cny is not None and record.suggested_price_reference is not None:
        snapshot.cash_cny = round(float(snapshot.cash_cny) + record.suggested_shares * record.suggested_price_reference, 2)


def save_portfolio_snapshot(snapshot: PortfolioSnapshot, path: Path | None = None) -> Path:
    output_path = path or default_holdings_path()
    output_path.write_text(json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def sync_trade_execution_payload_to_live_state(
    payload: dict,
    *,
    holdings_path: Path | None = None,
    trade_log_path: Path | None = None,
    source_trade_execution_path: str = "",
) -> tuple[Path, Path]:
    snapshot = load_portfolio_snapshot(holdings_path or default_holdings_path())
    existing_records = load_system_trade_log(trade_log_path)
    applied_ids = set(snapshot.applied_system_record_ids)

    buy_records = [_buy_record(payload, order, source_trade_execution_path=source_trade_execution_path) for order in list(payload.get("buy_orders", []))]
    sell_records = [_sell_record(payload, order, source_trade_execution_path=source_trade_execution_path) for order in list(payload.get("sell_orders", []))]
    merged_records = _upsert_records(existing_records, buy_records + sell_records)

    for record in buy_records:
        if record.record_id in applied_ids:
            continue
        _apply_buy_to_snapshot(snapshot, record)
        applied_ids.add(record.record_id)

    for record in sell_records:
        if record.record_id in applied_ids:
            continue
        _apply_sell_to_snapshot(snapshot, record)
        applied_ids.add(record.record_id)

    snapshot.as_of = str(payload.get("trade_date", "")).strip() or snapshot.as_of
    snapshot.applied_system_record_ids = sorted(applied_ids)
    snapshot.notes = _append_note(snapshot.notes, f"system_auto_sync:{payload.get('trade_date', '')}")
    snapshot.positions.sort(key=lambda item: (item.stock_code, item.planned_trade_date, item.stock_name))

    holdings_output = save_portfolio_snapshot(snapshot, holdings_path or default_holdings_path())
    trade_log_output = save_system_trade_log(merged_records, trade_log_path)
    return holdings_output, trade_log_output


def sync_trade_execution_file_to_live_state(
    trade_date: str,
    *,
    trade_execution_path: Path,
    holdings_path: Path | None = None,
    trade_log_path: Path | None = None,
) -> tuple[Path, Path]:
    payload = dict(_read_json(trade_execution_path))
    return sync_trade_execution_payload_to_live_state(
        payload,
        holdings_path=holdings_path,
        trade_log_path=trade_log_path,
        source_trade_execution_path=str(trade_execution_path),
    )
