from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl


MAIN_BOARD_PATTERN = r"^((600|601|603|605)\d{3}\.SH|(000|001|002|003)\d{3}\.SZ)$"


def zscore_by_date(df: pd.DataFrame, column: str) -> pd.Series:
    grouped = df.groupby("trade_date")[column]
    mean = grouped.transform("mean")
    std = grouped.transform("std").replace(0.0, np.nan)
    return ((df[column] - mean) / std).replace([np.inf, -np.inf], np.nan)


def optimize_numeric_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    float_cols = df.select_dtypes(include=["float64"]).columns
    int_cols = df.select_dtypes(include=["int64"]).columns
    for col in float_cols:
        df[col] = pd.to_numeric(df[col], downcast="float")
    for col in int_cols:
        df[col] = pd.to_numeric(df[col], downcast="integer")
    return df


def add_intraday_daily_context(panel: pd.DataFrame) -> pd.DataFrame:
    grouped = panel.groupby("stock_code", group_keys=False)
    amount_20 = grouped["amount_k"].transform(lambda s: s.rolling(20, min_periods=10).mean())
    panel["volume_ma20_gap"] = panel["amount_k"] / amount_20.replace(0.0, np.nan) - 1.0
    panel["volume_ma20_gap_z"] = zscore_by_date(panel, "volume_ma20_gap")
    return panel


def _date_to_int(value: str) -> int:
    return int(value.replace("-", ""))


def _list_intraday_files(
    intraday_dir: Path,
    start_date: str,
    end_date: str | None,
) -> list[Path]:
    start_int = _date_to_int(start_date)
    end_int = _date_to_int(end_date) if end_date else 99991231
    files: list[Path] = []
    for path in sorted(intraday_dir.glob("*.parquet")):
        try:
            date_int = int(path.stem)
        except ValueError:
            continue
        if start_int <= date_int <= end_int:
            files.append(path)
    return files


def _aggregate_intraday_file(path: Path) -> pd.DataFrame:
    day = (
        pl.read_parquet(
            str(path),
            columns=["code", "trade_time", "date", "open", "high", "low", "close", "vol", "amount"],
        )
        .with_columns(
            [
                pl.col("code").cast(pl.Utf8).str.to_uppercase().alias("stock_code"),
                pl.col("date").cast(pl.Int64, strict=False).alias("date_int"),
                pl.col("trade_time").cast(pl.Utf8).str.slice(-8).alias("hhmmss"),
            ]
        )
        .filter(pl.col("stock_code").str.contains(MAIN_BOARD_PATTERN))
        .with_columns(pl.col("date_int").cast(pl.Utf8).str.strptime(pl.Date, "%Y%m%d").alias("trade_date"))
    )

    first30 = pl.col("hhmmss") <= "10:00:00"
    first60 = pl.col("hhmmss") <= "10:30:00"
    last30 = pl.col("hhmmss") >= "14:30:00"
    last60 = pl.col("hhmmss") >= "14:00:00"

    daily = (
        day.group_by(["stock_code", "trade_date"])
        .agg(
            [
                pl.col("open").first().alias("m_open"),
                pl.col("close").last().alias("m_close"),
                pl.col("high").max().alias("m_high"),
                pl.col("low").min().alias("m_low"),
                pl.col("vol").sum().alias("m_vol_total"),
                pl.col("amount").sum().alias("m_amount_total"),
                pl.col("close").filter(pl.col("hhmmss") == "10:00:00").last().alias("m_close_1000"),
                pl.col("close").filter(pl.col("hhmmss") == "10:30:00").last().alias("m_close_1030"),
                pl.col("close").filter(pl.col("hhmmss") == "14:00:00").last().alias("m_close_1400"),
                pl.col("close").filter(pl.col("hhmmss") == "14:30:00").last().alias("m_close_1430"),
                pl.col("low").filter(first30).min().alias("m_low_first30"),
                pl.col("low").filter(first60).min().alias("m_low_first60"),
                pl.col("amount").filter(first30).sum().alias("m_amount_first30"),
                pl.col("amount").filter(last30).sum().alias("m_amount_last30"),
                pl.col("amount").filter(last60).sum().alias("m_amount_last60"),
                pl.col("high").filter(last60).max().alias("m_high_last60"),
            ]
        )
        .with_columns(
            [
                pl.when(pl.col("m_vol_total") > 0)
                .then(pl.col("m_amount_total") / pl.col("m_vol_total"))
                .otherwise(None)
                .alias("m_vwap"),
            ]
        )
        .with_columns(
            [
                (pl.col("m_close_1000") / pl.col("m_open") - 1.0).alias("m_first30_ret"),
                (pl.col("m_close_1030") / pl.col("m_open") - 1.0).alias("m_first60_ret"),
                (pl.col("m_close") / pl.col("m_close_1430") - 1.0).alias("m_last30_ret"),
                (pl.col("m_close") / pl.col("m_close_1400") - 1.0).alias("m_last60_ret"),
                (pl.col("m_close") / pl.col("m_vwap") - 1.0).alias("m_close_vs_vwap"),
                (pl.col("m_low_first30") / pl.col("m_open") - 1.0).alias("m_first30_drawdown"),
                (pl.col("m_low_first60") / pl.col("m_open") - 1.0).alias("m_first60_drawdown"),
                (pl.col("m_close") / pl.col("m_low_first60") - 1.0).alias("m_rebound_from_first60_low"),
                (pl.col("m_close") / pl.col("m_low") - 1.0).alias("m_close_from_day_low"),
                (pl.col("m_high_last60") / pl.col("m_close_1400") - 1.0).alias("m_high_break_last60"),
                (pl.col("m_amount_first30") / pl.col("m_amount_total")).alias("m_amount_share_first30"),
                (pl.col("m_amount_last30") / pl.col("m_amount_total")).alias("m_amount_share_last30"),
                (pl.col("m_amount_last60") / pl.col("m_amount_total")).alias("m_amount_share_last60"),
                (pl.col("m_high") / pl.col("m_low") - 1.0).alias("m_intraday_range"),
            ]
        )
        .sort(["trade_date", "stock_code"])
        .to_pandas()
    )
    daily["trade_date"] = pd.to_datetime(daily["trade_date"])
    return optimize_numeric_dtypes(daily)


