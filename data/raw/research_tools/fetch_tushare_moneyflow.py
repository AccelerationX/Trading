from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(r"D:\TradingMain")
sys.path.insert(0, str(ROOT))

from research.tools.fetch_tushare_reference_data import load_pro
OUT_DIR = ROOT / "research" / "reference" / "tushare" / "moneyflow"
CACHE_PATH = OUT_DIR / "moneyflow_daily_2020plus.parquet"
REPORT_PATH = OUT_DIR / "fetch_report.json"


def fetch_open_trade_dates(pro, start_date: str, end_date: str) -> list[str]:
    cal = pro.trade_cal(exchange="SSE", start_date=start_date, end_date=end_date, is_open=1)
    if cal is None or cal.empty:
        return []
    return sorted(cal["cal_date"].astype(str).tolist())


def _normalize_numeric(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        if col not in {"ts_code", "trade_date"}:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def fetch_moneyflow_daily(
    start_date: str = "20200101",
    end_date: str | None = None,
    force: bool = False,
) -> dict:
    end_date = end_date or pd.Timestamp.today().strftime("%Y%m%d")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pro = load_pro()

    existing = pd.DataFrame()
    if CACHE_PATH.exists() and not force:
        existing = pd.read_parquet(CACHE_PATH)
        existing["trade_date"] = pd.to_datetime(existing["trade_date"])
    existing_dates = set(existing["trade_date"].dt.strftime("%Y%m%d")) if not existing.empty else set()

    open_dates = fetch_open_trade_dates(pro, start_date=start_date, end_date=end_date)
    missing_dates = [d for d in open_dates if d not in existing_dates]

    batches: list[pd.DataFrame] = []
    total = len(missing_dates)
    for idx, trade_date in enumerate(missing_dates, start=1):
        df = pro.moneyflow(trade_date=trade_date)
        if df is None or df.empty:
            continue
        df = _normalize_numeric(df)
        df["stock_code"] = df["ts_code"].astype(str).str.upper()
        df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d", errors="coerce")
        batches.append(df)
        if idx % 20 == 0 or idx == total:
            print(f"[tushare-moneyflow] fetched {idx}/{total} trade dates")

    new_data = pd.concat(batches, ignore_index=True) if batches else pd.DataFrame()
    if not new_data.empty:
        keep_cols = [
            "stock_code",
            "trade_date",
            "buy_sm_amount",
            "sell_sm_amount",
            "buy_md_amount",
            "sell_md_amount",
            "buy_lg_amount",
            "sell_lg_amount",
            "buy_elg_amount",
            "sell_elg_amount",
            "net_mf_amount",
        ]
        new_data = new_data[[col for col in keep_cols if col in new_data.columns]].copy()

    full = pd.concat([existing, new_data], ignore_index=True) if not existing.empty else new_data
    if not full.empty:
        full = full.drop_duplicates(subset=["stock_code", "trade_date"], keep="last").sort_values(
            ["trade_date", "stock_code"]
        )
        full.to_parquet(CACHE_PATH, index=False)

    report = {
        "start_date": start_date,
        "end_date": end_date,
        "open_trade_dates": len(open_dates),
        "fetched_trade_dates": len(missing_dates),
        "rows_total": int(len(full)),
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    report = fetch_moneyflow_daily()
    print(json.dumps(report, ensure_ascii=False, indent=2))
