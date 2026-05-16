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


def _load_broker_recommend() -> pd.DataFrame:
    path = REFERENCE_DIR / "broker_recommend_monthly_2020plus.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing broker_recommend dataset: {path}")
    df = pd.read_parquet(path)
    if df.empty:
        raise RuntimeError(f"Empty broker_recommend dataset: {path}")
    df["stock_code"] = df["stock_code"].astype(str).str.upper()
    df["month"] = df["month"].astype(str)
    df["month_end"] = pd.PeriodIndex(df["month"], freq="M").to_timestamp("M")
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


def add_broker_attention_features(panel: pd.DataFrame) -> pd.DataFrame:
    df = add_external_tushare_features(panel.copy())
    broker = _load_broker_recommend()
    broker["coverage_flag"] = 1.0
    monthly = broker.groupby(["stock_code", "month_end"], as_index=False).agg(
        br_broker_count=("broker", "nunique"),
        br_report_count=("coverage_flag", "sum"),
    )
    monthly = monthly.sort_values(["stock_code", "month_end"]).copy()
    grouped = monthly.groupby("stock_code", group_keys=False)
    monthly["br_broker_count_chg_1"] = grouped["br_broker_count"].transform(lambda s: s.diff(1))
    monthly["br_broker_count_chg_3"] = grouped["br_broker_count"].transform(lambda s: s.diff(3))
    monthly["br_report_count_chg_1"] = grouped["br_report_count"].transform(lambda s: s.diff(1))
    monthly["br_report_count_chg_3"] = grouped["br_report_count"].transform(lambda s: s.diff(3))
    monthly["br_first_coverage_flag"] = (grouped.cumcount() == 0).astype(float)

    recent = _merge_recent_event(
        df,
        monthly,
        "month_end",
        [
            "br_broker_count",
            "br_report_count",
            "br_broker_count_chg_1",
            "br_broker_count_chg_3",
            "br_report_count_chg_1",
            "br_report_count_chg_3",
            "br_first_coverage_flag",
        ],
        "br",
    )
    df = df.merge(recent, on=["stock_code", "trade_date"], how="left")
    df["br_event_age"] = (df["trade_date"] - df["br_month_end"]).dt.days

    numeric_cols = [
        "br_br_broker_count",
        "br_br_report_count",
        "br_br_broker_count_chg_1",
        "br_br_broker_count_chg_3",
        "br_br_report_count_chg_1",
        "br_br_report_count_chg_3",
        "br_br_first_coverage_flag",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df[f"{col}_z"] = zscore_by_date(df, col)

    lowcrowd = -df["volume_ma20_gap_z"].fillna(0.0)
    value = df["bp_z"].fillna(0.0)
    reversal = df["short_reversal_5_z"].fillna(0.0)
    breakout = df["breakout_retest_score_z"].fillna(0.0)
    amount = df["amount_ratio_5_20_z"].fillna(0.0)
    close_pos = df["close_range_pos_z"].fillna(0.0)
    midcap = df["mid_size_score_z"].fillna(0.0)
    industry = df["industry_ret_20_z"].fillna(0.0)

    recent_br = df["br_event_age"].fillna(9999).between(0, 45)
    recent_fast = df["br_event_age"].fillna(9999).between(0, 20)
    coverage_up = df["br_br_broker_count_chg_1"].fillna(-999.0) > 0
    coverage_up_3m = df["br_br_broker_count_chg_3"].fillna(-999.0) > 0
    sparse_coverage = df["br_br_broker_count"].fillna(999.0) <= 5

    df["br901_coverage_diffusion_lowcrowding"] = np.where(
        recent_br & coverage_up,
        0.35 * df["br_br_broker_count_chg_1_z"].fillna(0.0)
        + 0.25 * lowcrowd
        + 0.20 * value
        + 0.20 * midcap,
        np.nan,
    )
    df["br902_sparse_coverage_breakout"] = np.where(
        recent_fast & coverage_up & sparse_coverage,
        0.30 * df["br_br_broker_count_chg_1_z"].fillna(0.0)
        + 0.25 * breakout
        + 0.20 * amount
        + 0.15 * close_pos
        + 0.10 * lowcrowd,
        np.nan,
    )
    df["br903_consensus_accel_midcap"] = np.where(
        recent_br & coverage_up_3m,
        0.30 * df["br_br_broker_count_chg_3_z"].fillna(0.0)
        + 0.25 * midcap
        + 0.20 * lowcrowd
        + 0.15 * value
        + 0.10 * industry,
        np.nan,
    )
    df["br904_first_coverage_repair"] = np.where(
        recent_fast & (df["br_br_first_coverage_flag"].fillna(0.0) > 0.0),
        0.35 * df["br_br_first_coverage_flag_z"].fillna(0.0)
        + 0.25 * reversal
        + 0.20 * value
        + 0.10 * lowcrowd
        + 0.10 * close_pos,
        np.nan,
    )
    df["br905_broad_coverage_strong_industry"] = np.where(
        recent_br & (df["industry_ret_20_rank"].fillna(0.0) >= 0.65),
        0.30 * df["br_br_broker_count_z"].fillna(0.0)
        + 0.25 * df["br_br_report_count_chg_3_z"].fillna(0.0)
        + 0.20 * industry
        + 0.15 * lowcrowd
        + 0.10 * close_pos,
        np.nan,
    )
    df["br906_coverage_accel_breakout"] = np.where(
        recent_fast & coverage_up_3m,
        0.25 * df["br_br_broker_count_chg_3_z"].fillna(0.0)
        + 0.25 * breakout
        + 0.20 * amount
        + 0.15 * close_pos
        + 0.15 * lowcrowd,
        np.nan,
    )

    report = {
        "panel_rows": int(len(df)),
        "recent_coverage_ratio": float(recent_br.mean()),
        "fast_coverage_ratio": float(recent_fast.mean()),
    }
    (REFERENCE_DIR / "broker_feature_build_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return df
