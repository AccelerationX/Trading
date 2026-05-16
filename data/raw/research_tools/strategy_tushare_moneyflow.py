from __future__ import annotations

from .backtester import StrategySpec


def build_tushare_moneyflow_specs() -> list[StrategySpec]:
    return [
        StrategySpec(
            "MF301_line_a_big_inflow",
            "mf301_line_a_big_inflow",
            "Line A with positive broad and extra-large moneyflow support",
            hold_days=10,
            top_n=8,
            keep_rank=12,
        ),
        StrategySpec(
            "MF302_oversold_institutional_support",
            "mf302_oversold_institutional_support",
            "Oversold reversal with institutional support",
            hold_days=6,
            top_n=10,
            keep_rank=15,
        ),
        StrategySpec(
            "MF303_breakout_big_order_follow",
            "mf303_breakout_big_order_follow",
            "Breakout with positive large-order follow-through",
            hold_days=6,
            top_n=10,
            keep_rank=15,
            market_gate_col="moneyflow_risk_on_gate",
        ),
        StrategySpec(
            "MF304_lowvol_big_inflow",
            "mf304_lowvol_big_inflow",
            "Low-vol value names with positive moneyflow",
            hold_days=20,
            top_n=20,
            keep_rank=30,
            exposure_col="moneyflow_exposure",
        ),
        StrategySpec(
            "MF305_smallcap_funds_rotation",
            "mf305_smallcap_funds_rotation",
            "Small-cap rotation under positive market moneyflow breadth",
            hold_days=10,
            top_n=10,
            keep_rank=15,
            exposure_col="moneyflow_exposure",
        ),
        StrategySpec(
            "MF306_contra_retail_dump",
            "mf306_contra_retail_dump",
            "Retail selling absorbed by larger money",
            hold_days=6,
            top_n=10,
            keep_rank=15,
        ),
    ]
