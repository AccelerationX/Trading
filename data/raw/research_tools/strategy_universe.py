from __future__ import annotations

from .backtester import StrategySpec


def build_strategy_specs() -> list[StrategySpec]:
    """Return the executable 65-line research universe.

    The signal columns are produced by ``research.tools.factors``. All signals
    are snapshot-date features; future execution fields are only consumed by the
    backtester after a rebalance date is fixed.
    """
    specs = [
        StrategySpec("S001_5d_oversold_reversal", "s001_5d_oversold_reversal", "5d oversold reversal", hold_days=6, top_n=10, keep_rank=15),
        StrategySpec("S002_3d_panic_rebound", "s002_3d_panic_rebound", "3d panic rebound", hold_days=3, top_n=10, keep_rank=15),
        StrategySpec("S003_oversold_lower_shadow", "s003_oversold_lower_shadow", "oversold with lower shadow support", hold_days=6, top_n=10, keep_rank=15),
        StrategySpec("S004_oversold_volume_dryup", "s004_oversold_volume_dryup", "oversold and volume dry-up", hold_days=6, top_n=10, keep_rank=15),
        StrategySpec("S005_value_oversold", "s005_value_oversold", "value plus oversold repair", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S006_oversold_with_breadth_gate", "s006_oversold_with_breadth_gate", "oversold reversal gated by market breadth", hold_days=6, top_n=10, keep_rank=15),
        StrategySpec("S007_low_position_repair_continue", "s007_low_position_repair_continue", "low-position repair continuation", hold_days=6, top_n=10, keep_rank=15),
        StrategySpec("S008_line_a_low_crowding_compression", "s008_line_a_low_crowding_compression", "legacy Line A rebuilt without lookahead", hold_days=10, top_n=8, keep_rank=12),
        StrategySpec("S009_pure_range_compression_reversal", "s009_pure_range_compression_reversal", "range compression plus reversal", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S010_low_crowding_lowvol", "s010_low_crowding_lowvol", "low crowding and low volatility", hold_days=10, top_n=20, keep_rank=30),
        StrategySpec("S011_dryup_then_amount_expansion", "s011_dryup_then_amount_expansion", "prior dry-up followed by amount expansion", hold_days=6, top_n=10, keep_rank=15),
        StrategySpec("S012_bollinger_width_contraction", "s012_bollinger_width_contraction", "Bollinger width contraction", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S013_compression_value", "s013_compression_value", "compression plus value", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S014_compression_small_mid", "s014_compression_small_mid", "compression with small-mid elasticity", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S015_20d_breakout", "s015_20d_breakout", "20d breakout", hold_days=6, top_n=10, keep_rank=15),
        StrategySpec("S016_breakout_with_amount", "s016_breakout_with_amount", "breakout confirmed by amount expansion", hold_days=6, top_n=10, keep_rank=15),
        StrategySpec("S017_lowvol_compression_breakout", "s017_lowvol_compression_breakout", "low-vol compression breakout", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S018_ma20_reclaim", "s018_ma20_reclaim", "MA20 reclaim repair", hold_days=6, top_n=10, keep_rank=15),
        StrategySpec("S019_midterm_strong_shortterm_cool", "s019_midterm_strong_shortterm_cool", "midterm strength with short-term cooling", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S020_60d_trend_lowvol", "s020_60d_trend_lowvol", "60d trend with low volatility", hold_days=20, top_n=20, keep_rank=30),
        StrategySpec("S021_inverse_momentum_validation", "s021_inverse_momentum_validation", "inverse 20d momentum validation", hold_days=10, top_n=20, keep_rank=30),
        StrategySpec("S022_pure_lowvol", "s022_pure_lowvol", "pure low volatility", hold_days=20, top_n=30, keep_rank=45),
        StrategySpec("S023_lowvol_value", "s023_lowvol_value", "low volatility plus value", hold_days=20, top_n=30, keep_rank=45),
        StrategySpec("S024_lowvol_liquidity", "s024_lowvol_liquidity", "low volatility plus liquidity", hold_days=20, top_n=30, keep_rank=45),
        StrategySpec("S025_low_amplitude_low_turnover", "s025_low_amplitude_low_turnover", "low amplitude and low turnover", hold_days=20, top_n=30, keep_rank=45),
        StrategySpec("S026_weak_market_defensive_switch", "s026_weak_market_defensive_switch", "weak-market defensive switch", hold_days=20, top_n=30, keep_rank=45),
        StrategySpec("S027_low_pb", "s027_low_pb", "low PB value", hold_days=20, top_n=30, keep_rank=45),
        StrategySpec("S028_low_pe_ttm", "s028_low_pe_ttm", "low PE TTM value proxy", hold_days=20, top_n=30, keep_rank=45),
        StrategySpec("S029_low_value_lowvol", "s029_low_value_lowvol", "value plus low volatility", hold_days=20, top_n=30, keep_rank=45),
        StrategySpec("S030_value_amount_improve", "s030_value_amount_improve", "value with amount improvement", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S031_value_trend_repair", "s031_value_trend_repair", "value trend repair", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S032_value_oversold_repair", "s032_value_oversold_repair", "value oversold repair", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S033_small_mainboard", "s033_small_mainboard", "main-board small-size premium", hold_days=20, top_n=30, keep_rank=45),
        StrategySpec("S034_small_low_crowding", "s034_small_low_crowding", "small size with low crowding", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S035_small_lowvol", "s035_small_lowvol", "small size with low volatility", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S036_small_value", "s036_small_value", "small value", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S037_midcap_quality_proxy", "s037_midcap_quality_proxy", "mid-cap defensive quality proxy", hold_days=20, top_n=30, keep_rank=45),
        StrategySpec("S038_long_lower_shadow_repair", "s038_long_lower_shadow_repair", "long lower-shadow repair", hold_days=3, top_n=10, keep_rank=15),
        StrategySpec("S039_avoid_upper_shadow", "s039_avoid_upper_shadow", "avoid upper-shadow pressure", hold_days=3, top_n=10, keep_rank=15),
        StrategySpec("S040_close_strength", "s040_close_strength", "close strength in daily range", hold_days=3, top_n=10, keep_rank=15),
        StrategySpec("S041_gap_down_recover", "s041_gap_down_recover", "gap-down recovery", hold_days=3, top_n=10, keep_rank=15),
        StrategySpec("S042_strong_body", "s042_strong_body", "strong candle body", hold_days=3, top_n=10, keep_rank=15),
        StrategySpec("S043_near_limit_up_not_limit", "s043_near_limit_up_not_limit", "near limit-up but not sealed", hold_days=3, top_n=10, keep_rank=15),
        StrategySpec("S044_limit_up_nextday_repair", "s044_limit_up_nextday_repair", "daily proxy for limit-up next-day repair", hold_days=3, top_n=5, keep_rank=8),
        StrategySpec("S045_limit_down_open_repair", "s045_limit_down_open_repair", "daily proxy for limit-down repair", hold_days=3, top_n=5, keep_rank=8),
        StrategySpec("S046_avoid_consecutive_big_up", "s046_avoid_consecutive_big_up", "avoid consecutive big-up overheating", hold_days=6, top_n=10, keep_rank=15),
        StrategySpec("S047_market_breadth_gate", "s047_market_breadth_gate", "Line A under breadth gate", hold_days=10, top_n=8, keep_rank=12),
        StrategySpec("S048_median_return_trend_gate", "s048_median_return_trend_gate", "Line A under median-return trend gate", hold_days=10, top_n=8, keep_rank=12),
        StrategySpec("S049_market_amount_gate", "s049_market_amount_gate", "Line A under market-amount gate", hold_days=10, top_n=8, keep_rank=12),
        StrategySpec("S050_limit_down_temperature", "s050_limit_down_temperature", "Line A under limit-down temperature gate", hold_days=10, top_n=8, keep_rank=12),
        StrategySpec("S051_mainboard_breadth_gate", "s051_mainboard_breadth_gate", "Line A under main-board risk-on gate", hold_days=10, top_n=8, keep_rank=12),
        StrategySpec("S052_reversal_lowvol_value", "s052_reversal_lowvol_value", "reversal plus low volatility and value", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S053_compression_reversal_lowcrowding", "s053_compression_reversal_lowcrowding", "compression reversal with low crowding", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S054_breakout_lowcrowding", "s054_breakout_lowcrowding", "breakout with low crowding", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S055_defensive_core", "s055_defensive_core", "defensive value-lowvol core", hold_days=20, top_n=30, keep_rank=45),
        StrategySpec("S056_balanced_mainboard_alpha", "s056_balanced_mainboard_alpha", "balanced main-board alpha", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S057_adaptive_reversal_breakout", "s057_adaptive_reversal_breakout", "regime-adaptive reversal or breakout", hold_days=6, top_n=10, keep_rank=15),
        StrategySpec("S058_defensive_aggressive_two_sleeve", "s058_defensive_aggressive_two_sleeve", "defensive and aggressive two-sleeve blend", hold_days=10, top_n=20, keep_rank=30),
        StrategySpec("S059_rank_buffer_hold", "s059_rank_buffer_hold", "Line A with wider rank buffer", hold_days=10, top_n=8, keep_rank=16),
        StrategySpec("S060_inverse_vol_weighting", "s060_inverse_vol_weighting", "Line A with inverse-volatility weighting", hold_days=10, top_n=8, keep_rank=12, weighting="inverse_vol"),
        StrategySpec("S061_equal_vs_signal_weight", "s061_equal_vs_signal_weight", "Line A with signal-strength weighting", hold_days=10, top_n=8, keep_rank=12, weighting="signal"),
        StrategySpec("S062_cap_floor_weights", "s062_cap_floor_weights", "Line A with capped and floored signal weights", hold_days=10, top_n=8, keep_rank=12, weighting="signal_cap_floor", weight_floor=0.05, weight_cap=0.20),
        StrategySpec("S063_strategy_drawdown_pause", "s063_strategy_drawdown_pause", "Line A with recent drawdown pause", hold_days=10, top_n=8, keep_rank=12, drawdown_pause=True),
        StrategySpec("S064_weak_market_deleverage", "s064_weak_market_deleverage", "Line A risk-on exposure gate", hold_days=10, top_n=8, keep_rank=12, market_gate_col="risk_on_gate"),
        StrategySpec("S065_buy_blocked_reallocation", "s065_buy_blocked_reallocation", "Line A with blocked-buy reallocation", hold_days=10, top_n=8, keep_rank=12, replace_blocked_buys=True),
    ]
    if len(specs) != 65:
        raise RuntimeError(f"Expected 65 strategy specs, got {len(specs)}")
    return specs
