from __future__ import annotations

from .backtester import StrategySpec


def build_earnings_event_family_specs() -> list[StrategySpec]:
    return [
        StrategySpec("EE301_positive_forecast_follow", "ee301_positive_forecast_follow", "positive forecast follow", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("EE302_forecast_repair_lowcrowding", "ee302_forecast_repair_lowcrowding", "forecast repair with low crowding", hold_days=6, top_n=10, keep_rank=15),
        StrategySpec("EE303_express_profit_surprise", "ee303_express_profit_surprise", "express profit surprise", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("EE304_express_lowvol_carry", "ee304_express_lowvol_carry", "express low-vol carry", hold_days=20, top_n=20, keep_rank=30),
        StrategySpec("EE305_forecast_plus_industry_strength", "ee305_forecast_plus_industry_strength", "forecast plus industry strength", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("EE306_forecast_and_express_combo", "ee306_forecast_and_express_combo", "forecast and express combo", hold_days=10, top_n=10, keep_rank=15),
    ]
