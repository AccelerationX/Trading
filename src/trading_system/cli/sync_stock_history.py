from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from pandas.errors import EmptyDataError, ParserError

from trading_system.config.paths import INBOX_DIR, OUTPUTS_DIR, RAW_DATA_DIR


STOCK_HISTORY_COLUMNS = [
    "\u80a1\u7968\u4ee3\u7801",
    "\u80a1\u7968\u540d\u79f0",
    "\u4ea4\u6613\u65e5",
    "\u5f00\u76d8\u4ef7",
    "\u6700\u9ad8\u4ef7",
    "\u6700\u4f4e\u4ef7",
    "\u6536\u76d8\u4ef7",
    "\u524d\u6536\u76d8\u4ef7",
    "\u6da8\u8dcc\u989d",
    "\u6da8\u8dcc\u5e45\uff08%\uff09",
    "\u6210\u4ea4\u91cf\uff08\u624b\uff09",
    "\u6210\u4ea4\u989d\uff08\u5343\u5143\uff09",
    "\u6362\u624b\u7387\uff08%\uff09",
    "\u6362\u624b\u7387\uff08%\uff0c\u81ea\u7531\u6d41\u901a\u80a1\uff09",
    "\u91cf\u6bd4",
    "\u5e02\u76c8\u7387\uff08\u4e8f\u635f\u4e3a\u7a7a\uff09",
    "\u5e02\u76c8\u7387\uff08TTM\uff0c\u4e8f\u635f\u4e3a\u7a7a\uff09",
    "\u5e02\u51c0\u7387",
    "\u5e02\u9500\u7387",
    "\u5e02\u9500\u7387\uff08TTM\uff09",
    "\u80a1\u606f\u7387\uff08%\uff09",
    "\u80a1\u606f\u7387\uff08%\uff0cTTM\uff09",
    "\u603b\u80a1\u672c\uff08\u4e07\u80a1\uff09",
    "\u6d41\u901a\u80a1\u672c\uff08\u4e07\u80a1\uff09",
    "\u81ea\u7531\u6d41\u901a\u80a1\u672c\uff08\u4e07\u80a1\uff09",
    "\u603b\u5e02\u503c\uff08\u4e07\u5143\uff09",
    "\u6d41\u901a\u5e02\u503c\uff08\u4e07\u5143\uff09",
    "\u590d\u6743\u56e0\u5b50",
    "\u5f53\u65e5\u6da8\u505c\u4ef7",
    "\u5f53\u65e5\u8dcc\u505c\u4ef7",
]

STOCK_CODE_COL = "\u80a1\u7968\u4ee3\u7801"
STOCK_NAME_COL = "\u80a1\u7968\u540d\u79f0"
TRADE_DATE_COL = "\u4ea4\u6613\u65e5"


@dataclass(slots=True)
class StockHistorySyncResult:
    trade_date: str
    updated_files: int
    new_files: int
    skipped_files: int
    source_path: Path
    reference_path: Path | None
    sample_codes: list[str]


def _stock_history_dir() -> Path:
    directory = RAW_DATA_DIR / "stock_history"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _report_dir() -> Path:
    directory = OUTPUTS_DIR / "daily_reports"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, encoding="utf-8-sig", low_memory=False, on_bad_lines="skip")
    except (EmptyDataError, ParserError):
        return pd.DataFrame(columns=STOCK_HISTORY_COLUMNS)
    except UnicodeDecodeError:
        try:
            return pd.read_csv(path, encoding="utf-8", low_memory=False, on_bad_lines="skip")
        except (EmptyDataError, ParserError):
            return pd.DataFrame(columns=STOCK_HISTORY_COLUMNS)


def _find_exact_file(directory: Path, prefix: str, trade_date: str, suffix: str = ".csv") -> Path:
    path = directory / f"{prefix}_{trade_date}{suffix}"
    if not path.exists():
        raise FileNotFoundError(f"Required source file missing: {path}")
    return path


