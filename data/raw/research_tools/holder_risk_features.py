from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .external_tushare_features import add_external_tushare_features


ROOT = Path(r"D:\TradingMain")
REFERENCE_DIR = ROOT / "research" / "reference" / "tushare" / "holder_risk"


def zscore_by_date(df: pd.DataFrame, column: str) -> pd.Series:
    grouped = df.groupby("trade_date")[column]
    mean = grouped.transform("mean")
    std = grouped.transform("std").replace(0.0, np.nan)
    return ((df[column] - mean) / std).replace([np.inf, -np.inf], np.nan)


def _load_table(name: str) -> pd.DataFrame:
    path = REFERENCE_DIR / f"{name}_daily_2020plus.parquet"
    if not path.exists():
        path = REFERENCE_DIR / f"{name}_weekly_2020plus.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing holder-risk dataset: {path}")
    df = pd.read_parquet(path)
    for col in ["ann_date", "end_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])
    if "stock_code" in df.columns:
        df["stock_code"] = df["stock_code"].astype(str).str.upper()
    return df


def _merge_recent_event(panel: pd.DataFrame, event_df: pd.DataFrame, event_date_col: str, value_cols: list[str], prefix: str) -> pd.DataFrame:
    left = panel[["stock_code", "trade_date"]].copy()
    left["trade_date"] = pd.to_datetime(left["trade_date"]).astype("datetime64[ns]")
    right = event_df[["stock_code", event_date_col] + value_cols].copy()
    right[event_date_col] = pd.to_datetime(right[event_date_col]).astype("datetime64[ns]")

    merged = pd.merge_asof(
        left.sort_values(["trade_date", "stock_code"]),
        right.sort_values([event_date_col, "stock_code"]),
        left_on="trade_date",
        right_on=event_date_col,
        by="stock_code",
        direction="backward",
    )
    merged = merged.rename(columns={event_date_col: f"{prefix}_{event_date_col}"})
    merged = merged.rename(columns={col: f"{prefix}_{col}" for col in value_cols})
    return merged


def add_holder_risk_features(panel: pd.DataFrame) -> pd.DataFrame:
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

    holder = _load_table("holdernumber")
    holder["holder_num"] = pd.to_numeric(holder["holder_num"], errors="coerce")
    holder = holder.sort_values(["stock_code", "ann_date", "end_date"]).copy()
    holder["prev_holder_num"] = holder.groupby("stock_code")["holder_num"].shift(1)
    holder["holder_change_ratio"] = holder["holder_num"] / holder["prev_holder_num"].replace(0.0, np.nan) - 1.0
    holder_daily = holder.groupby(["stock_code", "ann_date"], as_index=False).agg(
        hn_holder_num=("holder_num", "last"),
        hn_holder_change_ratio=("holder_change_ratio", "last"),
    )
    hn_recent = _merge_recent_event(df, holder_daily, "ann_date", ["hn_holder_num", "hn_holder_change_ratio"], "hn")
    df = df.merge(hn_recent, on=["stock_code", "trade_date"], how="left")
    df["hn_event_age"] = (df["trade_date"] - df["hn_ann_date"]).dt.days

    pledge = _load_table("pledge_stat")
    for col in ["pledge_count", "unrest_pledge", "rest_pledge", "total_share", "pledge_ratio"]:
        if col in pledge.columns:
            pledge[col] = pd.to_numeric(pledge[col], errors="coerce")
    pledge = pledge.sort_values(["stock_code", "end_date"]).copy()
    pledge["prev_pledge_ratio"] = pledge.groupby("stock_code")["pledge_ratio"].shift(1)
    pledge["pledge_ratio_change"] = pledge["pledge_ratio"] - pledge["prev_pledge_ratio"]
    pledge_weekly = pledge.groupby(["stock_code", "end_date"], as_index=False).agg(
        pr_pledge_ratio=("pledge_ratio", "last"),
        pr_pledge_count=("pledge_count", "last"),
        pr_pledge_ratio_change=("pledge_ratio_change", "last"),
    )
    pr_recent = _merge_recent_event(df, pledge_weekly, "end_date", ["pr_pledge_ratio", "pr_pledge_count", "pr_pledge_ratio_change"], "pr")
    df = df.merge(pr_recent, on=["stock_code", "trade_date"], how="left")
    df["pr_event_age"] = (df["trade_date"] - df["pr_end_date"]).dt.days

    numeric_cols = [
        "hn_hn_holder_num",
        "hn_hn_holder_change_ratio",
        "pr_pr_pledge_ratio",
        "pr_pr_pledge_count",
        "pr_pr_pledge_ratio_change",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df[f"{col}_z"] = zscore_by_date(df, col)

    recent_hn = df["hn_event_age"].fillna(9999).between(0, 120)
    recent_pr = df["pr_event_age"].fillna(9999).between(0, 21)

    concentration = -df["hn_hn_holder_change_ratio_z"].fillna(0.0)
    df["hn801_holder_concentration_improving"] = np.where(
        recent_hn & (df["hn_hn_holder_change_ratio"].fillna(999.0) < 0.0),
        0.35 * concentration + 0.25 * lowcrowd + 0.20 * value + 0.20 * industry20,
        np.nan,
    )
    df["hn802_holder_expansion_repair"] = np.where(
        recent_hn & (df["hn_hn_holder_change_ratio"].fillna(-999.0) > 0.0),
        0.30 * df["hn_hn_holder_change_ratio_z"].fillna(0.0) + 0.25 * reversal + 0.20 * value + 0.15 * lowcrowd + 0.10 * lowvol,
        np.nan,
    )
    df["hn803_concentration_strong_industry"] = np.where(
        recent_hn & (df["hn_hn_holder_change_ratio"].fillna(999.0) < 0.0) & (df["industry_ret_20_rank"].fillna(0.0) >= 0.65),
        0.35 * concentration + 0.25 * industry20 + 0.20 * lowcrowd + 0.20 * breakout,
        np.nan,
    )
    df["hn804_low_holder_growth_lowvol"] = np.where(
        recent_hn & (df["hn_hn_holder_change_ratio"].fillna(999.0) <= 0.05),
        0.30 * concentration + 0.25 * lowvol + 0.20 * midcap + 0.15 * value + 0.10 * close_pos,
        np.nan,
    )
    df["hn805_extreme_holder_decline_breakout"] = np.where(
        recent_hn & (df["hn_hn_holder_change_ratio"].fillna(999.0) <= -0.15),
        0.30 * concentration + 0.25 * breakout + 0.20 * amount_ratio + 0.15 * close_pos + 0.10 * lowcrowd,
        np.nan,
    )
    df["hn806_concentration_midcap_value"] = np.where(
        recent_hn & (df["hn_hn_holder_change_ratio"].fillna(999.0) < 0.0),
        0.30 * concentration + 0.25 * midcap + 0.20 * value + 0.15 * lowcrowd + 0.10 * reversal,
        np.nan,
    )

    low_pledge = -df["pr_pr_pledge_ratio_z"].fillna(0.0)
    falling_pledge = -df["pr_pr_pledge_ratio_change_z"].fillna(0.0)
    df["pr901_low_pledge_value_repair"] = np.where(
        recent_pr,
        0.35 * low_pledge + 0.25 * value + 0.20 * reversal + 0.20 * lowcrowd,
        np.nan,
    )
    df["pr902_falling_pledge_relief"] = np.where(
        recent_pr & (df["pr_pr_pledge_ratio_change"].fillna(999.0) < 0.0),
        0.35 * falling_pledge + 0.25 * reversal + 0.20 * value + 0.20 * lowcrowd,
        np.nan,
    )
    df["pr903_zero_pledge_midcap_quality"] = np.where(
        recent_pr & (df["pr_pr_pledge_ratio"].fillna(999.0) <= 1.0),
        0.30 * low_pledge + 0.25 * midcap + 0.20 * lowvol + 0.15 * value + 0.10 * industry20,
        np.nan,
    )
    df["pr904_high_pledge_overreaction_repair"] = np.where(
        recent_pr & (df["pr_pr_pledge_ratio"].fillna(-999.0) >= 15.0),
        0.30 * df["pr_pr_pledge_ratio_z"].fillna(0.0) + 0.25 * reversal + 0.20 * value + 0.15 * lowcrowd + 0.10 * breakout,
        np.nan,
    )
    df["pr905_pledge_relief_breakout"] = np.where(
        recent_pr & (df["pr_pr_pledge_ratio_change"].fillna(999.0) < 0.0),
        0.30 * falling_pledge + 0.25 * breakout + 0.20 * amount_ratio + 0.15 * close_pos + 0.10 * lowcrowd,
        np.nan,
    )
    df["pr906_low_pledge_strong_industry"] = np.where(
        recent_pr & (df["industry_ret_20_rank"].fillna(0.0) >= 0.65),
        0.30 * low_pledge + 0.25 * industry20 + 0.20 * lowcrowd + 0.15 * value + 0.10 * midcap,
        np.nan,
    )

    report = {
        "panel_rows": int(len(df)),
        "hn_recent_coverage": float(recent_hn.mean()),
        "pr_recent_coverage": float(recent_pr.mean()),
    }
    (REFERENCE_DIR / "feature_build_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return df
