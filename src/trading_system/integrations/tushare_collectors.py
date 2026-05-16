from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from trading_system.config.paths import INBOX_DIR
from trading_system.integrations.tushare_client import call_with_retry, latest_open_trade_date, load_open_trade_dates, load_pro_client


INDEX_MAP = {
    "000001.SH": "SSE Composite",
    "399001.SZ": "SZSE Component",
    "399006.SZ": "ChiNext",
    "000300.SH": "CSI300",
    "000905.SH": "CSI500",
    "000852.SH": "CSI1000",
}

MAIN_BOARD_PATTERNS = (
    re.compile(r"^(600|601|603|605)\d{3}\.SH$"),
    re.compile(r"^(000|001|002|003)\d{3}\.SZ$"),
)


@dataclass(slots=True)
class CollectionArtifact:
    source_id: str
    path: Path
    row_count: int
    notes: list[str]


def normalize_trade_date_str(trade_date: str) -> str:
    text = str(trade_date).strip()
    if "-" in text:
        return pd.Timestamp(text).strftime("%Y%m%d")
    if len(text) == 8 and text.isdigit():
        return text
    return pd.Timestamp(text).strftime("%Y%m%d")


def _inbox_file(source_id: str, trade_date: str, suffix: str) -> Path:
    directory = INBOX_DIR / source_id
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{source_id}_{trade_date}{suffix}"


def _normalize_stock_code(df: pd.DataFrame, code_col: str = "ts_code") -> pd.DataFrame:
    out = df.copy()
    if code_col in out.columns:
        out["stock_code"] = out[code_col].astype(str).str.upper()
    return out


def _stock_type(ts_code: str) -> str:
    code = ts_code.split(".")[0]
    if code.startswith("688"):
        return "kc"
    if code.startswith("300"):
        return "cy"
    if code.startswith(("430", "8", "4")) and ts_code.endswith("BJ"):
        return "bj"
    return "normal"


def _calc_limit(prev_close: float, stock_type: str) -> tuple[float | None, float | None]:
    if pd.isna(prev_close) or prev_close <= 0:
        return None, None
    if stock_type == "bj":
        up_pct, down_pct = 0.30, 0.30
    elif stock_type in {"kc", "cy"}:
        up_pct, down_pct = 0.20, 0.20
    else:
        up_pct, down_pct = 0.10, 0.10
    return round(float(prev_close) * (1 + up_pct), 2), round(float(prev_close) * (1 - down_pct), 2)


def _is_main_board(ts_code: str) -> bool:
    upper = str(ts_code).upper()
    return any(pattern.match(upper) for pattern in MAIN_BOARD_PATTERNS)


def _write_csv(path: Path, df: pd.DataFrame) -> CollectionArtifact:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return CollectionArtifact(source_id=path.parent.name, path=path, row_count=int(len(df)), notes=[])


def _write_json_records(path: Path, records: list[dict]) -> CollectionArtifact:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return CollectionArtifact(source_id=path.parent.name, path=path, row_count=len(records), notes=[])


REPURCHASE_STAGE_LABELS = {
    "board_pass": "董事会通过",
    "board passed": "董事会通过",
    "shareholders_meeting_pass": "股东大会通过",
    "shareholders meeting passed": "股东大会通过",
    "implemented": "实施",
    "progress": "实施",
    "completed": "完成",
    "proposal": "预案",
}


