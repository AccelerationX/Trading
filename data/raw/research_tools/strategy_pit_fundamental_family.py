from __future__ import annotations

from .backtester import StrategySpec


def build_pit_fundamental_family_specs() -> list[StrategySpec]:
    return [
        StrategySpec("PF201_profitability_turn_low_pb", "pf201_profitability_turn_low_pb", "profitability turn with low PB", hold_days=20, top_n=20, keep_rank=30),
        StrategySpec("PF202_operating_cashflow_improvement_low_pb", "pf202_operating_cashflow_improvement_low_pb", "operating cashflow improvement with low PB", hold_days=20, top_n=20, keep_rank=30),
        StrategySpec("PF203_gross_margin_rebound_low_crowding", "pf203_gross_margin_rebound_low_crowding", "gross-margin rebound with low crowding", hold_days=20, top_n=20, keep_rank=30),
        StrategySpec("PF204_roe_improvement_midcap_bias", "pf204_roe_improvement_midcap_bias", "ROE improvement with midcap bias", hold_days=20, top_n=20, keep_rank=30),
        StrategySpec("PF205_receivables_deterioration_avoidance", "pf205_receivables_deterioration_avoidance", "receivables deterioration avoidance", hold_days=20, top_n=20, keep_rank=30),
        StrategySpec("PF206_inventory_deterioration_avoidance", "pf206_inventory_deterioration_avoidance", "inventory deterioration avoidance", hold_days=20, top_n=20, keep_rank=30),
        StrategySpec("PF207_low_accrual_value_repair", "pf207_low_accrual_value_repair", "low-accrual value repair", hold_days=20, top_n=20, keep_rank=30),
        StrategySpec("PF208_cashflow_margin_improvement_combo", "pf208_cashflow_margin_improvement_combo", "cashflow plus margin-improvement combo", hold_days=20, top_n=20, keep_rank=30),
    ]
