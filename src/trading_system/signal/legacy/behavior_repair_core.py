from __future__ import annotations

import numpy as np
import pandas as pd

from trading_system.utils.main_board import is_main_board

WINDOW = 10  # 适配 ~20 天数据窗口（原 63）
DEFAULT_TOP_N = 8
DEFAULT_KEEP_RANK = 10


def _zscore_by_date(df: pd.DataFrame, column: str) -> pd.Series:
    grp = df.groupby("trade_date")[column]
    mean = grp.transform("mean")
    std = grp.transform("std").replace(0.0, np.nan)
    return ((df[column] - mean) / std).replace([np.inf, -np.inf], np.nan)


def _compute_base_and_round2(df: pd.DataFrame) -> pd.DataFrame:
    """计算 TM101 所需的全部前置因子（内联，不依赖 line_a_core）。"""
    df = df.copy()
    g = df.groupby("stock_code", group_keys=False)

    # base
    df["daily_ret"] = df["close"] / df["prev_close"] - 1.0
    df["mom_5"] = df["close"] / g["close"].shift(5) - 1.0
    df["short_reversal_5"] = 1.0 - df["close"] / g["close"].shift(5)
    df["volatility_20"] = g["daily_ret"].transform(lambda s: s.rolling(20, min_periods=10).std())
    df["turnover_20"] = g["turnover_pct"].transform(lambda s: s.rolling(20, min_periods=10).mean())
    df["bp"] = np.where(df["pb"] > 0, 1.0 / df["pb"], np.nan)
    df["liquidity"] = np.where(df["amount_k"] > 0, np.log(df["amount_k"]), np.nan)

    # round2
    high = df["high"]
    low = df["low"]
    close = df["close"]
    open_ = df["open"]

    roll_high_20 = g["high"].transform(lambda s: s.rolling(20, min_periods=10).max())
    roll_low_20 = g["low"].transform(lambda s: s.rolling(20, min_periods=10).min())
    std20 = g["close"].transform(lambda s: s.rolling(20, min_periods=10).std())
    ma20 = g["close"].transform(lambda s: s.rolling(20, min_periods=10).mean())

    body = (close - open_).abs()
    total_range = (high - low).replace(0, np.nan)

    df["breakout_20"] = close / roll_high_20.shift(1) - 1.0
    df["donchian_pos_20"] = (close - roll_low_20) / (roll_high_20 - roll_low_20)
    df["range_compress_10_20"] = (
        g["high"].transform(lambda s: s.rolling(10, min_periods=5).max())
        - g["low"].transform(lambda s: s.rolling(10, min_periods=5).min())
    ) / (roll_high_20 - roll_low_20)
    df["lower_shadow_ratio"] = (np.minimum(open_, close) - low) / total_range
    df["upper_shadow_ratio"] = (high - np.maximum(open_, close)) / total_range
    df["gap_from_prev_close"] = open_ / df["prev_close"] - 1.0
    df["intraday_body_ratio"] = body / total_range

    return df