def _find_latest_file(directory: Path, prefix: str, suffix: str = ".csv") -> Path | None:
    candidates = sorted(directory.glob(f"{prefix}_*{suffix}"))
    if not candidates:
        return None
    return candidates[-1]


def _load_reference_name_map(reference_path: Path | None) -> dict[str, str]:
    if reference_path is None or not reference_path.exists():
        return {}
    df = _read_csv(reference_path)
    if "stock_code" not in df.columns or "name" not in df.columns:
        return {}
    work = df[["stock_code", "name"]].copy()
    work["stock_code"] = work["stock_code"].astype(str).str.strip().str.upper()
    work["name"] = work["name"].fillna("").astype(str).str.strip()
    return {
        row["stock_code"]: row["name"]
        for row in work.to_dict(orient="records")
        if row["stock_code"]
    }


def _safe_number(value) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return None
    return float(numeric)


def _safe_div_k(value) -> float | None:
    numeric = _safe_number(value)
    if numeric is None:
        return None
    return round(numeric / 1000.0, 4)


def _existing_name(existing: pd.DataFrame) -> str:
    if existing.empty or STOCK_NAME_COL not in existing.columns:
        return ""
    names = existing[STOCK_NAME_COL].dropna().astype(str).str.strip()
    names = names[names != ""]
    if names.empty:
        return ""
    return names.iloc[0]


def _normalize_market_row(row: dict, name_map: dict[str, str], existing_name: str = "") -> dict[str, object]:
    stock_code = str(row.get("stock_code", "")).strip().upper()
    prev_close = _safe_number(row.get("prev_close"))
    close = _safe_number(row.get("close"))
    change_amount = None
    change_pct = None
    if prev_close not in (None, 0.0) and close is not None:
        change_amount = round(close - prev_close, 4)
        change_pct = round(((close / prev_close) - 1.0) * 100.0, 4)

    stock_name = existing_name.strip() or name_map.get(stock_code, "").strip()
    return {
        STOCK_CODE_COL: stock_code,
        STOCK_NAME_COL: stock_name,
        TRADE_DATE_COL: str(row.get("trade_date", "")).strip(),
        "\u5f00\u76d8\u4ef7": _safe_number(row.get("open")),
        "\u6700\u9ad8\u4ef7": _safe_number(row.get("high")),
        "\u6700\u4f4e\u4ef7": _safe_number(row.get("low")),
        "\u6536\u76d8\u4ef7": close,
        "\u524d\u6536\u76d8\u4ef7": prev_close,
        "\u6da8\u8dcc\u989d": change_amount,
        "\u6da8\u8dcc\u5e45\uff08%\uff09": change_pct,
        "\u6210\u4ea4\u91cf\uff08\u624b\uff09": _safe_number(row.get("volume")),
        "\u6210\u4ea4\u989d\uff08\u5343\u5143\uff09": _safe_div_k(row.get("amount")),
        "\u6362\u624b\u7387\uff08%\uff09": _safe_number(row.get("turnover_pct")),
        "\u6362\u624b\u7387\uff08%\uff0c\u81ea\u7531\u6d41\u901a\u80a1\uff09": _safe_number(row.get("turnover_rate_f")),
        "\u91cf\u6bd4": _safe_number(row.get("volume_ratio")),
        "\u5e02\u76c8\u7387\uff08\u4e8f\u635f\u4e3a\u7a7a\uff09": None,
        "\u5e02\u76c8\u7387\uff08TTM\uff0c\u4e8f\u635f\u4e3a\u7a7a\uff09": _safe_number(row.get("pe_ttm")),
        "\u5e02\u51c0\u7387": _safe_number(row.get("pb")),
        "\u5e02\u9500\u7387": None,
        "\u5e02\u9500\u7387\uff08TTM\uff09": None,
        "\u80a1\u606f\u7387\uff08%\uff09": None,
        "\u80a1\u606f\u7387\uff08%\uff0cTTM\uff09": None,
        "\u603b\u80a1\u672c\uff08\u4e07\u80a1\uff09": _safe_number(row.get("total_share")),
        "\u6d41\u901a\u80a1\u672c\uff08\u4e07\u80a1\uff09": _safe_number(row.get("float_share")),
        "\u81ea\u7531\u6d41\u901a\u80a1\u672c\uff08\u4e07\u80a1\uff09": _safe_number(row.get("free_share")),
        "\u603b\u5e02\u503c\uff08\u4e07\u5143\uff09": _safe_number(row.get("total_mv")),
        "\u6d41\u901a\u5e02\u503c\uff08\u4e07\u5143\uff09": _safe_number(row.get("circ_mv")),
        "\u590d\u6743\u56e0\u5b50": None,
        "\u5f53\u65e5\u6da8\u505c\u4ef7": _safe_number(row.get("limit_up_price")),
        "\u5f53\u65e5\u8dcc\u505c\u4ef7": _safe_number(row.get("limit_down_price")),
    }


