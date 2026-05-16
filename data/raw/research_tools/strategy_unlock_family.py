from __future__ import annotations

from .backtester import StrategySpec


def build_unlock_family_specs() -> list[StrategySpec]:
    return [
        StrategySpec("SF601_small_unlock_absorbed", "sf601_small_unlock_absorbed", "small unlock absorbed", hold_days=6, top_n=8, keep_rank=12),
        StrategySpec("SF602_large_unlock_overreaction_repair", "sf602_large_unlock_overreaction_repair", "large unlock overreaction repair", hold_days=3, top_n=8, keep_rank=12),
        StrategySpec("SF603_small_unlock_strong_industry", "sf603_small_unlock_strong_industry", "small unlock in strong industry", hold_days=6, top_n=6, keep_rank=10),
        StrategySpec("SF604_post_unlock_lowvol_carry", "sf604_post_unlock_lowvol_carry", "post unlock low vol carry", hold_days=6, top_n=8, keep_rank=12),
        StrategySpec("SF605_tiny_unlock_breakout_follow", "sf605_tiny_unlock_breakout_follow", "tiny unlock breakout follow", hold_days=3, top_n=6, keep_rank=10),
        StrategySpec("SF606_unlock_cluster_absorption", "sf606_unlock_cluster_absorption", "unlock cluster absorption", hold_days=6, top_n=8, keep_rank=12),
    ]