def build_intraday_feature_cache(
    intraday_dir: Path,
    cache_path: Path,
    start_date: str = "2020-01-01",
    end_date: str | None = None,
    force: bool = False,
) -> pd.DataFrame:
    """Aggregate daily minute-bar features and persist a resumable cache."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    requested_files = _list_intraday_files(intraday_dir, start_date, end_date)
    existing = pd.DataFrame()
    if cache_path.exists() and not force:
        existing = pd.read_parquet(cache_path)
        if not existing.empty:
            existing["trade_date"] = pd.to_datetime(existing["trade_date"])
            existing = optimize_numeric_dtypes(existing)
    existing_dates = set()
    if not existing.empty:
        existing_dates = set(existing["trade_date"].dt.strftime("%Y%m%d"))

    missing_files = [path for path in requested_files if path.stem not in existing_dates]
    if missing_files:
        batch_frames: list[pd.DataFrame] = []
        combined_batches: list[pd.DataFrame] = []
        total = len(missing_files)
        for idx, path in enumerate(missing_files, start=1):
            batch_frames.append(_aggregate_intraday_file(path))
            if idx % 20 == 0 or idx == total:
                print(f"[intraday-cache] aggregated {idx}/{total} daily files")
                combined_batches.append(pd.concat(batch_frames, ignore_index=True))
                batch_frames.clear()
        new_data = pd.concat(combined_batches, ignore_index=True) if combined_batches else pd.DataFrame()
        full = pd.concat([existing, new_data], ignore_index=True) if not existing.empty else new_data
        full = full.drop_duplicates(subset=["stock_code", "trade_date"], keep="last").sort_values(
            ["trade_date", "stock_code"]
        )
        full = optimize_numeric_dtypes(full)
        full.to_parquet(cache_path, index=False)
        existing = full

    if existing.empty:
        return existing

    start_ts = pd.Timestamp(start_date)
    mask = existing["trade_date"] >= start_ts
    if end_date:
        mask &= existing["trade_date"] <= pd.Timestamp(end_date)
    out = existing.loc[mask].copy()
    out = optimize_numeric_dtypes(out)
    return out


def add_intraday_signals(panel: pd.DataFrame, intraday_features: pd.DataFrame) -> pd.DataFrame:
    minute = intraday_features.copy()
    z_cols = [
        "m_first30_ret",
        "m_first60_ret",
        "m_last30_ret",
        "m_last60_ret",
        "m_close_vs_vwap",
        "m_first30_drawdown",
        "m_first60_drawdown",
        "m_rebound_from_first60_low",
        "m_close_from_day_low",
        "m_high_break_last60",
        "m_amount_share_first30",
        "m_amount_share_last30",
        "m_amount_share_last60",
        "m_intraday_range",
    ]
    for col in z_cols:
        if col in minute.columns:
            minute[f"{col}_z"] = zscore_by_date(minute, col)

    context = panel[
        [
            "stock_code",
            "trade_date",
            "volatility_20_z",
            "volume_ma20_gap_z",
            "short_reversal_5_z",
            "breakout_20_z",
        ]
    ].copy()
    df = context.merge(minute, on=["stock_code", "trade_date"], how="left")

    lowvol = -df["volatility_20_z"]
    lowcrowd = -df["volume_ma20_gap_z"]
    reversal = df["short_reversal_5_z"]

    signals = df[["stock_code", "trade_date"]].copy()
    signals["i201_open_panic_close_recover"] = np.where(
        (df["m_first60_drawdown"] < -0.02) & (df["m_close_vs_vwap"] > 0) & (df["m_last60_ret"] > 0),
        -df["m_first60_drawdown_z"] + 0.60 * df["m_close_vs_vwap_z"] + 0.40 * df["m_last60_ret_z"] + 0.20 * lowcrowd,
        np.nan,
    )
    signals["i202_weak_open_strong_close"] = np.where(
        (df["m_first30_ret"] < 0) & (df["m_last30_ret"] > 0) & (df["m_close_vs_vwap"] > 0),
        -df["m_first30_ret_z"] + 0.80 * df["m_last30_ret_z"] + 0.50 * df["m_close_vs_vwap_z"] + 0.20 * lowvol,
        np.nan,
    )
    signals["i203_afternoon_breakout_follow"] = np.where(
        (df["m_last60_ret"] > 0) & (df["m_amount_share_last60"] > 0.25),
        df["m_last60_ret_z"] + 0.60 * df["m_amount_share_last60_z"] + 0.40 * df["m_close_vs_vwap_z"] + 0.20 * df["breakout_20_z"],
        np.nan,
    )
    signals["i204_vwap_support_reversal"] = np.where(
        (df["m_first60_drawdown"] < -0.015) & (df["m_close_vs_vwap"] > 0),
        df["m_close_vs_vwap_z"] + 0.70 * df["m_rebound_from_first60_low_z"] - 0.50 * df["m_first60_drawdown_z"] + 0.20 * reversal,
        np.nan,
    )
    signals["i205_intraday_trend_day_lowvol"] = np.where(
        (df["m_first30_ret"] > 0) & (df["m_last60_ret"] > 0) & (df["m_close_vs_vwap"] > 0),
        0.60 * df["m_first30_ret_z"] + 0.80 * df["m_last60_ret_z"] + 0.60 * df["m_close_vs_vwap_z"] + 0.20 * lowvol,
        np.nan,
    )
    signals["i206_late_buying_pressure_lowcrowding"] = np.where(
        (df["m_last30_ret"] > 0) & (df["m_amount_share_last60"] > 0.22),
        df["m_last30_ret_z"] + 0.70 * df["m_amount_share_last60_z"] + 0.50 * df["m_close_vs_vwap_z"] + 0.30 * lowcrowd,
        np.nan,
    )
    signals["i207_morning_flush_afternoon_reverse"] = np.where(
        (df["m_first30_drawdown"] < -0.02) & (df["m_last30_ret"] > 0) & (df["m_close_from_day_low"] > 0.03),
        -df["m_first30_drawdown_z"] + 0.80 * df["m_last30_ret_z"] + 0.50 * df["m_close_from_day_low_z"] + 0.20 * reversal,
        np.nan,
    )
    signals = optimize_numeric_dtypes(signals)
    out = panel.merge(signals, on=["stock_code", "trade_date"], how="left")
    return optimize_numeric_dtypes(out)