def _prepare_existing_frame(file_path: Path) -> pd.DataFrame:
    if not file_path.exists():
        return pd.DataFrame(columns=STOCK_HISTORY_COLUMNS)
    existing = _read_csv(file_path)
    existing.columns = [str(column).lstrip("\ufeff").strip() for column in existing.columns]
    if existing.empty:
        return pd.DataFrame(columns=STOCK_HISTORY_COLUMNS)
    return existing.reindex(columns=STOCK_HISTORY_COLUMNS)


def _values_equal(left, right) -> bool:
    if pd.isna(left) and pd.isna(right):
        return True
    return left == right


def _row_matches(existing: pd.Series, incoming: dict[str, object]) -> bool:
    for column in STOCK_HISTORY_COLUMNS:
        if not _values_equal(existing.get(column), incoming.get(column)):
            return False
    return True


def _merge_and_save_stock_history(
    file_path: Path,
    row_dict: dict[str, object],
    existing: pd.DataFrame | None = None,
) -> tuple[bool, bool]:
    is_new_file = not file_path.exists()
    existing = existing if existing is not None else _prepare_existing_frame(file_path)
    current_name = _existing_name(existing)
    if current_name and not row_dict.get(STOCK_NAME_COL):
        row_dict[STOCK_NAME_COL] = current_name

    existing = existing.reindex(columns=STOCK_HISTORY_COLUMNS)
    existing = existing.dropna(how="all").reset_index(drop=True)
    trade_date = str(row_dict.get(TRADE_DATE_COL, "")).strip()
    if not trade_date:
        return False, is_new_file

    same_day_rows = pd.DataFrame(columns=STOCK_HISTORY_COLUMNS)
    if not existing.empty and TRADE_DATE_COL in existing.columns:
        existing_trade_dates = existing[TRADE_DATE_COL].astype(str)
        same_day_rows = existing.loc[existing_trade_dates == trade_date]
        if len(same_day_rows) == 1 and _row_matches(same_day_rows.iloc[0], row_dict):
            return False, is_new_file
    else:
        existing_trade_dates = pd.Series(dtype=str)

    existing_records = existing.to_dict(orient="records") if not existing.empty else []
    filtered_records = [
        {
            column: record.get(column)
            for column in STOCK_HISTORY_COLUMNS
        }
        for record in existing_records
        if str(record.get(TRADE_DATE_COL, "")).strip() != trade_date
    ]
    filtered_records.append({column: row_dict.get(column) for column in STOCK_HISTORY_COLUMNS})
    combined = pd.DataFrame(filtered_records, columns=STOCK_HISTORY_COLUMNS)
    combined[TRADE_DATE_COL] = combined[TRADE_DATE_COL].astype(str).str.strip()
    combined = combined[combined[TRADE_DATE_COL] != ""]
    combined = combined.drop_duplicates(subset=[TRADE_DATE_COL], keep="last")
    combined = combined.sort_values(TRADE_DATE_COL, ascending=False).reset_index(drop=True)
    combined.to_csv(file_path, index=False, encoding="utf-8-sig")

    return True, is_new_file


