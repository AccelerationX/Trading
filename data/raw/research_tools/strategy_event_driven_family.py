from __future__ import annotations

from .backtester import StrategySpec


def build_event_driven_family_specs() -> list[StrategySpec]:
    return [
        StrategySpec("EV201_buyback_follow", "ev201_buyback_follow", "buyback follow", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("EV202_management_increase_follow", "ev202_management_increase_follow", "management increase follow", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("EV203_holder_decrease_overreaction_repair", "ev203_holder_decrease_overreaction_repair", "holder decrease overreaction repair", hold_days=6, top_n=10, keep_rank=15),
        StrategySpec("EV204_buyback_lowvol_carry", "ev204_buyback_lowvol_carry", "buyback low-vol carry", hold_days=20, top_n=20, keep_rank=30),
        StrategySpec("EV205_event_plus_industry_strength", "ev205_event_plus_industry_strength", "event plus industry strength combo", hold_days=10, top_n=10, keep_rank=15),
        StrategySpec("EV206_buyback_plus_holder_increase_combo", "ev206_buyback_plus_holder_increase_combo", "buyback plus holder increase combo", hold_days=10, top_n=10, keep_rank=15),
    ]
