from __future__ import annotations

from .backtester import StrategySpec


def build_multifactor_composite_specs() -> list[StrategySpec]:
    return [
        StrategySpec("MF301_seq_two_step_repair", "mf301_seq_two_step_repair", "two-step repair sequence", hold_days=6, top_n=8, keep_rank=12),
        StrategySpec("MF302_seq_breakout_retest_absorb", "mf302_seq_breakout_retest_absorb", "breakout retest absorption sequence", hold_days=6, top_n=8, keep_rank=12),
        StrategySpec("MF303_seq_upper_shadow_repair_chain", "mf303_seq_upper_shadow_repair_chain", "upper-shadow repair chain", hold_days=3, top_n=8, keep_rank=12),
        StrategySpec("MF304_seq_dryup_then_pivot", "mf304_seq_dryup_then_pivot", "dry-up then pivot sequence", hold_days=6, top_n=8, keep_rank=12),
        StrategySpec("MF351_cond_breakout_only_when_uncrowded", "mf351_cond_breakout_only_when_uncrowded", "conditional breakout only when uncrowded", hold_days=6, top_n=8, keep_rank=12),
        StrategySpec("MF352_cond_reversal_only_in_uptrend", "mf352_cond_reversal_only_in_uptrend", "conditional reversal only in uptrend", hold_days=6, top_n=8, keep_rank=12),
        StrategySpec("MF353_cond_small_value_with_liquidity_turn", "mf353_cond_small_value_with_liquidity_turn", "conditional small value with liquidity turn", hold_days=10, top_n=8, keep_rank=12),
        StrategySpec("MF354_cond_cooling_breakout_resume", "mf354_cond_cooling_breakout_resume", "conditional cooling breakout resume", hold_days=6, top_n=8, keep_rank=12),
        StrategySpec("MF401_relative_repair_in_size_bucket", "mf401_relative_repair_in_size_bucket", "relative repair in size bucket", hold_days=10, top_n=8, keep_rank=12),
        StrategySpec("MF402_relative_breakout_in_liquidity_bucket", "mf402_relative_breakout_in_liquidity_bucket", "relative breakout in liquidity bucket", hold_days=6, top_n=8, keep_rank=12),
        StrategySpec("MF403_relative_resilience_in_momentum_bucket", "mf403_relative_resilience_in_momentum_bucket", "relative resilience in momentum bucket", hold_days=10, top_n=8, keep_rank=12),
        StrategySpec("MF404_relative_midcap_quality_in_vol_bucket", "mf404_relative_midcap_quality_in_vol_bucket", "relative midcap quality in vol bucket", hold_days=10, top_n=8, keep_rank=12),
    ]
