from __future__ import annotations

import numpy as np
import pandas as pd

from trading_system.utils.main_board import is_main_board

WINDOW = 10  # 适配 ~20 天数据
DEFAULT_TOP_N = 8
DEFAULT_KEEP_RANK = 10
DEFAULT_K_GROUPS = 4
DEFAULT_GROUP_PICK_N = 2
MIN_OBS = 5


def _zscore(s: pd.Series) -> pd.Series:
    std = s.std()
    if pd.isna(std) or std == 0:
        return pd.Series(0.0, index=s.index)
    return (s - s.mean()) / std


def _simple_kmeans(x: np.ndarray, k: int = 4, max_iter: int = 50, seed: int = 42) -> np.ndarray:
    if len(x) < k:
        return np.zeros(len(x), dtype=int)
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(x), size=k, replace=False)
    centroids = x[idx].copy()
    labels = np.zeros(len(x), dtype=int)
    for _ in range(max_iter):
        dists = ((x[:, None, :] - centroids[None, :, :]) ** 2).sum(axis=2)
        new_labels = dists.argmin(axis=1)
        if np.array_equal(new_labels, labels):
            break
        labels = new_labels
        for j in range(k):
            mask = labels == j
            if mask.any():
                centroids[j] = x[mask].mean(axis=0)
    return labels


def _compute_base_and_round2(df: pd.DataFrame) -> pd.DataFrame:
    """计算分组和信号所需的全部前置因子。"""
    df = df.copy()
    g = df.groupby("stock_code", group_keys=False)

    df["daily_ret"] = df["close"] / df["prev_close"] - 1.0
    df["mom_5"] = df["close"] / g["close"].shift(5) - 1.0
    df["mom_20"] = df["close"] / g["close"].shift(20) - 1.0
    df["short_reversal_5"] = 1.0 - df["close"] / g["close"].shift(5)
    df["volatility_20"] = g["daily_ret"].transform(lambda s: s.rolling(20, min_periods=10).std())
    df["turnover_20"] = g["turnover_pct"].transform(lambda s: s.rolling(20, min_periods=10).mean())
    df["bp"] = np.where(df["pb"] > 0, 1.0 / df["pb"], np.nan)
    df["amplitude"] = (df["high"] - df["low"]) / df["prev_close"].replace(0, np.nan)
    df["amplitude_5"] = g["amplitude"].transform(lambda s: s.rolling(5, min_periods=3).mean())

    high = df["high"]
    low = df["low"]
    close = df["close"]
    open_ = df["open"]

    roll_high_20 = g["high"].transform(lambda s: s.rolling(20, min_periods=10).max())
    roll_low_20 = g["low"].transform(lambda s: s.rolling(20, min_periods=10).min())

    body = (close - open_).abs()
    total_range = (high - low).replace(0, np.nan)

    df["breakout_20"] = close / roll_high_20.shift(1) - 1.0
    df["lower_shadow_ratio"] = (np.minimum(open_, close) - low) / total_range
    df["rebound_event"] = ((df["mom_5"] < -0.05) & (df["daily_ret"] > 0)).astype(float)
    df["breakout_event"] = df["breakout_20"].gt(0).astype(float)

    # zscores needed for rotation_repair_signal
    for col in ["short_reversal_5", "bp", "breakout_20", "turnover_20"]:
        df[f"{col}_z"] = df.groupby("trade_date")[col].transform(
            lambda s: ((s - s.mean()) / s.std()).replace([np.inf, -np.inf], np.nan) if s.std() > 0 else pd.Series(0.0, index=s.index)
        )

    df["rotation_repair_signal"] = (
        0.40 * df["short_reversal_5_z"]
        + 0.30 * df["bp_z"]
        + 0.20 * df["breakout_20_z"]
        - 0.10 * df["turnover_20_z"]
    )

    return df