def sync_stock_history_from_market_daily(trade_date: str) -> tuple[Path, Path]:
    market_path = _find_exact_file(INBOX_DIR / "market_equity_daily", "market_equity_daily", trade_date)
    reference_path = _find_latest_file(INBOX_DIR / "equity_reference_master", "equity_reference_master")
    json_path = _report_dir() / f"stock_history_sync_{trade_date}.json"
    md_path = _report_dir() / f"stock_history_sync_{trade_date}.md"
    source_mtime = market_path.stat().st_mtime

    if json_path.exists() and md_path.exists():
        try:
            previous = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = json.loads(json_path.read_text(encoding="utf-8-sig"))
        if float(previous.get("source_mtime", -1.0)) == source_mtime:
            return json_path, md_path

    market_df = _read_csv(market_path)
    if "stock_code" not in market_df.columns or "trade_date" not in market_df.columns:
        raise FileNotFoundError(f"market_equity_daily missing required columns: {market_path}")
    market_df["stock_code"] = market_df["stock_code"].astype(str).str.strip().str.upper()
    market_df["trade_date"] = market_df["trade_date"].astype(str).str.strip()
    market_df = market_df[market_df["trade_date"] == trade_date].copy()
    if market_df.empty:
        raise FileNotFoundError(f"market_equity_daily has no rows for {trade_date}: {market_path}")

    name_map = _load_reference_name_map(reference_path)
    stock_dir = _stock_history_dir()
    updated_files = 0
    new_files = 0
    skipped_files = 0
    sample_codes: list[str] = []

    for row in market_df.to_dict(orient="records"):
        stock_code = str(row.get("stock_code", "")).strip().upper()
        if not stock_code:
            skipped_files += 1
            continue
        file_path = stock_dir / f"{stock_code}.csv"
        existing = _prepare_existing_frame(file_path)
        row_dict = _normalize_market_row(row, name_map, existing_name=_existing_name(existing))
        updated, is_new_file = _merge_and_save_stock_history(file_path, row_dict, existing=existing)
        if updated:
            updated_files += 1
            if is_new_file:
                new_files += 1
            if len(sample_codes) < 10:
                sample_codes.append(stock_code)
        else:
            skipped_files += 1

    result = StockHistorySyncResult(
        trade_date=trade_date,
        updated_files=updated_files,
        new_files=new_files,
        skipped_files=skipped_files,
        source_path=market_path,
        reference_path=reference_path,
        sample_codes=sample_codes,
    )

    json_payload = {
        "trade_date": result.trade_date,
        "updated_files": result.updated_files,
        "new_files": result.new_files,
        "skipped_files": result.skipped_files,
        "source_path": str(result.source_path),
        "source_mtime": source_mtime,
        "reference_path": str(result.reference_path) if result.reference_path else None,
        "sample_codes": result.sample_codes,
    }
    json_path.write_text(json.dumps(json_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        f"# Stock History Sync - {trade_date}",
        "",
        f"- updated_files: `{result.updated_files}`",
        f"- new_files: `{result.new_files}`",
        f"- skipped_files: `{result.skipped_files}`",
        f"- source_path: `{result.source_path}`",
        f"- reference_path: `{result.reference_path}`",
        f"- sample_codes: `{', '.join(result.sample_codes) if result.sample_codes else 'none'}`",
    ]
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return json_path, md_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Trade date in YYYYMMDD format.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    json_path, md_path = sync_stock_history_from_market_daily(str(args.date))
    print(f"stock_history_sync_json={json_path}")
    print(f"stock_history_sync_md={md_path}")


if __name__ == "__main__":
    main()
