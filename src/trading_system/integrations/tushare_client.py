from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from trading_system.config.paths import PROJECT_ROOT


ENV_PATHS = (
    PROJECT_ROOT / ".env",
    Path(r"D:\Trading\.env"),
    Path(r"D:\TradingMain\.env"),
)


class TushareConfigurationError(RuntimeError):
    """Raised when local Tushare configuration is incomplete."""


@dataclass(frozen=True)
class TushareRuntimeConfig:
    token: str
    timeout: int = 30


def _read_env_value(env_path: Path, key: str) -> str:
    if not env_path.exists():
        return ""
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        current_key, value = line.split("=", 1)
        if current_key.strip() == key:
            return value.strip().strip("'\"")
    return ""


def load_tushare_runtime_config() -> TushareRuntimeConfig:
    token = os.getenv("TUSHARE_TOKEN", "").strip()
    if not token:
        for env_path in ENV_PATHS:
            token = _read_env_value(env_path, "TUSHARE_TOKEN")
            if token:
                break
    if not token:
        raise TushareConfigurationError(
            "TUSHARE_TOKEN not found. Set it in the environment or create a local .env file."
        )
    return TushareRuntimeConfig(token=token)


def load_pro_client(timeout: int = 30):
    import tushare as ts

    config = load_tushare_runtime_config()
    return ts.pro_api(config.token, timeout=timeout)


def is_retryable_tushare_error(message: str) -> bool:
    lowered = message.lower()
    tokens = [
        "rate",
        "connection aborted",
        "connectionreseterror",
        "httpconnectionpool",
        "read timed out",
        "timed out",
        "远程主机",
        "频率",
    ]
    return any(token in lowered for token in tokens) or ("频率" in message)


def call_with_retry(fetcher, *, max_retries: int = 5, sleep_seconds: int = 20):
    for attempt in range(1, max_retries + 1):
        try:
            return fetcher()
        except Exception as exc:
            if not is_retryable_tushare_error(str(exc)) or attempt >= max_retries:
                raise
            time.sleep(sleep_seconds)
    raise RuntimeError("unreachable")


def load_open_trade_dates(pro, start_date: str, end_date: str) -> list[str]:
    cal = call_with_retry(
        lambda: pro.trade_cal(exchange="SSE", start_date=start_date, end_date=end_date),
        sleep_seconds=10,
    )
    if cal is None or cal.empty:
        raise RuntimeError("trade_cal returned empty result set")
    work = cal.copy()
    work["cal_date"] = work["cal_date"].astype(str)
    work["is_open"] = pd.to_numeric(work["is_open"], errors="coerce").fillna(0).astype(int)
    return sorted(work.loc[work["is_open"] == 1, "cal_date"].tolist())


def _daily_has_rows(pro, trade_date: str) -> bool:
    daily = call_with_retry(lambda: pro.daily(trade_date=trade_date), sleep_seconds=8)
    return daily is not None and not daily.empty


def latest_open_trade_date(pro, anchor_date: str) -> str:
    start_date = (pd.Timestamp(anchor_date) - pd.Timedelta(days=20)).strftime("%Y%m%d")
    trade_dates = load_open_trade_dates(pro, start_date=start_date, end_date=anchor_date)
    if not trade_dates:
        raise RuntimeError(f"No open trade dates found before {anchor_date}")
    for current_date in reversed(trade_dates):
        try:
            if _daily_has_rows(pro, current_date):
                return current_date
        except Exception:
            continue
    return trade_dates[-1]
