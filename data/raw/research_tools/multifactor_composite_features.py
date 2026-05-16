from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .factors import add_research_factors, zscore_by_date


ROOT = Path(r"D:\TradingMain")
REFERENCE_DIR = ROOT / "research" / "reference" / "composite_factor"


def _bucketize_by_date(df: pd.DataFrame, column: str, buckets: int, out_col: str) -> None:
    pct = df.groupby("trade_date")[column].transform(lambda s: s.rank(pct=True, method="average"))
    bucket = np.floor((pct.fillna(0.0) - 1e-9) * buckets).clip(0, buckets - 1)
    df[out_col] = np.where(pct.notna(), bucket, np.nan)


def _rank_within_group(df: pd.DataFrame, group_cols: list[str], column: str, out_col: str) -> None:
    df[out_col] = df.groupby(group_cols)[column].transform(lambda s: s.rank(pct=True, method="average"))


def add_multifactor_composite_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Build composite trading-factor signals from same-day and lagged fields only."""
    df = add_research_factors(panel.copy())

    for col in ["rs_20", "rs_60"]:
        if col in df.columns and f"{col}_z" not in df.columns:
            df[f"{col}_z"] = zscore_by_date(df, col)

    lowvol = -df["volatility_20_z"].fillna(0.0)
    lowcrowd = -df["volume_ma20_gap_z"].fillna(0.0)
    value = df["bp_z"].fillna(0.0)
    reversal = df["short_reversal_5_z"].fillna(0.0)
    compression = -df["range_compress_10_20_z"].fillna(0.0)
    breakout = df["breakout_20_z"].fillna(0.0)
    amount_expansion = df["amount_ratio_5_20_z"].fillna(0.0)
    close_strength = df["close_range_pos_z"].fillna(0.0)
    body = df["body_signed_z"].fillna(0.0)
    lower_shadow = df["lower_shadow_ratio_z"].fillna(0.0)
    upper_shadow = -df["upper_shadow_ratio_z"].fillna(0.0)
    midcap = df["mid_size_score_z"].fillna(0.0)
    small = -df["size_z"].fillna(0.0)
    liquidity = df["liquidity_z"].fillna(0.0)
    rs20 = df.get("rs_20_z", pd.Series(0.0, index=df.index)).fillna(0.0)
    rs60 = df.get("rs_60_z", pd.Series(0.0, index=df.index)).fillna(0.0)

    # Sequence family: require a specific multi-day path before ranking.
    df["mf301_seq_two_step_repair"] = np.where(
        (df["prev2_daily_ret"] < -0.05)
        & df["prev_daily_ret"].between(-0.02, 0.02)
        & (df["daily_ret"] > 0.01)
        & (df["close_range_pos"] > 0.58),
        -df["prev2_daily_ret_z"].fillna(0.0)
        + 0.45 * df["daily_ret_z"].fillna(0.0)
        + 0.30 * close_strength
        + 0.15 * lowcrowd
        + 0.10 * value,
        np.nan,
    )
    df["mf302_seq_breakout_retest_absorb"] = np.where(
        (df["recent_breakout_10"] > 0)
        & df["breakout_gap"].between(-0.03, 0.02)
        & (df["volume_ma20_gap"] < 0.15)
        & (df["close_range_pos"] > 0.55),
        df["breakout_retest_score_z"].fillna(0.0)
        + 0.30 * close_strength
        + 0.25 * lowcrowd
        + 0.25 * amount_expansion
        + 0.20 * value,
        np.nan,
    )
    df["mf303_seq_upper_shadow_repair_chain"] = np.where(
        (df["prev_upper_shadow_ratio"] > 0.35)
        & df["daily_ret"].between(-0.01, 0.03)
        & (df["close_range_pos"] > 0.58)
        & (df["volume_ma20_gap"] < 0.10),
        df["prev_upper_shadow_ratio_z"].fillna(0.0)
        + 0.35 * close_strength
        + 0.25 * lowcrowd
        + 0.20 * lowvol
        + 0.20 * value,
        np.nan,
    )
    df["mf304_seq_dryup_then_pivot"] = np.where(
        (df["prev_amount_ratio_5_20"] < 0)
        & (df["amount_ratio_5_20"] > 0)
        & df["daily_ret"].between(0.0, 0.04)
        & (df["close_range_pos"] > 0.60),
        0.35 * amount_expansion
        + 0.25 * close_strength
        + 0.20 * lowcrowd
        + 0.10 * reversal
        + 0.10 * value,
        np.nan,
    )

    # Conditional family: a base factor only activates inside a clearly specified state.
    df["mf351_cond_breakout_only_when_uncrowded"] = np.where(
        (df["breakout_20"] > 0)
        & (df["volume_ma20_gap"] < 0.20)
        & (df["big_up_count_5"] <= 1)
        & (df["upper_shadow_ratio"] < 0.35),
        0.35 * breakout + 0.25 * compression + 0.20 * lowcrowd + 0.20 * close_strength,
        np.nan,
    )
    df["mf352_cond_reversal_only_in_uptrend"] = np.where(
        (df["mom_20"] > 0)
        & (df["short_reversal_5"] > 0.02)
        & (df["above_ma20"] > -0.03),
        0.35 * reversal + 0.25 * value + 0.20 * lowcrowd + 0.20 * close_strength,
        np.nan,
    )
    df["mf353_cond_small_value_with_liquidity_turn"] = np.where(
        (small > 0)
        & (df["amount_ratio_5_20"] > 0)
        & (df["turnover_rel_20"] > -0.10),
        0.30 * small + 0.25 * value + 0.20 * amount_expansion + 0.15 * lowcrowd + 0.10 * liquidity,
        np.nan,
    )
    df["mf354_cond_cooling_breakout_resume"] = np.where(
        (df["mom_20"] > 0)
        & (df["crowding_mean_10_prev"] > 0)
        & (df["volume_ma20_gap"] < df["crowding_mean_10_prev"])
        & (df["above_ma20"] > 0)
        & (df["close_range_pos"] > 0.55),
        0.30 * lowcrowd + 0.25 * df["breakout_retest_score_z"].fillna(0.0) + 0.20 * df["above_ma20_z"].fillna(0.0) + 0.15 * amount_expansion + 0.10 * close_strength,
        np.nan,
    )

    # Relative family: score stocks relative to peers in the same bucket instead of absolute values.
    _bucketize_by_date(df, "size", 3, "size_bucket_3")
    _bucketize_by_date(df, "liquidity", 3, "liquidity_bucket_3")
    _bucketize_by_date(df, "volatility_20", 3, "vol_bucket_3")
    _bucketize_by_date(df, "mom_20", 5, "mom_bucket_5")

    df["mf401_relative_repair_size_raw"] = 0.35 * reversal + 0.25 * lowcrowd + 0.20 * value + 0.20 * close_strength
    df["mf402_relative_breakout_liquidity_raw"] = 0.35 * breakout + 0.25 * compression + 0.20 * close_strength + 0.20 * upper_shadow
    df["mf403_relative_resilience_momentum_raw"] = 0.30 * rs20 + 0.25 * lowcrowd + 0.20 * value + 0.15 * close_strength + 0.10 * rs60
    df["mf404_relative_midcap_quality_vol_raw"] = 0.30 * midcap + 0.25 * lowcrowd + 0.20 * value + 0.15 * lowvol + 0.10 * close_strength

    _rank_within_group(df, ["trade_date", "size_bucket_3"], "mf401_relative_repair_size_raw", "mf401_relative_repair_size_rank")
    _rank_within_group(df, ["trade_date", "liquidity_bucket_3"], "mf402_relative_breakout_liquidity_raw", "mf402_relative_breakout_liquidity_rank")
    _rank_within_group(df, ["trade_date", "mom_bucket_5"], "mf403_relative_resilience_momentum_raw", "mf403_relative_resilience_momentum_rank")
    _rank_within_group(df, ["trade_date", "vol_bucket_3"], "mf404_relative_midcap_quality_vol_raw", "mf404_relative_midcap_quality_vol_rank")

    df["mf401_relative_repair_in_size_bucket"] = np.where(
        df["mom_20"] > -0.10,
        df["mf401_relative_repair_size_rank"],
        np.nan,
    )
    df["mf402_relative_breakout_in_liquidity_bucket"] = np.where(
        (df["breakout_20"] > -0.02) & (df["close_range_pos"] > 0.50),
        df["mf402_relative_breakout_liquidity_rank"],
        np.nan,
    )
    df["mf403_relative_resilience_in_momentum_bucket"] = np.where(
        df["mom_20"] > -0.15,
        df["mf403_relative_resilience_momentum_rank"],
        np.nan,
    )
    df["mf404_relative_midcap_quality_in_vol_bucket"] = np.where(
        df["above_ma20"] > -0.05,
        df["mf404_relative_midcap_quality_vol_rank"],
        np.nan,
    )

    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "panel_rows": int(len(df)),
        "signal_cols": [
            "mf301_seq_two_step_repair",
            "mf302_seq_breakout_retest_absorb",
            "mf303_seq_upper_shadow_repair_chain",
            "mf304_seq_dryup_then_pivot",
            "mf351_cond_breakout_only_when_uncrowded",
            "mf352_cond_reversal_only_in_uptrend",
            "mf353_cond_small_value_with_liquidity_turn",
            "mf354_cond_cooling_breakout_resume",
            "mf401_relative_repair_in_size_bucket",
            "mf402_relative_breakout_in_liquidity_bucket",
            "mf403_relative_resilience_in_momentum_bucket",
            "mf404_relative_midcap_quality_in_vol_bucket",
        ],
    }
    (REFERENCE_DIR / "multifactor_composite_feature_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return df
