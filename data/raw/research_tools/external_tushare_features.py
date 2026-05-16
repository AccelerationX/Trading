from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(r"D:\TradingMain")
REFERENCE_DIR = ROOT / "research" / "reference" / "tushare"
INDEX_DIR = REFERENCE_DIR / "index_daily"
INDUSTRY_DIR = REFERENCE_DIR / "sw_l1"
CACHE_DIR = ROOT / "research" / "cache"

INDEX_FILES = {
    "CSI300": INDEX_DIR / "CSI300_000300_SH.csv",
    "CSI500": INDEX_DIR / "CSI500_000905_SH.csv",
    "CSI1000": INDEX_DIR / "CSI1000_000852_SH.csv",
    "CSI_ALL_SHARE": INDEX_DIR / "CSI_ALL_SHARE_000985_CSI.csv",
}


def zscore_by_date(df: pd.DataFrame, column: str) -> pd.Series:
    grouped = df.groupby("trade_date")[column]
    mean = grouped.transform("mean")
    std = grouped.transform("std").replace(0.0, np.nan)
    return ((df[column] - mean) / std).replace([np.inf, -np.inf], np.nan)


def _load_index_frame(path: Path, prefix: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing index reference file: {path}")
    df = pd.read_csv(path)
    if df.empty:
        raise RuntimeError(f"Empty index reference file: {path}")
    df["trade_date"] = pd.to_datetime(df["trade_date"].astype(str), format="%Y%m%d", errors="coerce")
    df = df.sort_values("trade_date").copy()
    df[f"{prefix}_close"] = pd.to_numeric(df["close"], errors="coerce")
    df[f"{prefix}_ret_20"] = df[f"{prefix}_close"] / df[f"{prefix}_close"].shift(20) - 1.0
    df[f"{prefix}_ret_60"] = df[f"{prefix}_close"] / df[f"{prefix}_close"].shift(60) - 1.0
    return df[["trade_date", f"{prefix}_close", f"{prefix}_ret_20", f"{prefix}_ret_60"]]


def load_index_state_features() -> pd.DataFrame:
    base = None
    for prefix, path in INDEX_FILES.items():
        frame = _load_index_frame(path, prefix.lower())
        base = frame if base is None else base.merge(frame, on="trade_date", how="outer")
    df = base.sort_values("trade_date").copy()
    df["style_small_vs_large_20"] = (
        df["csi1000_ret_20"] - df["csi300_ret_20"]
    )
    df["style_small_vs_large_60"] = (
        df["csi1000_ret_60"] - df["csi300_ret_60"]
    )
    df["external_risk_on_gate"] = (
        (df["csi_all_share_ret_20"] > 0)
        | ((df["csi300_ret_20"] > 0) & (df["csi1000_ret_20"] > -0.02))
    )
    df["small_style_gate"] = (
        (df["style_small_vs_large_20"] > 0)
        | (df["style_small_vs_large_60"] > 0)
    )
    df["defensive_exposure"] = np.select(
        [
            df["csi_all_share_ret_20"] > 0.03,
            df["csi_all_share_ret_20"] > -0.03,
        ],
        [1.0, 0.60],
        default=0.25,
    )
    return df.sort_values("trade_date").reset_index(drop=True)


def load_sw_members() -> pd.DataFrame:
    path = INDUSTRY_DIR / "index_members.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing SW member file: {path}")
    df = pd.read_csv(path)
    if df.empty:
        raise RuntimeError(f"Empty SW member file: {path}")
    stock_col = "con_code" if "con_code" in df.columns else "ts_code"
    name_col = "industry_name" if "industry_name" in df.columns else "index_name"
    code_col = "industry_code" if "industry_code" in df.columns else "index_code"

    out = df[[stock_col, code_col, name_col, "in_date", "out_date"]].copy()
    out.columns = ["stock_code", "industry_code", "industry_name", "in_date", "out_date"]
    out["stock_code"] = out["stock_code"].astype(str).str.upper()
    out["in_date"] = pd.to_datetime(out["in_date"], format="%Y%m%d", errors="coerce")
    out["out_date"] = pd.to_datetime(out["out_date"], format="%Y%m%d", errors="coerce")
    return out.sort_values(["stock_code", "in_date", "out_date"]).reset_index(drop=True)


