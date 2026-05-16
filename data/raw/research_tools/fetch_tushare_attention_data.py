from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import pandas as pd


ROOT = Path(r"D:\TradingMain")
ENV_PATHS = [Path(r"D:\Trading\.env"), ROOT / ".env"]
OUT_DIR = ROOT / "research" / "reference" / "tushare" / "attention_event"
REPORT_RC_STATE_PATH = OUT_DIR / "report_rc_fetch_state.json"


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


def _month_chunks(start_month: str, end_month: str) -> list[str]:
    months = pd.period_range(start=start_month, end=end_month, freq="M")
    return [period.strftime("%Y%m") for period in months]


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


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "ts_code" in out.columns:
        out["stock_code"] = out["ts_code"].astype(str).str.upper()
    for col in ["report_date", "ann_date", "end_date"]:
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], format="%Y%m%d", errors="coerce")
    if "month" in out.columns:
        out["month"] = out["month"].astype(str)
    return out


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


def _load_report_rc_state() -> dict:
    if not REPORT_RC_STATE_PATH.exists():
        return {"completed_months": [], "last_attempt_month": None, "last_error": None}
    return json.loads(REPORT_RC_STATE_PATH.read_text(encoding="utf-8"))


def _write_report_rc_state(state: dict) -> None:
    REPORT_RC_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _fetch_report_rc_incremental(
    pro,
    report_rc_path: Path,
    start_date: str,
    end_date: str,
    max_months: int | None = None,
) -> pd.DataFrame:
    state = _load_report_rc_state()
    completed = set(state.get("completed_months", []))
    months = _month_chunks(start_date[:6], end_date[:6])
    pending = [month for month in months if month not in completed]
    if max_months is not None:
        pending = pending[:max_months]

    existing = pd.read_parquet(report_rc_path) if report_rc_path.exists() else pd.DataFrame()
    fetched = 0
    last_error = None
    for idx, month in enumerate(pending, start=1):
        month_start = f"{month}01"
        month_end = pd.Period(month, freq="M").end_time.strftime("%Y%m%d")
        try:
            chunk = _fetch_with_paging(pro, "report_rc", {"start_date": month_start, "end_date": month_end})
        except Exception as exc:
            last_error = str(exc)
            state["last_attempt_month"] = month
            state["last_error"] = last_error
            _write_report_rc_state(state)
            print(f"[report_rc] stopped at {month}: {last_error}")
            break

        if chunk is not None and not chunk.empty:
            chunk = _normalize(chunk).drop_duplicates().reset_index(drop=True)
            existing = pd.concat([existing, chunk], ignore_index=True)
            existing = existing.drop_duplicates().reset_index(drop=True)
            existing.to_parquet(report_rc_path, index=False)

        fetched += 1
        completed.add(month)
        state["completed_months"] = sorted(completed)
        state["last_attempt_month"] = month
        state["last_error"] = None
        _write_report_rc_state(state)
        print(f"[report_rc] fetched {fetched}/{len(pending)} pending months ({month})")
        time.sleep(0.25)

    if last_error is None and pending:
        state["last_error"] = None
        _write_report_rc_state(state)
    return existing


def fetch_attention_data(
    start_date: str = "20200101",
    end_date: str | None = None,
    skip_report_rc: bool = False,
    skip_broker_recommend: bool = False,
    skip_holdernumber: bool = False,
    report_rc_max_months: int | None = None,
) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    end_date = end_date or pd.Timestamp.today().strftime("%Y%m%d")
    pro = load_pro()
    report_rc_path = OUT_DIR / "report_rc_daily_2020plus.parquet"
    broker_recommend_path = OUT_DIR / "broker_recommend_monthly_2020plus.parquet"
    holdernumber_path = OUT_DIR / "holdernumber_daily_2020plus.parquet"
    report: dict[str, object] = {"start_date": start_date, "end_date": end_date, "endpoints": {}}

    if skip_report_rc:
        report["endpoints"]["report_rc"] = {"skipped": True}
    else:
        report_rc = _fetch_report_rc_incremental(
            pro=pro,
            report_rc_path=report_rc_path,
            start_date=start_date,
            end_date=end_date,
            max_months=report_rc_max_months,
        )
        state = _load_report_rc_state()
        report["endpoints"]["report_rc"] = {
            "rows": int(len(report_rc)),
            "path": str(report_rc_path),
            "columns": list(report_rc.columns),
            "completed_months": len(state.get("completed_months", [])),
            "last_attempt_month": state.get("last_attempt_month"),
            "last_error": state.get("last_error"),
        }

    if skip_broker_recommend:
        report["endpoints"]["broker_recommend"] = {"skipped": True}
    else:
        if broker_recommend_path.exists():
            broker_recommend = pd.read_parquet(broker_recommend_path)
        else:
            months = _month_chunks(start_date[:6], end_date[:6])
            frames = []
            for idx, month in enumerate(months, start=1):
                for attempt in range(1, 6):
                    try:
                        df = pro.query("broker_recommend", month=month)
                        break
                    except Exception as exc:
                        if _is_retryable_error(str(exc)) and attempt < 5:
                            time.sleep(65)
                            continue
                        raise
                if df is not None and not df.empty:
                    frames.append(df.copy())
                if idx % 12 == 0 or idx == len(months):
                    print(f"[broker_recommend] fetched {idx}/{len(months)} months")
                time.sleep(0.25)
            broker_recommend = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
            broker_recommend = _normalize(broker_recommend).drop_duplicates().reset_index(drop=True)
            broker_recommend.to_parquet(broker_recommend_path, index=False)
        report["endpoints"]["broker_recommend"] = {
            "rows": int(len(broker_recommend)),
            "path": str(broker_recommend_path),
            "columns": list(broker_recommend.columns),
        }

    if skip_holdernumber:
        report["endpoints"]["stk_holdernumber"] = {"skipped": True}
    else:
        if holdernumber_path.exists():
            holdernumber = pd.read_parquet(holdernumber_path)
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

    (OUT_DIR / "fetch_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", default="20200101")
    parser.add_argument("--end-date")
    parser.add_argument("--skip-report-rc", action="store_true")
    parser.add_argument("--skip-broker-recommend", action="store_true")
    parser.add_argument("--skip-holdernumber", action="store_true")
    parser.add_argument("--report-rc-max-months", type=int)
    args = parser.parse_args()
    result = fetch_attention_data(
        start_date=args.start_date,
        end_date=args.end_date,
        skip_report_rc=args.skip_report_rc,
        skip_broker_recommend=args.skip_broker_recommend,
        skip_holdernumber=args.skip_holdernumber,
        report_rc_max_months=args.report_rc_max_months,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
