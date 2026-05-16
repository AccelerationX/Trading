from __future__ import annotations

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# 配置常量
# ---------------------------------------------------------------------------

STRATEGIES = {
    "core_top10": {"filters": None, "top_n": 10},
    "range_q60_top10": {"filters": [("range_compress_10_20", "low", 0.6)], "top_n": 10},
    "double_q60_top10": {
        "filters": [("volume_ma20_gap", "low", 0.6), ("range_compress_10_20", "low", 0.6)],
        "top_n": 10,
    },
}

BASE_FACTOR_COLUMNS = [
    "mom_5", "mom_20", "mom_60", "short_reversal_5",
    "volatility_20", "amplitude_5", "turnover_20",
    "bp", "ep_ttm", "size", "liquidity",
]

ORIENTATION = {
    "mom_5": -1.0, "mom_20": -1.0, "mom_60": -1.0,
    "short_reversal_5": 1.0,
    "volatility_20": -1.0, "amplitude_5": -1.0, "turnover_20": -1.0,
    "bp": 1.0, "ep_ttm": 1.0,
    "size": -1.0, "liquidity": -1.0,
}

CORE_COMBO_INPUTS = ["bp", "short_reversal_5", "size", "liquidity"]

DEFAULT_MIN_LISTING_DAYS = 10
DEFAULT_MIN_AMOUNT_K = 5000.0
LOOKBACK_DAYS = 120  # 足够计算所有滚动窗口


# ---------------------------------------------------------------------------
# 基础因子计算（向量化优化版）
# ---------------------------------------------------------------------------

def _compute_base_factors(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["stock_code", "trade_date"]).copy()
    g = df.groupby("stock_code")

    close = df["close"]

    df["daily_ret"] = g["close"].transform(lambda s: s.pct_change())
    df["mom_5"] = g["close"].transform(lambda s: s / s.shift(5) - 1.0)
    df["mom_20"] = g["close"].transform(lambda s: s / s.shift(20) - 1.0)
    df["mom_60"] = g["close"].transform(lambda s: s / s.shift(60) - 1.0)
    df["short_reversal_5"] = 1.0 - g["close"].transform(lambda s: s / s.shift(5))
    df["volatility_20"] = g["daily_ret"].transform(lambda s: s.rolling(20, min_periods=10).std())

    df["amplitude"] = (df["high"] - df["low"]) / df["prev_close"].replace(0, np.nan)
    df["amplitude_5"] = g["amplitude"].transform(lambda s: s.rolling(5, min_periods=3).mean())

    df["turnover_20"] = g["turnover_pct"].transform(lambda s: s.rolling(20, min_periods=10).mean())
    df["bp"] = np.where(df["pb"] > 0, 1.0 / df["pb"], np.nan)
    df["ep_ttm"] = np.where(df["pe_ttm"] > 0, 1.0 / df["pe_ttm"], np.nan)
    df["size"] = np.where(df["float_mkt_cap_10k"] > 0, np.log(df["float_mkt_cap_10k"]), np.nan)
    df["liquidity"] = np.where(df["amount_k"] > 0, np.log(df["amount_k"]), np.nan)

    # volume_ma20_gap 用于 double_q60 策略
    df["volume_ma20_gap"] = g["amount_k"].transform(
        lambda s: s / s.rolling(20, min_periods=20).mean() - 1.0
    )

    return df


# ---------------------------------------------------------------------------
# Round-2 技术因子（向量化优化版）
# ---------------------------------------------------------------------------

def _calc_adx(group: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    high = group["high"]
    low = group["low"]
    close = group["close"]
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    prev_close = close.shift(1)

    plus_dm = (high - prev_high).where((high - prev_high) > (prev_low - low), 0.0).clip(lower=0)
    minus_dm = (prev_low - low).where((prev_low - low) > (high - prev_high), 0.0).clip(lower=0)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)

    tr_n = tr.rolling(window, min_periods=window).sum()
    plus_di = 100 * plus_dm.rolling(window, min_periods=window).sum() / tr_n.replace(0, np.nan)
    minus_di = 100 * minus_dm.rolling(window, min_periods=window).sum() / tr_n.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.rolling(window, min_periods=window).mean()

    group = group.copy()
    group["adx_14"] = adx
    group["plus_di_14"] = plus_di
    group["minus_di_14"] = minus_di
    return group


