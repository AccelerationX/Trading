from __future__ import annotations

import numpy as np
import pandas as pd


def zscore_by_date(df: pd.DataFrame, column: str) -> pd.Series:
    grouped = df.groupby("trade_date")[column]
    mean = grouped.transform("mean")
    std = grouped.transform("std").replace(0.0, np.nan)
    return ((df[column] - mean) / std).replace([np.inf, -np.inf], np.nan)


def add_research_factors(panel: pd.DataFrame) -> pd.DataFrame:
    """Add first-pass no-lookahead factors.

    All features use same-day close or earlier data. Future execution columns
    may exist in the input panel, but they are not used here.
    """
    df = panel.copy().sort_values(["stock_code", "trade_date"])
    grouped = df.groupby("stock_code", group_keys=False)

    df["ret_3"] = df["close"] / grouped["close"].shift(3) - 1.0
    df["ret_1_reverse"] = -df["daily_ret"]
    df["ret_3_reverse"] = -df["ret_3"]

    df["amount_5"] = grouped["amount_k"].transform(lambda s: s.rolling(5, min_periods=3).mean())
    df["amount_20"] = grouped["amount_k"].transform(lambda s: s.rolling(20, min_periods=10).mean())
    df["turnover_5"] = grouped["turnover_pct"].transform(lambda s: s.rolling(5, min_periods=3).mean())
    df["turnover_10"] = grouped["turnover_pct"].transform(lambda s: s.rolling(10, min_periods=5).mean())
    df["free_turnover_5"] = grouped["free_turnover_pct"].transform(lambda s: s.rolling(5, min_periods=3).mean())
    df["free_turnover_20"] = grouped["free_turnover_pct"].transform(lambda s: s.rolling(20, min_periods=10).mean())
    df["volume_ratio_5"] = grouped["volume_ratio"].transform(lambda s: s.rolling(5, min_periods=3).mean())
    df["volume_ma20_gap"] = df["amount_k"] / df["amount_20"].replace(0.0, np.nan) - 1.0
    df["amount_ratio_5_20"] = df["amount_5"] / df["amount_20"].replace(0.0, np.nan) - 1.0
    df["turnover_rel_20"] = df["turnover_pct"] / df["turnover_20"].replace(0.0, np.nan) - 1.0
    df["turnover_compress_10_20"] = df["turnover_10"] / df["turnover_20"].replace(0.0, np.nan) - 1.0
    df["free_turnover_ratio_5_20"] = df["free_turnover_5"] / df["free_turnover_20"].replace(0.0, np.nan) - 1.0
    df["amount_trend_20_10"] = df["amount_20"] / grouped["amount_20"].shift(10).replace(0.0, np.nan) - 1.0
    df["turnover_20_med_60"] = grouped["turnover_20"].transform(lambda s: s.rolling(60, min_periods=20).median())
    df["liquidity_jump_vs_med60"] = df["turnover_pct"] / df["turnover_20_med_60"].replace(0.0, np.nan) - 1.0
    df["recent_breakout_10"] = grouped["breakout_20"].transform(lambda s: s.shift(1).rolling(10, min_periods=3).max())
    df["prior_high_20"] = grouped["high"].transform(lambda s: s.rolling(20, min_periods=20).max().shift(1))
    df["prior_low_10"] = grouped["low"].transform(lambda s: s.rolling(10, min_periods=10).min().shift(1))
    df["breakout_gap"] = df["close"] / df["prior_high_20"].replace(0.0, np.nan) - 1.0
    df["breakout_retest_score"] = -df["breakout_gap"].abs()
    df["price_hold_10"] = df["close"] / df["prior_low_10"].replace(0.0, np.nan) - 1.0
    df["gap_fill_ratio"] = np.where(
        df["gap_from_prev_close"] < 0,
        (df["close"] - df["open"]) / (df["prev_close"] - df["open"]).replace(0.0, np.nan),
        np.nan,
    )
    df["prev_daily_ret"] = grouped["daily_ret"].shift(1)
    df["prev2_daily_ret"] = grouped["daily_ret"].shift(2)
    df["prev_high"] = grouped["high"].shift(1)
    df["prev_low"] = grouped["low"].shift(1)
    df["prev_upper_shadow_ratio"] = grouped["upper_shadow_ratio"].shift(1)
    df["prev_volume_ratio"] = grouped["volume_ratio"].shift(1)
    df["prev_turnover_rel_20"] = grouped["turnover_rel_20"].shift(1)
    df["prev_amount_ratio_5_20"] = grouped["amount_ratio_5_20"].shift(1)
    df["inside_day_flag"] = (
        df["prev_high"].notna()
        & df["prev_low"].notna()
        & (df["high"] <= df["prev_high"])
        & (df["low"] >= df["prev_low"])
    ).astype(float)
    df["outside_day_flag"] = (
        df["prev_high"].notna()
        & df["prev_low"].notna()
        & (df["high"] >= df["prev_high"])
        & (df["low"] <= df["prev_low"])
    ).astype(float)
    df["small_loss_flag"] = df["daily_ret"].between(-0.03, 0.0, inclusive="left").astype(float)
    df["small_loss_count_4_prev"] = grouped["small_loss_flag"].transform(lambda s: s.shift(1).rolling(4, min_periods=2).sum())
    df["cum_ret_4_prev"] = grouped["daily_ret"].transform(lambda s: (1.0 + s).shift(1).rolling(4, min_periods=2).apply(np.prod, raw=True) - 1.0)
    df["crowding_mean_10_prev"] = grouped["volume_ma20_gap"].transform(lambda s: s.shift(1).rolling(10, min_periods=5).mean())

    df["ma20"] = grouped["close"].transform(lambda s: s.rolling(20, min_periods=20).mean())
    df["drawdown_20"] = df["close"] / grouped["close"].transform(lambda s: s.rolling(20, min_periods=10).max()) - 1.0
    df["above_ma20"] = df["close"] / df["ma20"].replace(0.0, np.nan) - 1.0
    df["close_range_pos"] = (df["close"] - df["low"]) / (df["high"] - df["low"]).replace(0.0, np.nan)
    df["body_signed"] = (df["close"] - df["open"]) / (df["high"] - df["low"]).replace(0.0, np.nan)
    df["big_up"] = (df["daily_ret"] > 0.05).astype(float)
    df["big_up_count_5"] = grouped["big_up"].transform(lambda s: s.rolling(5, min_periods=1).sum())
    df["near_limit_up_not_limit"] = np.where(
        df["current_limit_up"].notna() & (df["current_limit_up"] > 0),
        (df["close"] / df["current_limit_up"] >= 0.97) & (df["close"] < df["current_limit_up"]),
        False,
    ).astype(float)
    df["near_limit_down"] = np.where(
        df["current_limit_down"].notna() & (df["current_limit_down"] > 0),
        df["close"] <= df["current_limit_down"] * 1.01,
        False,
    ).astype(float)
    df["mid_size_score"] = -((df.groupby("trade_date")["size"].transform(lambda s: s.rank(pct=True, method="average")) - 0.50).abs())

    z_cols = [
        "ret_3_reverse",
        "mom_5",
        "mom_60",
        "amplitude_5",
        "ep_ttm",
        "turnover_rel_20",
        "turnover_compress_10_20",
        "free_turnover_ratio_5_20",
        "volume_ma20_gap",
        "volume_ratio_5",
        "amount_ratio_5_20",
        "amount_trend_20_10",
        "liquidity_jump_vs_med60",
        "breakout_retest_score",
        "price_hold_10",
        "gap_fill_ratio",
        "crowding_mean_10_prev",
        "prev2_daily_ret",
        "prev_upper_shadow_ratio",
        "bb_width_20",
        "daily_ret",
        "above_ma20",
        "close_range_pos",
        "body_signed",
        "big_up_count_5",
        "near_limit_up_not_limit",
        "near_limit_down",
        "mid_size_score",
        "inside_day_flag",
        "outside_day_flag",
        "small_loss_count_4_prev",
        "cum_ret_4_prev",
    ]
    for col in z_cols:
        if col in df.columns and f"{col}_z" not in df.columns:
            df[f"{col}_z"] = zscore_by_date(df, col)

    df["s01_mom20_lowvol"] = (
        df["mom_20_z"]
        - 0.60 * df["volatility_20_z"]
        + 0.20 * df["liquidity_z"]
    )
    df["s02_reversal5_liquidity"] = (
        df["short_reversal_5_z"]
        + 0.40 * df["lower_shadow_ratio_z"]
        + 0.20 * df["liquidity_z"]
        - 0.40 * df["volatility_20_z"]
    )
    df["s03_compression_breakout"] = (
        -df["range_compress_10_20_z"]
        + 0.70 * df["breakout_20_z"]
        + 0.40 * df["amount_ratio_5_20_z"]
        - 0.20 * df["volatility_20_z"]
    )
    df["s04_value_momentum"] = (
        df["bp_z"]
        + 0.50 * df["mom_20_z"]
        + 0.20 * df["liquidity_z"]
        - 0.20 * df["volatility_20_z"]
    )
    df["s05_small_liquidity_improve"] = (
        -df["size_z"]
        + 0.50 * df["amount_ratio_5_20_z"]
        + 0.20 * df["liquidity_z"]
    )
    df["s09_lowvol_value"] = (
        -df["volatility_20_z"]
        + 0.30 * df["bp_z"]
        + 0.20 * df["liquidity_z"]
        - 0.10 * df["size_z"]
    )
    df["legacy_core_alpha_no_lookahead"] = (
        df["bp_z"]
        + df["short_reversal_5_z"]
        - df["size_z"]
        - df["liquidity_z"]
    ) / 4.0

    volume_rank = df.groupby("trade_date")["volume_ma20_gap"].transform(lambda s: s.rank(pct=True, method="average"))
    range_rank = df.groupby("trade_date")["range_compress_10_20"].transform(lambda s: s.rank(pct=True, method="average"))
    line_a_filter = (volume_rank <= 0.60) & (range_rank <= 0.60)
    df["s10_line_a_compact"] = np.where(line_a_filter, df["legacy_core_alpha_no_lookahead"], np.nan)

    low_prior_crowding = grouped["volume_ma20_gap"].transform(lambda s: s.rolling(20, min_periods=10).mean()) < 0
    size_rank = df.groupby("trade_date")["size"].transform(lambda s: s.rank(pct=True, method="average"))
    mid_size_filter = size_rank.between(0.30, 0.70)
    value = df["bp_z"]
    reversal = df["short_reversal_5_z"]
    lowvol = -df["volatility_20_z"]
    lowcrowd = -df["volume_ma20_gap_z"]
    compression = -df["range_compress_10_20_z"]
    breakout = df["breakout_20_z"]
    amount_expansion = df["amount_ratio_5_20_z"]
    mom20_rank = df.groupby("trade_date")["mom_20"].transform(lambda s: s.rank(pct=True, method="average"))

    # Candidate lines S001-S058. Every signal below uses same-day or past data only.
    df["s001_5d_oversold_reversal"] = df["short_reversal_5_z"]
    df["s002_3d_panic_rebound"] = df["ret_3_reverse_z"]
    df["s003_oversold_lower_shadow"] = reversal + 0.50 * df["lower_shadow_ratio_z"]
    df["s004_oversold_volume_dryup"] = reversal + 0.50 * lowcrowd
    df["s005_value_oversold"] = reversal + 0.50 * value
    df["s006_oversold_with_breadth_gate"] = df["s001_5d_oversold_reversal"]
    df["s007_low_position_repair_continue"] = np.where(
        (df["mom_5"] > 0) & (mom20_rank < 0.80),
        df["mom_5_z"] - 0.50 * df["mom_20_z"],
        np.nan,
    )
    df["s008_line_a_low_crowding_compression"] = df["s10_line_a_compact"]
    df["s009_pure_range_compression_reversal"] = compression + 0.50 * reversal
    df["s010_low_crowding_lowvol"] = lowcrowd + lowvol
    df["s011_dryup_then_amount_expansion"] = np.where(low_prior_crowding, amount_expansion + 0.50 * lowcrowd, np.nan)
    df["s012_bollinger_width_contraction"] = -df["bb_width_20_z"] + 0.30 * df["above_ma20_z"]
    df["s013_compression_value"] = compression + 0.50 * value
    df["s014_compression_small_mid"] = compression - 0.50 * df["size_z"]
    df["s015_20d_breakout"] = breakout
    df["s016_breakout_with_amount"] = breakout + 0.50 * amount_expansion
    df["s017_lowvol_compression_breakout"] = breakout + 0.50 * lowvol + 0.50 * compression
    df["s018_ma20_reclaim"] = df["above_ma20_z"] + 0.50 * reversal
    df["s019_midterm_strong_shortterm_cool"] = df["mom_20_z"] - df["mom_5_z"].abs()
    df["s020_60d_trend_lowvol"] = df["mom_60_z"] + 0.50 * lowvol
    df["s021_inverse_momentum_validation"] = -df["mom_20_z"]
    df["s022_pure_lowvol"] = lowvol
    df["s023_lowvol_value"] = lowvol + 0.50 * value
    df["s024_lowvol_liquidity"] = lowvol + 0.30 * df["liquidity_z"]
    df["s025_low_amplitude_low_turnover"] = -df["amplitude_5_z"] - df["turnover_20_z"]
    df["s026_weak_market_defensive_switch"] = df["s023_lowvol_value"]
    df["s027_low_pb"] = value
    df["s028_low_pe_ttm"] = df["ep_ttm_z"]
    df["s029_low_value_lowvol"] = value + lowvol
    df["s030_value_amount_improve"] = value + 0.50 * amount_expansion
    df["s031_value_trend_repair"] = value + 0.50 * df["mom_20_z"]
    df["s032_value_oversold_repair"] = value + reversal
    df["s033_small_mainboard"] = -df["size_z"]
    df["s034_small_low_crowding"] = -df["size_z"] + lowcrowd
    df["s035_small_lowvol"] = -df["size_z"] + lowvol
    df["s036_small_value"] = -df["size_z"] + value
    df["s037_midcap_quality_proxy"] = df["mid_size_score_z"] + 0.50 * df["s023_lowvol_value"]
    df["s038_long_lower_shadow_repair"] = np.where(df["mom_5"] < 0, df["lower_shadow_ratio_z"] + 0.50 * reversal, np.nan)
    df["s039_avoid_upper_shadow"] = -df["upper_shadow_ratio_z"]
    df["s040_close_strength"] = df["close_range_pos_z"]
    df["s041_gap_down_recover"] = -df["gap_from_prev_close_z"] + df["lower_shadow_ratio_z"]
    df["s042_strong_body"] = df["body_signed_z"] + 0.50 * df["daily_ret_z"]
    df["s043_near_limit_up_not_limit"] = df["near_limit_up_not_limit_z"]
    df["s044_limit_up_nextday_repair"] = df["near_limit_up_not_limit_z"]
    df["s045_limit_down_open_repair"] = df["near_limit_down_z"]
    df["s046_avoid_consecutive_big_up"] = -df["big_up_count_5_z"]
    df["s052_reversal_lowvol_value"] = reversal + lowvol + value
    df["s053_compression_reversal_lowcrowding"] = reversal + compression + lowcrowd
    df["s054_breakout_lowcrowding"] = breakout + lowcrowd
    df["s055_defensive_core"] = value + lowvol - 0.10 * df["size_z"]
    df["s056_balanced_mainboard_alpha"] = (value + reversal + lowvol + lowcrowd - 0.30 * df["size_z"]) / 5.0
    df["s057_adaptive_reversal_breakout"] = df["s003_oversold_lower_shadow"]
    df["s058_defensive_aggressive_two_sleeve"] = 0.50 * df["s023_lowvol_value"] + 0.50 * df["s053_compression_reversal_lowcrowding"]
    df["s059_rank_buffer_hold"] = df["s008_line_a_low_crowding_compression"]
    df["s060_inverse_vol_weighting"] = df["s008_line_a_low_crowding_compression"]
    df["s061_equal_vs_signal_weight"] = df["s008_line_a_low_crowding_compression"]
    df["s062_cap_floor_weights"] = df["s008_line_a_low_crowding_compression"]
    df["s063_strategy_drawdown_pause"] = df["s008_line_a_low_crowding_compression"]
    df["s064_weak_market_deleverage"] = df["s008_line_a_low_crowding_compression"]
    df["s065_buy_blocked_reallocation"] = df["s008_line_a_low_crowding_compression"]
    df["s076_failed_breakout_nextday_stability"] = np.where(
        (df["recent_breakout_10"] > 0)
        & df["breakout_gap"].between(-0.03, 0.01)
        & (df["close_range_pos"] > 0.55),
        df["breakout_retest_score_z"] + 0.50 * df["close_range_pos_z"] - 0.30 * df["upper_shadow_ratio_z"] + 0.20 * lowcrowd,
        np.nan,
    )
    df["s077_high_open_not_followed_by_selloff"] = np.where(
        (df["gap_from_prev_close"] > 0.01)
        & (df["close_range_pos"] > 0.55)
        & (df["upper_shadow_ratio"] < 0.35)
        & (df["close"] >= df["open"] * 0.995),
        df["gap_from_prev_close_z"] + 0.50 * df["close_range_pos_z"] - 0.40 * df["upper_shadow_ratio_z"] + 0.20 * lowcrowd,
        np.nan,
    )
    df["s078_pullback_to_breakout_level"] = np.where(
        (df["recent_breakout_10"] > 0)
        & df["breakout_gap"].between(-0.05, 0.02)
        & (df["volume_ma20_gap"] < 0.20)
        & (df["above_ma20"] > -0.03),
        df["breakout_retest_score_z"] + 0.40 * lowcrowd + 0.30 * df["above_ma20_z"] + 0.20 * df["close_range_pos_z"],
        np.nan,
    )
    df["s079_false_breakdown_recovery"] = np.where(
        df["prior_low_10"].notna()
        & (df["low"] < df["prior_low_10"])
        & (df["close"] > df["prior_low_10"])
        & (df["close"] > df["open"]),
        df["lower_shadow_ratio_z"] + 0.50 * df["close_range_pos_z"] + 0.30 * reversal,
        np.nan,
    )
    df["s080_two_day_repair_after_large_drop"] = np.where(
        (df["prev2_daily_ret"] < -0.05)
        & (df["prev_daily_ret"].abs() < 0.02)
        & (df["daily_ret"] > 0.015)
        & (df["close_range_pos"] > 0.55),
        -df["prev2_daily_ret_z"] + 0.60 * df["daily_ret_z"] + 0.40 * df["close_range_pos_z"] + 0.20 * lowcrowd,
        np.nan,
    )
    df["s081_inside_day_after_panic"] = np.where(
        (df["prev_daily_ret"] < -0.04)
        & (df["inside_day_flag"] > 0.5)
        & (df["close_range_pos"] > 0.60)
        & (df["close"] >= df["open"]),
        0.60 * df["inside_day_flag_z"] + 0.50 * df["close_range_pos_z"] + 0.30 * df["body_signed_z"] + 0.20 * lowvol,
        np.nan,
    )
    df["s082_outside_day_reversal"] = np.where(
        (df["mom_5"] < 0)
        & (df["outside_day_flag"] > 0.5)
        & (df["close_range_pos"] > 0.65)
        & (df["close"] > df["open"]),
        0.60 * df["outside_day_flag_z"] + 0.50 * df["close_range_pos_z"] + 0.30 * df["lower_shadow_ratio_z"] + 0.20 * reversal,
        np.nan,
    )
    df["s083_down_gap_filled_quickly"] = np.where(
        (df["gap_from_prev_close"] < -0.01)
        & (df["gap_fill_ratio"] > 0.50)
        & (df["close"] > df["open"]),
        df["gap_fill_ratio_z"] + 0.40 * df["close_range_pos_z"] + 0.30 * df["lower_shadow_ratio_z"],
        np.nan,
    )
    df["s084_upper_shadow_repaired_nextday"] = np.where(
        (df["prev_upper_shadow_ratio"] > 0.40)
        & df["daily_ret"].between(-0.01, 0.03)
        & (df["close"] >= df["prev_close"] * 0.995)
        & (df["volume_ma20_gap"] < 0.10),
        +df["prev_upper_shadow_ratio_z"]
        + 0.50 * df["close_range_pos_z"]
        + 0.30 * lowcrowd
        + 0.20 * lowvol,
        np.nan,
    )
    df["s085_consecutive_small_loss_exhaustion"] = np.where(
        (df["small_loss_count_4_prev"] >= 3)
        & (df["cum_ret_4_prev"] < -0.03)
        & (df["daily_ret"] > 0.01)
        & (df["close_range_pos"] > 0.60),
        df["small_loss_count_4_prev_z"] - 0.30 * df["cum_ret_4_prev_z"] + 0.50 * df["close_range_pos_z"] + 0.30 * df["body_signed_z"],
        np.nan,
    )
    df["s086_turnover_drop_then_price_hold"] = np.where(
        (df["turnover_rel_20"] < 0)
        & (df["price_hold_10"] > 0)
        & (df["mom_20"] > -0.10),
        -df["turnover_rel_20_z"] + 0.40 * df["above_ma20_z"] + 0.30 * lowvol,
        np.nan,
    )
    df["s087_turnover_expand_without_price_spike"] = np.where(
        (df["turnover_rel_20"] > 0.10)
        & df["daily_ret"].between(-0.01, 0.04)
        & (df["close_range_pos"] > 0.55)
        & (df["near_limit_up_not_limit"] < 0.5),
        df["turnover_rel_20_z"] + 0.40 * df["close_range_pos_z"] + 0.20 * lowcrowd - 0.20 * df["daily_ret_z"].abs(),
        np.nan,
    )
    df["s088_free_turnover_ratio_improve"] = np.where(
        (df["free_turnover_ratio_5_20"] > 0)
        & (df["turnover_rel_20"] > -0.20)
        & (df["mom_5"] < 0.08),
        df["free_turnover_ratio_5_20_z"] + 0.30 * df["amount_trend_20_10_z"] + 0.20 * df["above_ma20_z"] + 0.20 * lowcrowd,
        np.nan,
    )
    df["s089_volume_ratio_repair"] = np.where(
        (df["prev_volume_ratio"] > 2.0)
        & df["volume_ratio"].between(0.8, 1.5)
        & (df["close"] >= df["open"]),
        -df["volume_ratio_5_z"].abs() + 0.50 * df["close_range_pos_z"] + 0.30 * df["body_signed_z"] + 0.20 * lowcrowd,
        np.nan,
    )
    df["s090_amount_expansion_close_strength"] = np.where(
        (df["volume_ma20_gap"] > 0)
        & (df["close_range_pos"] > 0.60)
        & (df["near_limit_up_not_limit"] < 0.5),
        df["volume_ma20_gap_z"] + 0.50 * df["close_range_pos_z"] + 0.20 * df["body_signed_z"],
        np.nan,
    )
    df["s091_amount_trend_positive_price_not_hot"] = np.where(
        (df["amount_trend_20_10"] > 0)
        & (df["mom_5"] < 0.08),
        df["amount_trend_20_10_z"] + 0.40 * df["mom_20_z"] + 0.20 * df["above_ma20_z"] - 0.20 * df["mom_5_z"].abs(),
        np.nan,
    )
    df["s092_liquidity_improving_lowvol"] = np.where(
        (df["amount_ratio_5_20"] > 0)
        & (df["turnover_rel_20"] > -0.10)
        & (df["volatility_20"] <= grouped["volatility_20"].transform(lambda s: s.rolling(60, min_periods=20).median())),
        0.60 * df["amount_ratio_5_20_z"] + 0.40 * df["turnover_rel_20_z"] + 0.50 * lowvol + 0.20 * df["bp_z"],
        np.nan,
    )
    df["s093_crowding_release_after_hot_period"] = np.where(
        (df["crowding_mean_10_prev"] > 0.20)
        & (df["volume_ma20_gap"] < df["crowding_mean_10_prev"])
        & (df["above_ma20"] > 0),
        df["crowding_mean_10_prev_z"] + 0.50 * lowcrowd + 0.30 * df["above_ma20_z"] + 0.20 * df["close_range_pos_z"],
        np.nan,
    )
    df["s094_illiquid_to_liquid_transition"] = np.where(
        (df["turnover_20"] < df["turnover_20_med_60"])
        & (df["liquidity_jump_vs_med60"] > 0.50)
        & df["daily_ret"].between(-0.02, 0.05)
        & (df["amount_ratio_5_20"] > 0),
        df["liquidity_jump_vs_med60_z"] + 0.40 * df["amount_ratio_5_20_z"] + 0.20 * df["close_range_pos_z"] + 0.20 * lowcrowd,
        np.nan,
    )
    df["s095_turnover_compression_breakout"] = np.where(
        (df["turnover_compress_10_20"] < 0)
        & (df["breakout_20"] > 0),
        -df["turnover_compress_10_20_z"] + 0.60 * breakout + 0.20 * df["close_range_pos_z"],
        np.nan,
    )

    market = (
        df.groupby("trade_date")
        .agg(
            breadth=("daily_ret", lambda s: float((s > 0).mean())),
            median_ret=("daily_ret", "median"),
            market_mom20=("mom_20", "mean"),
            positive_mom20=("mom_20", lambda s: float((s > 0).mean())),
            ew_ret=("daily_ret", "mean"),
            dispersion=("daily_ret", "std"),
        )
        .sort_index()
    )
    market["ew_nav"] = (1.0 + market["ew_ret"].fillna(0.0)).cumprod()
    market["ew_mom_5"] = market["ew_nav"] / market["ew_nav"].shift(5) - 1.0
    market["ew_mom_20"] = market["ew_nav"] / market["ew_nav"].shift(20) - 1.0
    market["ew_mom_60"] = market["ew_nav"] / market["ew_nav"].shift(60) - 1.0
    market["ew_drawdown_20"] = market["ew_nav"] / market["ew_nav"].rolling(20, min_periods=10).max() - 1.0
    market["breadth_20"] = market["breadth"].rolling(20, min_periods=10).mean()
    market["median_ret_20"] = market["median_ret"].rolling(20, min_periods=10).mean()
    market["dispersion_20"] = market["dispersion"].rolling(20, min_periods=10).mean()
    market["dispersion_med_120"] = market["dispersion_20"].rolling(120, min_periods=60).median()
    market["market_amount_ratio"] = (
        df.groupby("trade_date")["amount_k"].sum().sort_index()
        / df.groupby("trade_date")["amount_k"].sum().sort_index().rolling(20, min_periods=10).mean()
        - 1.0
    )
    small_ret = df.loc[size_rank <= 0.30].groupby("trade_date")["daily_ret"].mean().sort_index()
    large_ret = df.loc[size_rank >= 0.70].groupby("trade_date")["daily_ret"].mean().sort_index()
    style = pd.concat([small_ret.rename("small_ret"), large_ret.rename("large_ret")], axis=1)
    style["small_nav"] = (1.0 + style["small_ret"].fillna(0.0)).cumprod()
    style["large_nav"] = (1.0 + style["large_ret"].fillna(0.0)).cumprod()
    style["small_mom_20"] = style["small_nav"] / style["small_nav"].shift(20) - 1.0
    style["large_mom_20"] = style["large_nav"] / style["large_nav"].shift(20) - 1.0
    style["small_minus_large_20"] = style["small_mom_20"] - style["large_mom_20"]
    market = market.join(style[["small_mom_20", "large_mom_20", "small_minus_large_20"]], how="left")
    market["limit_down_ratio"] = df.groupby("trade_date")["near_limit_down"].mean().sort_index()
    market["risk_on_gate"] = (
        (market["breadth_20"] > 0.50)
        & (market["market_mom20"] > 0.0)
        & (market["positive_mom20"] > 0.45)
    )
    market["breadth_gate"] = market["breadth_20"] > 0.50
    market["median_return_gate"] = market["median_ret_20"] > 0.0
    market["amount_gate"] = market["market_amount_ratio"] > 0.0
    market["limit_down_safe_gate"] = market["limit_down_ratio"] < 0.03
    market["weak_market_gate"] = market["breadth_20"] < 0.45
    market["high_dispersion_gate"] = market["dispersion_20"] > market["dispersion_med_120"]
    market["small_style_gate"] = market["small_minus_large_20"] > 0.0
    market["crowded_market_gate"] = (
        (market["positive_mom20"] > 0.58)
        & (market["market_amount_ratio"] > 0.12)
        & (market["limit_down_ratio"] < 0.02)
    )
    market["shrinking_market_turnover_gate"] = (
        (market["market_amount_ratio"] > -0.03)
        & (market["market_amount_ratio"].shift(5) > market["market_amount_ratio"] - 0.08)
    )
    market["lowbreadth_defensive_gate"] = (
        (market["breadth_20"] < 0.46)
        | (market["median_ret_20"] < 0.0)
    )
    market["breadth_trend_exposure"] = np.select(
        [
            (market["breadth_20"] < 0.42) | (market["market_mom20"] < -0.02),
            (market["breadth_20"] < 0.48) | (market["market_mom20"] < 0.00),
            market["breadth_20"] < 0.54,
        ],
        [0.0, 0.35, 0.65],
        default=1.0,
    )
    market["limitdown_exposure"] = np.select(
        [
            market["limit_down_ratio"] > 0.06,
            market["limit_down_ratio"] > 0.04,
            market["limit_down_ratio"] > 0.025,
        ],
        [0.0, 0.35, 0.65],
        default=1.0,
    )
    market["breadth_improve_5"] = market["breadth_20"] - market["breadth_20"].shift(5)
    market["recent_panic_max_5"] = market["limit_down_ratio"].shift(1).rolling(5, min_periods=1).max()
    market["panic_release_gate"] = (
        (market["recent_panic_max_5"] > 0.04)
        & (market["breadth_20"] > 0.48)
        & (market["breadth_improve_5"] > 0.04)
    )
    market["combined_state_exposure"] = np.select(
        [
            (market["breadth_20"] < 0.42) | (market["market_amount_ratio"] < -0.08) | (market["limit_down_ratio"] > 0.05),
            (market["breadth_20"] < 0.48) | (market["market_amount_ratio"] < -0.02) | (market["limit_down_ratio"] > 0.03),
            market["crowded_market_gate"],
        ],
        [0.0, 0.35, 0.55],
        default=1.0,
    )
    df = df.merge(market.reset_index(), on="trade_date", how="left")

    df["rs_5"] = df["mom_5"] - df["ew_mom_5"]
    df["rs_20"] = df["mom_20"] - df["ew_mom_20"]
    df["rs_60"] = df["mom_60"] - df["ew_mom_60"]
    df["rs_accel_20_60"] = df["rs_20"] - df["rs_60"]
    df["relative_drawdown_20"] = df["drawdown_20"] - df["ew_drawdown_20"]
    for col in ["rs_5", "rs_20", "rs_60", "rs_accel_20_60", "relative_drawdown_20"]:
        df[f"{col}_z"] = zscore_by_date(df, col)

    # Regime and portfolio lines are materialized after the market snapshot is merged.
    df["s006_oversold_with_breadth_gate"] = np.where(
        df["breadth_gate"].fillna(False),
        df["s001_5d_oversold_reversal"],
        np.nan,
    )
    df["s026_weak_market_defensive_switch"] = np.where(
        df["weak_market_gate"].fillna(False),
        df["s023_lowvol_value"],
        np.nan,
    )
    df["s047_market_breadth_gate"] = np.where(
        df["breadth_gate"].fillna(False),
        df["s008_line_a_low_crowding_compression"],
        np.nan,
    )
    df["s048_median_return_trend_gate"] = np.where(
        df["median_return_gate"].fillna(False),
        df["s008_line_a_low_crowding_compression"],
        np.nan,
    )
    df["s049_market_amount_gate"] = np.where(
        df["amount_gate"].fillna(False),
        df["s008_line_a_low_crowding_compression"],
        np.nan,
    )
    df["s050_limit_down_temperature"] = np.where(
        df["limit_down_safe_gate"].fillna(False),
        df["s008_line_a_low_crowding_compression"],
        np.nan,
    )
    df["s051_mainboard_breadth_gate"] = np.where(
        df["risk_on_gate"].fillna(False),
        df["s008_line_a_low_crowding_compression"],
        np.nan,
    )
    df["s057_adaptive_reversal_breakout"] = np.where(
        df["risk_on_gate"].fillna(False),
        df["s017_lowvol_compression_breakout"],
        df["s003_oversold_lower_shadow"],
    )
    df["s064_weak_market_deleverage"] = np.where(
        df["risk_on_gate"].fillna(False),
        df["s008_line_a_low_crowding_compression"],
        np.nan,
    )
    df["s066_rs_vs_mainboard_index_20d"] = df["rs_20_z"] + 0.20 * lowvol
    df["s067_rs_vs_mainboard_index_60d_lowvol"] = df["rs_60_z"] + 0.50 * lowvol
    df["s068_shortterm_weak_midterm_strong_relative"] = np.where(
        df["rs_20"] > 0,
        df["rs_20_z"] - 0.50 * df["rs_5_z"].abs() + 0.20 * lowvol,
        np.nan,
    )
    df["s070_breakout_relative_to_index"] = np.where(
        df["breakout_20"] > 0,
        breakout + 0.70 * df["rs_20_z"] + 0.30 * df["rs_5_z"],
        np.nan,
    )
    df["s071_defensive_rs_in_weak_market"] = np.where(
        df["weak_market_gate"].fillna(False),
        df["rs_20_z"] + lowvol + 0.30 * value,
        np.nan,
    )
    df["s072_smallcap_rs_without_crowding"] = -df["size_z"] + df["rs_20_z"] + lowcrowd
    df["s073_relative_drawdown_shallow"] = df["relative_drawdown_20_z"] + 0.20 * lowvol
    df["s074_rs_acceleration_20_over_60"] = df["rs_accel_20_60_z"] + 0.20 * breakout
    df["s075_post_correction_relative_leader"] = np.where(
        (df["rs_20"] > 0) & df["mom_5"].between(-0.12, 0.05),
        df["rs_20_z"] - 0.40 * df["mom_5_z"].abs() + 0.30 * df["close_range_pos_z"] + 0.20 * lowcrowd,
        np.nan,
    )
    df["s106_breadth_trend_exposure_ladder"] = df["s056_balanced_mainboard_alpha"]
    df["s107_limitdown_temperature_exposure_ladder"] = df["s056_balanced_mainboard_alpha"]
    df["s108_median_stock_state_switch"] = np.where(
        df["median_return_gate"].fillna(False),
        df["s017_lowvol_compression_breakout"],
        df["s052_reversal_lowvol_value"],
    )
    df["s109_crowded_market_avoidance"] = np.where(
        ~df["crowded_market_gate"].fillna(False),
        df["s054_breakout_lowcrowding"],
        np.nan,
    )
    df["s110_shrinking_market_turnover_pause"] = np.where(
        df["shrinking_market_turnover_gate"].fillna(False),
        df["s056_balanced_mainboard_alpha"],
        np.nan,
    )
    df["s111_market_dispersion_signal"] = np.where(
        df["high_dispersion_gate"].fillna(False),
        df["s052_reversal_lowvol_value"],
        df["s017_lowvol_compression_breakout"],
    )
    df["s112_style_rotation_small_vs_large"] = np.where(
        df["small_style_gate"].fillna(False),
        df["s034_small_low_crowding"],
        df["s023_lowvol_value"],
    )
    df["_s008_core_z"] = zscore_by_date(df, "s008_line_a_low_crowding_compression")
    df["_s023_core_z"] = zscore_by_date(df, "s023_lowvol_value")
    df["_s052_core_z"] = zscore_by_date(df, "s052_reversal_lowvol_value")
    df["_s056_core_z"] = zscore_by_date(df, "s056_balanced_mainboard_alpha")
    df["_s073_core_z"] = zscore_by_date(df, "s073_relative_drawdown_shallow")
    df["s121_line_a_relative_drawdown_blend"] = 0.70 * df["_s008_core_z"] + 0.30 * df["_s073_core_z"]
    df["s122_line_a_dispersion_switch"] = np.where(
        df["high_dispersion_gate"].fillna(False),
        df["_s052_core_z"],
        df["_s008_core_z"],
    )
    df["s123_balanced_relative_drawdown_blend"] = 0.50 * df["_s056_core_z"] + 0.50 * df["_s073_core_z"]
    df["s124_line_a_limitdown_relative"] = 0.60 * df["_s008_core_z"] + 0.25 * df["_s073_core_z"] + 0.15 * lowvol
    df["s125_regime_relative_resilience"] = np.where(
        df["weak_market_gate"].fillna(False),
        df["_s023_core_z"] + 0.30 * df["_s073_core_z"],
        0.75 * df["_s008_core_z"] + 0.25 * df["_s073_core_z"],
    )
    df["_phase2_offensive"] = df["s008_line_a_low_crowding_compression"].fillna(df["s053_compression_reversal_lowcrowding"])
    df["_phase2_defensive"] = df["s023_lowvol_value"]
    df["_phase2_offensive_z"] = zscore_by_date(df, "_phase2_offensive")
    df["_phase2_defensive_z"] = zscore_by_date(df, "_phase2_defensive")
    df["s113_defensive_offensive_blend_dynamic"] = (
        (1.0 - df["breadth_trend_exposure"].fillna(0.0)) * df["_phase2_defensive_z"]
        + df["breadth_trend_exposure"].fillna(0.0) * df["_phase2_offensive_z"]
    )
    df["s114_risk_on_after_panic_release"] = np.where(
        df["panic_release_gate"].fillna(False),
        df["s053_compression_reversal_lowcrowding"] + 0.30 * df["s003_oversold_lower_shadow"],
        np.nan,
    )
    df["s115_lowbreadth_select_only_defensive_value"] = np.where(
        df["lowbreadth_defensive_gate"].fillna(False),
        df["s055_defensive_core"],
        np.nan,
    )
    df["m201_reversal_vs_breakout_switch_by_crowding"] = np.where(
        df["crowded_market_gate"].fillna(False),
        df["s052_reversal_lowvol_value"],
        df["s054_breakout_lowcrowding"],
    )
    df["m202_exposure_ladder_by_combined_state"] = df["s056_balanced_mainboard_alpha"]
    df = df.drop(
        columns=[
            "_s008_core_z",
            "_s023_core_z",
            "_s052_core_z",
            "_s056_core_z",
            "_s073_core_z",
            "_phase2_offensive",
            "_phase2_defensive",
            "_phase2_offensive_z",
            "_phase2_defensive_z",
        ]
    )
    return df


FACTOR_SPECS = [
    ("S01", "s01_mom20_lowvol", "20d momentum + low volatility"),
    ("S02", "s02_reversal5_liquidity", "5d reversal + liquidity"),
    ("S03", "s03_compression_breakout", "compression + volume breakout"),
    ("S04", "s04_value_momentum", "value + momentum improvement"),
    ("S05", "s05_small_liquidity_improve", "small size + liquidity improvement"),
    ("S09", "s09_lowvol_value", "low volatility + value"),
    ("S10", "s10_line_a_compact", "legacy Line A idea rebuilt without lookahead"),
]
