from __future__ import annotations

import numpy as np
import pandas as pd

from TradingMain.data.loader import add_recent_features


WINDOW = 63
GROUP_FEATURES = [
    "avg_turnover",
    "avg_volatility",
    "avg_amplitude",
    "avg_mom20",
    "avg_bp",
    "rebound_rate",
    "breakout_rate",
]


def zscore(s: pd.Series) -> pd.Series:
    std = s.std()
    if pd.isna(std) or std == 0:
        return pd.Series(0.0, index=s.index)
    return (s - s.mean()) / std


def simple_kmeans(x: np.ndarray, k: int = 6, max_iter: int = 50, seed: int = 42) -> np.ndarray:
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


def add_group_rotation_signals(panel: pd.DataFrame, window: int = WINDOW) -> pd.DataFrame:
    df = add_recent_features(panel.copy(), window).sort_values(["stock_code", "trade_date"]).copy()
    df["rotation_repair_signal"] = (
        0.40 * df["short_reversal_5_z"]
        + 0.30 * df["bp_z"]
        + 0.20 * df["breakout_20_z"]
        - 0.10 * df["turnover_20_z"]
    )
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
    df["reset_value_signal_63"] = np.where(
        df[f"recent_reset_signal_{window}"].notna() & (df[f"recent_bp_{window}_z"] > -0.2),
        0.35 * df[f"recent_reset_signal_{window}"]
        + 0.20 * df[f"recent_bp_{window}_z"]
        + 0.15 * df["bp_z"]
        + 0.15 * df["short_reversal_5_z"]
        - 0.15 * df["turnover_20_z"],
        np.nan,
    )
    return df


def build_stock_groups(history: pd.DataFrame, min_obs: int = 120, k_groups: int = 6) -> pd.DataFrame:
    stats = (
        history.groupby("stock_code")
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
    for col in GROUP_FEATURES:
        stats[col] = stats[col].replace([np.inf, -np.inf], np.nan)
        stats[col] = stats[col].fillna(stats[col].median())
        stats[f"{col}_z"] = zscore(stats[col])
    x = stats[[f"{col}_z" for col in GROUP_FEATURES]].to_numpy(dtype=float)
    stats["latent_group"] = simple_kmeans(x, k=min(k_groups, len(stats)), max_iter=60, seed=42)
    return stats[["stock_code", "latent_group"]]