def _normalize_repurchase_stage(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "进展"
    lowered = text.lower()
    if lowered in REPURCHASE_STAGE_LABELS:
        return REPURCHASE_STAGE_LABELS[lowered]
    keyword_map = (
        ("董事会", "董事会通过"),
        ("股东大会", "股东大会通过"),
        ("实施", "实施"),
        ("完成", "完成"),
        ("预案", "预案"),
        ("提议", "提议"),
    )
    for keyword, label in keyword_map:
        if keyword in text:
            return label
    return text


def _format_repurchase_title(stage: object) -> str:
    return f"股份回购进展：{_normalize_repurchase_stage(stage)}"


def _format_repurchase_summary(amount: object, volume: object) -> str:
    amount_text = "未知" if pd.isna(pd.to_numeric(amount, errors="coerce")) else f"{float(amount):.2f}"
    volume_numeric = pd.to_numeric(volume, errors="coerce")
    volume_text = "未知" if pd.isna(volume_numeric) else f"{float(volume_numeric):.0f}"
    return f"回购金额={amount_text}元，回购数量={volume_text}股"


def _format_holdertrade_title(filing_type: str) -> str:
    mapping = {
        "share_increase": "重要股东增持",
        "share_reduction": "重要股东减持",
    }
    return mapping.get(filing_type, filing_type.replace("_", " "))


def _format_holdertrade_summary(record: dict) -> str:
    holder_name = str(record.get("holder_name", "")).strip() or "未披露股东"
    change_vol = str(record.get("change_vol", "")).strip() or "未知"
    change_ratio = str(record.get("change_ratio", "")).strip() or "未知"
    return f"股东={holder_name}，变动股数={change_vol}，变动比例={change_ratio}"


def _fetch_stock_basic(pro) -> pd.DataFrame:
    return call_with_retry(
        lambda: pro.stock_basic(
            exchange="",
            list_status="L",
            fields="ts_code,symbol,name,area,industry,market,list_date,list_status",
        ),
        sleep_seconds=10,
    )


def collect_equity_reference_master(trade_date: str) -> CollectionArtifact:
    pro = load_pro_client()
    effective_trade_date = latest_open_trade_date(pro, normalize_trade_date_str(trade_date))
    raw = _fetch_stock_basic(pro)
    raw = _normalize_stock_code(raw, "ts_code")
    raw["trade_date"] = effective_trade_date
    raw = raw.sort_values("stock_code").reset_index(drop=True)
    path = _inbox_file("equity_reference_master", effective_trade_date, ".csv")
    artifact = _write_csv(path, raw)
    artifact.notes.append("source=tushare.stock_basic")
    return artifact


def _fetch_daily_and_basic_for_trade_date(pro, trade_date: str) -> pd.DataFrame:
    daily = call_with_retry(lambda: pro.daily(trade_date=trade_date), sleep_seconds=10)
    basic = call_with_retry(lambda: pro.daily_basic(trade_date=trade_date), sleep_seconds=10)
    if daily is None or daily.empty:
        raise RuntimeError(f"daily returned empty result set for {trade_date}")

    work = daily.copy()
    work = _normalize_stock_code(work, "ts_code")
    work = work[work["stock_code"].map(_is_main_board)].copy()
    if basic is not None and not basic.empty:
        basic = _normalize_stock_code(basic, "ts_code")
        merge_columns = [
            "ts_code",
            "turnover_rate",
            "turnover_rate_f",
            "volume_ratio",
            "pe_ttm",
            "pb",
            "total_mv",
            "circ_mv",
            "float_share",
            "free_share",
            "total_share",
        ]
        available_columns = [column for column in merge_columns if column in basic.columns]
        work = work.merge(
            basic[available_columns],
            on="ts_code",
            how="left",
        )

    work["stock_type"] = work["stock_code"].map(_stock_type)
    limits = work.apply(
        lambda row: _calc_limit(float(row["pre_close"]) if pd.notna(row["pre_close"]) else 0.0, row["stock_type"]),
        axis=1,
        result_type="expand",
    )
    work["limit_up_price"] = limits[0]
    work["limit_down_price"] = limits[1]
    work["trade_date"] = work["trade_date"].astype(str)
    work["volume"] = pd.to_numeric(work["vol"], errors="coerce").fillna(0.0)
    work["amount"] = pd.to_numeric(work["amount"], errors="coerce").fillna(0.0) * 1000.0
    work["turnover_pct"] = pd.to_numeric(work.get("turnover_rate"), errors="coerce")
    return work


def collect_market_equity_daily(trade_date: str) -> CollectionArtifact:
    pro = load_pro_client()
    effective_trade_date = latest_open_trade_date(pro, normalize_trade_date_str(trade_date))
    work = _fetch_daily_and_basic_for_trade_date(pro, effective_trade_date)
    required_columns = [
        "stock_code",
        "trade_date",
        "open",
        "high",
        "low",
        "close",
        "pre_close",
        "volume",
        "amount",
        "turnover_pct",
        "turnover_rate_f",
        "volume_ratio",
        "pe_ttm",
        "pb",
        "limit_up_price",
        "limit_down_price",
        "total_share",
        "float_share",
        "free_share",
        "total_mv",
        "circ_mv",
    ]
    for column in required_columns:
        if column not in work.columns:
            work[column] = None
    out = work[required_columns].rename(columns={"pre_close": "prev_close"})
    out = out.sort_values("stock_code").reset_index(drop=True)
    path = _inbox_file("market_equity_daily", effective_trade_date, ".csv")
    artifact = _write_csv(path, out)
    artifact.notes.extend(["source=tushare.daily", "merged=tushare.daily_basic"])
    return artifact


def collect_market_index_daily(trade_date: str) -> CollectionArtifact:
    pro = load_pro_client()
    effective_trade_date = latest_open_trade_date(pro, normalize_trade_date_str(trade_date))
    frames: list[pd.DataFrame] = []
    for ts_code, index_name in INDEX_MAP.items():
        df = call_with_retry(lambda code=ts_code: pro.index_daily(ts_code=code, start_date=effective_trade_date, end_date=effective_trade_date), sleep_seconds=10)
        if df is None or df.empty:
            continue
        frame = df.copy()
        frame["index_code"] = ts_code
        frame["index_name"] = index_name
        frame["trade_date"] = frame["trade_date"].astype(str)
        frame["volume"] = pd.to_numeric(frame["vol"], errors="coerce").fillna(0.0)
        frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce").fillna(0.0) * 1000.0
        frames.append(frame)
    if not frames:
        raise RuntimeError(f"index_daily returned empty result set for {effective_trade_date}")
    out = pd.concat(frames, ignore_index=True)[
        ["index_code", "index_name", "trade_date", "open", "high", "low", "close", "pre_close", "volume", "amount"]
    ].rename(columns={"pre_close": "prev_close"})
    out = out.sort_values("index_code").reset_index(drop=True)
    path = _inbox_file("market_index_daily", effective_trade_date, ".csv")
    artifact = _write_csv(path, out)
    artifact.notes.append("source=tushare.index_daily")
    return artifact


def _fetch_recent_equity_history(pro, trade_date: str, lookback_open_days: int = 10) -> pd.DataFrame:
    trade_dates = load_open_trade_dates(
        pro,
        start_date=(pd.Timestamp(trade_date) - pd.Timedelta(days=40)).strftime("%Y%m%d"),
        end_date=trade_date,
    )
    selected = trade_dates[-lookback_open_days:]
    frames: list[pd.DataFrame] = []
    for current_date in selected:
        daily = call_with_retry(lambda d=current_date: pro.daily(trade_date=d), sleep_seconds=8)
        if daily is None or daily.empty:
            continue
        work = _normalize_stock_code(daily, "ts_code")
        work = work[work["stock_code"].map(_is_main_board)].copy()
        work["trade_date"] = work["trade_date"].astype(str)
        work["stock_type"] = work["stock_code"].map(_stock_type)
        limits = work.apply(
            lambda row: _calc_limit(float(row["pre_close"]) if pd.notna(row["pre_close"]) else 0.0, row["stock_type"]),
            axis=1,
            result_type="expand",
        )
        work["limit_up_price"] = limits[0]
        work["limit_down_price"] = limits[1]
        work["amount"] = pd.to_numeric(work["amount"], errors="coerce").fillna(0.0) * 1000.0
        frames.append(work)
    if not frames:
        raise RuntimeError("No recent equity history could be fetched for breadth calculation")
    return pd.concat(frames, ignore_index=True)


def _derive_max_board_height(history: pd.DataFrame, trade_date: str) -> int:
    if history.empty:
        return 0
    work = history.copy()
    work["is_limit_up"] = (
        pd.to_numeric(work["close"], errors="coerce").fillna(0.0)
        >= pd.to_numeric(work["limit_up_price"], errors="coerce").fillna(float("inf")) * 0.995
    )
    work = work.sort_values(["stock_code", "trade_date"])
    max_height = 0
    for _, group in work.groupby("stock_code"):
        streak = 0
        for row in group.itertuples(index=False):
            if getattr(row, "trade_date") > trade_date:
                continue
            if bool(getattr(row, "is_limit_up")):
                streak += 1
            else:
                streak = 0
            if getattr(row, "trade_date") == trade_date:
                max_height = max(max_height, streak)
    return int(max_height)


def collect_market_breadth_and_limit_structure(trade_date: str) -> CollectionArtifact:
    pro = load_pro_client()
    effective_trade_date = latest_open_trade_date(pro, normalize_trade_date_str(trade_date))
    work = _fetch_daily_and_basic_for_trade_date(pro, effective_trade_date)
    close = pd.to_numeric(work["close"], errors="coerce")
    prev_close = pd.to_numeric(work["pre_close"], errors="coerce")
    high = pd.to_numeric(work["high"], errors="coerce")
    limit_up = pd.to_numeric(work["limit_up_price"], errors="coerce")
    limit_down = pd.to_numeric(work["limit_down_price"], errors="coerce")
    total_mv = pd.to_numeric(work.get("total_mv"), errors="coerce")

    history = _fetch_recent_equity_history(pro, effective_trade_date, lookback_open_days=10)
    payload = {
        "trade_date": effective_trade_date,
        "up_count": int((close > prev_close).sum()),
        "down_count": int((close < prev_close).sum()),
        "flat_count": int((close == prev_close).sum()),
        "limit_up_count": int((close >= limit_up * 0.995).sum()),
        "limit_down_count": int((close <= limit_down * 1.005).sum()),
        "broken_limit_up_count": int(((high >= limit_up * 0.995) & (close < limit_up * 0.995)).sum()),
        "max_board_height": _derive_max_board_height(history, effective_trade_date),
        "total_turnover": float(pd.to_numeric(work["amount"], errors="coerce").fillna(0.0).sum()),
        "small_cap_turnover": float(pd.to_numeric(work.loc[total_mv < 1500000, "amount"], errors="coerce").fillna(0.0).sum()),
        "large_cap_turnover": float(pd.to_numeric(work.loc[total_mv >= 1500000, "amount"], errors="coerce").fillna(0.0).sum()),
    }
    path = _inbox_file("market_breadth_and_limit_structure", effective_trade_date, ".json")
    artifact = _write_json_records(path, [payload])
    artifact.notes.extend(["source=derived_from_tushare.daily", "uses_recent_history_for_board_height"])
    return artifact


def collect_company_announcements_structured(trade_date: str, lookback_days: int = 7) -> CollectionArtifact:
    pro = load_pro_client()
    effective_trade_date = latest_open_trade_date(pro, normalize_trade_date_str(trade_date))
    start_date = (pd.Timestamp(effective_trade_date) - pd.Timedelta(days=lookback_days)).strftime("%Y%m%d")

    records: list[dict] = []
    repurchase = call_with_retry(lambda: pro.repurchase(start_date=start_date, end_date=effective_trade_date), sleep_seconds=10)
    if repurchase is not None and not repurchase.empty:
        repurchase = _normalize_stock_code(repurchase, "ts_code")
        for row in repurchase.itertuples(index=False):
            records.append(
                {
                    "stock_code": getattr(row, "stock_code"),
                    "filing_type": "share_repurchase",
                    "title": _format_repurchase_title(getattr(row, "proc", "")),
                    "publish_time": str(getattr(row, "ann_date", "")),
                    "summary_text": _format_repurchase_summary(getattr(row, "amount", None), getattr(row, "vol", None)),
                }
            )

    holder_frames: list[pd.DataFrame] = []
    for trade_type, filing_type in (("IN", "share_increase"), ("DE", "share_reduction")):
        df = call_with_retry(
            lambda t=trade_type: pro.stk_holdertrade(start_date=start_date, end_date=effective_trade_date, trade_type=t),
            sleep_seconds=10,
        )
        if df is not None and not df.empty:
            normalized = _normalize_stock_code(df, "ts_code")
            normalized["__filing_type"] = filing_type
            holder_frames.append(normalized)
    if holder_frames:
        holdertrade = pd.concat(holder_frames, ignore_index=True)
        for record in holdertrade.to_dict(orient="records"):
            records.append(
                {
                    "stock_code": str(record.get("stock_code", "")).upper(),
                    "filing_type": str(record.get("__filing_type", "")),
                    "title": _format_holdertrade_title(str(record.get("__filing_type", ""))),
                    "publish_time": str(record.get("ann_date", "")),
                    "summary_text": _format_holdertrade_summary(record),
                }
            )

    path = _inbox_file("company_announcements_structured", effective_trade_date, ".json")
    artifact = _write_json_records(path, records)
    artifact.notes.extend(["source=tushare.repurchase", "source=tushare.stk_holdertrade"])
    return artifact


def collect_dragon_tiger_board(trade_date: str) -> CollectionArtifact:
    pro = load_pro_client()
    effective_trade_date = latest_open_trade_date(pro, normalize_trade_date_str(trade_date))
    raw = call_with_retry(lambda: pro.top_list(trade_date=effective_trade_date), sleep_seconds=10)
    if raw is None or raw.empty:
        raise RuntimeError(f"top_list returned empty result set for {effective_trade_date}")
    work = _normalize_stock_code(raw, "ts_code")
    work["trade_date"] = effective_trade_date
    path = _inbox_file("dragon_tiger_board", effective_trade_date, ".csv")
    artifact = _write_csv(path, work)
    artifact.notes.append("source=tushare.top_list")
    return artifact


def collect_northbound_and_margin_flow(trade_date: str) -> CollectionArtifact:
    pro = load_pro_client()
    effective_trade_date = latest_open_trade_date(pro, normalize_trade_date_str(trade_date))
    recent_trade_dates = load_open_trade_dates(
        pro,
        start_date=(pd.Timestamp(effective_trade_date) - pd.Timedelta(days=20)).strftime("%Y%m%d"),
        end_date=effective_trade_date,
    )[-5:]
    recent_trade_dates = list(reversed(recent_trade_dates))

    frames: list[pd.DataFrame] = []
    margin_trade_date = ""
    hk_hold_trade_date = ""

    for current_date in recent_trade_dates:
        margin = call_with_retry(lambda d=current_date: pro.margin_detail(trade_date=d), sleep_seconds=10)
        if margin is not None and not margin.empty:
            margin = _normalize_stock_code(margin, "ts_code")
            margin["trade_date"] = current_date
            margin["capital_signal_type"] = "margin_detail"
            margin["net_amount"] = pd.to_numeric(margin.get("rzmre"), errors="coerce").fillna(0.0) * 1000.0
            frames.append(margin[["stock_code", "trade_date", "capital_signal_type", "net_amount", "rzye", "rqye", "rzmre", "rqmcl"]])
            margin_trade_date = current_date
            break

    for current_date in recent_trade_dates:
        hk_hold = call_with_retry(lambda d=current_date: pro.hk_hold(trade_date=d), sleep_seconds=10)
        if hk_hold is not None and not hk_hold.empty:
            hk_hold = _normalize_stock_code(hk_hold, "ts_code")
            hk_hold["trade_date"] = current_date
            hk_hold["capital_signal_type"] = "hk_hold"
            hk_hold["net_amount"] = pd.to_numeric(hk_hold.get("ratio"), errors="coerce").fillna(0.0)
            frames.append(hk_hold[["stock_code", "trade_date", "capital_signal_type", "net_amount", "vol", "ratio", "exchange"]])
            hk_hold_trade_date = current_date
            break

    if not frames:
        raise RuntimeError(f"margin_detail and hk_hold both returned empty result set near {effective_trade_date}")
    out = pd.concat(frames, ignore_index=True).sort_values(["capital_signal_type", "stock_code"]).reset_index(drop=True)
    path = _inbox_file("northbound_and_margin_flow", effective_trade_date, ".csv")
    artifact = _write_csv(path, out)
    artifact.notes.extend(
        [
            "source=tushare.margin_detail",
            "source=tushare.hk_hold",
            f"margin_trade_date={margin_trade_date or 'none'}",
            f"hk_hold_trade_date={hk_hold_trade_date or 'none'}",
        ]
    )
    return artifact


def collect_block_trade_and_abnormal_volume(trade_date: str) -> CollectionArtifact:
    pro = load_pro_client()
    effective_trade_date = latest_open_trade_date(pro, normalize_trade_date_str(trade_date))
    block_trade = call_with_retry(
        lambda: pro.block_trade(
            start_date=(pd.Timestamp(effective_trade_date) - pd.Timedelta(days=1)).strftime("%Y%m%d"),
            end_date=effective_trade_date,
        ),
        sleep_seconds=10,
    )
    if block_trade is None or block_trade.empty:
        raise RuntimeError(f"block_trade returned empty result set for {effective_trade_date}")

    market_daily = _fetch_daily_and_basic_for_trade_date(pro, effective_trade_date)
    history = _fetch_recent_equity_history(pro, effective_trade_date, lookback_open_days=6)
    avg_volume = (
        history.groupby("stock_code", as_index=False)["vol"]
        .mean()
        .rename(columns={"vol": "avg_recent_vol"})
    )

    work = _normalize_stock_code(block_trade, "ts_code")
    work["trade_date"] = pd.to_datetime(work["trade_date"], errors="coerce").dt.strftime("%Y%m%d")
    work["trade_date"] = work["trade_date"].fillna(effective_trade_date)
    work = work.merge(
        market_daily[["stock_code", "volume", "close"]].rename(columns={"volume": "daily_volume", "close": "close_price"}),
        on="stock_code",
        how="left",
    )
    work = work.merge(avg_volume, on="stock_code", how="left")
    work["amount"] = pd.to_numeric(work.get("amount"), errors="coerce").fillna(0.0) * 1000.0
    work["abnormal_volume_ratio"] = (
        pd.to_numeric(work["daily_volume"], errors="coerce").fillna(0.0)
        / pd.to_numeric(work["avg_recent_vol"], errors="coerce").replace(0.0, pd.NA)
    ).fillna(0.0)
    work["premium_pct"] = (
        pd.to_numeric(work.get("price"), errors="coerce").fillna(0.0)
        / pd.to_numeric(work["close_price"], errors="coerce").replace(0.0, pd.NA)
        - 1.0
    ).fillna(0.0) * 100.0
    path = _inbox_file("block_trade_and_abnormal_volume", effective_trade_date, ".csv")
    artifact = _write_csv(path, work)
    artifact.notes.append("source=tushare.block_trade")
    return artifact


def collect_all_tushare_supported_sources(trade_date: str) -> tuple[list[CollectionArtifact], list[str]]:
    normalized_trade_date = normalize_trade_date_str(trade_date)
    artifacts: list[CollectionArtifact] = []
    warnings: list[str] = []
    for source_id, collector, required in TUSHARE_SOURCE_SPECS:
        try:
            artifacts.append(collector(normalized_trade_date))
        except Exception as exc:
            if required:
                raise
            warnings.append(f"{source_id} skipped: {exc}")
    return artifacts, warnings


TUSHARE_SOURCE_SPECS: tuple[tuple[str, object, bool], ...] = (
    ("equity_reference_master", collect_equity_reference_master, True),
    ("market_equity_daily", collect_market_equity_daily, True),
    ("market_index_daily", collect_market_index_daily, True),
    ("market_breadth_and_limit_structure", collect_market_breadth_and_limit_structure, True),
    ("company_announcements_structured", collect_company_announcements_structured, False),
    ("dragon_tiger_board", collect_dragon_tiger_board, False),
    ("northbound_and_margin_flow", collect_northbound_and_margin_flow, False),
    ("block_trade_and_abnormal_volume", collect_block_trade_and_abnormal_volume, False),
)
