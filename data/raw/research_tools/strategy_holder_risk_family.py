from __future__ import annotations

from .backtester import StrategySpec


def build_holder_risk_specs() -> list[StrategySpec]:
    return [
        StrategySpec("HN801_holder_concentration_improving", "hn801_holder_concentration_improving", "holder concentration improving", hold_days=10, top_n=8, keep_rank=12),
        StrategySpec("HN802_holder_expansion_repair", "hn802_holder_expansion_repair", "holder expansion repair", hold_days=6, top_n=8, keep_rank=12),
        StrategySpec("HN803_concentration_strong_industry", "hn803_concentration_strong_industry", "concentration strong industry", hold_days=10, top_n=6, keep_rank=10),
        StrategySpec("HN804_low_holder_growth_lowvol", "hn804_low_holder_growth_lowvol", "low holder growth low vol", hold_days=10, top_n=8, keep_rank=12),
        StrategySpec("HN805_extreme_holder_decline_breakout", "hn805_extreme_holder_decline_breakout", "extreme holder decline breakout", hold_days=6, top_n=6, keep_rank=10),
        StrategySpec("HN806_concentration_midcap_value", "hn806_concentration_midcap_value", "concentration midcap value", hold_days=10, top_n=8, keep_rank=12),
    ]
