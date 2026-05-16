from __future__ import annotations

from .backtester import StrategySpec


def build_toplist_family_specs() -> list[StrategySpec]:
    return [
        StrategySpec("TL401_netbuy_lowcrowding", "tl401_netbuy_lowcrowding", "toplist net buy low crowding", hold_days=6, top_n=8, keep_rank=12),
        StrategySpec("TL402_high_attention_follow", "tl402_high_attention_follow", "toplist high attention follow", hold_days=3, top_n=6, keep_rank=10),
        StrategySpec("TL403_negative_exhaustion_repair", "tl403_negative_exhaustion_repair", "toplist negative exhaustion repair", hold_days=3, top_n=6, keep_rank=10),
        StrategySpec("TL404_repeat_heat_not_crowded", "tl404_repeat_heat_not_crowded", "toplist repeat heat not crowded", hold_days=6, top_n=8, keep_rank=12),
        StrategySpec("TL405_strong_industry_toplist", "tl405_strong_industry_toplist", "toplist in strong industry", hold_days=6, top_n=6, keep_rank=10),
        StrategySpec("TL406_large_netamount_midcap", "tl406_large_netamount_midcap", "toplist large net amount midcap", hold_days=6, top_n=6, keep_rank=10),
    ]
