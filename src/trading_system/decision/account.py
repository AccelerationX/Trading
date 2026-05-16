from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from trading_system.config.paths import CONFIGS_DIR, INBOX_DIR, PROCESSED_DATA_DIR


@dataclass(slots=True)
class AccountConstraints:
    profile_name: str
    capital_total: float
    capital_liquid_ratio_min: float
    single_position_max_pct: float
    single_trade_capital_max: float
    max_holdings: int
    max_new_positions_per_day: int
    max_portfolio_turnover_per_day: float
    daily_drawdown_alert_pct: float
    portfolio_drawdown_alert_pct: float
    preferred_holding_horizon_days: int
    execution_mode: str
    can_watch_intraday: bool
    preopen_available: bool
    midday_available: bool
    close_available: bool
    avoid_chasing_limit_up: bool
    avoid_low_liquidity: bool
    main_board_only: bool = True
    board_lot_size: int = 100
    single_lot_alert_capital_pct: float = 0.35
    single_lot_block_capital_pct: float = 0.5
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def account_inbox_dir() -> Path:
    return INBOX_DIR / "account_constraints"


def account_processed_dir() -> Path:
    directory = PROCESSED_DATA_DIR / "account"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _candidate_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(
        [path for path in directory.glob("*.json") if path.is_file()],
        key=lambda path: (path.stat().st_mtime, path.name),
        reverse=True,
    )


def _default_runtime_account_payload() -> dict:
    template_path = CONFIGS_DIR / "account_profile.template.json"
    try:
        payload = json.loads(template_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = json.loads(template_path.read_text(encoding="utf-8-sig"))

    capital_total = float(payload.get("capital_total", 0.0) or 0.0)
    if capital_total <= 0:
        capital_total = 43000.0
    single_position_max_pct = float(payload.get("single_position_max_pct", 1.0) or 1.0)
    single_trade_capital_max = float(payload.get("single_trade_capital_max", 0.0) or 0.0)
    if single_trade_capital_max <= 0:
        single_trade_capital_max = round(capital_total * single_position_max_pct, 2)

    payload["profile_name"] = "default_runtime_demo"
    payload["capital_total"] = capital_total
    payload["single_trade_capital_max"] = single_trade_capital_max
    payload["main_board_only"] = bool(payload.get("main_board_only", True))
    payload["board_lot_size"] = int(payload.get("board_lot_size", 100) or 100)
    payload["single_lot_alert_capital_pct"] = float(payload.get("single_lot_alert_capital_pct", 0.35) or 0.35)
    payload["single_lot_block_capital_pct"] = float(payload.get("single_lot_block_capital_pct", 0.5) or 0.5)
    payload["notes"] = (
        str(payload.get("notes", "")).strip()
        + " Runtime fallback profile loaded because no account constraint JSON was found in data/inbox/account_constraints."
    ).strip()
    return payload


def load_active_account_constraints(path: Path | None = None) -> AccountConstraints:
    candidate_path = path
    if candidate_path is None:
        files = _candidate_files(account_inbox_dir())
        if not files:
            payload = _default_runtime_account_payload()
        else:
            candidate_path = files[0]

    if candidate_path is not None:
        try:
            raw_text = candidate_path.read_text(encoding="utf-8")
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            raw_text = candidate_path.read_text(encoding="utf-8-sig")
            payload = json.loads(raw_text)
    return AccountConstraints(
        profile_name=str(payload.get("profile_name", "default")),
        capital_total=float(payload.get("capital_total", 0.0)),
        capital_liquid_ratio_min=float(payload.get("capital_liquid_ratio_min", 0.0)),
        single_position_max_pct=float(payload.get("single_position_max_pct", 0.0)),
        single_trade_capital_max=float(payload.get("single_trade_capital_max", 0.0)),
        max_holdings=int(payload.get("max_holdings", 0)),
        max_new_positions_per_day=int(payload.get("max_new_positions_per_day", 0)),
        max_portfolio_turnover_per_day=float(payload.get("max_portfolio_turnover_per_day", 0.0)),
        daily_drawdown_alert_pct=float(payload.get("daily_drawdown_alert_pct", 0.0)),
        portfolio_drawdown_alert_pct=float(payload.get("portfolio_drawdown_alert_pct", 0.0)),
        preferred_holding_horizon_days=int(payload.get("preferred_holding_horizon_days", 0)),
        execution_mode=str(payload.get("execution_mode", "manual")),
        can_watch_intraday=bool(payload.get("can_watch_intraday", False)),
        preopen_available=bool(payload.get("preopen_available", False)),
        midday_available=bool(payload.get("midday_available", False)),
        close_available=bool(payload.get("close_available", False)),
        avoid_chasing_limit_up=bool(payload.get("avoid_chasing_limit_up", True)),
        avoid_low_liquidity=bool(payload.get("avoid_low_liquidity", True)),
        main_board_only=bool(payload.get("main_board_only", True)),
        board_lot_size=int(payload.get("board_lot_size", 100) or 100),
        single_lot_alert_capital_pct=float(payload.get("single_lot_alert_capital_pct", 0.35) or 0.35),
        single_lot_block_capital_pct=float(payload.get("single_lot_block_capital_pct", 0.5) or 0.5),
        notes=str(payload.get("notes", "")),
    )


def save_normalized_account_constraints(account: AccountConstraints, path: Path | None = None) -> Path:
    output_path = path or (account_processed_dir() / "active_account_constraints.json")
    output_path.write_text(json.dumps(account.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