def _compute_recent_features(df: pd.DataFrame, window: int = WINDOW) -> pd.DataFrame:
    """计算近期行为特征（原 window=63，现适配为 10）。"""
    df = df.copy()
    df["rebound_event"] = ((df["mom_5"] < -0.05) & (df["daily_ret"] > 0)).astype(float)
    df["breakout_event"] = df["breakout_20"].gt(0).astype(float)

    g = df.groupby("stock_code", group_keys=False)
    min_periods = max(3, window // 3)

    df[f"recent_rebound_rate_{window}"] = g["rebound_event"].transform(
        lambda s: s.rolling(window, min_periods=min_periods).mean().shift(1)
    )
    df[f"recent_breakout_rate_{window}"] = g["breakout_event"].transform(
        lambda s: s.rolling(window, min_periods=min_periods).mean().shift(1)
    )

    # zscore
    df[f"recent_rebound_rate_{window}_z"] = _zscore_by_date(df, f"recent_rebound_rate_{window}")
    df[f"recent_breakout_rate_{window}_z"] = _zscore_by_date(df, f"recent_breakout_rate_{window}")
    df["short_reversal_5_z"] = _zscore_by_date(df, "short_reversal_5")
    df["breakout_20_z"] = _zscore_by_date(df, "breakout_20")
    df["bp_z"] = _zscore_by_date(df, "bp")
    df["volatility_20_z"] = _zscore_by_date(df, "volatility_20")

    return df


def _compute_repair_signals(df: pd.DataFrame, window: int = WINDOW) -> pd.DataFrame:
    """计算修复反弹信号。"""
    df = df.copy()
    rbz = f"recent_rebound_rate_{window}_z"
    boz = f"recent_breakout_rate_{window}_z"

    # 修复加速信号（原 repair_accel_signal_63）
    cond = (df[rbz] > 0.0) & (df[boz] > -0.2)
    df["repair_accel_signal"] = np.where(
        cond,
        0.25 * df[rbz]
        + 0.20 * df[boz]
        + 0.15 * df["short_reversal_5_z"]
        + 0.15 * df["breakout_20_z"]
        + 0.15 * df["bp_z"]
        - 0.10 * df["volatility_20_z"],
        np.nan,
    )

    # 趋势修复低波信号（原 trend_repair_signal_63）
    trend_cond = (
        (df[boz] > -0.1)
        & (df[rbz] > -0.1)
        & (df["volatility_20_z"] <= -0.1)
    )
    df["trend_repair_raw"] = (
        0.22 * df[boz]
        + 0.18 * df[rbz]
        + 0.15 * df["short_reversal_5_z"]
        + 0.12 * df["donchian_pos_20"]
        + 0.12 * df["bp_z"]
        - 0.10 * df["volatility_20_z"]
        - 0.11 * df["turnover_20"]
    )
    df["trend_repair_signal"] = np.where(trend_cond, df["trend_repair_raw"], np.nan)

    return df


def scan_behavior_repair_candidates(
    df: pd.DataFrame,
    trade_date: str | None = None,
    top_n: int = DEFAULT_TOP_N,
    keep_rank: int = DEFAULT_KEEP_RANK,
    min_amount_k: float = 2000.0,
) -> pd.DataFrame:
    """
    行为修复反弹扫描器。

    返回 DataFrame，包含 repair_accel_signal 和 trend_repair_signal 的候选。
    优先使用 repair_accel_signal 排序，trend_repair_signal 作为备选。
    """
    if trade_date is not None:
        target_date = pd.to_datetime(trade_date)
        if target_date not in df["trade_date"].values:
            return pd.DataFrame()
    else:
        target_date = df["trade_date"].max()

    df = _compute_base_and_round2(df)
    df = _compute_recent_features(df)
    df = _compute_repair_signals(df)

    day_df = df[df["trade_date"] == target_date].copy()
    if day_df.empty:
        return pd.DataFrame()

    # 基础过滤
    day_df = day_df[day_df["amount_k"] >= min_amount_k]
    day_df = day_df[day_df["stock_code"].apply(is_main_board)]
    if "stock_name" in day_df.columns:
        day_df = day_df[~day_df["stock_name"].str.upper().str.contains("ST", na=False)]

    # 优先 repair_accel_signal，其次 trend_repair_signal
    day_df["signal"] = day_df["repair_accel_signal"]
    mask_na = day_df["signal"].isna()
    day_df.loc[mask_na, "signal"] = day_df.loc[mask_na, "trend_repair_signal"]

    day_df = day_df.dropna(subset=["signal"]).copy()
    if day_df.empty:
        return pd.DataFrame()

    day_df = day_df.sort_values("signal", ascending=False).reset_index(drop=True)
    day_df["rank_pos"] = np.arange(1, len(day_df) + 1)
    day_df["in_entry_top_n"] = day_df["rank_pos"] <= top_n
    day_df["in_keep_zone"] = day_df["rank_pos"] <= keep_rank

    def _label(row: pd.Series) -> str:
        if row["in_entry_top_n"]:
            return "strong"
        if row["in_keep_zone"]:
            return "moderate"
        return "watch"

    day_df["signal_type"] = day_df.apply(_label, axis=1)
    day_df["technical_state"] = day_df.apply(
        lambda r: "repair_accel" if pd.notna(r["repair_accel_signal"]) else "trend_repair_lowvol",
        axis=1,
    )

    cols = [
        "stock_code", "stock_name", "trade_date",
        "signal", "repair_accel_signal", "trend_repair_signal",
        "rank_pos", "in_entry_top_n", "in_keep_zone", "signal_type", "technical_state",
    ]
    available_cols = [c for c in cols if c in day_df.columns]
    return day_df[available_cols]
