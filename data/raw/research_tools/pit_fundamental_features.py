from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(r"D:\TradingMain")
REFERENCE_DIR = ROOT / "research" / "reference" / "tushare" / "pit_fundamental"
CACHE_PATH = ROOT / "research" / "cache" / "pit_fundamental_daily_features_2020plus.parquet"


def zscore_by_date(df: pd.DataFrame, column: str) -> pd.Series:
    grouped = df.groupby("trade_date")[column]
    mean = grouped.transform("mean")
    std = grouped.transform("std").replace(0.0, np.nan)
    return ((df[column] - mean) / std).replace([np.inf, -np.inf], np.nan)


def _pick_first_existing(columns: list[str], candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def _load_statement(endpoint: str) -> pd.DataFrame:
    path = REFERENCE_DIR / f"{endpoint}_quarterly_2018plus.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing PIT fundamental dataset: {path}")
    df = pd.read_parquet(path)
    for col in ["ann_date", "f_ann_date", "end_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])
    if "stock_code" in df.columns:
        df["stock_code"] = df["stock_code"].astype(str).str.upper()
    return df


def _merge_statements() -> pd.DataFrame:
    fina = _load_statement("fina_indicator")
    income = _load_statement("income")
    cashflow = _load_statement("cashflow")
    balance = _load_statement("balancesheet")
    keys = ["stock_code", "ann_date", "end_date"]

    base = fina.copy()
    for other in [income, cashflow, balance]:
        keep_cols = [col for col in other.columns if col not in base.columns or col in keys]
        base = base.merge(other[keep_cols], on=keys, how="outer")
    base = base.sort_values(["stock_code", "ann_date", "end_date"]).reset_index(drop=True)
    return base


def _derive_statement_features(statement: pd.DataFrame) -> pd.DataFrame:
    df = statement.copy().sort_values(["stock_code", "end_date", "ann_date"])
    cols = list(df.columns)

    roe_col = _pick_first_existing(cols, ["q_roe", "roe", "roe_dt"])
    gross_margin_col = _pick_first_existing(cols, ["grossprofit_margin", "gross_margin"])
    net_profit_col = _pick_first_existing(cols, ["n_income_attr_p", "n_income", "profit_dedt"])
    revenue_col = _pick_first_existing(cols, ["total_revenue", "revenue", "total_operate_income"])
    ocf_col = _pick_first_existing(cols, ["n_cashflow_act", "n_cashflow_act_activity"])
    assets_col = _pick_first_existing(cols, ["total_assets"])
    receivables_col = _pick_first_existing(cols, ["accounts_receiv", "acct_receiv"])
    inventory_col = _pick_first_existing(cols, ["inventories"])

    if roe_col is None or gross_margin_col is None or net_profit_col is None or revenue_col is None or ocf_col is None or assets_col is None:
        raise RuntimeError("PIT fundamental datasets are missing required core columns")

    df["pit_roe"] = pd.to_numeric(df[roe_col], errors="coerce")
    df["pit_gross_margin"] = pd.to_numeric(df[gross_margin_col], errors="coerce")
    df["pit_net_profit"] = pd.to_numeric(df[net_profit_col], errors="coerce")
    df["pit_revenue"] = pd.to_numeric(df[revenue_col], errors="coerce")
    df["pit_ocf"] = pd.to_numeric(df[ocf_col], errors="coerce")
    df["pit_total_assets"] = pd.to_numeric(df[assets_col], errors="coerce")
    df["pit_receivables"] = pd.to_numeric(df[receivables_col], errors="coerce") if receivables_col else np.nan
    df["pit_inventory"] = pd.to_numeric(df[inventory_col], errors="coerce") if inventory_col else np.nan

    df["pit_ocf_margin"] = df["pit_ocf"] / df["pit_revenue"].replace(0.0, np.nan)
    df["pit_receivables_ratio"] = df["pit_receivables"] / df["pit_total_assets"].replace(0.0, np.nan)
    df["pit_inventory_ratio"] = df["pit_inventory"] / df["pit_total_assets"].replace(0.0, np.nan)
    df["pit_accrual_gap"] = (df["pit_net_profit"] - df["pit_ocf"]) / df["pit_total_assets"].replace(0.0, np.nan)

    grouped = df.groupby("stock_code", group_keys=False)
    for col in [
        "pit_roe",
        "pit_gross_margin",
        "pit_ocf_margin",
        "pit_receivables_ratio",
        "pit_inventory_ratio",
        "pit_accrual_gap",
    ]:
        df[f"{col}_chg_yoy"] = grouped[col].transform(lambda s: s - s.shift(4))
        df[f"{col}_chg_qoq"] = grouped[col].transform(lambda s: s - s.shift(1))

    keep_cols = [
        "stock_code",
        "ann_date",
        "end_date",
        "pit_roe",
        "pit_gross_margin",
        "pit_ocf_margin",
        "pit_receivables_ratio",
        "pit_inventory_ratio",
        "pit_accrual_gap",
        "pit_roe_chg_yoy",
        "pit_roe_chg_qoq",
        "pit_gross_margin_chg_yoy",
        "pit_gross_margin_chg_qoq",
        "pit_ocf_margin_chg_yoy",
        "pit_ocf_margin_chg_qoq",
        "pit_receivables_ratio_chg_yoy",
        "pit_inventory_ratio_chg_yoy",
        "pit_accrual_gap_chg_yoy",
    ]
    return df[keep_cols].dropna(subset=["stock_code", "ann_date"]).reset_index(drop=True)


def _merge_asof_by_stock(panel: pd.DataFrame, statement_features: pd.DataFrame) -> pd.DataFrame:
    left = panel.copy()
    right = statement_features.copy()
    left["trade_date"] = pd.to_datetime(left["trade_date"]).astype("datetime64[ns]")
    right["ann_date"] = pd.to_datetime(right["ann_date"]).astype("datetime64[ns]")

    right_groups = {
        stock_code: group.sort_values("ann_date").reset_index(drop=True)
        for stock_code, group in right.groupby("stock_code", sort=False)
    }
    frames: list[pd.DataFrame] = []
    for stock_code, left_group in left.groupby("stock_code", sort=False):
        right_group = right_groups.get(stock_code)
        work_left = left_group.sort_values("trade_date").reset_index(drop=True)
        if right_group is None or right_group.empty:
            for col in right.columns:
                if col != "stock_code" and col not in work_left.columns:
                    work_left[col] = pd.NA
            frames.append(work_left)
            continue
        merged = pd.merge_asof(
            work_left,
            right_group,
            left_on="trade_date",
            right_on="ann_date",
            direction="backward",
            allow_exact_matches=True,
        )
        if "stock_code_x" in merged.columns:
            merged["stock_code"] = merged["stock_code_x"]
            merged = merged.drop(columns=[col for col in ["stock_code_x", "stock_code_y"] if col in merged.columns])
        frames.append(merged)
    return pd.concat(frames, ignore_index=True) if frames else left


def add_pit_fundamental_features(panel: pd.DataFrame, use_cache: bool = True) -> pd.DataFrame:
    cache_key_cols = ["stock_code", "trade_date"]
    if use_cache and CACHE_PATH.exists():
        cached = pd.read_parquet(CACHE_PATH)
        cached["trade_date"] = pd.to_datetime(cached["trade_date"])
        cached["stock_code"] = cached["stock_code"].astype(str).str.upper()
        merged = panel.merge(cached, on=cache_key_cols, how="left")
        required = ["pf201_profitability_turn_low_pb", "pf208_cashflow_margin_improvement_combo"]
        if all(col in merged.columns for col in required):
            return merged

    df = panel.copy().sort_values(["stock_code", "trade_date"]).reset_index(drop=True)
    statement = _merge_statements()
    statement_features = _derive_statement_features(statement)
    merged = _merge_asof_by_stock(df, statement_features)

    merged["mid_size_score"] = -((merged.groupby("trade_date")["size"].transform(lambda s: s.rank(pct=True, method="average")) - 0.50).abs())
    merged["mid_size_score_z"] = zscore_by_date(merged, "mid_size_score")
    merged["volume_ma20_gap"] = merged["amount_k"] / merged.groupby("stock_code")["amount_k"].transform(lambda s: s.rolling(20, min_periods=10).mean()).replace(0.0, np.nan) - 1.0

    score_cols = [
        "pit_roe",
        "pit_gross_margin",
        "pit_ocf_margin",
        "pit_receivables_ratio",
        "pit_inventory_ratio",
        "pit_accrual_gap",
        "pit_roe_chg_yoy",
        "pit_roe_chg_qoq",
        "pit_gross_margin_chg_yoy",
        "pit_gross_margin_chg_qoq",
        "pit_ocf_margin_chg_yoy",
        "pit_ocf_margin_chg_qoq",
        "pit_receivables_ratio_chg_yoy",
        "pit_inventory_ratio_chg_yoy",
        "pit_accrual_gap_chg_yoy",
        "volume_ma20_gap",
    ]
    for col in score_cols:
        merged[f"{col}_z"] = zscore_by_date(merged, col)

    lowvol = -merged["volatility_20_z"].fillna(0.0)
    lowcrowd = -merged["volume_ma20_gap_z"].fillna(0.0)
    value = merged["bp_z"].fillna(0.0)
    reversal = merged["short_reversal_5_z"].fillna(0.0)
    mom20 = merged["mom_20_z"].fillna(0.0)
    mid = merged["mid_size_score_z"].fillna(0.0)

    merged["pf201_profitability_turn_low_pb"] = np.where(
        (merged["pit_roe_chg_yoy"].fillna(-9.0) > 0)
        & (merged["pit_roe"].fillna(-9.0) > 0),
        0.55 * merged["pit_roe_chg_yoy_z"].fillna(0.0) + 0.25 * merged["pit_roe_z"].fillna(0.0) + 0.30 * value + 0.10 * lowvol,
        np.nan,
    )
    merged["pf202_operating_cashflow_improvement_low_pb"] = np.where(
        merged["pit_ocf_margin_chg_yoy"].fillna(-9.0) > 0,
        0.60 * merged["pit_ocf_margin_chg_yoy_z"].fillna(0.0) + 0.35 * value + 0.15 * lowvol,
        np.nan,
    )
    merged["pf203_gross_margin_rebound_low_crowding"] = np.where(
        merged["pit_gross_margin_chg_yoy"].fillna(-9.0) > 0,
        0.55 * merged["pit_gross_margin_chg_yoy_z"].fillna(0.0) + 0.25 * lowcrowd + 0.15 * mom20 + 0.10 * value,
        np.nan,
    )
    merged["pf204_roe_improvement_midcap_bias"] = np.where(
        merged["pit_roe_chg_qoq"].fillna(-9.0) > 0,
        0.50 * merged["pit_roe_chg_qoq_z"].fillna(0.0) + 0.25 * merged["pit_roe_z"].fillna(0.0) + 0.20 * mid + 0.15 * value,
        np.nan,
    )
    merged["pf205_receivables_deterioration_avoidance"] = np.where(
        merged["pit_receivables_ratio_chg_yoy"].fillna(9.0) < 0.02,
        -0.55 * merged["pit_receivables_ratio_chg_yoy_z"].fillna(0.0) - 0.20 * merged["pit_receivables_ratio_z"].fillna(0.0) + 0.30 * value + 0.15 * lowvol,
        np.nan,
    )
    merged["pf206_inventory_deterioration_avoidance"] = np.where(
        merged["pit_inventory_ratio_chg_yoy"].fillna(9.0) < 0.02,
        -0.55 * merged["pit_inventory_ratio_chg_yoy_z"].fillna(0.0) - 0.20 * merged["pit_inventory_ratio_z"].fillna(0.0) + 0.25 * value + 0.15 * mom20,
        np.nan,
    )
    merged["pf207_low_accrual_value_repair"] = np.where(
        merged["pit_accrual_gap"].fillna(9.0) < 0.0,
        -0.55 * merged["pit_accrual_gap_z"].fillna(0.0) - 0.20 * merged["pit_accrual_gap_chg_yoy_z"].fillna(0.0) + 0.35 * value + 0.20 * reversal + 0.10 * lowvol,
        np.nan,
    )
    merged["pf208_cashflow_margin_improvement_combo"] = np.where(
        (merged["pit_ocf_margin_chg_yoy"].fillna(-9.0) > 0)
        & (merged["pit_gross_margin_chg_yoy"].fillna(-9.0) > 0),
        0.45 * merged["pit_ocf_margin_chg_yoy_z"].fillna(0.0) + 0.45 * merged["pit_gross_margin_chg_yoy_z"].fillna(0.0) + 0.25 * value + 0.10 * mom20,
        np.nan,
    )

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    cache_cols = ["stock_code", "trade_date"] + [col for col in merged.columns if col.startswith("pit_") or col.startswith("pf") or col == "mid_size_score" or col == "mid_size_score_z" or col == "volume_ma20_gap" or col == "volume_ma20_gap_z"]
    merged[cache_cols].to_parquet(CACHE_PATH, index=False)

    report = {
        "panel_rows": int(len(merged)),
        "statement_rows": int(len(statement_features)),
        "coverage_ratio": float(merged["ann_date"].notna().mean()),
    }
    (REFERENCE_DIR / "pit_feature_build_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return merged
