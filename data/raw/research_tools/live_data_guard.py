from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import polars as pl

from TradingMain.config import DATA_DIR, ROOT
from TradingMain.data.loader import _scan_base
from TradingMain.state.calendar import is_trading_day


REFERENCE_ROOT = ROOT / "research" / "reference" / "tushare"
INTRADAY_DIR = ROOT / "1m_price"
INTRADAY_CACHE = ROOT / "research" / "cache" / "intraday_1m_daily_features_2020plus.parquet"


def _as_ts(value: str | pd.Timestamp | None) -> pd.Timestamp | pd.NaT:
    if value is None or value == "":
        return pd.NaT
    parsed = pd.to_datetime(value, errors="coerce", format="%Y%m%d")
    if pd.isna(parsed):
        parsed = pd.to_datetime(value, errors="coerce")
    return parsed


def latest_stock_history_trade_date(data_dir: Path = DATA_DIR) -> pd.Timestamp:
    # 轻量优先：从更新报告读取
    report_path = data_dir.parent / "logs" / "stockhistory_update_report.json"
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            for key in ["latest_trade_date", "expected_trade_date"]:
                latest_text = report.get(key)
                if latest_text:
                    parsed = _as_ts(latest_text)
                    if not pd.isna(parsed):
                        return pd.Timestamp(parsed)
        except Exception:
            pass
    # 次轻量：抽样读取最近修改文件的首条数据日期（StockHistory 文件按日期倒序）
    import re
    files = sorted(data_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)[:200]
    latest = None
    for f in files:
        try:
            with open(f, "rb") as fh:
                fh.readline()
                first_data = fh.readline(300).decode("utf-8-sig", errors="ignore")
            dates = [pd.Timestamp(m.group()) for m in re.finditer(r"\d{8}", first_data)]
            if dates:
                local_max = max(dates)
                if latest is None or local_max > latest:
                    latest = local_max
        except Exception:
            pass
    if latest is not None:
        return latest
    # 回退到原方案（数据量可控时）
    frame = _scan_base(data_dir).select(pl.col("trade_date").max().alias("max_trade_date")).collect().to_pandas()
    value = frame.loc[0, "max_trade_date"]
    return pd.Timestamp(value)


def expected_latest_trade_date(anchor: pd.Timestamp | None = None) -> pd.Timestamp:
    current = (anchor.normalize() if anchor is not None else pd.Timestamp.today().normalize()).date()
    current -= pd.Timedelta(days=1)
    cursor = current
    while not is_trading_day(cursor):
        cursor -= pd.Timedelta(days=1)
    return pd.Timestamp(cursor)


def latest_date_in_table(path: Path, date_cols: list[str]) -> pd.Timestamp | pd.NaT:
    if not path.exists():
        return pd.NaT
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        frame = pd.read_parquet(path)
    else:
        frame = pd.read_csv(path, usecols=lambda c: c in set(date_cols))
    candidates: list[pd.Timestamp] = []
    for col in date_cols:
        if col not in frame.columns:
            continue
        series = pd.to_datetime(frame[col], errors="coerce", format="%Y%m%d")
        if not series.dropna().empty:
            candidates.append(pd.Timestamp(series.max()))
    return max(candidates) if candidates else pd.NaT


def _load_fetch_end_date(report_path: Path) -> pd.Timestamp | pd.NaT:
    if not report_path.exists():
        return pd.NaT
    report = json.loads(report_path.read_text(encoding="utf-8"))
    return _as_ts(report.get("end_date"))


def _build_status_row(
    name: str,
    expected_date: pd.Timestamp,
    source_path: Path,
    observed_date: pd.Timestamp | pd.NaT,
    tolerance_days: int,
    source_kind: str,
) -> dict[str, object]:
    if not source_path.exists():
        status = "missing"
    elif pd.isna(observed_date):
        status = "unknown"
    elif observed_date < expected_date - pd.Timedelta(days=tolerance_days):
        status = "stale"
    else:
        status = "ok"
    return {
        "name": name,
        "status": status,
        "source_kind": source_kind,
        "expected_date": expected_date.date().isoformat(),
        "observed_date": "" if pd.isna(observed_date) else pd.Timestamp(observed_date).date().isoformat(),
        "tolerance_days": tolerance_days,
        "path": str(source_path),
    }


