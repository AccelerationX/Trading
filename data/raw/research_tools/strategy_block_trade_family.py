from __future__ import annotations

from .backtester import StrategySpec


def build_block_trade_family_specs() -> list[StrategySpec]:
    return [
        StrategySpec("BT501_discount_repair_lowcrowding", "bt501_discount_repair_lowcrowding", "block trade discount repair low crowding", hold_days=6, top_n=8, keep_rank=12),
        StrategySpec("BT502_premium_follow_breakout", "bt502_premium_follow_breakout", "block trade premium follow breakout", hold_days=6, top_n=6, keep_rank=10),
        StrategySpec("BT503_large_block_absorption", "bt503_large_block_absorption", "large block absorption", hold_days=3, top_n=8, keep_rank=12),
        StrategySpec("BT504_discount_strong_industry", "bt504_discount_strong_industry", "discount block in strong industry", hold_days=6, top_n=6, keep_rank=10),
        StrategySpec("BT505_premium_midcap_strength", "bt505_premium_midcap_strength", "premium block midcap strength", hold_days=6, top_n=6, keep_rank=10),
        StrategySpec("BT506_large_discount_turnaround", "bt506_large_discount_turnaround", "large discount turnaround", hold_days=3, top_n=6, keep_rank=10),
    ]
