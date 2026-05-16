from __future__ import annotations

from .backtester import StrategySpec


def build_earnings_event_refine_specs() -> list[StrategySpec]:
    return [
        StrategySpec("EE306R_forecast_and_express_combo_h6_top6", "ee306_forecast_and_express_combo", "forecast and express combo refined", hold_days=6, top_n=6, keep_rank=10),
        StrategySpec("EE302R_forecast_repair_lowcrowding_h6_top6", "ee302_forecast_repair_lowcrowding", "forecast repair refined", hold_days=6, top_n=6, keep_rank=10),
        StrategySpec("EE303R_express_profit_surprise_h6_top8", "ee303_express_profit_surprise", "express profit surprise refined", hold_days=6, top_n=8, keep_rank=12),
        StrategySpec("EE307_express_turnaround_follow_h6_top8", "ee307_express_turnaround_follow", "express turnaround follow", hold_days=6, top_n=8, keep_rank=12),
        StrategySpec("EE308_dual_positive_revision_h6_top6", "ee308_dual_positive_revision", "dual positive revision", hold_days=6, top_n=6, keep_rank=10),
        StrategySpec("EE309_large_positive_forecast_h6_top6", "ee309_large_positive_forecast_short_hold", "large positive forecast short hold", hold_days=6, top_n=6, keep_rank=10),
        StrategySpec("EE310_forecast_turnaround_value_h6_top8", "ee310_forecast_turnaround_value", "forecast turnaround value", hold_days=6, top_n=8, keep_rank=12),
    ]
