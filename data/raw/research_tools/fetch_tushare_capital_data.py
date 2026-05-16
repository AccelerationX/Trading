from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pandas as pd
import polars as pl


ROOT = Path(r"D:\TradingMain")
ENV_PATHS = [Path(r"D:\Trading\.env"), ROOT / ".env"]
OUT_DIR = ROOT / "research" / "reference" / "tushare"
NORTH_DIR = OUT_DIR / "northbound"
MARGIN_DIR = OUT_DIR / "margin"
NORTH_MARKET_DIR = OUT_DIR / "northbound_market"
DATA_DIR = ROOT / "StockHistory"


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


def load_trade_dates(start_date: str = "20200101", end_date: str | None = None) -> list[str]:
    end_date = end_date or pd.Timestamp.today().strftime("%Y%m%d")
    pattern = str(DATA_DIR / "*.csv")
    dates = (
        pl.scan_csv(
            pattern,
            glob=True,
            infer_schema_length=50,
            null_values=["", "None"],
            with_column_names=lambda names: [name.lstrip("\ufeff") for name in names],
        )
        .select(pl.col("交易日").cast(pl.Utf8))
        .rename({"交易日": "trade_date"})
        .unique()
        .collect()
        .to_pandas()["trade_date"]
        .dropna()
        .astype(str)
        .sort_values()
        .tolist()
    )
    return [d for d in dates if start_date <= d <= end_date]


