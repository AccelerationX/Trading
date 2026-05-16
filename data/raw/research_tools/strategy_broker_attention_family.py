from __future__ import annotations

from .backtester import StrategySpec


def build_broker_attention_specs() -> list[StrategySpec]:
    return [
        StrategySpec("BR901_coverage_diffusion_lowcrowding", "br901_coverage_diffusion_lowcrowding", "coverage diffusion low crowding", hold_days=10, top_n=8, keep_rank=12),
        StrategySpec("BR902_sparse_coverage_breakout", "br902_sparse_coverage_breakout", "sparse coverage breakout", hold_days=6, top_n=4, keep_rank=6),
        StrategySpec("BR903_consensus_accel_midcap", "br903_consensus_accel_midcap", "consensus acceleration midcap", hold_days=10, top_n=6, keep_rank=10),
        StrategySpec("BR904_first_coverage_repair", "br904_first_coverage_repair", "first coverage repair", hold_days=6, top_n=4, keep_rank=6),
        StrategySpec("BR905_broad_coverage_strong_industry", "br905_broad_coverage_strong_industry", "broad coverage strong industry", hold_days=10, top_n=6, keep_rank=10),
        StrategySpec("BR906_coverage_accel_breakout", "br906_coverage_accel_breakout", "coverage acceleration breakout", hold_days=6, top_n=4, keep_rank=6),
    ]
