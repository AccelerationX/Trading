from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .external_tushare_features import add_external_tushare_features, zscore_by_date


ROOT = Path(r"D:\TradingMain")
REFERENCE_DIR = ROOT / "research" / "reference" / "tushare"
NORTH_PATH = REFERENCE_DIR / "northbound" / "hk_hold_daily_2020plus.parquet"
NORTH_MARKET_PATH = REFERENCE_DIR / "northbound_market" / "moneyflow_hsgt_daily_2020plus.parquet"
MARGIN_PATH = REFERENCE_DIR / "margin" / "margin_detail_daily_2020plus.parquet"


def _pick_first_existing(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    return None


def load_northbound_features() -> pd.DataFrame:
    if not NORTH_PATH.exists():
        raise FileNotFoundError(f"Missing northbound dataset: {NORTH_PATH}")
    raw = pd.read_parquet(NORTH_PATH)
    raw["trade_date"] = pd.to_datetime(raw["trade_date"])
    raw["stock_code"] = raw["stock_code"].astype(str).str.upper()
    ratio_col = _pick_first_existing(raw, ["ratio", "hold_ratio", "vol_ratio"])
    vol_col = _pick_first_existing(raw, ["vol", "hold_vol"])
    amount_col = _pick_first_existing(raw, ["amount", "hold_amount"])
    if ratio_col is None and vol_col is None:
        raise RuntimeError("Northbound dataset missing ratio/vol columns")

    out = raw[["trade_date", "stock_code"]].copy()
    if ratio_col is not None:
        out["north_ratio"] = pd.to_numeric(raw[ratio_col], errors="coerce")
    else:
        out["north_ratio"] = np.nan
    if vol_col is not None:
        out["north_vol"] = pd.to_numeric(raw[vol_col], errors="coerce")
    else:
        out["north_vol"] = np.nan
    if amount_col is not None:
        out["north_amount"] = pd.to_numeric(raw[amount_col], errors="coerce")
    else:
        out["north_amount"] = np.nan

    grouped = out.sort_values(["stock_code", "trade_date"]).groupby("stock_code", group_keys=False)
    out["north_ratio_chg_5"] = grouped["north_ratio"].transform(lambda s: s - s.shift(5))
    out["north_ratio_chg_20"] = grouped["north_ratio"].transform(lambda s: s - s.shift(20))
    out["north_vol_chg_5"] = grouped["north_vol"].transform(lambda s: s.pct_change(5))
    out["north_vol_chg_20"] = grouped["north_vol"].transform(lambda s: s.pct_change(20))
    for col in ["north_ratio", "north_ratio_chg_5", "north_ratio_chg_20", "north_vol_chg_5", "north_vol_chg_20"]:
        out[f"{col}_z"] = zscore_by_date(out, col)

    return out


def load_northbound_market_features() -> pd.DataFrame:
    if not NORTH_MARKET_PATH.exists():
        raise FileNotFoundError(f"Missing northbound market dataset: {NORTH_MARKET_PATH}")
    df = pd.read_parquet(NORTH_MARKET_PATH)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.sort_values("trade_date").copy()
    for col in ["north_money", "hgt", "sgt"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["north_money_5"] = df["north_money"].rolling(5, min_periods=3).mean()
    df["north_money_20"] = df["north_money"].rolling(20, min_periods=10).mean()
    df["north_money_trend"] = df["north_money_5"] - df["north_money_20"]
    df["north_market_gate"] = (df["north_money_5"] > 0) | (df["north_money_trend"] > 0)
    df["north_market_exposure"] = np.select(
        [
            (df["north_money_5"] > 15) & (df["north_money_trend"] > 0),
            df["north_money_5"] > -10,
        ],
        [1.0, 0.65],
        default=0.25,
    )
    return df[["trade_date", "north_money", "north_money_5", "north_money_20", "north_money_trend", "north_market_gate", "north_market_exposure"]]


def load_margin_features() -> pd.DataFrame:
    if not MARGIN_PATH.exists():
        raise FileNotFoundError(f"Missing margin dataset: {MARGIN_PATH}")
    raw = pd.read_parquet(MARGIN_PATH)
    raw["trade_date"] = pd.to_datetime(raw["trade_date"])
    raw["stock_code"] = raw["stock_code"].astype(str).str.upper()

    rzye_col = _pick_first_existing(raw, ["rzye", "fin_balance"])
    rzmre_col = _pick_first_existing(raw, ["rzmre", "fin_buy_value"])
    rqye_col = _pick_first_existing(raw, ["rqye", "sec_balance"])
    rzrqye_col = _pick_first_existing(raw, ["rzrqye", "margin_balance"])
    if rzye_col is None:
        raise RuntimeError("Margin dataset missing rzye column")

    out = raw[["trade_date", "stock_code"]].copy()
    out["margin_rzye"] = pd.to_numeric(raw[rzye_col], errors="coerce")
    out["margin_rzmre"] = pd.to_numeric(raw[rzmre_col], errors="coerce") if rzmre_col else np.nan
    out["margin_rqye"] = pd.to_numeric(raw[rqye_col], errors="coerce") if rqye_col else np.nan
    out["margin_total"] = pd.to_numeric(raw[rzrqye_col], errors="coerce") if rzrqye_col else out["margin_rzye"]

    grouped = out.sort_values(["stock_code", "trade_date"]).groupby("stock_code", group_keys=False)
    out["margin_rzye_chg_5"] = grouped["margin_rzye"].transform(lambda s: s.pct_change(5))
    out["margin_rzye_chg_20"] = grouped["margin_rzye"].transform(lambda s: s.pct_change(20))
    out["margin_rzmre_ma5"] = grouped["margin_rzmre"].transform(lambda s: s.rolling(5, min_periods=3).mean())
    out["margin_rzmre_ma20"] = grouped["margin_rzmre"].transform(lambda s: s.rolling(20, min_periods=10).mean())
    out["margin_flow_accel"] = out["margin_rzmre_ma5"] / out["margin_rzmre_ma20"].replace(0.0, np.nan) - 1.0
    for col in ["margin_rzye", "margin_rzye_chg_5", "margin_rzye_chg_20", "margin_flow_accel"]:
        out[f"{col}_z"] = zscore_by_date(out, col)

    market = (
        out.groupby("trade_date")[["margin_rzye_chg_5", "margin_rzye_chg_20", "margin_flow_accel"]]
        .mean()
        .reset_index()
        .sort_values("trade_date")
    )
    market["margin_crowding_gate"] = (market["margin_rzye_chg_5"] < 0.05) & (market["margin_flow_accel"] < 0.20)
    market["margin_crowding_exposure"] = np.select(
        [
            (market["margin_rzye_chg_5"] < 0.01) & (market["margin_flow_accel"] < 0.05),
            market["margin_rzye_chg_5"] < 0.08,
        ],
        [1.0, 0.70],
        default=0.30,
    )
    return out.merge(market, on="trade_date", how="left")


def add_line_a_overlay_tushare_features(panel: pd.DataFrame) -> pd.DataFrame:
    df = add_external_tushare_features(panel.copy())
    north = load_northbound_features()
    north_market = load_northbound_market_features()
    margin = load_margin_features()
    df = df.merge(
        north[
            [
                "trade_date",
                "stock_code",
                "north_ratio_z",
                "north_ratio_chg_5_z",
                "north_ratio_chg_20_z",
                "north_vol_chg_5_z",
            ]
        ],
        on=["trade_date", "stock_code"],
        how="left",
    )
    df = df.merge(north_market, on="trade_date", how="left")
    df = df.merge(
        margin[
            [
                "trade_date",
                "stock_code",
                "margin_rzye_z",
                "margin_rzye_chg_5_z",
                "margin_rzye_chg_20_z",
                "margin_flow_accel_z",
                "margin_crowding_gate",
                "margin_crowding_exposure",
            ]
        ],
        on=["trade_date", "stock_code"],
        how="left",
    )

    north_support = (
        0.30 * df["north_ratio_chg_5_z"].fillna(0.0)
        + 0.20 * df["north_ratio_chg_20_z"].fillna(0.0)
        + 0.10 * df["north_vol_chg_5_z"].fillna(0.0)
    )
    anti_margin_crowding = (
        -0.25 * df["margin_rzye_chg_5_z"].fillna(0.0)
        - 0.20 * df["margin_flow_accel_z"].fillna(0.0)
        - 0.10 * df["margin_rzye_z"].fillna(0.0)
    )
    industry_support = 0.15 * df["industry_ret_20_z"].fillna(0.0)
    df["north_margin_market_gate"] = (
        df["north_market_gate"].fillna(False) & df["margin_crowding_gate"].fillna(False)
    )
    df["north_margin_exposure"] = (
        df["north_market_exposure"].fillna(0.50) * df["margin_crowding_exposure"].fillna(0.50)
    ).clip(lower=0.0, upper=1.0)

    df["ov301_line_a_north_support"] = np.where(
        df["north_ratio_chg_5_z"].fillna(-9.0) > -0.5,
        df["line_a_core_signal"] + north_support + industry_support,
        np.nan,
    )
    df["ov302_line_a_anti_margin_crowding"] = np.where(
        df["margin_rzye_chg_5_z"].fillna(9.0) < 1.2,
        df["line_a_core_signal"] + anti_margin_crowding,
        np.nan,
    )
    df["ov303_line_a_north_margin_combo"] = np.where(
        (df["north_ratio_chg_5_z"].fillna(-9.0) > -0.5) & (df["margin_rzye_chg_5_z"].fillna(9.0) < 1.2),
        df["line_a_core_signal"] + north_support + anti_margin_crowding + industry_support,
        np.nan,
    )
    df["ov304_line_a_industry_north_combo"] = np.where(
        df["industry_ret_20_rank"].fillna(0.0) >= 0.55,
        df["tx205_line_a_style_exposure"] + north_support - 0.15 * df["margin_flow_accel_z"].fillna(0.0),
        np.nan,
    )

    report = {
        "panel_rows": int(len(df)),
        "north_available_ratio": float(df["north_ratio_chg_5_z"].notna().mean()),
        "margin_available_ratio": float(df["margin_rzye_chg_5_z"].notna().mean()),
    }
    (REFERENCE_DIR / "capital_feature_build_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return df
