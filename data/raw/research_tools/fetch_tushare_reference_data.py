from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd


ROOT = Path(r"D:\TradingMain")
ENV_PATHS = [Path(r"D:\Trading\.env"), ROOT / ".env"]
OUT_DIR = ROOT / "research" / "reference" / "tushare"
INDEX_DIR = OUT_DIR / "index_daily"
INDUSTRY_DIR = OUT_DIR / "sw_l1"

DEFAULT_INDEXES = {
    "000300.SH": "CSI300",
    "000905.SH": "CSI500",
    "000852.SH": "CSI1000",
    "000985.CSI": "CSI_ALL_SHARE",
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
    pro,
    start_date: str = "20200101",
    end_date: str | None = None,
    index_map: dict[str, str] | None = None,
) -> dict[str, int]:
    end_date = end_date or pd.Timestamp.today().strftime("%Y%m%d")
    index_map = index_map or DEFAULT_INDEXES
    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    written: dict[str, int] = {}
    for ts_code, label in index_map.items():
        df = pro.index_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        if df is None or df.empty:
            written[ts_code] = 0
            continue
        df = df.sort_values("trade_date")
        out_path = INDEX_DIR / f"{label}_{ts_code.replace('.', '_')}.csv"
        df.to_csv(out_path, index=False, encoding="utf-8-sig")
        written[ts_code] = int(len(df))
    return written


def fetch_sw_level1_members(pro, src: str = "SW2021") -> dict[str, int]:
    INDUSTRY_DIR.mkdir(parents=True, exist_ok=True)

    classify = pro.index_classify(
        level="L1",
        src=src,
        fields="index_code,industry_name,level,industry_code,parent_code,is_pub",
    )
    if classify is None or classify.empty:
        raise RuntimeError(f"No SW level-1 industries returned for src={src}")
    classify = classify.sort_values("index_code").reset_index(drop=True)
    classify.to_csv(INDUSTRY_DIR / "index_classify.csv", index=False, encoding="utf-8-sig")

    member_frames: list[pd.DataFrame] = []
    written: dict[str, int] = {}
    for row in classify.itertuples(index=False):
        code = getattr(row, "index_code")
        name = getattr(row, "industry_name")
        member = pro.index_member(
            index_code=code,
            fields="index_code,index_name,con_code,con_name,in_date,out_date,is_new",
        )
        if member is None or member.empty:
            written[code] = 0
            continue
        member["industry_code"] = code
        member["industry_name"] = name
        member_frames.append(member)
        written[code] = int(len(member))

    members = pd.concat(member_frames, ignore_index=True) if member_frames else pd.DataFrame()
    members.to_csv(INDUSTRY_DIR / "index_members.csv", index=False, encoding="utf-8-sig")
    return written


def fetch_all_reference_data(
    start_date: str = "20200101",
    end_date: str | None = None,
    src: str = "SW2021",
) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pro = load_pro()

    index_rows = fetch_index_daily(pro=pro, start_date=start_date, end_date=end_date)
    industry_rows = fetch_sw_level1_members(pro=pro, src=src)

    report = {
        "start_date": start_date,
        "end_date": end_date or pd.Timestamp.today().strftime("%Y%m%d"),
        "sw_src": src,
        "index_written_rows": index_rows,
        "industry_member_rows": industry_rows,
        "index_count": len(index_rows),
        "industry_count": len(industry_rows),
    }
    (OUT_DIR / "fetch_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    report = fetch_all_reference_data()
    print(json.dumps(report, ensure_ascii=False, indent=2))
