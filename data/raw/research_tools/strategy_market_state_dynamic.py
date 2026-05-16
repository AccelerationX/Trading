from __future__ import annotations

from .backtester import StrategySpec


def build_market_state_dynamic_specs() -> list[StrategySpec]:
    return [
        StrategySpec("S109_crowded_market_avoidance", "s109_crowded_market_avoidance", "avoid breakout sleeve in crowded market", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S110_shrinking_market_turnover_pause", "s110_shrinking_market_turnover_pause", "pause aggressive sleeve when turnover shrinks", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S115_lowbreadth_select_only_defensive_value", "s115_lowbreadth_select_only_defensive_value", "defensive value only in low-breadth market", hold_days=20, top_n=20, keep_rank=30),
        StrategySpec("M201_reversal_vs_breakout_switch_by_crowding", "m201_reversal_vs_breakout_switch_by_crowding", "reversal vs breakout switch by crowding state", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("M202_exposure_ladder_by_combined_state", "m202_exposure_ladder_by_combined_state", "exposure ladder by combined breadth turnover limit-down state", hold_days=10, top_n=10, keep_rank=15, exposure_col="combined_state_exposure"),
    ]
