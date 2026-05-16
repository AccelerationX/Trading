from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pandas as pd


ROOT = Path(r"D:\TradingMain")
ENV_PATHS = [Path(r"D:\Trading\.env"), ROOT / ".env"]
OUT_DIR = ROOT / "research" / "reference" / "tushare" / "holder_risk"


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


def _date_chunks(start_date: str, end_date: str, step_days: int) -> list[tuple[str, str]]:
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    chunks: list[tuple[str, str]] = []
    current = start
    while current <= end:
        chunk_end = min(current + pd.Timedelta(days=step_days - 1), end)
        chunks.append((current.strftime("%Y%m%d"), chunk_end.strftime("%Y%m%d")))
        current = chunk_end + pd.Timedelta(days=1)
    return chunks


def _is_retryable_error(message: str) -> bool:
    lowered = message.lower()
    checks = ["rate", "connection aborted", "connectionreseterror", "httpconnectionpool", "远程主机", "频率"]
    return any(token in lowered for token in checks) or ("频率" in message)


def _fetch_with_paging(pro, api_name: str, base_kwargs: dict, page_limit: int = 5000) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    offset = 0
    while True:
        for attempt in range(1, 6):
            try:
                df = pro.query(api_name, limit=page_limit, offset=offset, **base_kwargs)
                break
            except Exception as exc:
                if _is_retryable_error(str(exc)) and attempt < 5:
                    time.sleep(65)
                    continue
                raise
        if df is None or df.empty:
            break
        frames.append(df.copy())
        if len(df) < page_limit:
            break
        offset += page_limit
        time.sleep(0.25)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _load_weekly_trade_dates(pro, start_date: str, end_date: str) -> list[str]:
    cal = pro.trade_cal(exchange="SSE", start_date=start_date, end_date=end_date)
    if cal is None or cal.empty:
        raise RuntimeError("trade_cal returned empty result set")
    cal["cal_date"] = pd.to_datetime(cal["cal_date"], format="%Y%m%d", errors="coerce")
    cal["is_open"] = pd.to_numeric(cal["is_open"], errors="coerce").fillna(0).astype(int)
    open_days = cal.loc[cal["is_open"] == 1, "cal_date"].sort_values()
    if open_days.empty:
        return []
    week_end_days = open_days.groupby(open_days.dt.to_period("W-FRI")).max().tolist()
    return [pd.Timestamp(day).strftime("%Y%m%d") for day in week_end_days]


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "ts_code" in out.columns:
        out["stock_code"] = out["ts_code"].astype(str).str.upper()
    for col in ["ann_date", "end_date"]:
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], format="%Y%m%d", errors="coerce")
    return out


def fetch_holder_risk_data(start_date: str = "20200101", end_date: str | None = None) -> dict:
    from ._fetch_incremental_utils import latest_date_in_parquet, merge_save_parquet

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    end_date = end_date or pd.Timestamp.today().strftime("%Y%m%d")
    pro = load_pro()

    holdernumber_path = OUT_DIR / "holdernumber_daily_2020plus.parquet"
    pledge_path = OUT_DIR / "pledge_stat_weekly_2020plus.parquet"
    report: dict[str, object] = {"start_date": start_date, "end_date": end_date, "endpoints": {}}

    # holdernumber 增量更新
    if holdernumber_path.exists():
        existing = pd.read_parquet(holdernumber_path)
        latest = latest_date_in_parquet(holdernumber_path, "ann_date")
        if latest is not None:
            inc_start = (latest - pd.Timedelta(days=3)).strftime("%Y%m%d")
            if inc_start < end_date:
                frames = []
                chunks = _date_chunks(inc_start, end_date, 45)
                for idx, (chunk_start, chunk_end) in enumerate(chunks, start=1):
                    df = _fetch_with_paging(pro, "stk_holdernumber", {"start_date": chunk_start, "end_date": chunk_end})
                    if df is not None and not df.empty:
                        frames.append(df.copy())
                    if idx % 10 == 0 or idx == len(chunks):
                        print(f"[stk_holdernumber] fetched {idx}/{len(chunks)} chunks")
                    time.sleep(0.25)
                new_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
                new_df = _normalize(new_df)
                holdernumber = merge_save_parquet(existing, new_df, holdernumber_path)
            else:
                holdernumber = existing
        else:
            holdernumber = existing
    else:
        frames = []
        chunks = _date_chunks(start_date, end_date, 45)
        for idx, (chunk_start, chunk_end) in enumerate(chunks, start=1):
            df = _fetch_with_paging(pro, "stk_holdernumber", {"start_date": chunk_start, "end_date": chunk_end})
            if df is not None and not df.empty:
                frames.append(df.copy())
            if idx % 10 == 0 or idx == len(chunks):
                print(f"[stk_holdernumber] fetched {idx}/{len(chunks)} chunks")
            time.sleep(0.25)
        holdernumber = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        holdernumber = _normalize(holdernumber).drop_duplicates().reset_index(drop=True)
        holdernumber.to_parquet(holdernumber_path, index=False)
    report["endpoints"]["stk_holdernumber"] = {
        "rows": int(len(holdernumber)),
        "path": str(holdernumber_path),
        "columns": list(holdernumber.columns),
    }

    # pledge_stat 增量更新（周频）
    if pledge_path.exists():
        existing = pd.read_parquet(pledge_path)
        latest = latest_date_in_parquet(pledge_path, "end_date")
        if latest is not None:
            inc_start = (latest - pd.Timedelta(days=7)).strftime("%Y%m%d")
            if inc_start < end_date:
                week_dates = _load_weekly_trade_dates(pro, inc_start, end_date)
                existing_dates = set(pd.to_datetime(existing["end_date"], errors="coerce").dt.strftime("%Y%m%d").dropna())
                new_week_dates = [d for d in week_dates if d not in existing_dates]
                if new_week_dates:
                    frames = []
                    for idx, week_end in enumerate(new_week_dates, start=1):
                        df = _fetch_with_paging(pro, "pledge_stat", {"end_date": week_end})
                        if df is not None and not df.empty:
                            frames.append(df.copy())
                        if idx % 20 == 0 or idx == len(new_week_dates):
                            print(f"[pledge_stat] fetched {idx}/{len(new_week_dates)} weekly snapshots")
                        time.sleep(0.25)
                    new_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
                    new_df = _normalize(new_df)
                    pledge = merge_save_parquet(existing, new_df, pledge_path)
                else:
                    pledge = existing
            else:
                pledge = existing
        else:
            pledge = existing
    else:
        week_dates = _load_weekly_trade_dates(pro, start_date, end_date)
        frames = []
        for idx, week_end in enumerate(week_dates, start=1):
            df = _fetch_with_paging(pro, "pledge_stat", {"end_date": week_end})
            if df is not None and not df.empty:
                frames.append(df.copy())
            if idx % 20 == 0 or idx == len(week_dates):
                print(f"[pledge_stat] fetched {idx}/{len(week_dates)} weekly snapshots")
            time.sleep(0.25)
        pledge = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        pledge = _normalize(pledge).drop_duplicates().reset_index(drop=True)
        pledge.to_parquet(pledge_path, index=False)
    report["endpoints"]["pledge_stat"] = {
        "rows": int(len(pledge)),
        "path": str(pledge_path),
        "columns": list(pledge.columns),
    }

    (OUT_DIR / "fetch_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    result = fetch_holder_risk_data()
    print(json.dumps(result, ensure_ascii=False, indent=2))
