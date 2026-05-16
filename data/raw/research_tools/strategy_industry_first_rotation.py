from __future__ import annotations

from .backtester import StrategySpec


def build_industry_first_rotation_specs() -> list[StrategySpec]:
    return [
        StrategySpec("S096_industry_relative_strength_leader", "s096_industry_relative_strength_leader", "industry-first relative-strength leader", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S097_industry_improving_stock_not_yet_hot", "s097_industry_improving_stock_not_yet_hot", "improving industry with lagging-but-repairing stock", hold_days=6, top_n=10, keep_rank=15),
        StrategySpec("S098_weak_industry_avoidance_overlay", "s098_weak_industry_avoidance_overlay", "Line A style overlay removing weak industries", hold_days=10, top_n=8, keep_rank=12),
        StrategySpec("S099_industry_breadth_expansion", "s099_industry_breadth_expansion", "industry breadth expansion leader", hold_days=6, top_n=10, keep_rank=15),
        StrategySpec("S100_industry_amount_share_gain", "s100_industry_amount_share_gain", "industry amount-share gain", hold_days=6, top_n=10, keep_rank=15),
        StrategySpec("S101_strong_industry_lowvol_stock", "s101_strong_industry_lowvol_stock", "strong industry low-vol stock", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S102_strong_industry_breakout_retest", "s102_strong_industry_breakout_retest", "strong-industry breakout retest", hold_days=6, top_n=10, keep_rank=15),
        StrategySpec("S103_industry_reversal_after_extreme_weakness", "s103_industry_reversal_after_extreme_weakness", "industry reversal after extreme weakness", hold_days=3, top_n=10, keep_rank=15),
        StrategySpec("S104_leader_industry_midcap_bias", "s104_leader_industry_midcap_bias", "leader industry with midcap bias", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S105_avoid_overcrowded_industry_breakouts", "s105_avoid_overcrowded_industry_breakouts", "avoid overcrowded industry breakouts", hold_days=6, top_n=10, keep_rank=15),
    ]
