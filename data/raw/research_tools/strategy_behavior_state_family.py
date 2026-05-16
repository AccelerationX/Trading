from __future__ import annotations

import numpy as np
import pandas as pd

from TradingMain.data.loader import add_recent_features

from .backtester import StrategySpec


WINDOW = 63


def add_behavior_state_signals(panel: pd.DataFrame, window: int = WINDOW) -> pd.DataFrame:
    df = add_recent_features(panel.copy(), window).sort_values(["stock_code", "trade_date"]).copy()

    df["repair_accel_signal_63"] = np.where(
        (df[f"recent_rebound_rate_{window}_z"] > 0.0) & (df[f"recent_breakout_rate_{window}_z"] > -0.2),
        0.25 * df[f"recent_rebound_rate_{window}_z"]
        + 0.20 * df[f"recent_breakout_rate_{window}_z"]
        + 0.15 * df["short_reversal_5_z"]
        + 0.15 * df["breakout_20_z"]
        + 0.15 * df["bp_z"]
        - 0.10 * df["volatility_20_z"],
        np.nan,
    )

    df["trend_repair_raw_63"] = (
        0.22 * df[f"recent_breakout_rate_{window}_z"]
        + 0.18 * df[f"recent_rebound_rate_{window}_z"]
        + 0.15 * df["mom_20_z"]
        + 0.12 * df["donchian_pos_20_z"]
        + 0.12 * df["bp_z"]
        - 0.10 * df["volatility_20_z"]
        - 0.11 * df["turnover_20_z"]
    )
    trend_cond = (
        (df[f"recent_breakout_rate_{window}_z"] > -0.1)
        & (df[f"recent_rebound_rate_{window}_z"] > -0.1)
        & (df["volatility_20_z"] <= -0.1)
    )
    df["trend_repair_signal_63"] = np.where(trend_cond, df["trend_repair_raw_63"], np.nan)
    return df


def build_behavior_state_specs() -> list[StrategySpec]:
    base_kwargs = {
        "hold_days": 6,
        "top_n": 8,
        "keep_rank": 10,
        "weighting": "legacy_cap_floor",
        "weight_floor": 0.02,
        "weight_cap": 0.28,
    }
    return [
        StrategySpec(
            "BS101_recent_rebound_h6_top8",
            "recent_rebound_signal_63",
            "Recent rebound behavior, canonical 6d/8 names",
            **base_kwargs,
        ),
        StrategySpec(
            "BS102_repair_accel_hist_h6_top8",
            "repair_accel_signal_63",
            "Historical repair acceleration, canonical 6d/8 names",
            **base_kwargs,
        ),
        StrategySpec(
            "BS103_trend_repair_lowvol_h6_top8",
            "trend_repair_signal_63",
            "Trend repair with low-volatility gate, canonical 6d/8 names",
            **base_kwargs,
        ),
        StrategySpec(
            "BS104_recent_trend_h6_top8",
            "recent_trend_signal_63",
            "Recent trend continuation, canonical 6d/8 names",
            **base_kwargs,
        ),
        StrategySpec(
            "BS105_recent_reset_h6_top8",
            "recent_reset_signal_63",
            "Recent reset behavior, canonical 6d/8 names",
            **base_kwargs,
        ),
        StrategySpec(
            "BS106_recent_quiet_h6_top8",
            "recent_quiet_signal_63",
            "Recent quiet-value behavior, canonical 6d/8 names",
            **base_kwargs,
        ),
    ]
