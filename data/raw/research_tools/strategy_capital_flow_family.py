from __future__ import annotations

from .backtester import StrategySpec


def build_capital_flow_family_specs() -> list[StrategySpec]:
    return [
        StrategySpec("CF201_northbound_market_inflow_ladder", "cf201_northbound_market_inflow_ladder", "northbound market inflow ladder", hold_days=10, top_n=10, keep_rank=15, exposure_col="north_market_exposure"),
        StrategySpec("CF202_anti_margin_crowding_cross_section", "cf202_anti_margin_crowding_cross_section", "anti-margin-crowding cross-section", hold_days=20, top_n=10, keep_rank=15, exposure_col="margin_crowding_exposure"),
        StrategySpec("CF203_northbound_support_inside_strong_industries", "cf203_northbound_support_inside_strong_industries", "northbound support inside strong industries", hold_days=10, top_n=10, keep_rank=15, exposure_col="north_market_exposure"),
        StrategySpec("CF204_financing_squeeze_repair", "cf204_financing_squeeze_repair", "financing squeeze repair", hold_days=6, top_n=10, keep_rank=15, exposure_col="margin_crowding_exposure"),
        StrategySpec("CF205_low_margin_low_crowding_continuation", "cf205_low_margin_low_crowding_continuation", "low-margin low-crowding continuation", hold_days=20, top_n=20, keep_rank=30, exposure_col="north_margin_exposure"),
        StrategySpec("CF206_northbound_financing_divergence", "cf206_northbound_financing_divergence", "northbound plus financing divergence", hold_days=10, top_n=10, keep_rank=15, exposure_col="north_margin_exposure", market_gate_col="north_margin_market_gate"),
    ]
