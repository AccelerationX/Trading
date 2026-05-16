from __future__ import annotations

from .backtester import StrategySpec


def build_phase2_stage_a_remaining_specs() -> list[StrategySpec]:
    specs = [
        StrategySpec("S077_high_open_not_followed_by_selloff", "s077_high_open_not_followed_by_selloff", "high open without immediate selloff", hold_days=6, top_n=10, keep_rank=15),
        StrategySpec("S080_two_day_repair_after_large_drop", "s080_two_day_repair_after_large_drop", "two-day repair after large drop", hold_days=6, top_n=10, keep_rank=15),
        StrategySpec("S081_inside_day_after_panic", "s081_inside_day_after_panic", "inside day after panic bar", hold_days=3, top_n=10, keep_rank=15),
        StrategySpec("S082_outside_day_reversal", "s082_outside_day_reversal", "outside-day reversal after decline", hold_days=3, top_n=10, keep_rank=15),
        StrategySpec("S084_upper_shadow_repaired_nextday", "s084_upper_shadow_repaired_nextday", "upper shadow repaired next day", hold_days=6, top_n=10, keep_rank=15),
        StrategySpec("S085_consecutive_small_loss_exhaustion", "s085_consecutive_small_loss_exhaustion", "consecutive small-loss exhaustion", hold_days=6, top_n=10, keep_rank=15),
        StrategySpec("S087_turnover_expand_without_price_spike", "s087_turnover_expand_without_price_spike", "turnover expansion without price spike", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S088_free_turnover_ratio_improve", "s088_free_turnover_ratio_improve", "free-turnover ratio improvement", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S089_volume_ratio_repair", "s089_volume_ratio_repair", "volume-ratio repair after panic spike", hold_days=6, top_n=10, keep_rank=15),
        StrategySpec("S092_liquidity_improving_lowvol", "s092_liquidity_improving_lowvol", "liquidity improving with low volatility", hold_days=20, top_n=20, keep_rank=30),
        StrategySpec("S094_illiquid_to_liquid_transition", "s094_illiquid_to_liquid_transition", "illiquid-to-liquid transition", hold_days=10, top_n=10, keep_rank=15),
    ]
    if len(specs) != 11:
        raise RuntimeError(f"Expected 11 phase-2 remaining specs, got {len(specs)}")
    return specs
