from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from trading_system.config.paths import PROCESSED_DATA_DIR, WORKSPACE_DIR
from trading_system.context.cards import CandidateCard, TradePlanCard
from trading_system.decision.account import AccountConstraints
from trading_system.ingest.simple_tabular import read_records
from trading_system.config.paths import INBOX_DIR


@dataclass(slots=True)
class HoldingPosition:
    stock_code: str
    stock_name: str = ""
    shares: int = 0
    available_shares: int = 0
    cost_basis: float | None = None
    execution_status: str = ""
    planned_trade_date: str = ""
    source_record_id: str = ""
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class PortfolioSnapshot:
    as_of: str = ""
    broker: str = ""
    cash_cny: float | None = None
    positions: list[HoldingPosition] = field(default_factory=list)
    applied_system_record_ids: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "as_of": self.as_of,
            "broker": self.broker,
            "cash_cny": self.cash_cny,
            "positions": [position.to_dict() for position in self.positions],
            "applied_system_record_ids": list(self.applied_system_record_ids),
            "notes": self.notes,
        }


@dataclass(slots=True)
class HoldingAssessment:
    stock_code: str
    stock_name: str = ""
    shares: int = 0
    available_shares: int = 0
    cost_basis: float | None = None
    last_close_price: float | None = None
    market_value: float | None = None
    unrealized_return_pct: float | None = None
    portfolio_weight_pct: float | None = None
    plan_action: str = "none"
    summary_action: str = "hold_review"
    recommendation: str = ""
    rationale: str = ""
    risk_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def portfolio_workspace_dir() -> Path:
    directory = WORKSPACE_DIR / "portfolio"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def default_holdings_path() -> Path:
    return portfolio_workspace_dir() / "current_holdings.json"


def holdings_processed_dir() -> Path:
    directory = PROCESSED_DATA_DIR / "holdings"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _default_payload() -> dict:
    return {
        "as_of": "",
        "broker": "",
        "cash_cny": None,
        "positions": [],
        "applied_system_record_ids": [],
        "notes": "",
    }


