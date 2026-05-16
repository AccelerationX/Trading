from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .external_tushare_features import add_external_tushare_features
from .line_a_overlay_tushare_features import (
    REFERENCE_DIR,
    load_margin_features,
    load_northbound_features,
    load_northbound_market_features,
)


def add_capital_flow_family_features(panel: pd.DataFrame) -> pd.DataFrame:
    df = add_external_tushare_features(panel.copy())
    north = load_northbound_features()
    north_market = load_northbound_market_features()
    margin = load_margin_features()

    df = df.merge(
        north[
            [
                "trade_date",
                "stock_code",
                "north_ratio_z",
                "north_ratio_chg_5_z",
                "north_ratio_chg_20_z",
                "north_vol_chg_5_z",
            ]
        ],
        on=["trade_date", "stock_code"],
        how="left",
    )
    df = df.merge(north_market, on="trade_date", how="left")
    df = df.merge(
        margin[
            [
                "trade_date",
                "stock_code",
                "margin_rzye_z",
                "margin_rzye_chg_5_z",
                "margin_rzye_chg_20_z",
                "margin_flow_accel_z",
                "margin_crowding_gate",
                "margin_crowding_exposure",
            ]
        ],
        on=["trade_date", "stock_code"],
        how="left",
    )

    lowvol = -df["volatility_20_z"].fillna(0.0)
    lowcrowd = -df["volume_ma20_gap_z"].fillna(0.0)
    reversal = df["short_reversal_5_z"].fillna(0.0)
    value = df["bp_z"].fillna(0.0)
    breakout = df["breakout_20_z"].fillna(0.0)
    compression = -df["range_compress_10_20_z"].fillna(0.0)
    mom20 = df["mom_20_z"].fillna(0.0)
    industry20 = df["industry_ret_20_z"].fillna(0.0)
    industry_breadth = df["industry_breadth_20_z"].fillna(0.0)

    north_support = (
        0.40 * df["north_ratio_chg_5_z"].fillna(0.0)
        + 0.25 * df["north_ratio_chg_20_z"].fillna(0.0)
        + 0.15 * df["north_vol_chg_5_z"].fillna(0.0)
        + 0.10 * industry20
    )
    anti_margin = (
        -0.35 * df["margin_rzye_chg_5_z"].fillna(0.0)
        - 0.25 * df["margin_flow_accel_z"].fillna(0.0)
        - 0.15 * df["margin_rzye_z"].fillna(0.0)
    )

    df["north_margin_exposure"] = (
        df["north_market_exposure"].fillna(0.50) * df["margin_crowding_exposure"].fillna(0.50)
    ).clip(lower=0.0, upper=1.0)
    df["north_margin_market_gate"] = (
        df["north_market_gate"].fillna(False) & df["margin_crowding_gate"].fillna(False)
    )

    df["cf201_northbound_market_inflow_ladder"] = np.where(
        df["north_market_gate"].fillna(False),
        north_support + 0.25 * mom20 + 0.20 * lowcrowd + 0.15 * lowvol,
        np.nan,
    )
    df["cf202_anti_margin_crowding_cross_section"] = np.where(
        df["margin_rzye_chg_5_z"].fillna(9.0) < 1.2,
        anti_margin + 0.25 * mom20 + 0.20 * lowcrowd + 0.15 * lowvol + 0.10 * value,
        np.nan,
    )
    df["cf203_northbound_support_inside_strong_industries"] = np.where(
        (df["industry_ret_20_rank"].fillna(0.0) >= 0.70)
        & (df["north_ratio_chg_5_z"].fillna(-9.0) > -0.5),
        north_support + 0.25 * industry_breadth + 0.20 * mom20 + 0.15 * lowcrowd,
        np.nan,
    )
    df["cf204_financing_squeeze_repair"] = np.where(
        (df["margin_rzye_chg_20_z"].fillna(9.0) < -0.2)
        & (df["margin_flow_accel_z"].fillna(9.0) < 0.3)
        & (df["mom_5"].fillna(9.0) < 0.02),
        anti_margin + 0.35 * reversal + 0.20 * industry20 + 0.10 * lowcrowd,
        np.nan,
    )
    df["cf205_low_margin_low_crowding_continuation"] = np.where(
        (df["margin_rzye_chg_5_z"].fillna(9.0) < 0.6)
        & (df["volume_ma20_gap_z"].fillna(9.0) < 0.8)
        & (df["mom_20"].fillna(-9.0) > -0.02),
        anti_margin + 0.35 * lowcrowd + 0.25 * mom20 + 0.20 * compression + 0.10 * lowvol,
        np.nan,
    )
    df["cf206_northbound_financing_divergence"] = np.where(
        (df["north_ratio_chg_5_z"].fillna(-9.0) > 0.0)
        & (df["margin_rzye_chg_5_z"].fillna(9.0) < 0.4),
        north_support + anti_margin + 0.20 * industry20 + 0.15 * lowcrowd + 0.10 * breakout,
        np.nan,
    )

    report = {
        "panel_rows": int(len(df)),
        "north_available_ratio": float(df["north_ratio_chg_5_z"].notna().mean()),
        "margin_available_ratio": float(df["margin_rzye_chg_5_z"].notna().mean()),
        "gated_rows_ratio": float(df["north_margin_market_gate"].fillna(False).mean()),
    }
    Path(REFERENCE_DIR).mkdir(parents=True, exist_ok=True)
    (REFERENCE_DIR / "capital_flow_family_feature_build_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return df
