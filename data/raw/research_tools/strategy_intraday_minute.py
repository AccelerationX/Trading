from __future__ import annotations

from .backtester import StrategySpec


def build_intraday_minute_specs() -> list[StrategySpec]:
    specs = [
        StrategySpec("I201_open_panic_close_recover", "i201_open_panic_close_recover", "morning panic then close recovery", hold_days=3, top_n=10, keep_rank=15),
        StrategySpec("I202_weak_open_strong_close", "i202_weak_open_strong_close", "weak open and strong close", hold_days=3, top_n=10, keep_rank=15),
        StrategySpec("I203_afternoon_breakout_follow", "i203_afternoon_breakout_follow", "afternoon breakout follow-through", hold_days=6, top_n=10, keep_rank=15),
        StrategySpec("I204_vwap_support_reversal", "i204_vwap_support_reversal", "vwap reclaim after intraday flush", hold_days=3, top_n=10, keep_rank=15),
        StrategySpec("I205_intraday_trend_day_lowvol", "i205_intraday_trend_day_lowvol", "intraday trend day with low volatility", hold_days=6, top_n=10, keep_rank=15),
        StrategySpec("I206_late_buying_pressure_lowcrowding", "i206_late_buying_pressure_lowcrowding", "late-session buying pressure with low crowding", hold_days=6, top_n=10, keep_rank=15),
        StrategySpec("I207_morning_flush_afternoon_reverse", "i207_morning_flush_afternoon_reverse", "morning flush and afternoon reverse", hold_days=3, top_n=10, keep_rank=15),
    ]
    if len(specs) != 7:
        raise RuntimeError(f"Expected 7 intraday minute specs, got {len(specs)}")
    return specs