def _compute_round2_factors(panel: pd.DataFrame) -> pd.DataFrame:
    df = panel.copy().sort_values(["stock_code", "trade_date"]).reset_index(drop=True)
    g = df.groupby("stock_code")

    high = df["high"]
    low = df["low"]
    close = df["close"]
    open_ = df["open"]

    roll_high_20 = g["high"].transform(lambda s: s.rolling(20, min_periods=20).max())
    roll_low_20 = g["low"].transform(lambda s: s.rolling(20, min_periods=20).min())
    std20 = g["close"].transform(lambda s: s.rolling(20, min_periods=20).std())
    ma20 = g["close"].transform(lambda s: s.rolling(20, min_periods=20).mean())
    range10 = (
        g["high"].transform(lambda s: s.rolling(10, min_periods=10).max())
        - g["low"].transform(lambda s: s.rolling(10, min_periods=10).min())
    )
    range20 = (
        g["high"].transform(lambda s: s.rolling(20, min_periods=20).max())
        - g["low"].transform(lambda s: s.rolling(20, min_periods=20).min())
    )

    df["donchian_pos_20"] = (close - roll_low_20) / (roll_high_20 - roll_low_20).replace(0, np.nan)
    df["breakout_20"] = close / roll_high_20.shift(1) - 1.0
    df["pullback_from_20d_high"] = close / roll_high_20 - 1.0
    df["bb_width_20"] = (4 * std20) / ma20.replace(0, np.nan)
    df["range_compress_10_20"] = range10 / range20.replace(0, np.nan)

    body = (close - open_).abs()
    total_range = (high - low).replace(0, np.nan)
    df["intraday_body_ratio"] = body / total_range
    df["upper_shadow_ratio"] = (high - np.maximum(open_, close)) / total_range
    df["lower_shadow_ratio"] = (np.minimum(open_, close) - low) / total_range
    df["gap_from_prev_close"] = open_ / df["prev_close"].replace(0, np.nan) - 1.0

    # ADX 仍需逐股计算，但数据量已因裁剪而减小
    adx_frames = []
    for _, group in df.groupby("stock_code"):
        adx_frames.append(_calc_adx(group, 14))
    df = pd.concat(adx_frames).sort_values(["stock_code", "trade_date"]).reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# 因子处理
# ---------------------------------------------------------------------------

def _winsorize_series(s: pd.Series, lower_pct: float = 0.01, upper_pct: float = 0.01) -> pd.Series:
    lower = s.quantile(lower_pct)
    upper = s.quantile(1.0 - upper_pct)
    return s.clip(lower=lower, upper=upper)


def _zscore_series(s: pd.Series) -> pd.Series:
    mean = s.mean()
    std = s.std(ddof=0)
    if std is None or std == 0 or pd.isna(std):
        return pd.Series(0.0, index=s.index)
    return (s - mean) / std


