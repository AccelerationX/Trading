from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd


ROOT = Path(r"D:\TradingMain")
ENV_PATHS = [Path(r"D:\Trading\.env"), ROOT / ".env"]
OUT_DIR = ROOT / "research" / "reference" / "index_daily"

DEFAULT_INDEXES = {
    "000300.SH": "CSI300",
    "000905.SH": "CSI500",
    "000852.SH": "CSI1000",
    "000985.CSI": "CSI_ALL_SHARE",
    "399303.SZ": "SZR1000",
}


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


def fetch_index_daily(
    start_date: str = "20100101",
    end_date: str | None = None,
    index_map: dict[str, str] | None = None,
) -> dict[str, int]:
    pro = load_pro()
    end_date = end_date or pd.Timestamp.today().strftime("%Y%m%d")
    index_map = index_map or DEFAULT_INDEXES
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    written: dict[str, int] = {}
    for ts_code, label in index_map.items():
        df = pro.index_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        if df is None or df.empty:
            written[ts_code] = 0
            continue
        df = df.sort_values("trade_date")
        out_path = OUT_DIR / f"{label}_{ts_code.replace('.', '_')}.csv"
        df.to_csv(out_path, index=False, encoding="utf-8-sig")
        written[ts_code] = int(len(df))

    report = {
        "start_date": start_date,
        "end_date": end_date,
        "written_rows": written,
        "index_count": len(index_map),
    }
    (OUT_DIR / "fetch_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return written


if __name__ == "__main__":
    result = fetch_index_daily()
    print(json.dumps(result, ensure_ascii=False, indent=2))
