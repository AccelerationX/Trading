from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import pandas as pd


ROOT = Path(r"D:\TradingMain")
ENV_PATHS = [Path(r"D:\Trading\.env"), ROOT / ".env"]
OUT_DIR = ROOT / "research" / "reference" / "tushare" / "pit_fundamental"
DATA_DIR = ROOT / "StockHistory"
ENDPOINTS = {
    "fina_indicator": {"vip": "fina_indicator_vip", "regular": "fina_indicator"},
    "income": {"vip": "income_vip", "regular": "income"},
    "cashflow": {"vip": "cashflow_vip", "regular": "cashflow"},
    "balancesheet": {"vip": "balancesheet_vip", "regular": "balancesheet"},
}
MAIN_BOARD_PATTERNS = [
    re.compile(r"^(600|601|603|605)\d{3}\.SH$"),
    re.compile(r"^(000|001|002|003)\d{3}\.SZ$"),
]


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


def load_stock_codes() -> list[str]:
    codes = sorted(path.stem.upper() for path in DATA_DIR.glob("*.csv"))
    return [code for code in codes if any(pattern.match(code) for pattern in MAIN_BOARD_PATTERNS)]


def quarter_periods(start_year: int = 2018, end_date: str | None = None) -> list[str]:
    end_ts = pd.Timestamp.today() if end_date is None else pd.Timestamp(end_date)
    periods: list[str] = []
    for year in range(start_year, end_ts.year + 1):
        for month_day in ["0331", "0630", "0930", "1231"]:
            period = f"{year}{month_day}"
            if pd.Timestamp(period) <= end_ts + pd.offsets.QuarterEnd(0):
                periods.append(period)
    return periods


def _normalize_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "ts_code" in out.columns:
        out["stock_code"] = out["ts_code"].astype(str).str.upper()
    for col in ["ann_date", "f_ann_date", "end_date"]:
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], format="%Y%m%d", errors="coerce")
    return out


def _dedupe_statement_rows(df: pd.DataFrame) -> pd.DataFrame:
    keys = [col for col in ["stock_code", "ann_date", "end_date"] if col in df.columns]
    if not keys:
        return df
    sort_cols = [col for col in ["stock_code", "end_date", "ann_date", "f_ann_date", "update_flag"] if col in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols)
    return df.drop_duplicates(subset=keys, keep="last").reset_index(drop=True)


def _is_retryable_error(message: str) -> bool:
    checks = [
        "频率",
        "rate",
        "connection aborted",
        "connectionreseterror",
        "httpconnectionpool",
        "远程主机强迫关闭",
    ]
    lowered = message.lower()
    return any(token in lowered for token in checks) or ("频率" in message)


