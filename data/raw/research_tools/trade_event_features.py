from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .external_tushare_features import add_external_tushare_features


ROOT = Path(r"D:\TradingMain")
REFERENCE_DIR = ROOT / "research" / "reference" / "tushare" / "trade_event"


def zscore_by_date(df: pd.DataFrame, column: str) -> pd.Series:
    grouped = df.groupby("trade_date")[column]
    mean = grouped.transform("mean")
    std = grouped.transform("std").replace(0.0, np.nan)
    return ((df[column] - mean) / std).replace([np.inf, -np.inf], np.nan)


def _load_table(name: str) -> pd.DataFrame:
    path = REFERENCE_DIR / f"{name}_daily_2020plus.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing trade event dataset: {path}")
    df = pd.read_parquet(path)
    for col in ["trade_date", "float_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])
    if "stock_code" in df.columns:
        df["stock_code"] = df["stock_code"].astype(str).str.upper()
    return df


def _merge_recent_event(panel: pd.DataFrame, event_df: pd.DataFrame, value_cols: list[str], prefix: str) -> pd.DataFrame:
    left = panel[["stock_code", "trade_date"]].copy()
    left["trade_date"] = pd.to_datetime(left["trade_date"]).astype("datetime64[ns]")
    right = event_df[["stock_code", "trade_date"] + value_cols].copy()
    right["trade_date"] = pd.to_datetime(right["trade_date"]).astype("datetime64[ns]")
    pieces: list[pd.DataFrame] = []
    right = right.sort_values(["stock_code", "trade_date"])
    for stock_code, left_group in left.sort_values(["stock_code", "trade_date"]).groupby("stock_code", sort=False):
        right_group = right[right["stock_code"] == stock_code]
        if right_group.empty:
            merged_group = left_group.copy()
            for col in value_cols:
                merged_group[col] = np.nan
        else:
            merged_group = pd.merge_asof(
                left_group.sort_values("trade_date"),
                right_group.sort_values("trade_date"),
                on="trade_date",
                direction="backward",
                allow_exact_matches=True,
            )
        pieces.append(merged_group)
    merged = pd.concat(pieces, ignore_index=True)
    merged = merged.rename(columns={col: f"{prefix}_{col}" for col in value_cols})
    if f"{prefix}_trade_date" not in merged.columns:
        merged[f"{prefix}_trade_date"] = merged["trade_date"]
    return merged


def _merge_recent_event_with_date(
    panel: pd.DataFrame,
    event_df: pd.DataFrame,
    value_cols: list[str],
    prefix: str,
) -> pd.DataFrame:
    left = panel[["stock_code", "trade_date"]].copy()
    left["trade_date"] = pd.to_datetime(left["trade_date"]).astype("datetime64[ns]")
    right = event_df[["stock_code", "event_trade_date"] + value_cols].copy()
    right["event_trade_date"] = pd.to_datetime(right["event_trade_date"]).astype("datetime64[ns]")
    pieces: list[pd.DataFrame] = []
    right = right.sort_values(["stock_code", "event_trade_date"])
    for stock_code, left_group in left.sort_values(["stock_code", "trade_date"]).groupby("stock_code", sort=False):
        right_group = right[right["stock_code"] == stock_code]
        if right_group.empty:
            merged_group = left_group.copy()
            merged_group["event_trade_date"] = pd.NaT
            for col in value_cols:
                merged_group[col] = np.nan
        else:
            merged_group = pd.merge_asof(
                left_group.sort_values("trade_date"),
                right_group.sort_values("event_trade_date"),
                left_on="trade_date",
                right_on="event_trade_date",
                direction="backward",
                allow_exact_matches=True,
            )
        pieces.append(merged_group)
    merged = pd.concat(pieces, ignore_index=True)
    merged = merged.rename(columns={col: f"{prefix}_{col}" for col in value_cols})
    merged = merged.rename(columns={"event_trade_date": f"{prefix}_event_trade_date"})
    return merged


def _merge_recent_event_by_row(
    panel_keys: pd.DataFrame,
    event_df: pd.DataFrame,
    value_cols: list[str],
    prefix: str,
) -> pd.DataFrame:
    left = panel_keys[["row_id", "stock_code", "trade_date"]].copy()
    left["trade_date"] = pd.to_datetime(left["trade_date"]).astype("datetime64[ns]")
    right = event_df[["stock_code", "event_trade_date"] + value_cols].copy()
    right["event_trade_date"] = pd.to_datetime(right["event_trade_date"]).astype("datetime64[ns]")
    pieces: list[pd.DataFrame] = []
    right = right.sort_values(["stock_code", "event_trade_date"])
    for stock_code, left_group in left.sort_values(["stock_code", "trade_date"]).groupby("stock_code", sort=False):
        right_group = right[right["stock_code"] == stock_code]
        if right_group.empty:
            merged_group = left_group.copy()
            merged_group["event_trade_date"] = pd.NaT
            for col in value_cols:
                merged_group[col] = np.nan
        else:
            merged_group = pd.merge_asof(
                left_group.sort_values("trade_date"),
                right_group.sort_values("event_trade_date"),
                left_on="trade_date",
                right_on="event_trade_date",
                direction="backward",
                allow_exact_matches=True,
            )
        pieces.append(merged_group)
    merged = pd.concat(pieces, ignore_index=True)
    merged = merged.rename(columns={col: f"{prefix}_{col}" for col in value_cols})
    merged = merged.rename(columns={"event_trade_date": f"{prefix}_event_trade_date"})
    return merged


def add_trade_event_features(panel: pd.DataFrame) -> pd.DataFrame:
    df = add_external_tushare_features(panel.copy())
    lowvol = -df["volatility_20_z"].fillna(0.0)
    lowcrowd = -df["volume_ma20_gap_z"].fillna(0.0)
    value = df["bp_z"].fillna(0.0)
    reversal = df["short_reversal_5_z"].fillna(0.0)
    breakout = df["breakout_retest_score_z"].fillna(0.0)
    close_pos = df["close_range_pos_z"].fillna(0.0)
    midcap = df["mid_size_score_z"].fillna(0.0)
    industry20 = df["industry_ret_20_z"].fillna(0.0)
    amount_ratio = df["amount_ratio_5_20_z"].fillna(0.0)

    top_list = _load_table("toplist")
    for col in ["turnover_rate", "amount", "l_buy", "l_sell", "net_amount", "net_rate", "amount_rate", "float_values"]:
        if col in top_list.columns:
            top_list[col] = pd.to_numeric(top_list[col], errors="coerce")
    top_list["reason_count"] = 1.0
    top_list["net_amount_ratio"] = top_list.get("net_amount", pd.Series(index=top_list.index, dtype=float)) / top_list.get("float_values", pd.Series(index=top_list.index, dtype=float)).replace(0.0, np.nan)
    top_list_daily = top_list.groupby(["stock_code", "trade_date"], as_index=False).agg(
        toplist_turnover_rate=("turnover_rate", "max"),
        toplist_amount=("amount", "sum"),
        toplist_net_amount=("net_amount", "sum"),
        toplist_net_rate=("net_rate", "mean"),
        toplist_amount_rate=("amount_rate", "max"),
        toplist_net_amount_ratio=("net_amount_ratio", "mean"),
        toplist_reason_count=("reason_count", "sum"),
    )
    top_recent = _merge_recent_event_with_date(
        df,
        top_list_daily.rename(columns={"trade_date": "event_trade_date"}),
        [
            "toplist_turnover_rate",
            "toplist_amount",
            "toplist_net_amount",
            "toplist_net_rate",
            "toplist_amount_rate",
            "toplist_net_amount_ratio",
            "toplist_reason_count",
        ],
        "toplist",
    )
    df = df.merge(top_recent, on=["stock_code", "trade_date"], how="left")
    df["toplist_event_age"] = (df["trade_date"] - df["toplist_event_trade_date"]).dt.days

    block_trade = _load_table("block_trade")
    for col in ["price", "vol", "amount"]:
        if col in block_trade.columns:
            block_trade[col] = pd.to_numeric(block_trade[col], errors="coerce")
    block_trade["trade_count"] = 1.0
    amount_col = block_trade.get("amount", pd.Series(index=block_trade.index, dtype=float))
    price_col = block_trade.get("price", pd.Series(index=block_trade.index, dtype=float))
    block_trade["price_amount"] = price_col * amount_col
    block_daily = block_trade.groupby(["stock_code", "trade_date"], as_index=False).agg(
        block_amount=("amount", "sum"),
        block_vol=("vol", "sum"),
        block_trade_count=("trade_count", "sum"),
        block_price_amount=("price_amount", "sum"),
    )
    block_daily["block_avg_price"] = block_daily["block_price_amount"] / block_daily["block_amount"].replace(0.0, np.nan)
    event_close = df[["stock_code", "trade_date", "close", "amount_k"]].drop_duplicates().rename(
        columns={"trade_date": "event_trade_date", "close": "event_close", "amount_k": "event_amount_k"}
    )
    block_daily = block_daily.rename(columns={"trade_date": "event_trade_date"}).merge(event_close, on=["stock_code", "event_trade_date"], how="left")
    block_daily["block_discount"] = block_daily["block_avg_price"] / block_daily["event_close"].replace(0.0, np.nan) - 1.0
    block_daily["block_liquidity_share"] = block_daily["block_amount"] / block_daily["event_amount_k"].replace(0.0, np.nan)
    block_recent = _merge_recent_event_with_date(
        df,
        block_daily,
        [
            "block_amount",
            "block_vol",
            "block_trade_count",
            "block_avg_price",
            "block_discount",
            "block_liquidity_share",
        ],
        "block",
    )
    df = df.merge(block_recent, on=["stock_code", "trade_date"], how="left")
    df["block_event_age"] = (df["trade_date"] - df["block_event_trade_date"]).dt.days

    numeric_cols = [
        "toplist_toplist_turnover_rate",
        "toplist_toplist_amount",
        "toplist_toplist_net_amount",
        "toplist_toplist_net_rate",
        "toplist_toplist_amount_rate",
        "toplist_toplist_net_amount_ratio",
        "toplist_toplist_reason_count",
        "block_block_amount",
        "block_block_vol",
        "block_block_trade_count",
        "block_block_avg_price",
        "block_block_discount",
        "block_block_liquidity_share",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df[f"{col}_z"] = zscore_by_date(df, col)

    recent_top = df["toplist_event_age"].fillna(9999).between(0, 8)
    fresh_top = df["toplist_event_age"].fillna(9999).between(0, 3)
    recent_block = df["block_event_age"].fillna(9999).between(0, 8)
    fresh_block = df["block_event_age"].fillna(9999).between(0, 3)

    df["tl401_netbuy_lowcrowding"] = np.where(
        recent_top & (df["toplist_toplist_net_rate"].fillna(-999.0) > 0.0),
        0.40 * df["toplist_toplist_net_rate_z"].fillna(0.0) + 0.20 * lowcrowd + 0.20 * reversal + 0.20 * value,
        np.nan,
    )
    df["tl402_high_attention_follow"] = np.where(
        fresh_top,
        0.35 * df["toplist_toplist_amount_rate_z"].fillna(0.0)
        + 0.25 * df["toplist_toplist_net_rate_z"].fillna(0.0)
        + 0.20 * close_pos
        + 0.20 * breakout,
        np.nan,
    )
    df["tl403_negative_exhaustion_repair"] = np.where(
        fresh_top & (df["toplist_toplist_net_rate"].fillna(999.0) < 0.0),
        0.35 * (-df["toplist_toplist_net_rate_z"].fillna(0.0)) + 0.25 * reversal + 0.20 * value + 0.20 * lowcrowd,
        np.nan,
    )
    df["tl404_repeat_heat_not_crowded"] = np.where(
        recent_top,
        0.30 * df["toplist_toplist_reason_count_z"].fillna(0.0)
        + 0.25 * df["toplist_toplist_amount_rate_z"].fillna(0.0)
        + 0.25 * lowcrowd
        + 0.20 * midcap,
        np.nan,
    )
    df["tl405_strong_industry_toplist"] = np.where(
        recent_top & (df["industry_ret_20_rank"].fillna(0.0) >= 0.65) & (df["toplist_toplist_net_rate"].fillna(-999.0) > 0.0),
        0.35 * df["toplist_toplist_net_rate_z"].fillna(0.0) + 0.25 * industry20 + 0.20 * close_pos + 0.20 * breakout,
        np.nan,
    )
    df["tl406_large_netamount_midcap"] = np.where(
        recent_top & (df["toplist_toplist_net_amount_ratio"].fillna(-999.0) > 0.0),
        0.35 * df["toplist_toplist_net_amount_ratio_z"].fillna(0.0) + 0.25 * midcap + 0.20 * value + 0.20 * lowcrowd,
        np.nan,
    )

    df["bt501_discount_repair_lowcrowding"] = np.where(
        recent_block & (df["block_block_discount"].fillna(999.0) < 0.0),
        0.40 * (-df["block_block_discount_z"].fillna(0.0)) + 0.25 * reversal + 0.20 * lowcrowd + 0.15 * value,
        np.nan,
    )
    df["bt502_premium_follow_breakout"] = np.where(
        recent_block & (df["block_block_discount"].fillna(-999.0) > 0.0),
        0.35 * df["block_block_discount_z"].fillna(0.0) + 0.25 * breakout + 0.20 * close_pos + 0.20 * amount_ratio,
        np.nan,
    )
    df["bt503_large_block_absorption"] = np.where(
        fresh_block,
        0.35 * df["block_block_liquidity_share_z"].fillna(0.0) + 0.25 * lowcrowd + 0.20 * reversal + 0.20 * value,
        np.nan,
    )
    df["bt504_discount_strong_industry"] = np.where(
        recent_block & (df["block_block_discount"].fillna(999.0) < 0.0) & (df["industry_ret_20_rank"].fillna(0.0) >= 0.65),
        0.35 * (-df["block_block_discount_z"].fillna(0.0)) + 0.25 * industry20 + 0.20 * lowcrowd + 0.20 * value,
        np.nan,
    )
    df["bt505_premium_midcap_strength"] = np.where(
        recent_block & (df["block_block_discount"].fillna(-999.0) > 0.0),
        0.30 * df["block_block_discount_z"].fillna(0.0) + 0.20 * midcap + 0.20 * close_pos + 0.15 * industry20 + 0.15 * amount_ratio,
        np.nan,
    )
    df["bt506_large_discount_turnaround"] = np.where(
        fresh_block & (df["block_block_discount"].fillna(999.0) <= -0.03),
        0.40 * (-df["block_block_discount_z"].fillna(0.0)) + 0.20 * reversal + 0.20 * close_pos + 0.20 * lowvol,
        np.nan,
    )

    unlock_base = df[
        [
            "stock_code",
            "trade_date",
            "industry_ret_20_rank",
            "industry_ret_20_z",
            "volatility_20_z",
            "volume_ma20_gap_z",
            "bp_z",
            "short_reversal_5_z",
            "breakout_retest_score_z",
            "close_range_pos_z",
            "mid_size_score_z",
            "amount_ratio_5_20_z",
        ]
    ].copy()
    unlock_base["row_id"] = np.arange(len(unlock_base))
    share_float = _load_table("share_float")
    for col in ["float_share", "float_ratio"]:
        if col in share_float.columns:
            share_float[col] = pd.to_numeric(share_float[col], errors="coerce")
    share_float_daily = share_float.rename(columns={"float_date": "event_trade_date"}).copy()
    share_float_daily["unlock_count"] = 1.0
    share_float_recent = _merge_recent_event_by_row(
        unlock_base[["row_id", "stock_code", "trade_date"]],
        share_float_daily,
        ["float_share", "float_ratio", "unlock_count"],
        "unlock",
    )
    unlock_df = share_float_recent.merge(
        unlock_base.drop(columns=["stock_code", "trade_date"]),
        on="row_id",
        how="left",
    )
    unlock_df["unlock_event_age"] = (unlock_df["trade_date"] - unlock_df["unlock_event_trade_date"]).dt.days
    for col in ["unlock_float_share", "unlock_float_ratio", "unlock_unlock_count"]:
        unlock_df[col] = pd.to_numeric(unlock_df[col], errors="coerce")
        unlock_df[f"{col}_z"] = zscore_by_date(unlock_df, col)
    recent_unlock = unlock_df["unlock_event_age"].fillna(9999).between(0, 8)
    fresh_unlock = unlock_df["unlock_event_age"].fillna(9999).between(0, 3)
    unlock_lowvol = -unlock_df["volatility_20_z"].fillna(0.0)
    unlock_lowcrowd = -unlock_df["volume_ma20_gap_z"].fillna(0.0)
    unlock_value = unlock_df["bp_z"].fillna(0.0)
    unlock_reversal = unlock_df["short_reversal_5_z"].fillna(0.0)
    unlock_breakout = unlock_df["breakout_retest_score_z"].fillna(0.0)
    unlock_close_pos = unlock_df["close_range_pos_z"].fillna(0.0)
    unlock_midcap = unlock_df["mid_size_score_z"].fillna(0.0)
    unlock_amount_ratio = unlock_df["amount_ratio_5_20_z"].fillna(0.0)
    unlock_industry20 = unlock_df["industry_ret_20_z"].fillna(0.0)
    unlock_df["sf601_small_unlock_absorbed"] = np.where(
        recent_unlock & (unlock_df["unlock_float_ratio"].fillna(999.0) <= 5.0),
        0.35 * (-unlock_df["unlock_float_ratio_z"].fillna(0.0)) + 0.25 * unlock_lowcrowd + 0.20 * unlock_value + 0.20 * unlock_reversal,
        np.nan,
    )
    unlock_df["sf602_large_unlock_overreaction_repair"] = np.where(
        fresh_unlock & (unlock_df["unlock_float_ratio"].fillna(-999.0) >= 10.0),
        0.35 * unlock_df["unlock_float_ratio_z"].fillna(0.0) + 0.25 * unlock_reversal + 0.20 * unlock_value + 0.20 * unlock_lowcrowd,
        np.nan,
    )
    unlock_df["sf603_small_unlock_strong_industry"] = np.where(
        recent_unlock & (unlock_df["unlock_float_ratio"].fillna(999.0) <= 5.0) & (unlock_df["industry_ret_20_rank"].fillna(0.0) >= 0.65),
        0.30 * (-unlock_df["unlock_float_ratio_z"].fillna(0.0)) + 0.25 * unlock_industry20 + 0.25 * unlock_lowcrowd + 0.20 * unlock_breakout,
        np.nan,
    )
    unlock_df["sf604_post_unlock_lowvol_carry"] = np.where(
        recent_unlock & (unlock_df["unlock_float_ratio"].fillna(999.0) <= 8.0),
        0.30 * (-unlock_df["unlock_float_ratio_z"].fillna(0.0)) + 0.30 * unlock_lowvol + 0.20 * unlock_value + 0.20 * unlock_midcap,
        np.nan,
    )
    unlock_df["sf605_tiny_unlock_breakout_follow"] = np.where(
        fresh_unlock & (unlock_df["unlock_float_ratio"].fillna(999.0) <= 3.0),
        0.30 * (-unlock_df["unlock_float_ratio_z"].fillna(0.0)) + 0.25 * unlock_breakout + 0.25 * unlock_close_pos + 0.20 * unlock_amount_ratio,
        np.nan,
    )
    unlock_df["sf606_unlock_cluster_absorption"] = np.where(
        recent_unlock,
        0.30 * (-unlock_df["unlock_float_ratio_z"].fillna(0.0)) + 0.25 * (-unlock_df["unlock_unlock_count_z"].fillna(0.0)) + 0.25 * unlock_lowcrowd + 0.20 * unlock_value,
        np.nan,
    )
    unlock_df = unlock_df.sort_values("row_id")
    for col in [
        "unlock_event_age",
        "sf601_small_unlock_absorbed",
        "sf602_large_unlock_overreaction_repair",
        "sf603_small_unlock_strong_industry",
        "sf604_post_unlock_lowvol_carry",
        "sf605_tiny_unlock_breakout_follow",
        "sf606_unlock_cluster_absorption",
    ]:
        df[col] = unlock_df[col].to_numpy()

    report = {
        "panel_rows": int(len(df)),
        "toplist_recent_coverage": float(recent_top.mean()),
        "block_recent_coverage": float(recent_block.mean()),
        "unlock_recent_coverage": float(recent_unlock.mean()),
    }
    (REFERENCE_DIR / "feature_build_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return df
