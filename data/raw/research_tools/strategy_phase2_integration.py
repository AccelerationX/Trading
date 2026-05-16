from __future__ import annotations

from .backtester import StrategySpec


def build_phase2_integration_specs() -> list[StrategySpec]:
    specs = [
        StrategySpec("S121_line_a_relative_drawdown_blend", "s121_line_a_relative_drawdown_blend", "Line A blended with relative drawdown resilience", hold_days=10, top_n=8, keep_rank=12),
        StrategySpec("S122_line_a_dispersion_switch", "s122_line_a_dispersion_switch", "switch between Line A and reversal by market dispersion", hold_days=10, top_n=8, keep_rank=12),
        StrategySpec("S123_balanced_relative_drawdown_blend", "s123_balanced_relative_drawdown_blend", "balanced alpha blended with relative resilience", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("S124_line_a_limitdown_relative", "s124_line_a_limitdown_relative", "Line A plus relative resilience under limit-down exposure ladder", hold_days=10, top_n=8, keep_rank=12, exposure_col="limitdown_exposure"),
        StrategySpec("S125_regime_relative_resilience", "s125_regime_relative_resilience", "regime-sensitive blend with relative resilience", hold_days=10, top_n=10, keep_rank=15),
    ]
    if len(specs) != 5:
        raise RuntimeError(f"Expected 5 phase-2 integration specs, got {len(specs)}")
    return specs
