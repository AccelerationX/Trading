from __future__ import annotations

from .backtester import StrategySpec


def build_pledge_risk_specs() -> list[StrategySpec]:
    return [
        StrategySpec("PR901_low_pledge_value_repair", "pr901_low_pledge_value_repair", "low pledge value repair", hold_days=10, top_n=8, keep_rank=12),
        StrategySpec("PR902_falling_pledge_relief", "pr902_falling_pledge_relief", "falling pledge relief", hold_days=6, top_n=8, keep_rank=12),
        StrategySpec("PR903_zero_pledge_midcap_quality", "pr903_zero_pledge_midcap_quality", "zero pledge midcap quality", hold_days=10, top_n=8, keep_rank=12),
        StrategySpec("PR904_high_pledge_overreaction_repair", "pr904_high_pledge_overreaction_repair", "high pledge overreaction repair", hold_days=6, top_n=6, keep_rank=10),
        StrategySpec("PR905_pledge_relief_breakout", "pr905_pledge_relief_breakout", "pledge relief breakout", hold_days=6, top_n=6, keep_rank=10),
        StrategySpec("PR906_low_pledge_strong_industry", "pr906_low_pledge_strong_industry", "low pledge strong industry", hold_days=10, top_n=8, keep_rank=12),
    ]
