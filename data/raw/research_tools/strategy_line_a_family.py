from __future__ import annotations

import numpy as np
import pandas as pd

from .backtester import StrategySpec


def add_line_a_family_signal(panel: pd.DataFrame) -> pd.DataFrame:
    """Compute the minimal Line A family signal without building the full factor universe."""
    df = panel.copy().sort_values(["stock_code", "trade_date"])
    grouped = df.groupby("stock_code", group_keys=False)

    df["amount_20"] = grouped["amount_k"].transform(lambda s: s.rolling(20, min_periods=10).mean())
    df["volume_ma20_gap"] = df["amount_k"] / df["amount_20"].replace(0.0, np.nan) - 1.0
    df["legacy_core_alpha_no_lookahead"] = (
        df["bp_z"] + df["short_reversal_5_z"] - df["size_z"] - df["liquidity_z"]
    ) / 4.0

    volume_rank = df.groupby("trade_date")["volume_ma20_gap"].transform(
        lambda s: s.rank(pct=True, method="average")
    )
    range_rank = df.groupby("trade_date")["range_compress_10_20"].transform(
        lambda s: s.rank(pct=True, method="average")
    )
    line_a_filter = (volume_rank <= 0.60) & (range_rank <= 0.60)
    df["line_a_core_signal"] = np.where(line_a_filter, df["legacy_core_alpha_no_lookahead"], np.nan)
    return df


def build_line_a_validation_specs() -> list[StrategySpec]:
    specs = [
        StrategySpec(
            "LA001_line_a_h10_top6",
            "line_a_core_signal",
            "Line A base variant, hold 10, top 6",
            hold_days=10,
            top_n=6,
            keep_rank=8,
        ),
        StrategySpec(
            "LA002_line_a_h10_top8",
            "line_a_core_signal",
            "Line A base variant, hold 10, top 8",
            hold_days=10,
            top_n=8,
            keep_rank=12,
        ),
        StrategySpec(
            "LA003_line_a_h10_top10",
            "line_a_core_signal",
            "Line A base variant, hold 10, top 10",
            hold_days=10,
            top_n=10,
            keep_rank=12,
        ),
        StrategySpec(
            "LA004_line_a_h20_top20",
            "line_a_core_signal",
            "Line A diversified variant, hold 20, top 20",
            hold_days=20,
            top_n=20,
            keep_rank=30,
        ),
        StrategySpec(
            "LA005_line_a_rank_buffer",
            "line_a_core_signal",
            "Line A with wider rank buffer",
            hold_days=10,
            top_n=8,
            keep_rank=16,
        ),
        StrategySpec(
            "LA006_line_a_inverse_vol",
            "line_a_core_signal",
            "Line A with inverse-volatility weighting",
            hold_days=10,
            top_n=8,
            keep_rank=12,
            weighting="inverse_vol",
        ),
        StrategySpec(
            "LA007_line_a_cap_floor",
            "line_a_core_signal",
            "Line A with capped and floored signal weights",
            hold_days=10,
            top_n=8,
            keep_rank=12,
            weighting="signal_cap_floor",
            weight_floor=0.05,
            weight_cap=0.20,
        ),
        StrategySpec(
            "LA008_line_a_drawdown_pause",
            "line_a_core_signal",
            "Line A with recent drawdown pause",
            hold_days=10,
            top_n=8,
            keep_rank=12,
            drawdown_pause=True,
        ),
        StrategySpec(
            "LA009_line_a_reallocate_blocked",
            "line_a_core_signal",
            "Line A with blocked-buy reallocation",
            hold_days=10,
            top_n=8,
            keep_rank=12,
            replace_blocked_buys=True,
        ),
    ]
    return specs