def _normalize_stock_code(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    code_col = None
    for candidate in ["ts_code", "stock_code", "con_code", "code"]:
        if candidate in out.columns:
            code_col = candidate
            break
    if code_col is not None:
        out["stock_code"] = out[code_col].astype(str).str.upper()
        if "exchange" in out.columns:
            missing_suffix = ~out["stock_code"].str.contains(".", regex=False)
            out.loc[missing_suffix, "stock_code"] = out.loc[missing_suffix, "stock_code"] + "." + out.loc[
                missing_suffix, "exchange"
            ].astype(str).str.upper()
    return out


def _fetch_by_trade_dates(
    pro,
    api_name: str,
    trade_dates: list[str],
    flush_every: int = 20,
    sleep_sec: float = 0.35,
    retry_wait_sec: int = 65,
    max_retries: int = 5,
    range_chunk_size: int = 60,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for chunk_start in range(0, len(trade_dates), range_chunk_size):
        chunk = trade_dates[chunk_start : chunk_start + range_chunk_size]
        chunk_label = f"{chunk[0]}->{chunk[-1]}"
        used_range_fetch = False
        for attempt in range(1, max_retries + 1):
            try:
                df = getattr(pro, api_name)(start_date=chunk[0], end_date=chunk[-1])
                if df is not None and not df.empty:
                    frames.append(df.copy())
                used_range_fetch = True
                break
            except Exception as exc:
                msg = str(exc)
                if "频率超限" in msg and attempt < max_retries:
                    print(f"[{api_name}] rate-limited on range {chunk_label}, sleeping {retry_wait_sec}s before retry {attempt + 1}/{max_retries}")
                    time.sleep(retry_wait_sec)
                    continue
                break
        if not used_range_fetch:
            for idx, trade_date in enumerate(chunk, start=1):
                for attempt in range(1, max_retries + 1):
                    try:
                        df = getattr(pro, api_name)(trade_date=trade_date)
                        if df is not None and not df.empty:
                            frames.append(df.copy())
                        break
                    except Exception as exc:
                        msg = str(exc)
                        if "频率超限" in msg and attempt < max_retries:
                            print(f"[{api_name}] rate-limited on {trade_date}, sleeping {retry_wait_sec}s before retry {attempt + 1}/{max_retries}")
                            time.sleep(retry_wait_sec)
                            continue
                        raise
                if idx % flush_every == 0 or idx == len(chunk):
                    print(f"[{api_name}] fallback-fetched {chunk_start + idx}/{len(trade_dates)} trade dates")
                time.sleep(sleep_sec)
        else:
            print(f"[{api_name}] range-fetched {min(chunk_start + len(chunk), len(trade_dates))}/{len(trade_dates)} trade dates")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def fetch_northbound(
    pro,
    trade_dates: list[str],
    out_path: Path | None = None,
) -> dict:
    out_path = out_path or NORTH_DIR / "hk_hold_daily_2020plus.parquet"
    NORTH_DIR.mkdir(parents=True, exist_ok=True)
    df = _fetch_by_trade_dates(pro, "hk_hold", trade_dates, range_chunk_size=4)
    if df.empty:
        raise RuntimeError("hk_hold returned empty result set")
    df = _normalize_stock_code(df)
    if "trade_date" in df.columns:
        df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d", errors="coerce")
    df.to_parquet(out_path, index=False)
    report = {
        "rows": int(len(df)),
        "trade_dates": int(pd.Series(df["trade_date"]).nunique()) if "trade_date" in df.columns else 0,
        "columns": list(df.columns),
        "path": str(out_path),
    }
    (NORTH_DIR / "fetch_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def fetch_margin(
    pro,
    trade_dates: list[str],
    out_path: Path | None = None,
) -> dict:
    out_path = out_path or MARGIN_DIR / "margin_detail_daily_2020plus.parquet"
    MARGIN_DIR.mkdir(parents=True, exist_ok=True)
    df = _fetch_by_trade_dates(pro, "margin_detail", trade_dates, range_chunk_size=2)
    if df.empty:
        raise RuntimeError("margin_detail returned empty result set")
    df = _normalize_stock_code(df)
    if "trade_date" in df.columns:
        df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d", errors="coerce")
    df.to_parquet(out_path, index=False)
    report = {
        "rows": int(len(df)),
        "trade_dates": int(pd.Series(df["trade_date"]).nunique()) if "trade_date" in df.columns else 0,
        "columns": list(df.columns),
        "path": str(out_path),
    }
    (MARGIN_DIR / "fetch_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def fetch_northbound_market(
    pro,
    trade_dates: list[str],
    out_path: Path | None = None,
) -> dict:
    out_path = out_path or NORTH_MARKET_DIR / "moneyflow_hsgt_daily_2020plus.parquet"
    NORTH_MARKET_DIR.mkdir(parents=True, exist_ok=True)
    frames: list[pd.DataFrame] = []
    chunk_size = 250
    for idx in range(0, len(trade_dates), chunk_size):
        chunk = trade_dates[idx : idx + chunk_size]
        df = pro.moneyflow_hsgt(start_date=chunk[0], end_date=chunk[-1])
        if df is not None and not df.empty:
            frames.append(df.copy())
        print(f"[moneyflow_hsgt] range-fetched {min(idx + len(chunk), len(trade_dates))}/{len(trade_dates)} trade dates")
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if df.empty:
        raise RuntimeError("moneyflow_hsgt returned empty result set")
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d", errors="coerce")
    df = df.sort_values("trade_date").drop_duplicates(subset=["trade_date"]).reset_index(drop=True)
    df.to_parquet(out_path, index=False)
    report = {
        "rows": int(len(df)),
        "trade_dates": int(df["trade_date"].nunique()),
        "columns": list(df.columns),
        "path": str(out_path),
    }
    (NORTH_MARKET_DIR / "fetch_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def fetch_all_capital_data(
    start_date: str = "20200101",
    end_date: str | None = None,
) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    trade_dates = load_trade_dates(start_date=start_date, end_date=end_date)
    if not trade_dates:
        raise RuntimeError("No local trade dates found")
    pro = load_pro()
    north = fetch_northbound(pro, trade_dates)
    margin = fetch_margin(pro, trade_dates)
    north_market = fetch_northbound_market(pro, trade_dates)
    report = {
        "start_date": start_date,
        "end_date": end_date or pd.Timestamp.today().strftime("%Y%m%d"),
        "trade_dates": len(trade_dates),
        "northbound": north,
        "margin": margin,
        "northbound_market": north_market,
    }
    (OUT_DIR / "capital_fetch_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    report = fetch_all_capital_data()
    print(json.dumps(report, ensure_ascii=False, indent=2))