def build_champion_live_guard_report(require_intraday: bool = False) -> tuple[pd.DataFrame, dict[str, object]]:
    latest_trade_date = latest_stock_history_trade_date()
    today = pd.Timestamp.today().normalize()
    live_recency_floor = expected_latest_trade_date(today)
    rows: list[dict[str, object]] = []

    rows.append(
        _build_status_row(
            "stock_history",
            latest_trade_date,
            DATA_DIR,
            latest_trade_date,
            0,
            "daily_price",
        )
    )
    rows.append(
        _build_status_row(
            "stock_history_live_recency",
            live_recency_floor,
            DATA_DIR,
            latest_trade_date,
            0,
            "live_recency",
        )
    )

    guard_targets = [
        (
            "holder_risk_fetch",
            REFERENCE_ROOT / "holder_risk" / "fetch_report.json",
            _load_fetch_end_date(REFERENCE_ROOT / "holder_risk" / "fetch_report.json"),
            3,
            "fetch_report",
        ),
        (
            "event_fetch",
            REFERENCE_ROOT / "event" / "fetch_report.json",
            _load_fetch_end_date(REFERENCE_ROOT / "event" / "fetch_report.json"),
            3,
            "fetch_report",
        ),
        (
            "earnings_event_fetch",
            REFERENCE_ROOT / "earnings_event" / "fetch_report.json",
            _load_fetch_end_date(REFERENCE_ROOT / "earnings_event" / "fetch_report.json"),
            3,
            "fetch_report",
        ),
        (
            "index_daily_csi_all_share",
            REFERENCE_ROOT / "index_daily" / "CSI_ALL_SHARE_000985_CSI.csv",
            latest_date_in_table(REFERENCE_ROOT / "index_daily" / "CSI_ALL_SHARE_000985_CSI.csv", ["trade_date"]),
            3,
            "csv_table",
        ),
        (
            "holdernumber_daily",
            REFERENCE_ROOT / "holder_risk" / "holdernumber_daily_2020plus.parquet",
            latest_date_in_table(REFERENCE_ROOT / "holder_risk" / "holdernumber_daily_2020plus.parquet", ["ann_date", "end_date"]),
            180,
            "parquet_table",
        ),
        (
            "pledge_stat_weekly",
            REFERENCE_ROOT / "holder_risk" / "pledge_stat_weekly_2020plus.parquet",
            latest_date_in_table(REFERENCE_ROOT / "holder_risk" / "pledge_stat_weekly_2020plus.parquet", ["ann_date", "end_date"]),
            14,
            "parquet_table",
        ),
        (
            "forecast_quarterly",
            REFERENCE_ROOT / "earnings_event" / "forecast_quarterly_2019plus.parquet",
            latest_date_in_table(REFERENCE_ROOT / "earnings_event" / "forecast_quarterly_2019plus.parquet", ["ann_date", "first_ann_date", "end_date"]),
            180,
            "parquet_table",
        ),
        (
            "express_quarterly",
            REFERENCE_ROOT / "earnings_event" / "express_quarterly_2019plus.parquet",
            latest_date_in_table(REFERENCE_ROOT / "earnings_event" / "express_quarterly_2019plus.parquet", ["ann_date", "end_date"]),
            180,
            "parquet_table",
        ),
        (
            "repurchase_daily",
            REFERENCE_ROOT / "event" / "repurchase_daily_2020plus.parquet",
            latest_date_in_table(REFERENCE_ROOT / "event" / "repurchase_daily_2020plus.parquet", ["ann_date", "end_date", "exp_date"]),
            180,
            "parquet_table",
        ),
        (
            "holdertrade_daily",
            REFERENCE_ROOT / "event" / "holdertrade_daily_2020plus.parquet",
            latest_date_in_table(REFERENCE_ROOT / "event" / "holdertrade_daily_2020plus.parquet", ["ann_date"]),
            180,
            "parquet_table",
        ),
    ]

    if require_intraday:
        latest_intraday_file = max((path.stem for path in INTRADAY_DIR.glob("*.parquet")), default="")
        rows.append(
            _build_status_row(
                "intraday_1m_raw",
                latest_trade_date,
                INTRADAY_DIR,
                _as_ts(latest_intraday_file),
                3,
                "minute_files",
            )
        )
        rows.append(
            _build_status_row(
                "intraday_1m_cache",
                latest_trade_date,
                INTRADAY_CACHE,
                latest_date_in_table(INTRADAY_CACHE, ["trade_date"]),
                3,
                "parquet_table",
            )
        )

    for name, path, observed_date, tolerance_days, source_kind in guard_targets:
        rows.append(_build_status_row(name, latest_trade_date, path, observed_date, tolerance_days, source_kind))

    report = pd.DataFrame(rows)
    summary = {
        "today": today.date().isoformat(),
        "latest_trade_date": latest_trade_date.date().isoformat(),
        "expected_latest_trade_date": live_recency_floor.date().isoformat(),
        "live_recency_floor": live_recency_floor.date().isoformat(),
        "ok_count": int((report["status"] == "ok").sum()),
        "stale_count": int((report["status"] == "stale").sum()),
        "missing_count": int((report["status"] == "missing").sum()),
        "unknown_count": int((report["status"] == "unknown").sum()),
        "require_intraday": require_intraday,
    }
    return report, summary


def assert_champion_live_ready(require_intraday: bool = False) -> tuple[pd.DataFrame, dict[str, object]]:
    report, summary = build_champion_live_guard_report(require_intraday=require_intraday)
    blocking = report["status"].isin(["missing", "stale"])
    if bool(blocking.any()):
        failed = report.loc[blocking, ["name", "status", "observed_date", "expected_date"]]
        raise RuntimeError("Champion live data guard failed:\n" + failed.to_string(index=False))
    return report, summary
