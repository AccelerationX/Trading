from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import pandas as pd


ROOT = Path(r"D:\TradingMain")
ENV_PATHS = [Path(r"D:\Trading\.env"), ROOT / ".env"]
OUT_DIR = ROOT / "research" / "reference" / "tushare" / "event"


def load_token() -> str:
    for env_path in ENV_PATHS:
        if not env_path.exists():
            continue
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "TUSHARE_TOKEN":
                token = value.strip().strip("'\"")
                if token:
                    return token
    token = os.getenv("TUSHARE_TOKEN", "").strip()
    if token:
        return token
    raise RuntimeError("TUSHARE_TOKEN not found")


def load_pro():
    import tushare as ts

    return ts.pro_api(load_token())


def _chunk_dates(start_date: str, end_date: str, step_days: int) -> list[tuple[str, str]]:
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    chunks: list[tuple[str, str]] = []
    current = start
    while current <= end:
        chunk_end = min(current + pd.Timedelta(days=step_days - 1), end)
        chunks.append((current.strftime("%Y%m%d"), chunk_end.strftime("%Y%m%d")))
        current = chunk_end + pd.Timedelta(days=1)
    return chunks


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "ts_code" in out.columns:
        out["stock_code"] = out["ts_code"].astype(str).str.upper()
    for col in ["ann_date", "end_date", "begin_date", "close_date", "exp_date"]:
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], format="%Y%m%d", errors="coerce")
    return out


def _is_retryable_error(message: str) -> bool:
    lowered = message.lower()
    checks = ["频率", "rate", "connection aborted", "connectionreseterror", "httpconnectionpool", "远程主机强迫关闭"]
    return any(token in lowered for token in checks) or ("频率" in message)


def _fetch_range_chunks(pro, api_name: str, chunks: list[tuple[str, str]], extra_kwargs: dict | None = None) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    extra_kwargs = extra_kwargs or {}
    for idx, (start_date, end_date) in enumerate(chunks, start=1):
        for attempt in range(1, 6):
            try:
                df = getattr(pro, api_name)(start_date=start_date, end_date=end_date, **extra_kwargs)
                if df is not None and not df.empty:
                    frames.append(df.copy())
                break
            except Exception as exc:
                if _is_retryable_error(str(exc)) and attempt < 5:
                    time.sleep(65)
                    continue
                raise
        print(f"[{api_name}] fetched {idx}/{len(chunks)} chunks")
        time.sleep(0.35)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def fetch_event_data(start_date: str = "20200101", end_date: str | None = None) -> dict:
    from ._fetch_incremental_utils import latest_date_in_parquet, merge_save_parquet

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    end_date = end_date or pd.Timestamp.today().strftime("%Y%m%d")
    pro = load_pro()

    repurchase_path = OUT_DIR / "repurchase_daily_2020plus.parquet"
    holdertrade_path = OUT_DIR / "holdertrade_daily_2020plus.parquet"
    report: dict[str, object] = {"start_date": start_date, "end_date": end_date, "endpoints": {}}

    # repurchase 增量更新
    if repurchase_path.exists():
        existing = pd.read_parquet(repurchase_path)
        latest = latest_date_in_parquet(repurchase_path, "ann_date")
        if latest is not None:
            inc_start = (latest - pd.Timedelta(days=3)).strftime("%Y%m%d")
            if inc_start < end_date:
                new_df = _fetch_range_chunks(pro, "repurchase", _chunk_dates(inc_start, end_date, 180))
                new_df = _normalize(new_df)
                repurchase = merge_save_parquet(existing, new_df, repurchase_path)
            else:
                repurchase = existing
        else:
            repurchase = existing
    else:
        repurchase = _fetch_range_chunks(pro, "repurchase", _chunk_dates(start_date, end_date, 180))
        repurchase = _normalize(repurchase).drop_duplicates().reset_index(drop=True)
        repurchase.to_parquet(repurchase_path, index=False)
    report["endpoints"]["repurchase"] = {
        "rows": int(len(repurchase)),
        "path": str(repurchase_path),
        "columns": list(repurchase.columns),
    }

    # holdertrade 增量更新
    if holdertrade_path.exists():
        existing = pd.read_parquet(holdertrade_path)
        latest = latest_date_in_parquet(holdertrade_path, "ann_date")
        if latest is not None:
            inc_start = (latest - pd.Timedelta(days=3)).strftime("%Y%m%d")
            if inc_start < end_date:
                frames: list[pd.DataFrame] = []
                holder_chunks = _chunk_dates(inc_start, end_date, 45)
                for trade_type in ["IN", "DE"]:
                    df = _fetch_range_chunks(pro, "stk_holdertrade", holder_chunks, extra_kwargs={"trade_type": trade_type})
                    if df is not None and not df.empty:
                        frames.append(df.copy())
                new_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
                new_df = _normalize(new_df)
                holdertrade = merge_save_parquet(existing, new_df, holdertrade_path)
            else:
                holdertrade = existing
        else:
            holdertrade = existing
    else:
        frames: list[pd.DataFrame] = []
        holder_chunks = _chunk_dates(start_date, end_date, 45)
        for trade_type in ["IN", "DE"]:
            df = _fetch_range_chunks(pro, "stk_holdertrade", holder_chunks, extra_kwargs={"trade_type": trade_type})
            if df is not None and not df.empty:
                frames.append(df.copy())
        holdertrade = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        holdertrade = _normalize(holdertrade).drop_duplicates().reset_index(drop=True)
        holdertrade.to_parquet(holdertrade_path, index=False)
    report["endpoints"]["holdertrade"] = {
        "rows": int(len(holdertrade)),
        "path": str(holdertrade_path),
        "columns": list(holdertrade.columns),
    }

    (OUT_DIR / "fetch_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    result = fetch_event_data()
    print(json.dumps(result, ensure_ascii=False, indent=2))