def _build_stock_groups(df: pd.DataFrame, k_groups: int = DEFAULT_K_GROUPS, min_obs: int = MIN_OBS) -> pd.DataFrame:
    """基于历史统计特征对股票进行 k-means 聚类分组。"""
    stats = (
        df.groupby("stock_code")
        .agg(
            obs=("trade_date", "count"),
            avg_turnover=("turnover_20", "mean"),
            avg_volatility=("volatility_20", "mean"),
            avg_amplitude=("amplitude_5", "mean"),
            avg_mom20=("mom_20", "mean"),
            avg_bp=("bp", "mean"),
            rebound_rate=("rebound_event", "mean"),
            breakout_rate=("breakout_event", "mean"),
        )
        .reset_index()
    )
    stats = stats[stats["obs"] >= min_obs].copy()
    if stats.empty:
        return stats

    group_features = [
        "avg_turnover", "avg_volatility", "avg_amplitude",
        "avg_mom20", "avg_bp", "rebound_rate", "breakout_rate",
    ]
    for col in group_features:
        stats[col] = stats[col].replace([np.inf, -np.inf], np.nan)
        stats[col] = stats[col].fillna(stats[col].median())
        stats[f"{col}_z"] = _zscore(stats[col])

    x = stats[[f"{col}_z" for col in group_features]].to_numpy(dtype=float)
    stats["latent_group"] = _simple_kmeans(x, k=min(k_groups, len(stats)), max_iter=60, seed=42)
    return stats[["stock_code", "latent_group"]]


def scan_group_rotation_candidates(
    df: pd.DataFrame,
    trade_date: str | None = None,
    top_n: int = DEFAULT_TOP_N,
    keep_rank: int = DEFAULT_KEEP_RANK,
    group_pick_n: int = DEFAULT_GROUP_PICK_N,
    min_amount_k: float = 2000.0,
) -> pd.DataFrame:
    """
    板块轮动扫描器：先聚类分组，选最强组，组内按 rotation_repair_signal 排序。
    """
    if trade_date is not None:
        target_date = pd.to_datetime(trade_date)
        if target_date not in df["trade_date"].values:
            return pd.DataFrame()
    else:
        target_date = df["trade_date"].max()

    df = _compute_base_and_round2(df)

    # 构建股票分组（使用 target_date 之前所有可用历史）
    stock_groups = _build_stock_groups(df)
    if stock_groups.empty:
        return pd.DataFrame()

    df = df.merge(stock_groups, on="stock_code", how="inner")

    # 计算每组近期收益（过去 5 日累积）
    df["trail_ret_5"] = df.groupby("stock_code")["daily_ret"].transform(
        lambda s: (1 + s).rolling(5, min_periods=3).apply(np.prod, raw=True) - 1.0
    )

    # 选最强组（基于最新日期的组平均收益）
    latest_group_perf = (
        df[df["trade_date"] == target_date]
        .groupby("latent_group")["trail_ret_5"]
        .mean()
        .reset_index()
        .dropna()
    )
    if latest_group_perf.empty:
        return pd.DataFrame()

    chosen_groups = latest_group_perf.sort_values("trail_ret_5", ascending=False).head(group_pick_n)["latent_group"].tolist()

    # 在选中组内当日数据做过滤和排序
    day_df = df[df["trade_date"] == target_date].copy()
    day_df = day_df[day_df["latent_group"].isin(chosen_groups)]
    day_df = day_df[day_df["amount_k"] >= min_amount_k]
    day_df = day_df[day_df["stock_code"].apply(is_main_board)]
    if "stock_name" in day_df.columns:
        day_df = day_df[~day_df["stock_name"].str.upper().str.contains("ST", na=False)]

    day_df = day_df.dropna(subset=["rotation_repair_signal"]).copy()
    if day_df.empty:
        return pd.DataFrame()

    day_df = day_df.sort_values("rotation_repair_signal", ascending=False).reset_index(drop=True)
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

    cols = [
        "stock_code", "stock_name", "trade_date", "latent_group",
        "rotation_repair_signal", "rank_pos",
        "in_entry_top_n", "in_keep_zone", "signal_type",
    ]
    available_cols = [c for c in cols if c in day_df.columns]
    return day_df[available_cols]
