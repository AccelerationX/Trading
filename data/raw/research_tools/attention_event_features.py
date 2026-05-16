from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .external_tushare_features import add_external_tushare_features


ROOT = Path(r"D:\TradingMain")
REFERENCE_DIR = ROOT / "research" / "reference" / "tushare" / "attention_event"


def zscore_by_date(df: pd.DataFrame, column: str) -> pd.Series:
    grouped = df.groupby("trade_date")[column]
    mean = grouped.transform("mean")
    std = grouped.transform("std").replace(0.0, np.nan)
    return ((df[column] - mean) / std).replace([np.inf, -np.inf], np.nan)


def _load_table(name: str) -> pd.DataFrame:
    path = REFERENCE_DIR / f"{name}_daily_2020plus.parquet"
    if not path.exists():
        path = REFERENCE_DIR / f"{name}_monthly_2020plus.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing attention event dataset: {path}")
    df = pd.read_parquet(path)
    for col in ["report_date", "ann_date", "end_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])
    if "stock_code" in df.columns:
        df["stock_code"] = df["stock_code"].astype(str).str.upper()
    return df


def _merge_recent_event(
    panel: pd.DataFrame,
    event_df: pd.DataFrame,
    event_date_col: str,
    value_cols: list[str],
    prefix: str,
) -> pd.DataFrame:
    left = panel[["stock_code", "trade_date"]].copy()
    left["trade_date"] = pd.to_datetime(left["trade_date"]).astype("datetime64[ns]")
    event_df = event_df.sort_values(["stock_code", event_date_col]).reset_index(drop=True)
    event_groups = {code: grp for code, grp in event_df.groupby("stock_code", sort=False)}
    frames: list[pd.DataFrame] = []
    for stock_code, left_group in left.groupby("stock_code", sort=False):
        right_group = event_groups.get(stock_code)
        work_left = left_group.sort_values("trade_date").reset_index(drop=True)
        if right_group is None or right_group.empty:
            work_left[f"{prefix}_{event_date_col}"] = pd.NaT
            for col in value_cols:
                work_left[f"{prefix}_{col}"] = pd.NA
            frames.append(work_left)
            continue
        merged = pd.merge_asof(
            work_left,
            right_group[[event_date_col] + value_cols].sort_values(event_date_col),
            left_on="trade_date",
            right_on=event_date_col,
            direction="backward",
            allow_exact_matches=True,
        )
        merged = merged.rename(columns={event_date_col: f"{prefix}_{event_date_col}"})
        merged = merged.rename(columns={col: f"{prefix}_{col}" for col in value_cols})
        frames.append(merged)
    return pd.concat(frames, ignore_index=True) if frames else left


def add_attention_event_features(panel: pd.DataFrame) -> pd.DataFrame:
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

    event_close = df[["stock_code", "trade_date", "close"]].drop_duplicates().rename(columns={"trade_date": "report_date", "close": "event_close"})

    report_rc = _load_table("report_rc")
    for col in ["tp", "max_price", "min_price"]:
        if col in report_rc.columns:
            report_rc[col] = pd.to_numeric(report_rc[col], errors="coerce")
    report_rc["report_title"] = report_rc.get("report_title", "").astype(str)
    report_rc["classify"] = report_rc.get("classify", "").astype(str)
    report_rc["report_type"] = report_rc.get("report_type", "").astype(str)
    report_rc["rating"] = report_rc.get("rating", "").astype(str)
    report_rc = report_rc[report_rc["report_type"] != "非个股"].copy()
    report_rc["initiation_flag"] = report_rc["classify"].isin(["首次关注", "首份报告", "首次评级"]).astype(float)
    report_rc["deep_flag"] = report_rc["report_type"].isin(["深度"]).astype(float)
    report_rc["positive_flag"] = report_rc["rating"].isin(["买入", "增持", "推荐", "强烈推荐", "优于大市"]).astype(float)
    report_rc["target_price"] = report_rc["max_price"].fillna(report_rc["tp"])
    report_rc["report_count"] = 1.0
    report_rc = report_rc.drop_duplicates(subset=["stock_code", "report_date", "org_name", "report_title", "classify", "report_type"])
    report_rc = report_rc.merge(event_close, on=["stock_code", "report_date"], how="left")
    report_rc["target_premium"] = report_rc["target_price"] / report_rc["event_close"].replace(0.0, np.nan) - 1.0
    report_rc_daily = report_rc.groupby(["stock_code", "report_date"], as_index=False).agg(
        rc_report_count=("report_count", "sum"),
        rc_org_count=("org_name", "nunique"),
        rc_init_count=("initiation_flag", "sum"),
        rc_deep_count=("deep_flag", "sum"),
        rc_positive_count=("positive_flag", "sum"),
        rc_avg_target_premium=("target_premium", "mean"),
    )
    rc_recent = _merge_recent_event(
        df,
        report_rc_daily,
        "report_date",
        ["rc_report_count", "rc_org_count", "rc_init_count", "rc_deep_count", "rc_positive_count", "rc_avg_target_premium"],
        "rc",
    )
    df = df.merge(rc_recent, on=["stock_code", "trade_date"], how="left")
    df["rc_event_age"] = (df["trade_date"] - df["rc_report_date"]).dt.days

    broker = _load_table("broker_recommend")
    broker["month_end"] = pd.PeriodIndex(broker["month"].astype(str), freq="M").to_timestamp("M")
    broker["broker_count"] = 1.0
    broker_monthly = broker.groupby(["stock_code", "month_end"], as_index=False).agg(
        br_broker_count=("broker", "nunique"),
        br_recommend_count=("broker_count", "sum"),
    )
    br_recent = _merge_recent_event(df, broker_monthly.rename(columns={"month_end": "event_date"}), "event_date", ["br_broker_count", "br_recommend_count"], "br")
    df = df.merge(br_recent, on=["stock_code", "trade_date"], how="left")
    df["br_event_age"] = (df["trade_date"] - df["br_event_date"]).dt.days

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

    numeric_cols = [
        "rc_rc_report_count",
        "rc_rc_org_count",
        "rc_rc_init_count",
        "rc_rc_deep_count",
        "rc_rc_positive_count",
        "rc_rc_avg_target_premium",
        "br_br_broker_count",
        "br_br_recommend_count",
        "hn_hn_holder_num",
        "hn_hn_holder_change_ratio",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df[f"{col}_z"] = zscore_by_date(df, col)

    recent_rc = df["rc_event_age"].fillna(9999).between(0, 10)
    recent_br = df["br_event_age"].fillna(9999).between(0, 40)
    recent_hn = df["hn_event_age"].fillna(9999).between(0, 120)

    df["rc701_initiation_follow"] = np.where(
        recent_rc & (df["rc_rc_init_count"].fillna(0.0) > 0.0),
        0.30 * df["rc_rc_init_count_z"].fillna(0.0) + 0.25 * df["rc_rc_org_count_z"].fillna(0.0) + 0.20 * lowcrowd + 0.15 * value + 0.10 * midcap,
        np.nan,
    )
    df["rc702_multi_org_positive_lowcrowding"] = np.where(
        recent_rc,
        0.30 * df["rc_rc_org_count_z"].fillna(0.0) + 0.25 * df["rc_rc_positive_count_z"].fillna(0.0) + 0.20 * lowcrowd + 0.15 * value + 0.10 * reversal,
        np.nan,
    )
    df["rc703_deep_coverage_midcap"] = np.where(
        recent_rc & (df["rc_rc_deep_count"].fillna(0.0) > 0.0),
        0.30 * df["rc_rc_deep_count_z"].fillna(0.0) + 0.25 * midcap + 0.20 * value + 0.15 * industry20 + 0.10 * lowcrowd,
        np.nan,
    )
    df["rc704_target_premium_follow"] = np.where(
        recent_rc & (df["rc_rc_avg_target_premium"].fillna(-999.0) > 0.15),
        0.35 * df["rc_rc_avg_target_premium_z"].fillna(0.0) + 0.20 * breakout + 0.20 * close_pos + 0.15 * amount_ratio + 0.10 * lowcrowd,
        np.nan,
    )
    df["rc705_repeat_coverage_strong_industry"] = np.where(
        recent_rc & (df["industry_ret_20_rank"].fillna(0.0) >= 0.65),
        0.30 * df["rc_rc_report_count_z"].fillna(0.0) + 0.25 * df["rc_rc_org_count_z"].fillna(0.0) + 0.20 * industry20 + 0.15 * lowcrowd + 0.10 * close_pos,
        np.nan,
    )
    df["rc706_broker_consensus_plus_report"] = np.where(
        recent_rc & recent_br,
        0.30 * df["br_br_broker_count_z"].fillna(0.0) + 0.25 * df["rc_rc_org_count_z"].fillna(0.0) + 0.20 * value + 0.15 * lowcrowd + 0.10 * industry20,
        np.nan,
    )

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

    report = {
        "panel_rows": int(len(df)),
        "rc_recent_coverage": float(recent_rc.mean()),
        "br_recent_coverage": float(recent_br.mean()),
        "hn_recent_coverage": float(recent_hn.mean()),
    }
    (REFERENCE_DIR / "feature_build_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return df