def _fetch_endpoint(
    pro,
    api_name: str,
    periods: list[str],
    sleep_sec: float = 0.35,
    retry_wait_sec: int = 65,
    max_retries: int = 5,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for idx, period in enumerate(periods, start=1):
        for attempt in range(1, max_retries + 1):
            try:
                df = getattr(pro, api_name)(period=period)
                if df is not None and not df.empty:
                    frames.append(df.copy())
                break
            except Exception as exc:
                if _is_retryable_error(str(exc)) and attempt < max_retries:
                    print(f"[{api_name}] retryable error on {period}, sleeping {retry_wait_sec}s before retry {attempt + 1}/{max_retries}")
                    time.sleep(retry_wait_sec)
                    continue
                raise
        print(f"[{api_name}] fetched {idx}/{len(periods)} periods")
        time.sleep(sleep_sec)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _fetch_endpoint_by_stock(
    pro,
    endpoint_name: str,
    api_name: str,
    stock_codes: list[str],
    start_date: str,
    end_date: str,
    sleep_sec: float = 0.20,
    retry_wait_sec: int = 65,
    max_retries: int = 5,
) -> pd.DataFrame:
    partial_path = OUT_DIR / f"{endpoint_name}_partial.parquet"
    progress_path = OUT_DIR / f"{endpoint_name}_progress.json"
    frames: list[pd.DataFrame] = []
    start_idx = 0

    if partial_path.exists():
        frames.append(pd.read_parquet(partial_path))
    if progress_path.exists():
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
        start_idx = int(progress.get("last_completed_idx", 0))

    for idx, ts_code in enumerate(stock_codes[start_idx:], start=start_idx + 1):
        for attempt in range(1, max_retries + 1):
            try:
                df = getattr(pro, api_name)(ts_code=ts_code, start_date=start_date, end_date=end_date)
                if df is not None and not df.empty:
                    frames.append(df.copy())
                break
            except Exception as exc:
                if _is_retryable_error(str(exc)) and attempt < max_retries:
                    print(f"[{api_name}] retryable error on {ts_code}, sleeping {retry_wait_sec}s before retry {attempt + 1}/{max_retries}")
                    time.sleep(retry_wait_sec)
                    continue
                raise
        if idx % 100 == 0 or idx == len(stock_codes):
            snapshot = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
            if not snapshot.empty:
                snapshot.to_parquet(partial_path, index=False)
            progress_path.write_text(json.dumps({"last_completed_idx": idx}, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[{api_name}] fetched {idx}/{len(stock_codes)} stocks")
        time.sleep(sleep_sec)

    result = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if partial_path.exists():
        partial_path.unlink()
    if progress_path.exists():
        progress_path.unlink()
    return result


def fetch_all_pit_fundamentals(
    start_year: int = 2018,
    end_date: str | None = None,
) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    periods = quarter_periods(start_year=start_year, end_date=end_date)
    pro = load_pro()
    stock_codes = load_stock_codes()
    start_date = f"{start_year}0101"
    final_end_date = (pd.Timestamp.today() if end_date is None else pd.Timestamp(end_date)).strftime("%Y%m%d")

    report: dict[str, object] = {
        "start_year": start_year,
        "end_date": end_date or pd.Timestamp.today().strftime("%Y-%m-%d"),
        "period_count": len(periods),
        "periods": periods,
        "stock_count": len(stock_codes),
        "endpoints": {},
    }

    for endpoint_name, api_names in ENDPOINTS.items():
        final_path = OUT_DIR / f"{endpoint_name}_quarterly_2018plus.parquet"
        if final_path.exists():
            existing = pd.read_parquet(final_path)
            report["endpoints"][endpoint_name] = {
                "api_used": "existing_file",
                "rows": int(len(existing)),
                "path": str(final_path),
                "columns": list(existing.columns),
                "stocks": int(existing["stock_code"].nunique()) if "stock_code" in existing.columns else 0,
                "ann_dates": int(existing["ann_date"].nunique()) if "ann_date" in existing.columns else 0,
            }
            continue

        used_api = api_names["vip"]
        try:
            df = _fetch_endpoint(pro, api_names["vip"], periods)
        except Exception as exc:
            msg = str(exc)
            can_fallback = ("积分" in msg) or ("权限" in msg) or ("抱歉" in msg) or ("ts_code" in msg)
            if not can_fallback:
                raise
            used_api = api_names["regular"]
            print(f"[{endpoint_name}] vip path unavailable, falling back to per-stock regular endpoint")
            df = _fetch_endpoint_by_stock(
                pro,
                endpoint_name=endpoint_name,
                api_name=api_names["regular"],
                stock_codes=stock_codes,
                start_date=start_date,
                end_date=final_end_date,
            )

        if df.empty:
            report["endpoints"][endpoint_name] = {"rows": 0, "path": "", "columns": [], "api_used": used_api}
            continue

        df = _normalize_frame(df)
        df = _dedupe_statement_rows(df)
        df.to_parquet(final_path, index=False)
        report["endpoints"][endpoint_name] = {
            "api_used": used_api,
            "rows": int(len(df)),
            "path": str(final_path),
            "columns": list(df.columns),
            "stocks": int(df["stock_code"].nunique()) if "stock_code" in df.columns else 0,
            "ann_dates": int(df["ann_date"].nunique()) if "ann_date" in df.columns else 0,
        }

    (OUT_DIR / "fetch_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    result = fetch_all_pit_fundamentals()
    print(json.dumps(result, ensure_ascii=False, indent=2))