def _read_json_payload(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return json.loads(path.read_text(encoding="utf-8-sig"))


def _normalize_stock_code(value: object) -> str:
    return str(value or "").strip().upper()


def load_portfolio_snapshot(path: Path | None = None) -> PortfolioSnapshot:
    snapshot_path = path or default_holdings_path()
    if not snapshot_path.exists():
        payload = _default_payload()
    else:
        payload = _read_json_payload(snapshot_path)

    raw_positions = payload.get("positions") if isinstance(payload, dict) else []
    positions: list[HoldingPosition] = []
    if isinstance(raw_positions, list):
        for item in raw_positions:
            if not isinstance(item, dict):
                continue
            shares = int(item.get("shares", 0) or 0)
            available_shares = int(item.get("available_shares", shares) or shares)
            positions.append(
                HoldingPosition(
                    stock_code=_normalize_stock_code(item.get("stock_code")),
                    stock_name=str(item.get("stock_name", "")).strip(),
                    shares=shares,
                    available_shares=max(0, available_shares),
                    cost_basis=float(item["cost_basis"]) if item.get("cost_basis") not in ("", None) else None,
                    execution_status=str(item.get("execution_status", "")).strip(),
                    planned_trade_date=str(item.get("planned_trade_date", "")).strip(),
                    source_record_id=str(item.get("source_record_id", "")).strip(),
                    notes=str(item.get("notes", "")).strip(),
                )
            )

    return PortfolioSnapshot(
        as_of=str(payload.get("as_of", "")).strip() if isinstance(payload, dict) else "",
        broker=str(payload.get("broker", "")).strip() if isinstance(payload, dict) else "",
        cash_cny=float(payload["cash_cny"]) if isinstance(payload, dict) and payload.get("cash_cny") not in ("", None) else None,
        positions=[position for position in positions if position.stock_code and position.shares > 0],
        applied_system_record_ids=[
            str(item).strip()
            for item in (payload.get("applied_system_record_ids", []) if isinstance(payload, dict) else [])
            if str(item).strip()
        ],
        notes=str(payload.get("notes", "")).strip() if isinstance(payload, dict) else "",
    )


def save_normalized_portfolio_snapshot(snapshot: PortfolioSnapshot, path: Path | None = None) -> Path:
    output_path = path or (holdings_processed_dir() / "current_holdings_snapshot.json")
    output_path.write_text(json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def _load_market_quote_map(trade_date: str) -> dict[str, dict]:
    trade_date_compact = trade_date.replace("-", "")
    path = INBOX_DIR / "market_equity_daily" / f"market_equity_daily_{trade_date_compact}.csv"
    if not path.exists():
        return {}
    quote_map: dict[str, dict] = {}
    for record in read_records(path):
        stock_code = _normalize_stock_code(record.get("stock_code"))
        if stock_code:
            quote_map[stock_code] = record
    return quote_map


def assess_portfolio_positions(
    snapshot: PortfolioSnapshot,
    account: AccountConstraints,
    trade_date: str,
    candidate_cards: list[CandidateCard],
    trade_plans: list[TradePlanCard],
) -> list[HoldingAssessment]:
    candidate_map = {card.stock_code: card for card in candidate_cards}
    plan_map = {plan.stock_code: plan for plan in trade_plans}
    quote_map = _load_market_quote_map(trade_date)
    total_capital = max(1.0, float(account.capital_total or 0.0))
    assessments: list[HoldingAssessment] = []

    for position in snapshot.positions:
        quote = quote_map.get(position.stock_code, {})
        stock_name = position.stock_name or str(quote.get("stock_name", "")).strip()
        last_close = float(quote["close"]) if quote.get("close") not in ("", None) else None
        market_value = round(last_close * position.shares, 2) if last_close is not None else None
        unrealized_return_pct = None
        if last_close is not None and position.cost_basis not in (None, 0):
            unrealized_return_pct = round(last_close / float(position.cost_basis) - 1.0, 4)
        portfolio_weight_pct = round((market_value / total_capital), 4) if market_value is not None else None

        plan = plan_map.get(position.stock_code)
        candidate = candidate_map.get(position.stock_code)
        if plan is None:
            summary_action = "hold_review"
            recommendation = "No fresh plan entry today. Hold only if relative strength remains intact and your original thesis still stands."
            rationale = candidate.llm_diagnostic_summary if candidate and candidate.llm_diagnostic_summary else (candidate.diagnostic_summary if candidate else "No new system-confirmed setup.")
            risk_notes = ["no_fresh_trade_plan"]
        elif plan.action == "buy_pilot":
            summary_action = "hold_or_add"
            recommendation = "Already held. Only consider adding after opening confirmation, not as an immediate blind add."
            rationale = plan.llm_refined_plan or plan.rationale
            risk_notes = list(plan.risk_notes)
        elif plan.action == "watch_only":
            summary_action = "hold_and_observe"
            recommendation = "Existing position can be monitored, but do not add unless strength and breadth confirm again."
            rationale = plan.llm_refined_plan or plan.rationale
            risk_notes = list(plan.risk_notes)
        else:
            summary_action = "reduce_or_exit_review"
            recommendation = "System does not support aggressive holding here. Review whether to reduce or exit on weakness."
            rationale = plan.llm_refined_plan or plan.rationale
            risk_notes = list(plan.risk_notes)

        if portfolio_weight_pct is not None and portfolio_weight_pct >= account.single_position_max_pct:
            risk_notes.append("existing_position_at_or_above_single_position_limit")
        if unrealized_return_pct is not None and unrealized_return_pct <= -0.05:
            risk_notes.append("unrealized_drawdown_alert")
        if candidate and candidate.tradeability_verdict in {"too_concentrated", "blocked_by_budget"}:
            risk_notes.append(f"account_fit_warning:{candidate.tradeability_verdict}")

        assessments.append(
            HoldingAssessment(
                stock_code=position.stock_code,
                stock_name=stock_name,
                shares=position.shares,
                available_shares=position.available_shares,
                cost_basis=position.cost_basis,
                last_close_price=last_close,
                market_value=market_value,
                unrealized_return_pct=unrealized_return_pct,
                portfolio_weight_pct=portfolio_weight_pct,
                plan_action=plan.action if plan else "none",
                summary_action=summary_action,
                recommendation=recommendation,
                rationale=rationale,
                risk_notes=list(dict.fromkeys(note for note in risk_notes if note)),
            )
        )

    assessments.sort(
        key=lambda item: (
            -(item.market_value if item.market_value is not None else 0.0),
            item.stock_code,
        )
    )
    return assessments
