from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pandas as pd


ROOT = Path(r"D:\TradingMain")
ENV_PATHS = [Path(r"D:\Trading\.env"), ROOT / ".env"]
OUT_DIR = ROOT / "research" / "reference" / "tushare" / "trade_event"


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
    if "trade_date" in out.columns:
        out["trade_date"] = pd.to_datetime(out["trade_date"], format="%Y%m%d", errors="coerce")
    if "float_date" in out.columns:
        out["float_date"] = pd.to_datetime(out["float_date"], format="%Y%m%d", errors="coerce")
    return out


def _is_retryable_error(message: str) -> bool:
    lowered = message.lower()
    checks = ["rate", "connection aborted", "connectionreseterror", "httpconnectionpool", "远程主机", "频率"]
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


def _load_trade_dates(pro, start_date: str, end_date: str) -> list[str]:
    cal = pro.trade_cal(exchange="SSE", start_date=start_date, end_date=end_date)
    if cal is None or cal.empty:
        raise RuntimeError("trade_cal returned empty result set")
    cal["cal_date"] = cal["cal_date"].astype(str)
    cal["is_open"] = pd.to_numeric(cal["is_open"], errors="coerce").fillna(0).astype(int)
    return sorted(cal.loc[cal["is_open"] == 1, "cal_date"].tolist())


def _fetch_by_trade_date(pro, api_name: str, trade_dates: list[str], extra_kwargs: dict | None = None) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    extra_kwargs = extra_kwargs or {}
    for idx, trade_date in enumerate(trade_dates, start=1):
        for attempt in range(1, 6):
            try:
                df = getattr(pro, api_name)(trade_date=trade_date, **extra_kwargs)
                if df is not None and not df.empty:
                    frames.append(df.copy())
                break
            except Exception as exc:
                if _is_retryable_error(str(exc)) and attempt < 5:
                    time.sleep(65)
                    continue
                raise
        if idx % 100 == 0 or idx == len(trade_dates):
            print(f"[{api_name}] fetched {idx}/{len(trade_dates)} trade dates")
        time.sleep(0.25)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def fetch_trade_event_data(start_date: str = "20200101", end_date: str | None = None) -> dict:
    from ._fetch_incremental_utils import latest_date_in_parquet, merge_save_parquet

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    end_date = end_date or pd.Timestamp.today().strftime("%Y%m%d")
    pro = load_pro()

    toplist_path = OUT_DIR / "toplist_daily_2020plus.parquet"
    block_trade_path = OUT_DIR / "block_trade_daily_2020plus.parquet"
    share_float_path = OUT_DIR / "share_float_daily_2020plus.parquet"
    report: dict[str, object] = {"start_date": start_date, "end_date": end_date, "endpoints": {}}

    # toplist 增量更新（按 trade_date）
    if toplist_path.exists():
        existing = pd.read_parquet(toplist_path)
        latest = latest_date_in_parquet(toplist_path, "trade_date")
        if latest is not None:
            inc_start = (latest - pd.Timedelta(days=3)).strftime("%Y%m%d")
            if inc_start < end_date:
                trade_dates = _load_trade_dates(pro, inc_start, end_date)
                existing_dates = set(pd.to_datetime(existing["trade_date"], errors="coerce").dt.strftime("%Y%m%d").dropna())
                new_dates = [d for d in trade_dates if d not in existing_dates]
                if new_dates:
                    new_df = _fetch_by_trade_date(pro, "top_list", new_dates)
                    new_df = _normalize(new_df)
                    toplist = merge_save_parquet(existing, new_df, toplist_path)
                else:
                    toplist = existing
            else:
                toplist = existing
        else:
            toplist = existing
    else:
        toplist = _fetch_by_trade_date(pro, "top_list", _load_trade_dates(pro, start_date, end_date))
        toplist = _normalize(toplist).drop_duplicates().reset_index(drop=True)
        toplist.to_parquet(toplist_path, index=False)
    report["endpoints"]["top_list"] = {
        "rows": int(len(toplist)),
        "path": str(toplist_path),
        "columns": list(toplist.columns),
    }

    # block_trade 增量更新
    if block_trade_path.exists():
        existing = pd.read_parquet(block_trade_path)
        latest = latest_date_in_parquet(block_trade_path, "trade_date")
        if latest is not None:
            inc_start = (latest - pd.Timedelta(days=3)).strftime("%Y%m%d")
            if inc_start < end_date:
                new_df = _fetch_range_chunks(pro, "block_trade", _chunk_dates(inc_start, end_date, 45))
                new_df = _normalize(new_df)
                block_trade = merge_save_parquet(existing, new_df, block_trade_path)
            else:
                block_trade = existing
        else:
            block_trade = existing
    else:
        block_trade = _fetch_range_chunks(pro, "block_trade", _chunk_dates(start_date, end_date, 45))
        block_trade = _normalize(block_trade).drop_duplicates().reset_index(drop=True)
        block_trade.to_parquet(block_trade_path, index=False)
    report["endpoints"]["block_trade"] = {
        "rows": int(len(block_trade)),
        "path": str(block_trade_path),
        "columns": list(block_trade.columns),
    }

    # share_float 增量更新
    if share_float_path.exists():
        existing = pd.read_parquet(share_float_path)
        latest = latest_date_in_parquet(share_float_path, "float_date")
        if latest is None:
            latest = latest_date_in_parquet(share_float_path, "ann_date")
        if latest is not None:
            inc_start = (latest - pd.Timedelta(days=3)).strftime("%Y%m%d")
            if inc_start < end_date:
                new_df = _fetch_range_chunks(pro, "share_float", _chunk_dates(inc_start, end_date, 45))
                new_df = _normalize(new_df)
                share_float = merge_save_parquet(existing, new_df, share_float_path)
            else:
                share_float = existing
        else:
            share_float = existing
    else:
        share_float = _fetch_range_chunks(pro, "share_float", _chunk_dates(start_date, end_date, 45))
        share_float = _normalize(share_float).drop_duplicates().reset_index(drop=True)
        share_float.to_parquet(share_float_path, index=False)
    report["endpoints"]["share_float"] = {
        "rows": int(len(share_float)),
        "path": str(share_float_path),
        "columns": list(share_float.columns),
    }

    (OUT_DIR / "fetch_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    result = fetch_trade_event_data()
    print(json.dumps(result, ensure_ascii=False, indent=2))
