from __future__ import annotations

from .backtester import StrategySpec


def build_report_attention_specs() -> list[StrategySpec]:
    return [
        StrategySpec("RC701_initiation_follow", "rc701_initiation_follow", "initiation report follow", hold_days=6, top_n=6, keep_rank=10),
        StrategySpec("RC702_multi_org_positive_lowcrowding", "rc702_multi_org_positive_lowcrowding", "multi org positive low crowding", hold_days=6, top_n=8, keep_rank=12),
        StrategySpec("RC703_deep_coverage_midcap", "rc703_deep_coverage_midcap", "deep coverage midcap", hold_days=10, top_n=6, keep_rank=10),
        StrategySpec("RC704_target_premium_follow", "rc704_target_premium_follow", "target premium follow", hold_days=6, top_n=6, keep_rank=10),
        StrategySpec("RC705_repeat_coverage_strong_industry", "rc705_repeat_coverage_strong_industry", "repeat coverage strong industry", hold_days=6, top_n=8, keep_rank=12),
        StrategySpec("RC706_broker_consensus_plus_report", "rc706_broker_consensus_plus_report", "broker consensus plus report", hold_days=10, top_n=8, keep_rank=12),
    ]
