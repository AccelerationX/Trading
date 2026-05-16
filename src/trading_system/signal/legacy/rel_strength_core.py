from __future__ import annotations

import numpy as np
import pandas as pd

from trading_system.utils.main_board import is_main_board

MOMENTUM_WINDOW = 10  # N日动量窗口（适配~20天数据窗口）
DEFAULT_TOP_N = 10


def _build_market_momentum(df: pd.DataFrame, window: int = MOMENTUM_WINDOW) -> pd.Series:
    """构建主板等权指数N日动量序列。"""
    mainboard = df[df["stock_code"].apply(is_main_board)].copy()
    mainboard["daily_ret"] = mainboard.groupby("stock_code")["close"].pct_change()
    market_daily = mainboard.groupby("trade_date")["daily_ret"].mean()
    market_mom = market_daily.rolling(window, min_periods=max(3, window // 2)).sum()
    return market_mom.rename("market_mom")


def _compute_rel_strength(df: pd.DataFrame, window: int = MOMENTUM_WINDOW) -> pd.DataFrame:
    """
    计算相对强弱：个股N日动量 - 市场N日动量。
    返回带有 rel_strength, rs_zscore, rs_positive 等列的 DataFrame。
    """
    df = df.copy()
    df["daily_ret"] = df.groupby("stock_code")["close"].pct_change()
    df["stock_mom"] = df.groupby("stock_code")["daily_ret"].transform(
        lambda s: s.rolling(window, min_periods=max(3, window // 2)).sum()
    )

    market_mom = _build_market_momentum(df, window)
    df["market_mom"] = df["trade_date"].map(market_mom)
    df["rel_strength"] = df["stock_mom"] - df["market_mom"]

    # 归一化（MAD robust zscore）
    rs_median = df["rel_strength"].median()
    rs_mad = (df["rel_strength"] - rs_median).abs().median()
    if rs_mad > 0:
        df["rs_zscore"] = (df["rel_strength"] - rs_median) / (rs_mad * 1.4826)
    else:
        df["rs_zscore"] = 0.0

    df["rs_positive"] = (df["rel_strength"] > 0).astype(float)
    df["rs_weight"] = df["rs_positive"] * df["rs_zscore"].clip(0.0, 1.0)
    return df


def scan_rel_strength_candidates(
    df: pd.DataFrame,
    trade_date: str | None = None,
    top_n: int = DEFAULT_TOP_N,
    min_amount_k: float = 2000.0,
) -> pd.DataFrame:
    """
    相对强弱扫描器：选出当日跑赢市场的主板股票，按 rel_strength 排序。

    Returns
    -------
    DataFrame with columns: stock_code, stock_name, trade_date, rel_strength,
    rs_zscore, rs_weight, stock_mom, market_mom, rank_pos, signal_type
    """
    if trade_date is not None:
        target_date = pd.to_datetime(trade_date)
        if target_date not in df["trade_date"].values:
            return pd.DataFrame()
    else:
        target_date = df["trade_date"].max()

    df = _compute_rel_strength(df)

    day_df = df[df["trade_date"] == target_date].copy()
    if day_df.empty:
        return pd.DataFrame()

    # 基础过滤
    day_df = day_df[day_df["amount_k"] >= min_amount_k]
    day_df = day_df[day_df["stock_code"].apply(is_main_board)]
    if "stock_name" in day_df.columns:
        day_df = day_df[~day_df["stock_name"].str.upper().str.contains("ST", na=False)]

    # 排除动量缺失的
    day_df = day_df.dropna(subset=["rel_strength", "stock_mom", "market_mom"])
    if day_df.empty:
        return pd.DataFrame()

    # 只保留跑赢市场的
    day_df = day_df[day_df["rel_strength"] > 0].copy()
    if day_df.empty:
        return pd.DataFrame()

    day_df = day_df.sort_values("rel_strength", ascending=False).reset_index(drop=True)
    day_df["rank_pos"] = np.arange(1, len(day_df) + 1)
    day_df["in_top_n"] = day_df["rank_pos"] <= top_n

    # 信号分级
    def _label(row: pd.Series) -> str:
        if row["in_top_n"]:
            return "strong"
        if row["rs_zscore"] > 0.5:
            return "moderate"
        return "watch"

    day_df["signal_type"] = day_df.apply(_label, axis=1)

    cols = [
        "stock_code", "stock_name", "trade_date",
        "rel_strength", "rs_zscore", "rs_weight",
        "stock_mom", "market_mom",
        "rank_pos", "in_top_n", "signal_type",
    ]
    available_cols = [c for c in cols if c in day_df.columns]
    return day_df[available_cols]
