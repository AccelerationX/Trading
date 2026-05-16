from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .broker_attention_features import add_broker_attention_features
from .earnings_event_features import add_earnings_event_features
from .holder_risk_features import add_holder_risk_features
from .line_a_overlay_tushare_features import load_margin_features, load_northbound_features


ROOT = Path(r"D:\TradingMain")
REFERENCE_DIR = ROOT / "research" / "reference" / "tushare"


def zscore_by_date(df: pd.DataFrame, column: str) -> pd.Series:
    grouped = df.groupby("trade_date")[column]
    mean = grouped.transform("mean")
    std = grouped.transform("std").replace(0.0, np.nan)
    return ((df[column] - mean) / std).replace([np.inf, -np.inf], np.nan)


def add_event_meta_ranking_features(panel: pd.DataFrame) -> pd.DataFrame:
    base = add_earnings_event_features(panel.copy())
    base_cols = [
        "stock_code",
        "trade_date",
        "volume_ma20_gap_z",
        "bp_z",
        "short_reversal_5_z",
        "breakout_retest_score_z",
        "amount_ratio_5_20_z",
        "close_range_pos_z",
        "mid_size_score_z",
        "industry_ret_20_z",
        "industry_ret_20_rank",
        "close_range_pos",
        "ee301_positive_forecast_follow",
        "ee302_forecast_repair_lowcrowding",
        "ee303_express_profit_surprise",
        "ee309_large_positive_forecast_short_hold",
    ]
    df = base[base_cols].copy()

    holder_panel = add_holder_risk_features(panel.copy())
    holder_cols = [
        "stock_code",
        "trade_date",
        "hn801_holder_concentration_improving",
        "hn805_extreme_holder_decline_breakout",
        "pr902_falling_pledge_relief",
        "pr904_high_pledge_overreaction_repair",
    ]
    df = df.merge(holder_panel[holder_cols], on=["stock_code", "trade_date"], how="left")

    broker_panel = add_broker_attention_features(panel.copy())
    broker_cols = [
        "stock_code",
        "trade_date",
        "br901_coverage_diffusion_lowcrowding",
        "br903_consensus_accel_midcap",
        "br904_first_coverage_repair",
    ]
    df = df.merge(broker_panel[broker_cols], on=["stock_code", "trade_date"], how="left")

    margin = load_margin_features()[
        [
            "trade_date",
            "stock_code",
            "margin_rzye_z",
            "margin_rzye_chg_5_z",
            "margin_flow_accel_z",
            "margin_crowding_gate",
        ]
    ]
    north = load_northbound_features()[
        [
            "trade_date",
            "stock_code",
            "north_ratio_z",
            "north_ratio_chg_5_z",
            "north_ratio_chg_20_z",
        ]
    ]
    df = df.merge(margin, on=["trade_date", "stock_code"], how="left")
    df = df.merge(north, on=["trade_date", "stock_code"], how="left")

    signal_cols = [
        "ee301_positive_forecast_follow",
        "ee302_forecast_repair_lowcrowding",
        "ee303_express_profit_surprise",
        "ee309_large_positive_forecast_short_hold",
        "hn801_holder_concentration_improving",
        "hn805_extreme_holder_decline_breakout",
        "pr902_falling_pledge_relief",
        "pr904_high_pledge_overreaction_repair",
        "br901_coverage_diffusion_lowcrowding",
        "br903_consensus_accel_midcap",
        "br904_first_coverage_repair",
    ]
    for col in signal_cols:
        df[f"{col}_z"] = zscore_by_date(df, col)

    lowcrowd = -df["volume_ma20_gap_z"].fillna(0.0)
    value = df["bp_z"].fillna(0.0)
    reversal = df["short_reversal_5_z"].fillna(0.0)
    breakout = df["breakout_retest_score_z"].fillna(0.0)
    amount = df["amount_ratio_5_20_z"].fillna(0.0)
    close_pos = df["close_range_pos_z"].fillna(0.0)
    midcap = df["mid_size_score_z"].fillna(0.0)
    industry = df["industry_ret_20_z"].fillna(0.0)
    anti_margin = (
        -0.25 * df["margin_rzye_chg_5_z"].fillna(0.0)
        - 0.15 * df["margin_flow_accel_z"].fillna(0.0)
        - 0.10 * df["margin_rzye_z"].fillna(0.0)
    )
    north_support = (
        0.10 * df["north_ratio_chg_5_z"].fillna(0.0)
        + 0.05 * df["north_ratio_chg_20_z"].fillna(0.0)
        + 0.05 * df["north_ratio_z"].fillna(0.0)
    )

    catalyst_count = (
        df[
            [
                "ee301_positive_forecast_follow",
                "ee303_express_profit_surprise",
                "hn801_holder_concentration_improving",
                "br901_coverage_diffusion_lowcrowding",
            ]
        ]
        .notna()
        .sum(axis=1)
    )
    df["event_catalyst_count"] = catalyst_count
    df["event_catalyst_count_z"] = zscore_by_date(df, "event_catalyst_count")

    df["em901_event_strength_blend"] = np.where(
        catalyst_count >= 1,
        0.28 * df["ee301_positive_forecast_follow_z"].fillna(0.0)
        + 0.20 * df["ee303_express_profit_surprise_z"].fillna(0.0)
        + 0.14 * df["hn801_holder_concentration_improving_z"].fillna(0.0)
        + 0.10 * breakout
        + 0.10 * amount
        + 0.08 * close_pos
        + 0.10 * anti_margin,
        np.nan,
    )
    df["em902_event_repair_quality"] = np.where(
        catalyst_count >= 1,
        0.22 * df["ee302_forecast_repair_lowcrowding_z"].fillna(0.0)
        + 0.18 * df["hn801_holder_concentration_improving_z"].fillna(0.0)
        + 0.12 * df["pr902_falling_pledge_relief_z"].fillna(0.0)
        + 0.12 * reversal
        + 0.12 * value
        + 0.12 * lowcrowd
        + 0.12 * anti_margin,
        np.nan,
    )
    df["em903_multi_event_confirmation"] = np.where(
        catalyst_count >= 2,
        0.18 * df["ee301_positive_forecast_follow_z"].fillna(0.0)
        + 0.14 * df["ee303_express_profit_surprise_z"].fillna(0.0)
        + 0.12 * df["hn801_holder_concentration_improving_z"].fillna(0.0)
        + 0.10 * df["br901_coverage_diffusion_lowcrowding_z"].fillna(0.0)
        + 0.10 * df["event_catalyst_count_z"].fillna(0.0)
        + 0.10 * midcap
        + 0.08 * industry
        + 0.08 * breakout
        + 0.10 * anti_margin,
        np.nan,
    )
    df["em904_high_conviction_breakout"] = np.where(
        (df["ee309_large_positive_forecast_short_hold"].notna() | df["br904_first_coverage_repair"].notna())
        & (df["close_range_pos"].fillna(0.0) > 0.55),
        0.24 * df["ee309_large_positive_forecast_short_hold_z"].fillna(0.0)
        + 0.12 * df["br904_first_coverage_repair_z"].fillna(0.0)
        + 0.12 * breakout
        + 0.14 * amount
        + 0.12 * close_pos
        + 0.10 * midcap
        + 0.08 * lowcrowd
        + 0.08 * anti_margin,
        np.nan,
    )
    df["em905_quality_industry_catalyst"] = np.where(
        (catalyst_count >= 1) & (df["industry_ret_20_rank"].fillna(0.0) >= 0.55),
        0.20 * df["ee301_positive_forecast_follow_z"].fillna(0.0)
        + 0.14 * df["ee303_express_profit_surprise_z"].fillna(0.0)
        + 0.12 * df["br903_consensus_accel_midcap_z"].fillna(0.0)
        + 0.10 * industry
        + 0.10 * midcap
        + 0.10 * lowcrowd
        + 0.08 * north_support
        + 0.16 * anti_margin,
        np.nan,
    )
    df["em906_special_situations_blend"] = np.where(
        df[
            [
                "hn805_extreme_holder_decline_breakout",
                "pr904_high_pledge_overreaction_repair",
                "br904_first_coverage_repair",
            ]
        ]
        .notna()
        .any(axis=1),
        0.22 * df["hn805_extreme_holder_decline_breakout_z"].fillna(0.0)
        + 0.22 * df["pr904_high_pledge_overreaction_repair_z"].fillna(0.0)
        + 0.18 * df["br904_first_coverage_repair_z"].fillna(0.0)
        + 0.12 * reversal
        + 0.10 * breakout
        + 0.08 * lowcrowd
        + 0.08 * anti_margin,
        np.nan,
    )

    report = {
        "panel_rows": int(len(df)),
        "catalyst_ge_1_ratio": float((catalyst_count >= 1).mean()),
        "catalyst_ge_2_ratio": float((catalyst_count >= 2).mean()),
        "signal_cols": [
            "em901_event_strength_blend",
            "em902_event_repair_quality",
            "em903_multi_event_confirmation",
            "em904_high_conviction_breakout",
            "em905_quality_industry_catalyst",
            "em906_special_situations_blend",
        ],
    }
    (REFERENCE_DIR / "event_meta_ranking_feature_build_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return df
