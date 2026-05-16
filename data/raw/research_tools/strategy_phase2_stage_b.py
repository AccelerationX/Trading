from __future__ import annotations

from .backtester import StrategySpec


def build_phase2_stage_b_specs() -> list[StrategySpec]:
    specs = [
        StrategySpec("S066_rs_vs_mainboard_index_20d", "s066_rs_vs_mainboard_index_20d", "20d relative strength vs internal main-board benchmark", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S067_rs_vs_mainboard_index_60d_lowvol", "s067_rs_vs_mainboard_index_60d_lowvol", "60d relative strength with low volatility", hold_days=20, top_n=20, keep_rank=30),
        StrategySpec("S068_shortterm_weak_midterm_strong_relative", "s068_shortterm_weak_midterm_strong_relative", "relative leader after short-term cooling", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S070_breakout_relative_to_index", "s070_breakout_relative_to_index", "breakout with internal benchmark-relative strength", hold_days=6, top_n=10, keep_rank=15),
        StrategySpec("S071_defensive_rs_in_weak_market", "s071_defensive_rs_in_weak_market", "defensive relative strength in weak market", hold_days=10, top_n=20, keep_rank=30),
        StrategySpec("S072_smallcap_rs_without_crowding", "s072_smallcap_rs_without_crowding", "small-cap relative strength without crowding", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S073_relative_drawdown_shallow", "s073_relative_drawdown_shallow", "shallower drawdown than internal benchmark", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S074_rs_acceleration_20_over_60", "s074_rs_acceleration_20_over_60", "relative-strength acceleration", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S075_post_correction_relative_leader", "s075_post_correction_relative_leader", "relative leader after correction", hold_days=6, top_n=10, keep_rank=15),
        StrategySpec("S111_market_dispersion_signal", "s111_market_dispersion_signal", "switch by market dispersion", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S112_style_rotation_small_vs_large", "s112_style_rotation_small_vs_large", "switch by internal small-vs-large style trend", hold_days=10, top_n=20, keep_rank=30),
    ]
    if len(specs) != 11:
        raise RuntimeError(f"Expected 11 phase-2 stage-B specs, got {len(specs)}")
    return specs
