from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .external_tushare_features import add_external_tushare_features


ROOT = Path(r"D:\TradingMain")
REFERENCE_DIR = ROOT / "research" / "reference" / "tushare" / "earnings_event"


def zscore_by_date(df: pd.DataFrame, column: str) -> pd.Series:
    grouped = df.groupby("trade_date")[column]
    mean = grouped.transform("mean")
    std = grouped.transform("std").replace(0.0, np.nan)
    return ((df[column] - mean) / std).replace([np.inf, -np.inf], np.nan)


def _load_table(name: str) -> pd.DataFrame:
    path = REFERENCE_DIR / f"{name}_quarterly_2019plus.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing earnings event dataset: {path}")
    df = pd.read_parquet(path)
    for col in ["ann_date", "end_date", "first_ann_date"]:
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

    merged = pd.merge_asof(
        left.sort_values(["trade_date", "stock_code"]),
        right.sort_values(["ann_date", "stock_code"]),
        left_on="trade_date",
        right_on="ann_date",
        by="stock_code",
        direction="backward",
    )
    merged = merged.rename(columns={col: f"{prefix}_{col}" for col in ["ann_date"] + value_cols})
    return merged


def add_earnings_event_features(panel: pd.DataFrame) -> pd.DataFrame:
    df = add_external_tushare_features(panel.copy())

    forecast = _load_table("forecast")
    forecast["p_change_min"] = pd.to_numeric(forecast.get("p_change_min"), errors="coerce")
    forecast["p_change_max"] = pd.to_numeric(forecast.get("p_change_max"), errors="coerce")
    forecast["net_profit_min"] = pd.to_numeric(forecast.get("net_profit_min"), errors="coerce")
    forecast["net_profit_max"] = pd.to_numeric(forecast.get("net_profit_max"), errors="coerce")
    forecast["type"] = forecast.get("type", "").astype(str)
    forecast["forecast_mid"] = (forecast["p_change_min"].fillna(0.0) + forecast["p_change_max"].fillna(0.0)) / 2.0
    forecast["forecast_type_score"] = np.select(
        [
            forecast["type"].isin(["预增", "扭亏", "续盈"]),
            forecast["type"].isin(["略增"]),
            forecast["type"].isin(["预减", "首亏", "续亏", "略减"]),
        ],
        [1.0, 0.5, -1.0],
        default=0.0,
    )
    forecast = forecast.groupby(["stock_code", "ann_date"], as_index=False).agg(
        forecast_mid=("forecast_mid", "mean"),
        forecast_type_score=("forecast_type_score", "max"),
        forecast_profit_max=("net_profit_max", "max"),
    )

    express = _load_table("express")
    express["revenue"] = pd.to_numeric(express.get("revenue"), errors="coerce")
    express["n_income"] = pd.to_numeric(express.get("n_income"), errors="coerce")
    # Tushare express stores last year's comparable net profit in yoy_net_profit.
    express["profit_last_year"] = pd.to_numeric(express.get("yoy_net_profit"), errors="coerce")
    express["operate_profit"] = pd.to_numeric(express.get("operate_profit"), errors="coerce")
    express["express_profit_yoy"] = express["n_income"] / express["profit_last_year"].replace(0.0, np.nan) - 1.0
    express["express_profit_delta_ratio"] = (express["n_income"] - express["profit_last_year"]) / express["profit_last_year"].abs().replace(0.0, np.nan)
    express["express_oper_margin"] = express["operate_profit"] / express["revenue"].replace(0.0, np.nan)
    express["express_positive_flag"] = np.where(express["n_income"].fillna(0.0) > 0.0, 1.0, 0.0)
    express["express_turnaround_flag"] = np.where(
        (express["n_income"].fillna(0.0) > 0.0) & (express["profit_last_year"].fillna(0.0) <= 0.0),
        1.0,
        0.0,
    )
    express = express.groupby(["stock_code", "ann_date"], as_index=False).agg(
        express_profit_yoy=("express_profit_yoy", "mean"),
        express_profit_delta_ratio=("express_profit_delta_ratio", "mean"),
        express_oper_margin=("express_oper_margin", "mean"),
        express_revenue=("revenue", "max"),
        express_positive_flag=("express_positive_flag", "max"),
        express_turnaround_flag=("express_turnaround_flag", "max"),
    )

    forecast_daily = _merge_recent_event(df, forecast, ["forecast_mid", "forecast_type_score", "forecast_profit_max"], "forecast")
    express_daily = _merge_recent_event(
        df,
        express,
        [
            "express_profit_yoy",
            "express_profit_delta_ratio",
            "express_oper_margin",
            "express_revenue",
            "express_positive_flag",
            "express_turnaround_flag",
        ],
        "express",
    )
    for extra in [forecast_daily, express_daily]:
        df = df.merge(extra, on=["stock_code", "trade_date"], how="left")

    for prefix in ["forecast_ann_date", "express_ann_date"]:
        if prefix in df.columns:
            df[f"{prefix}_age"] = (df["trade_date"] - df[prefix]).dt.days

    numeric_cols = [
        "forecast_forecast_mid",
        "forecast_forecast_type_score",
        "forecast_forecast_profit_max",
        "express_express_profit_yoy",
        "express_express_profit_delta_ratio",
        "express_express_oper_margin",
        "express_express_revenue",
        "express_express_positive_flag",
        "express_express_turnaround_flag",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df[f"{col}_z"] = zscore_by_date(df, col)

    lowvol = -df["volatility_20_z"].fillna(0.0)
    lowcrowd = -df["volume_ma20_gap_z"].fillna(0.0)
    value = df["bp_z"].fillna(0.0)
    industry20 = df["industry_ret_20_z"].fillna(0.0)
    reversal = df["short_reversal_5_z"].fillna(0.0)

    recent_forecast = df["forecast_ann_date_age"].fillna(9999).between(0, 30)
    recent_forecast_fast = df["forecast_ann_date_age"].fillna(9999).between(0, 12)
    recent_express = df["express_ann_date_age"].fillna(9999).between(0, 30)
    recent_dual = recent_forecast & recent_express
    positive_forecast = df["forecast_forecast_type_score"].fillna(-9.0) > 0.0
    positive_express = df["express_express_positive_flag"].fillna(0.0) > 0.0
    express_turnaround = df["express_express_turnaround_flag"].fillna(0.0) > 0.0

    df["ee301_positive_forecast_follow"] = np.where(
        recent_forecast & positive_forecast,
        0.55 * df["forecast_forecast_mid_z"].fillna(0.0) + 0.20 * df["forecast_forecast_type_score_z"].fillna(0.0) + 0.15 * lowcrowd + 0.10 * value,
        np.nan,
    )
    df["ee302_forecast_repair_lowcrowding"] = np.where(
        recent_forecast & positive_forecast,
        0.40 * df["forecast_forecast_mid_z"].fillna(0.0) + 0.25 * reversal + 0.20 * lowcrowd + 0.15 * value,
        np.nan,
    )
    df["ee303_express_profit_surprise"] = np.where(
        recent_express & positive_express,
        0.50 * df["express_express_profit_delta_ratio_z"].fillna(0.0)
        + 0.25 * df["express_express_oper_margin_z"].fillna(0.0)
        + 0.15 * lowcrowd
        + 0.10 * value,
        np.nan,
    )
    df["ee304_express_lowvol_carry"] = np.where(
        recent_express & positive_express,
        0.40 * df["express_express_profit_delta_ratio_z"].fillna(0.0) + 0.30 * lowvol + 0.15 * value + 0.15 * industry20,
        np.nan,
    )
    df["ee305_forecast_plus_industry_strength"] = np.where(
        recent_forecast & positive_forecast & (df["industry_ret_20_rank"].fillna(0.0) >= 0.65),
        0.45 * df["forecast_forecast_mid_z"].fillna(0.0) + 0.25 * industry20 + 0.20 * lowcrowd + 0.10 * value,
        np.nan,
    )
    df["ee306_forecast_and_express_combo"] = np.where(
        recent_dual & positive_forecast & positive_express,
        0.25 * df["forecast_forecast_mid_z"].fillna(0.0)
        + 0.30 * df["express_express_profit_delta_ratio_z"].fillna(0.0)
        + 0.20 * value
        + 0.15 * lowcrowd
        + 0.10 * df["forecast_forecast_type_score_z"].fillna(0.0),
        np.nan,
    )
    df["ee307_express_turnaround_follow"] = np.where(
        recent_express & express_turnaround,
        0.45 * df["express_express_profit_delta_ratio_z"].fillna(0.0)
        + 0.20 * df["express_express_oper_margin_z"].fillna(0.0)
        + 0.20 * value
        + 0.15 * lowcrowd,
        np.nan,
    )
    df["ee308_dual_positive_revision"] = np.where(
        recent_dual & positive_forecast & positive_express,
        0.30 * df["forecast_forecast_mid_z"].fillna(0.0)
        + 0.25 * df["express_express_profit_delta_ratio_z"].fillna(0.0)
        + 0.15 * df["express_express_oper_margin_z"].fillna(0.0)
        + 0.15 * value
        + 0.15 * lowcrowd,
        np.nan,
    )
    df["ee309_large_positive_forecast_short_hold"] = np.where(
        recent_forecast_fast & positive_forecast & (df["forecast_forecast_mid"].fillna(-999.0) >= 30.0),
        0.60 * df["forecast_forecast_mid_z"].fillna(0.0) + 0.20 * lowcrowd + 0.20 * value,
        np.nan,
    )
    df["ee310_forecast_turnaround_value"] = np.where(
        recent_forecast & (df["forecast_forecast_type_score"].fillna(0.0) >= 1.0),
        0.35 * df["forecast_forecast_mid_z"].fillna(0.0)
        + 0.25 * df["forecast_forecast_type_score_z"].fillna(0.0)
        + 0.20 * reversal
        + 0.20 * value,
        np.nan,
    )

    report = {
        "panel_rows": int(len(df)),
        "forecast_coverage": float(recent_forecast.mean()),
        "express_coverage": float(recent_express.mean()),
        "dual_coverage": float(recent_dual.mean()),
    }
    (REFERENCE_DIR / "feature_build_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return df
