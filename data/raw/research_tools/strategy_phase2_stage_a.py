from __future__ import annotations

from .backtester import StrategySpec


def build_phase2_stage_a_specs() -> list[StrategySpec]:
    specs = [
        StrategySpec("S076_failed_breakout_nextday_stability", "s076_failed_breakout_nextday_stability", "failed breakout followed by stability", hold_days=6, top_n=10, keep_rank=15),
        StrategySpec("S078_pullback_to_breakout_level", "s078_pullback_to_breakout_level", "pullback to recent breakout level", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S079_false_breakdown_recovery", "s079_false_breakdown_recovery", "false breakdown and recovery", hold_days=3, top_n=10, keep_rank=15),
        StrategySpec("S083_down_gap_filled_quickly", "s083_down_gap_filled_quickly", "down-gap quickly filled", hold_days=3, top_n=10, keep_rank=15),
        StrategySpec("S086_turnover_drop_then_price_hold", "s086_turnover_drop_then_price_hold", "turnover drops while price holds", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S090_amount_expansion_close_strength", "s090_amount_expansion_close_strength", "amount expansion with close strength", hold_days=6, top_n=10, keep_rank=15),
        StrategySpec("S091_amount_trend_positive_price_not_hot", "s091_amount_trend_positive_price_not_hot", "positive amount trend without overheating", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S093_crowding_release_after_hot_period", "s093_crowding_release_after_hot_period", "crowding release after hot period", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S095_turnover_compression_breakout", "s095_turnover_compression_breakout", "turnover compression breakout", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S106_breadth_trend_exposure_ladder", "s106_breadth_trend_exposure_ladder", "balanced alpha with breadth exposure ladder", hold_days=10, top_n=10, keep_rank=15, exposure_col="breadth_trend_exposure"),
        StrategySpec("S107_limitdown_temperature_exposure_ladder", "s107_limitdown_temperature_exposure_ladder", "balanced alpha with limit-down exposure ladder", hold_days=10, top_n=10, keep_rank=15, exposure_col="limitdown_exposure"),
        StrategySpec("S108_median_stock_state_switch", "s108_median_stock_state_switch", "switch between trend and reversal by median-stock state", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S113_defensive_offensive_blend_dynamic", "s113_defensive_offensive_blend_dynamic", "dynamic defensive-offensive blend", hold_days=10, top_n=20, keep_rank=30, weighting="signal", exposure_col="breadth_trend_exposure"),
        StrategySpec("S114_risk_on_after_panic_release", "s114_risk_on_after_panic_release", "risk-on after panic release", hold_days=6, top_n=10, keep_rank=15),
    ]
    if len(specs) != 14:
        raise RuntimeError(f"Expected 14 phase-2 stage-A specs, got {len(specs)}")
    return specs