def build_daily_sw_membership_cache(
    panel_dates: pd.Series,
    members: pd.DataFrame,
    cache_path: Path | None = None,
) -> pd.DataFrame:
    import numpy as np

    cache_path = cache_path or CACHE_DIR / "sw_l1_daily_membership_2020plus.parquet"
    dates = pd.DatetimeIndex(sorted(pd.to_datetime(panel_dates).drop_duplicates()))
    min_date = dates.min()
    max_date = dates.max()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if cache_path.exists():
        cached = pd.read_parquet(cache_path)
        cached["trade_date"] = pd.to_datetime(cached["trade_date"])
        if cached["trade_date"].min() <= min_date and cached["trade_date"].max() >= max_date:
            return cached[
                (cached["trade_date"] >= min_date) & (cached["trade_date"] <= max_date)
            ].copy()

    # 向量化重建：避免每次循环创建 DataFrame，改用 numpy 数组累积
    records: list[tuple] = []
    total = len(members)
    for idx, row in enumerate(members.itertuples(index=False), start=1):
        start = row.in_date if pd.notna(row.in_date) else min_date
        end = row.out_date if pd.notna(row.out_date) else max_date
        start = max(start, min_date)
        end = min(end, max_date)
        if start > end:
            continue
        mask = (dates >= start) & (dates <= end)
        matched_dates = dates[mask]
        if len(matched_dates) == 0:
            continue
        n = len(matched_dates)
        records.append((
            np.full(n, row.stock_code, dtype=object),
            matched_dates.values,
            np.full(n, row.industry_code, dtype=object),
            np.full(n, row.industry_name, dtype=object),
        ))
        if idx % 1000 == 0 or idx == total:
            print(f"[sw-membership-cache] expanded {idx}/{total} membership rows")

    if records:
        daily = pd.DataFrame({
            "stock_code": np.concatenate([r[0] for r in records]),
            "trade_date": np.concatenate([r[1] for r in records]),
            "industry_code": np.concatenate([r[2] for r in records]),
            "industry_name": np.concatenate([r[3] for r in records]),
        })
        daily["trade_date"] = pd.to_datetime(daily["trade_date"])
    else:
        daily = pd.DataFrame(columns=["stock_code", "trade_date", "industry_code", "industry_name"])
    daily.to_parquet(cache_path, index=False)
    return daily


