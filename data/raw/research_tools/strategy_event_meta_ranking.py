from __future__ import annotations

from .backtester import StrategySpec


def build_event_meta_ranking_specs() -> list[StrategySpec]:
    return [
        StrategySpec("EM901_event_strength_blend", "em901_event_strength_blend", "event strength blend", hold_days=6, top_n=2, keep_rank=4),
        StrategySpec("EM902_event_repair_quality", "em902_event_repair_quality", "event repair quality", hold_days=10, top_n=4, keep_rank=6),
        StrategySpec("EM903_multi_event_confirmation", "em903_multi_event_confirmation", "multi event confirmation", hold_days=6, top_n=2, keep_rank=4),
        StrategySpec("EM904_high_conviction_breakout", "em904_high_conviction_breakout", "high conviction breakout", hold_days=3, top_n=1, keep_rank=2),
        StrategySpec("EM905_quality_industry_catalyst", "em905_quality_industry_catalyst", "quality industry catalyst", hold_days=6, top_n=2, keep_rank=4),
        StrategySpec("EM906_special_situations_blend", "em906_special_situations_blend", "special situations blend", hold_days=6, top_n=2, keep_rank=4),
    ]