def _prepare_factors(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    processed_factors = []
    oriented_factors = []

    df["size_w"] = df.groupby("trade_date")["size"].transform(lambda s: _winsorize_series(s))
    df["size_z"] = df.groupby("trade_date")["size_w"].transform(lambda s: _zscore_series(s))

    for factor in BASE_FACTOR_COLUMNS:
        if factor not in df.columns:
            continue

        w_col = f"{factor}_w"
        z_col = f"{factor}_z"
        neutral_col = f"{factor}_xn"
        oriented_col = f"{factor}_alpha"

        df[w_col] = df.groupby("trade_date")[factor].transform(lambda s: _winsorize_series(s))
        df[z_col] = df.groupby("trade_date")[w_col].transform(lambda s: _zscore_series(s))

        if factor == "size":
            df[neutral_col] = df[z_col]
        else:
            residuals = []
            for _, group in df.groupby("trade_date"):
                x = group["size_z"].values
                y = group[z_col].values
                mask = np.isfinite(x) & np.isfinite(y)
                resid = np.full(len(group), np.nan)
                if mask.sum() >= 10 and np.var(x[mask]) > 0:
                    beta = np.cov(x[mask], y[mask])[0, 1] / np.var(x[mask])
                    resid[mask] = y[mask] - beta * x[mask]
                residuals.append(pd.Series(resid, index=group.index))
            df[neutral_col] = pd.concat(residuals)

        df[oriented_col] = df[neutral_col] * ORIENTATION.get(factor, 1.0)
        processed_factors.append(neutral_col)
        oriented_factors.append(oriented_col)

    core_cols = [f"{f}_alpha" for f in CORE_COMBO_INPUTS if f"{f}_alpha" in df.columns]
    if core_cols:
        df["core_combo_alpha"] = df[core_cols].mean(axis=1)
    else:
        df["core_combo_alpha"] = np.nan

    all_cols = [c for c in oriented_factors if c in df.columns]
    if all_cols:
        df["full_combo_alpha"] = df[all_cols].mean(axis=1)
    else:
        df["full_combo_alpha"] = np.nan

    return df


# ---------------------------------------------------------------------------
# 信号生成
# ---------------------------------------------------------------------------

def make_signal(df: pd.DataFrame, filters: list[tuple[str, str, float]] | None) -> pd.Series:
    if not filters:
        return df["core_combo_alpha"].copy()

    cond = pd.Series(True, index=df.index)
    for col, side, q in filters:
        if col not in df.columns:
            continue
        ranks = df.groupby("trade_date")[col].transform(lambda s: s.rank(pct=True, method="average"))
        if side == "low":
            cond &= ranks <= q
        else:
            cond &= ranks >= q

    out = pd.Series(np.nan, index=df.index)
    out.loc[cond] = df.loc[cond, "core_combo_alpha"]
    return out


# ---------------------------------------------------------------------------
# 过滤
# ---------------------------------------------------------------------------

def _apply_filters(
    df: pd.DataFrame,
    min_listing_days: int = DEFAULT_MIN_LISTING_DAYS,
    min_amount_k: float = DEFAULT_MIN_AMOUNT_K,
) -> pd.DataFrame:
    df = df.copy()
    if "listing_days" not in df.columns:
        df["listing_days"] = df.groupby("stock_code")["trade_date"].transform("cumcount") + 1

    if "stock_name" in df.columns:
        df["is_st"] = df["stock_name"].str.upper().str.contains("ST", na=False)
    else:
        df["is_st"] = False

    df["exchange"] = df["stock_code"].str.split(".").str[-1]

    mask = (
        (df["listing_days"] >= min_listing_days)
        & df["close"].notna()
        & (df["volume"] > 0)
        & (df["amount_k"] >= min_amount_k)
        & ~df["is_st"]
        & (df["exchange"] != "BJ")
    )
    return df[mask].copy()


# ---------------------------------------------------------------------------
# 最新日扫描（核心入口）
# ---------------------------------------------------------------------------

def scan_line_a_candidates(
    df: pd.DataFrame,
    trade_date: str | None = None,
    strategy: str = "double_q60_top10",
    top_n: int = 6,
    keep_rank: int = 8,
    min_listing_days: int = DEFAULT_MIN_LISTING_DAYS,
    min_amount_k: float = DEFAULT_MIN_AMOUNT_K,
) -> pd.DataFrame:
    if strategy not in STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy}. Available: {list(STRATEGIES.keys())}")

    spec = STRATEGIES[strategy]
    filters = spec["filters"]

    # 日期回退：如果请求的日期不存在，使用最新日期
    if trade_date is not None:
        target_date = pd.to_datetime(trade_date)
        if target_date not in df["trade_date"].values:
            return pd.DataFrame()
    else:
        target_date = df["trade_date"].max()

    # 先在完整数据上计算 listing_days，避免裁剪后 cumcount 过小
    df["listing_days"] = df.groupby("stock_code")["trade_date"].transform("cumcount") + 1

    # 裁剪数据到回退日期前 LOOKBACK_DAYS 天，加速计算
    cutoff_date = target_date - pd.Timedelta(days=LOOKBACK_DAYS)
    df = df[df["trade_date"] >= cutoff_date].copy()

    df = _compute_base_factors(df)
    df = _compute_round2_factors(df)
    df = _apply_filters(df, min_listing_days, min_amount_k)
    df = _prepare_factors(df)

    day_df = df[df["trade_date"] == target_date].copy()
    if day_df.empty:
        return pd.DataFrame()

    day_df["signal"] = make_signal(day_df, filters)
    day_df = day_df.dropna(subset=["signal"]).copy()
    if day_df.empty:
        return pd.DataFrame()

    day_df = day_df.sort_values("signal", ascending=False).reset_index(drop=True)
    day_df["rank_pos"] = np.arange(1, len(day_df) + 1)
    day_df["in_entry_top_n"] = day_df["rank_pos"] <= top_n
    day_df["in_keep_zone"] = day_df["rank_pos"] <= keep_rank

    day_df["action"] = "watch"
    day_df.loc[day_df["in_entry_top_n"], "action"] = "target"

    def _label_state(row: pd.Series) -> str:
        if row["in_entry_top_n"]:
            return "line_a_top_entry"
        if row["in_keep_zone"]:
            return "line_a_keep_zone"
        return "line_a_watch"

    day_df["technical_state"] = day_df.apply(_label_state, axis=1)

    output_cols = [
        "trade_date", "stock_code", "stock_name",
        "rank_pos", "signal", "action",
        "in_entry_top_n", "in_keep_zone", "technical_state",
    ]
    available_cols = [c for c in output_cols if c in day_df.columns]
    return day_df[available_cols].copy()