def add_external_tushare_features(panel: pd.DataFrame) -> pd.DataFrame:
    df = panel.copy().sort_values(["stock_code", "trade_date"])
    members = load_sw_members()
    daily_members = build_daily_sw_membership_cache(df["trade_date"], members)
    df = df.merge(daily_members, on=["stock_code", "trade_date"], how="left")

    grouped = df.groupby("stock_code", group_keys=False)
    df["amount_5"] = grouped["amount_k"].transform(lambda s: s.rolling(5, min_periods=3).mean())
    df["amount_20"] = grouped["amount_k"].transform(lambda s: s.rolling(20, min_periods=10).mean())
    df["ma20"] = grouped["close"].transform(lambda s: s.rolling(20, min_periods=20).mean())
    df["prior_high_20"] = grouped["high"].transform(lambda s: s.rolling(20, min_periods=20).max().shift(1))
    df["recent_breakout_10"] = grouped["breakout_20"].transform(lambda s: s.shift(1).rolling(10, min_periods=3).max())
    df["breakout_gap"] = df["close"] / df["prior_high_20"].replace(0.0, np.nan) - 1.0
    df["breakout_retest_score"] = -df["breakout_gap"].abs()
    df["amount_ratio_5_20"] = df["amount_5"] / df["amount_20"].replace(0.0, np.nan) - 1.0
    df["volume_ma20_gap"] = df["amount_k"] / df["amount_20"].replace(0.0, np.nan) - 1.0
    df["close_range_pos"] = (df["close"] - df["low"]) / (df["high"] - df["low"]).replace(0.0, np.nan)
    df["amount_ratio_5_20_z"] = zscore_by_date(df, "amount_ratio_5_20")
    df["volume_ma20_gap_z"] = zscore_by_date(df, "volume_ma20_gap")
    df["breakout_retest_score_z"] = zscore_by_date(df, "breakout_retest_score")
    df["close_range_pos_z"] = zscore_by_date(df, "close_range_pos")
    df["mid_size_score"] = -((df.groupby("trade_date")["size"].transform(lambda s: s.rank(pct=True, method="average")) - 0.50).abs())
    df["mid_size_score_z"] = zscore_by_date(df, "mid_size_score")
    df["line_a_core_signal"] = np.where(
        (
            df.groupby("trade_date")["volume_ma20_gap"].transform(lambda s: s.rank(pct=True, method="average")) <= 0.60
        )
        & (
            df.groupby("trade_date")["range_compress_10_20"].transform(lambda s: s.rank(pct=True, method="average")) <= 0.60
        ),
        (df["bp_z"] + df["short_reversal_5_z"] - df["size_z"] - df["liquidity_z"]) / 4.0,
        np.nan,
    )

    industry = (
        df.dropna(subset=["industry_code"])
        .groupby(["trade_date", "industry_code", "industry_name"])
        .agg(
            industry_ew_ret=("daily_ret", "mean"),
            industry_amount_k=("amount_k", "sum"),
            industry_adv_ratio=("daily_ret", lambda s: float((s > 0).mean())),
            industry_avg_volume_gap=("volume_ma20_gap", "mean"),
        )
        .reset_index()
        .sort_values(["industry_code", "trade_date"])
    )
    industry["market_amount_k"] = industry.groupby("trade_date")["industry_amount_k"].transform("sum")
    industry["industry_amount_share"] = industry["industry_amount_k"] / industry["market_amount_k"].replace(0.0, np.nan)
    industry["industry_nav"] = industry.groupby("industry_code")["industry_ew_ret"].transform(
        lambda s: (1.0 + s.fillna(0.0)).cumprod()
    )
    industry["industry_ret_20"] = industry.groupby("industry_code")["industry_nav"].transform(
        lambda s: s / s.shift(20) - 1.0
    )
    industry["industry_ret_60"] = industry.groupby("industry_code")["industry_nav"].transform(
        lambda s: s / s.shift(60) - 1.0
    )
    industry["industry_breadth_5"] = industry.groupby("industry_code")["industry_adv_ratio"].transform(
        lambda s: s.rolling(5, min_periods=3).mean()
    )
    industry["industry_breadth_20"] = industry.groupby("industry_code")["industry_adv_ratio"].transform(
        lambda s: s.rolling(20, min_periods=10).mean()
    )
    industry["industry_breadth_improve_5"] = industry["industry_breadth_5"] - industry.groupby("industry_code")["industry_breadth_5"].shift(5)
    industry["industry_amount_share_20"] = industry.groupby("industry_code")["industry_amount_share"].transform(
        lambda s: s.rolling(20, min_periods=10).mean()
    )
    industry["industry_amount_share_gain"] = (
        industry["industry_amount_share"] / industry["industry_amount_share_20"].replace(0.0, np.nan) - 1.0
    )
    industry["industry_crowding_5"] = industry.groupby("industry_code")["industry_avg_volume_gap"].transform(
        lambda s: s.rolling(5, min_periods=3).mean()
    )
    industry["industry_ret_20_rank"] = industry.groupby("trade_date")["industry_ret_20"].transform(
        lambda s: s.rank(pct=True, method="average")
    )
    industry["industry_ret_60_rank"] = industry.groupby("trade_date")["industry_ret_60"].transform(
        lambda s: s.rank(pct=True, method="average")
    )
    industry["industry_breadth_rank"] = industry.groupby("trade_date")["industry_breadth_20"].transform(
        lambda s: s.rank(pct=True, method="average")
    )
    industry["industry_amount_share_rank"] = industry.groupby("trade_date")["industry_amount_share_gain"].transform(
        lambda s: s.rank(pct=True, method="average")
    )

    df = df.merge(
        industry[
            [
                "trade_date",
                "industry_code",
                "industry_ew_ret",
                "industry_ret_20",
                "industry_ret_60",
                "industry_ret_20_rank",
                "industry_ret_60_rank",
                "industry_breadth_5",
                "industry_breadth_20",
                "industry_breadth_improve_5",
                "industry_amount_share_gain",
                "industry_crowding_5",
                "industry_breadth_rank",
                "industry_amount_share_rank",
            ]
        ],
        on=["trade_date", "industry_code"],
        how="left",
    )
    df["industry_ret_20_z"] = zscore_by_date(df, "industry_ret_20")
    df["industry_ret_60_z"] = zscore_by_date(df, "industry_ret_60")
    df["industry_breadth_20_z"] = zscore_by_date(df, "industry_breadth_20")
    df["industry_breadth_improve_5_z"] = zscore_by_date(df, "industry_breadth_improve_5")
    df["industry_amount_share_gain_z"] = zscore_by_date(df, "industry_amount_share_gain")
    df["industry_crowding_5_z"] = zscore_by_date(df, "industry_crowding_5")
    df["industry_breadth_rank_z"] = zscore_by_date(df, "industry_breadth_rank")
    df["industry_amount_share_rank_z"] = zscore_by_date(df, "industry_amount_share_rank")
    df["industry_mom20_rank_in_group"] = df.groupby(["trade_date", "industry_code"])["mom_20"].transform(
        lambda s: s.rank(pct=True, method="average")
    )
    df["industry_line_a_rank_in_group"] = df.groupby(["trade_date", "industry_code"])["line_a_core_signal"].transform(
        lambda s: s.rank(pct=True, method="average")
    )
    df["industry_lowvol_rank_in_group"] = df.groupby(["trade_date", "industry_code"])["volatility_20"].transform(
        lambda s: 1.0 - s.rank(pct=True, method="average")
    )

    index_state = load_index_state_features()
    df = df.merge(index_state, on="trade_date", how="left")

    strong_industry = df["industry_ret_20_rank"] >= 0.70
    weak_industry = df["industry_ret_20_rank"] <= 0.20
    line_a = df["line_a_core_signal"]
    lowvol = -df["volatility_20_z"]
    lowcrowd = -df["volume_ma20_gap_z"]
    reversal = df["short_reversal_5_z"]
    value = df["bp_z"]
    small = -df["size_z"]
    breakout = df["breakout_20_z"]
    compression = -df["range_compress_10_20_z"]

    df["tx201_line_a_industry_leader"] = np.where(
        strong_industry,
        line_a + 0.35 * df["industry_ret_20_z"],
        np.nan,
    )
    df["tx202_line_a_avoid_weak_industry"] = np.where(
        ~weak_industry,
        line_a,
        np.nan,
    )
    df["tx203_small_value_style_gate"] = np.where(
        df["small_style_gate"],
        0.45 * small + 0.35 * value + 0.20 * reversal + 0.20 * df["industry_ret_20_z"],
        np.nan,
    )
    df["tx204_breakout_industry_risk_on"] = np.where(
        df["external_risk_on_gate"] & strong_industry,
        breakout + 0.50 * compression + 0.35 * df["industry_ret_20_z"] + 0.20 * lowcrowd,
        np.nan,
    )
    df["tx205_line_a_style_exposure"] = line_a + 0.20 * df["industry_ret_20_z"]
    df["tx206_defensive_value_index_exposure"] = (
        0.45 * value + 0.35 * lowvol + 0.20 * df["industry_ret_60_z"] - 0.10 * small
    )
    df["tx207_industry_relative_reversal"] = np.where(
        ~weak_industry,
        reversal + 0.40 * df["industry_ret_20_z"] + 0.20 * lowcrowd + 0.15 * value,
        np.nan,
    )
    df["tx208_industry_compression_breakout"] = np.where(
        strong_industry & df["external_risk_on_gate"],
        compression + 0.60 * breakout + 0.30 * df["industry_ret_20_z"] + 0.20 * lowcrowd,
        np.nan,
    )
    df["s096_industry_relative_strength_leader"] = np.where(
        (df["industry_ret_20_rank"] >= 0.75)
        & (df["industry_mom20_rank_in_group"] >= 0.65),
        0.60 * df["industry_ret_20_z"] + 0.40 * df["mom_20_z"] + 0.25 * lowcrowd,
        np.nan,
    )
    df["s097_industry_improving_stock_not_yet_hot"] = np.where(
        (df["industry_ret_20_rank"] >= 0.70)
        & (df["industry_breadth_improve_5"] > 0)
        & df["mom_5"].between(-0.08, 0.03)
        & (df["close"] >= df["ma20"] * 0.97),
        0.50 * df["industry_ret_20_z"] + 0.40 * df["industry_breadth_improve_5_z"] + 0.35 * reversal + 0.20 * lowcrowd,
        np.nan,
    )
    df["s098_weak_industry_avoidance_overlay"] = np.where(
        (df["industry_ret_20_rank"] > 0.25) & (df["industry_breadth_rank"] > 0.25),
        line_a + 0.15 * df["industry_breadth_20_z"],
        np.nan,
    )
    df["s099_industry_breadth_expansion"] = np.where(
        (df["industry_breadth_rank"] >= 0.65)
        & (df["industry_breadth_improve_5"] > 0),
        0.55 * df["industry_breadth_improve_5_z"] + 0.35 * df["industry_ret_20_z"] + 0.20 * df["mom_20_z"] + 0.20 * lowcrowd,
        np.nan,
    )
    df["s100_industry_amount_share_gain"] = np.where(
        (df["industry_amount_share_rank"] >= 0.70)
        & (df["mom_5"] < 0.08),
        0.55 * df["industry_amount_share_gain_z"] + 0.30 * df["industry_ret_20_z"] + 0.25 * df["amount_ratio_5_20_z"] + 0.15 * lowcrowd,
        np.nan,
    )
    df["s101_strong_industry_lowvol_stock"] = np.where(
        (df["industry_ret_20_rank"] >= 0.70)
        & (df["industry_lowvol_rank_in_group"] >= 0.60),
        0.45 * df["industry_ret_20_z"] + 0.45 * lowvol + 0.20 * value,
        np.nan,
    )
    df["s102_strong_industry_breakout_retest"] = np.where(
        (df["industry_ret_20_rank"] >= 0.70)
        & (df["recent_breakout_10"] > 0)
        & df["breakout_gap"].between(-0.05, 0.02)
        & (df["volume_ma20_gap"] < 0.20),
        0.45 * df["industry_ret_20_z"] + 0.35 * df["breakout_retest_score_z"] + 0.20 * lowcrowd + 0.15 * df["close_range_pos_z"],
        np.nan,
    )
    df["s103_industry_reversal_after_extreme_weakness"] = np.where(
        (df["industry_ret_20_rank"] <= 0.20)
        & (df["industry_breadth_improve_5"] > 0.05),
        -0.45 * df["industry_ret_20_z"] + 0.40 * df["industry_breadth_improve_5_z"] + 0.35 * reversal + 0.20 * lowcrowd,
        np.nan,
    )
    df["s104_leader_industry_midcap_bias"] = np.where(
        (df["industry_ret_20_rank"] >= 0.75)
        & df["mid_size_score"].notna(),
        0.45 * df["industry_ret_20_z"] + 0.30 * df["mid_size_score_z"] + 0.20 * df["industry_mom20_rank_in_group"] + 0.15 * lowcrowd,
        np.nan,
    )
    df["s105_avoid_overcrowded_industry_breakouts"] = np.where(
        (df["industry_ret_20_rank"] >= 0.70)
        & (df["breakout_20"] > 0),
        0.45 * breakout + 0.25 * compression + 0.20 * df["industry_ret_20_z"] - 0.30 * df["industry_crowding_5_z"] - 0.15 * df["volume_ma20_gap_z"],
        np.nan,
    )

    report = {
        "panel_rows": int(len(df)),
        "industry_rows": int(len(industry)),
        "coverage_ratio": float(df["industry_code"].notna().mean()),
    }
    (REFERENCE_DIR / "feature_build_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return df
