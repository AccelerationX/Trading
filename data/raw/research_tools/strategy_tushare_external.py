from __future__ import annotations

from .backtester import StrategySpec


def build_tushare_external_specs() -> list[StrategySpec]:
    specs = [
        StrategySpec(
            "TX201_line_a_industry_leader",
            "tx201_line_a_industry_leader",
            "Line A restricted to strong SW L1 industries",
            hold_days=10,
            top_n=8,
            keep_rank=12,
        ),
        StrategySpec(
            "TX202_line_a_avoid_weak_industry",
            "tx202_line_a_avoid_weak_industry",
            "Line A with weak SW L1 industries removed",
            hold_days=10,
            top_n=8,
            keep_rank=12,
        ),
        StrategySpec(
            "TX203_small_value_style_gate",
            "tx203_small_value_style_gate",
            "Small-value reversal only when CSI1000 style is stronger than CSI300",
            hold_days=10,
            top_n=10,
            keep_rank=15,
        ),
        StrategySpec(
            "TX204_breakout_industry_risk_on",
            "tx204_breakout_industry_risk_on",
            "Breakout plus industry strength under external index risk-on gate",
            hold_days=6,
            top_n=10,
            keep_rank=15,
            market_gate_col="external_risk_on_gate",
        ),
        StrategySpec(
            "TX205_line_a_style_exposure",
            "tx205_line_a_style_exposure",
            "Line A with external style-dependent exposure ladder",
            hold_days=10,
            top_n=8,
            keep_rank=12,
            exposure_col="defensive_exposure",
        ),
        StrategySpec(
            "TX206_defensive_value_index_exposure",
            "tx206_defensive_value_index_exposure",
            "Defensive value sleeve with external index exposure control",
            hold_days=20,
            top_n=20,
            keep_rank=30,
            exposure_col="defensive_exposure",
        ),
        StrategySpec(
            "TX207_industry_relative_reversal",
            "tx207_industry_relative_reversal",
            "Reversal in non-weak industries with value and low-crowding support",
            hold_days=6,
            top_n=10,
            keep_rank=15,
        ),
        StrategySpec(
            "TX208_industry_compression_breakout",
            "tx208_industry_compression_breakout",
            "Compression breakout inside strong industries and risk-on index state",
            hold_days=10,
            top_n=10,
            keep_rank=15,
            market_gate_col="external_risk_on_gate",
        ),
    ]
    return specs
