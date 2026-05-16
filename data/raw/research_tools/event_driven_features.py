from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .external_tushare_features import add_external_tushare_features


ROOT = Path(r"D:\TradingMain")
REFERENCE_DIR = ROOT / "research" / "reference" / "tushare" / "event"


def zscore_by_date(df: pd.DataFrame, column: str) -> pd.Series:
    grouped = df.groupby("trade_date")[column]
    mean = grouped.transform("mean")
    std = grouped.transform("std").replace(0.0, np.nan)
    return ((df[column] - mean) / std).replace([np.inf, -np.inf], np.nan)


def _load_event_table(name: str) -> pd.DataFrame:
    path = REFERENCE_DIR / f"{name}_daily_2020plus.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing event dataset: {path}")
    df = pd.read_parquet(path)
    for col in ["ann_date", "end_date", "begin_date", "close_date", "exp_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])
    if "stock_code" in df.columns:
        df["stock_code"] = df["stock_code"].astype(str).str.upper()
    return df


def _merge_recent_event(panel: pd.DataFrame, event_df: pd.DataFrame, value_cols: list[str], prefix: str) -> pd.DataFrame:
    left = panel[["stock_code", "trade_date"]].copy()
    left["trade_date"] = pd.to_datetime(left["trade_date"]).astype("datetime64[ns]")
    right = event_df[["stock_code", "ann_date"] + value_cols].copy()
    right["ann_date"] = pd.to_datetime(right["ann_date"]).astype("datetime64[ns]")
    pieces: list[pd.DataFrame] = []
    right = right.sort_values(["stock_code", "ann_date"])
    for stock_code, left_group in left.sort_values(["stock_code", "trade_date"]).groupby("stock_code", sort=False):
        right_group = right[right["stock_code"] == stock_code]
        if right_group.empty:
            merged_group = left_group.copy()
            merged_group["ann_date"] = pd.NaT
            for col in value_cols:
                merged_group[col] = np.nan
        else:
            merged_group = pd.merge_asof(
                left_group.sort_values("trade_date"),
                right_group.sort_values("ann_date"),
                left_on="trade_date",
                right_on="ann_date",
                direction="backward",
                allow_exact_matches=True,
            )
        pieces.append(merged_group)
    merged = pd.concat(pieces, ignore_index=True)
    rename_map = {col: f"{prefix}_{col}" for col in ["ann_date"] + value_cols}
    merged = merged.rename(columns=rename_map)
    return merged


def add_event_driven_features(panel: pd.DataFrame) -> pd.DataFrame:
    df = add_external_tushare_features(panel.copy())

    repurchase = _load_event_table("repurchase")
    repurchase["amount"] = pd.to_numeric(repurchase.get("amount"), errors="coerce")
    repurchase["vol"] = pd.to_numeric(repurchase.get("vol"), errors="coerce")
    repurchase["repurchase_stage_score"] = repurchase.get("proc", "").astype(str).map(
        {"股东大会通过": 0.4, "实施": 0.8, "完成": 1.0}
    ).fillna(0.2)
    repurchase_agg = (
        repurchase.groupby(["stock_code", "ann_date"], as_index=False)
        .agg(
            repurchase_amount=("amount", "sum"),
            repurchase_vol=("vol", "sum"),
            repurchase_stage_score=("repurchase_stage_score", "max"),
        )
    )

    holdertrade = _load_event_table("holdertrade")
    holdertrade["change_ratio"] = pd.to_numeric(holdertrade.get("change_ratio"), errors="coerce")
    holdertrade["avg_price"] = pd.to_numeric(holdertrade.get("avg_price"), errors="coerce")
    holdertrade["holder_type"] = holdertrade.get("holder_type", "").astype(str)
    holdertrade["in_de"] = holdertrade.get("in_de", "").astype(str)
    holdertrade["is_mgmt"] = holdertrade["holder_type"].eq("G").astype(float)
    holdertrade["is_company"] = holdertrade["holder_type"].eq("C").astype(float)
    holdertrade["is_person"] = holdertrade["holder_type"].eq("P").astype(float)
    holder_agg = (
        holdertrade.groupby(["stock_code", "ann_date", "in_de"], as_index=False)
        .agg(
            holder_change_ratio=("change_ratio", "sum"),
            holder_avg_price=("avg_price", "mean"),
            mgmt_flag=("is_mgmt", "max"),
            company_flag=("is_company", "max"),
            person_flag=("is_person", "max"),
        )
    )
    holder_in = holder_agg[holder_agg["in_de"] == "IN"].drop(columns=["in_de"]).rename(
        columns={
            "holder_change_ratio": "holder_in_ratio",
            "holder_avg_price": "holder_in_avg_price",
            "mgmt_flag": "holder_in_mgmt_flag",
            "company_flag": "holder_in_company_flag",
            "person_flag": "holder_in_person_flag",
        }
    )
    holder_de = holder_agg[holder_agg["in_de"] == "DE"].drop(columns=["in_de"]).rename(
        columns={
            "holder_change_ratio": "holder_de_ratio",
            "holder_avg_price": "holder_de_avg_price",
            "mgmt_flag": "holder_de_mgmt_flag",
            "company_flag": "holder_de_company_flag",
            "person_flag": "holder_de_person_flag",
        }
    )

    repurchase_daily = _merge_recent_event(
        df,
        repurchase_agg,
        ["repurchase_amount", "repurchase_vol", "repurchase_stage_score"],
        "repurchase",
    )
    holder_in_daily = _merge_recent_event(
        df,
        holder_in,
        ["holder_in_ratio", "holder_in_avg_price", "holder_in_mgmt_flag", "holder_in_company_flag", "holder_in_person_flag"],
        "holder_in",
    )
    holder_de_daily = _merge_recent_event(
        df,
        holder_de,
        ["holder_de_ratio", "holder_de_avg_price", "holder_de_mgmt_flag", "holder_de_company_flag", "holder_de_person_flag"],
        "holder_de",
    )

    for extra in [repurchase_daily, holder_in_daily, holder_de_daily]:
        df = df.merge(extra, on=["stock_code", "trade_date"], how="left")

    for event_prefix in ["repurchase_ann_date", "holder_in_ann_date", "holder_de_ann_date"]:
        if event_prefix in df.columns:
            df[f"{event_prefix}_age"] = (df["trade_date"] - df[event_prefix]).dt.days

    numeric_cols = [
        "repurchase_repurchase_amount",
        "repurchase_repurchase_vol",
        "repurchase_repurchase_stage_score",
        "holder_in_holder_in_ratio",
        "holder_de_holder_de_ratio",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df[f"{col}_z"] = zscore_by_date(df, col)

    lowvol = -df["volatility_20_z"].fillna(0.0)
    lowcrowd = -df["volume_ma20_gap_z"].fillna(0.0)
    value = df["bp_z"].fillna(0.0)
    reversal = df["short_reversal_5_z"].fillna(0.0)
    industry20 = df["industry_ret_20_z"].fillna(0.0)

    recent_repurchase = df["repurchase_ann_date_age"].fillna(9999) <= 60
    recent_holder_in = df["holder_in_ann_date_age"].fillna(9999) <= 60
    recent_holder_de = df["holder_de_ann_date_age"].fillna(9999) <= 60

    df["ev201_buyback_follow"] = np.where(
        recent_repurchase,
        0.50 * df["repurchase_repurchase_amount_z"].fillna(0.0) + 0.20 * df["repurchase_repurchase_stage_score_z"].fillna(0.0) + 0.20 * value + 0.10 * lowcrowd,
        np.nan,
    )
    df["ev202_management_increase_follow"] = np.where(
        recent_holder_in & (df["holder_in_holder_in_mgmt_flag"].fillna(0.0) > 0.5),
        0.55 * df["holder_in_holder_in_ratio_z"].fillna(0.0) + 0.20 * value + 0.15 * lowcrowd + 0.10 * lowvol,
        np.nan,
    )
    df["ev203_holder_decrease_overreaction_repair"] = np.where(
        recent_holder_de & (df["holder_de_holder_de_ratio"].fillna(0.0) > 0),
        -0.45 * df["holder_de_holder_de_ratio_z"].fillna(0.0) + 0.35 * reversal + 0.20 * value + 0.10 * lowvol,
        np.nan,
    )
    df["ev204_buyback_lowvol_carry"] = np.where(
        recent_repurchase,
        0.40 * df["repurchase_repurchase_amount_z"].fillna(0.0) + 0.30 * lowvol + 0.20 * value + 0.10 * df["repurchase_repurchase_stage_score_z"].fillna(0.0),
        np.nan,
    )
    df["ev205_event_plus_industry_strength"] = np.where(
        (recent_repurchase | recent_holder_in)
        & (df["industry_ret_20_rank"].fillna(0.0) >= 0.65),
        0.25 * df["repurchase_repurchase_amount_z"].fillna(0.0) + 0.25 * df["holder_in_holder_in_ratio_z"].fillna(0.0) + 0.25 * industry20 + 0.15 * lowcrowd + 0.10 * value,
        np.nan,
    )
    df["ev206_buyback_plus_holder_increase_combo"] = np.where(
        recent_repurchase & recent_holder_in,
        0.35 * df["repurchase_repurchase_amount_z"].fillna(0.0) + 0.35 * df["holder_in_holder_in_ratio_z"].fillna(0.0) + 0.15 * value + 0.15 * lowcrowd,
        np.nan,
    )

    report = {
        "panel_rows": int(len(df)),
        "repurchase_coverage": float(recent_repurchase.mean()),
        "holder_in_coverage": float(recent_holder_in.mean()),
        "holder_de_coverage": float(recent_holder_de.mean()),
    }
    (REFERENCE_DIR / "event_feature_build_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return df
