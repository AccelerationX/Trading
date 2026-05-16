from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .strategy_line_a_family import add_line_a_family_signal


ROOT = Path(r"D:\TradingMain")
MONEYFLOW_PATH = ROOT / "research" / "reference" / "tushare" / "moneyflow" / "moneyflow_daily_2020plus.parquet"


def zscore_by_date(df: pd.DataFrame, column: str) -> pd.Series:
    grouped = df.groupby("trade_date")[column]
    mean = grouped.transform("mean")
    std = grouped.transform("std").replace(0.0, np.nan)
    return ((df[column] - mean) / std).replace([np.inf, -np.inf], np.nan)


def load_moneyflow() -> pd.DataFrame:
    if not MONEYFLOW_PATH.exists():
        raise FileNotFoundError(f"Missing moneyflow cache: {MONEYFLOW_PATH}")
    df = pd.read_parquet(MONEYFLOW_PATH)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df.sort_values(["trade_date", "stock_code"]).copy()


def add_moneyflow_features(panel: pd.DataFrame) -> pd.DataFrame:
    df = add_line_a_family_signal(panel)
    flow = load_moneyflow()
    merged = df.merge(flow, on=["stock_code", "trade_date"], how="left")

    amount_base = merged["amount_k"].replace(0.0, np.nan).abs()
    merged["volume_ma20_gap_z"] = zscore_by_date(merged, "volume_ma20_gap")
    merged["net_mf_ratio"] = merged["net_mf_amount"] / amount_base
    merged["elg_mf_ratio"] = (merged["buy_elg_amount"] - merged["sell_elg_amount"]) / amount_base
    merged["lg_mf_ratio"] = (merged["buy_lg_amount"] - merged["sell_lg_amount"]) / amount_base
    merged["retail_mf_ratio"] = (merged["buy_sm_amount"] - merged["sell_sm_amount"]) / amount_base
    merged["mid_mf_ratio"] = (merged["buy_md_amount"] - merged["sell_md_amount"]) / amount_base

    for col in ["net_mf_ratio", "elg_mf_ratio", "lg_mf_ratio", "retail_mf_ratio", "mid_mf_ratio"]:
        merged[f"{col}_z"] = zscore_by_date(merged, col)

    merged["moneyflow_breadth"] = merged.groupby("trade_date")["net_mf_ratio"].transform(
        lambda s: float((s > 0).mean())
    )
    merged["moneyflow_risk_on_gate"] = merged["moneyflow_breadth"] >= 0.50
    merged["moneyflow_exposure"] = np.select(
        [
            merged["moneyflow_breadth"] >= 0.58,
            merged["moneyflow_breadth"] >= 0.48,
        ],
        [1.0, 0.60],
        default=0.25,
    )

    lowvol = -merged["volatility_20_z"]
    lowcrowd = -merged["volume_ma20_gap_z"]
    reversal = merged["short_reversal_5_z"]
    value = merged["bp_z"]
    small = -merged["size_z"]
    breakout = merged["breakout_20_z"]
    compression = -merged["range_compress_10_20_z"]

    merged["mf301_line_a_big_inflow"] = np.where(
        (merged["net_mf_ratio"] > 0) & (merged["elg_mf_ratio"] > 0),
        merged["line_a_core_signal"] + 0.35 * merged["net_mf_ratio_z"] + 0.25 * merged["elg_mf_ratio_z"],
        np.nan,
    )
    merged["mf302_oversold_institutional_support"] = np.where(
        (merged["daily_ret"] < 0) & (merged["elg_mf_ratio"] > 0),
        reversal + 0.45 * merged["elg_mf_ratio_z"] + 0.20 * value + 0.20 * lowcrowd,
        np.nan,
    )
    merged["mf303_breakout_big_order_follow"] = np.where(
        (merged["breakout_20"] > 0) & (merged["net_mf_ratio"] > 0),
        breakout + 0.40 * merged["elg_mf_ratio_z"] + 0.25 * merged["lg_mf_ratio_z"] + 0.15 * compression,
        np.nan,
    )
    merged["mf304_lowvol_big_inflow"] = np.where(
        merged["net_mf_ratio"] > 0,
        0.40 * lowvol + 0.30 * value + 0.35 * merged["net_mf_ratio_z"] + 0.20 * merged["lg_mf_ratio_z"],
        np.nan,
    )
    merged["mf305_smallcap_funds_rotation"] = np.where(
        merged["moneyflow_risk_on_gate"] & (merged["net_mf_ratio"] > 0),
        0.40 * small + 0.35 * merged["net_mf_ratio_z"] + 0.20 * merged["elg_mf_ratio_z"] + 0.15 * breakout,
        np.nan,
    )
    merged["mf306_contra_retail_dump"] = np.where(
        (merged["retail_mf_ratio"] < 0) & (merged["elg_mf_ratio"] > 0),
        reversal + 0.35 * value + 0.35 * merged["elg_mf_ratio_z"] - 0.25 * merged["retail_mf_ratio_z"],
        np.nan,
    )
    return merged
