from __future__ import annotations

import gc
from pathlib import Path

import numpy as np
import pandas as pd

from TradingMain.config import DATA_DIR, OUTPUT_DIR
from TradingMain.data.loader import ResearchConfig, load_dataset
from research.tools.backtester import StrategySpec
from research.tools.earnings_event_features import add_earnings_event_features
from research.tools.external_tushare_features import add_external_tushare_features
from research.tools.holder_risk_features import add_holder_risk_features


ROOT = Path(r"D:\TradingMain")
TRADE_EVENT_DIR = ROOT / "research" / "reference" / "tushare" / "trade_event"
EVENT_DIR = ROOT / "research" / "reference" / "tushare" / "event"

HOLDER_VALUE_COLS = [
    "next_open",
    "next_limit_up",
    "exit_close_3",
    "exit_close_6",
    "exit_close_10",
    "exit_limit_down_3",
    "exit_limit_down_6",
    "exit_limit_down_10",
    "exit_next_open_3_d1",
    "exit_next_limit_down_3_d1",
    "exit_next_open_3_d2",
    "exit_next_limit_down_3_d2",
    "exit_next_open_3_d3",
    "exit_next_limit_down_3_d3",
    "exit_next_open_6_d1",
    "exit_next_limit_down_6_d1",
    "exit_next_open_6_d2",
    "exit_next_limit_down_6_d2",
    "exit_next_open_6_d3",
    "exit_next_limit_down_6_d3",
    "exit_next_open_10_d1",
    "exit_next_limit_down_10_d1",
    "exit_next_open_10_d2",
    "exit_next_limit_down_10_d2",
    "exit_next_open_10_d3",
    "exit_next_limit_down_10_d3",
    "pr904_high_pledge_overreaction_repair",
    "hn801_holder_concentration_improving",
    "hn805_extreme_holder_decline_breakout",
    "defensive_exposure",
]

EVENT_VALUE_COLS = ["ev202_management_increase_follow"]
EXTERNAL_VALUE_COLS = [
    "s098_weak_industry_avoidance_overlay",
    "tx205_line_a_style_exposure",
    "external_risk_on_gate",
    "small_style_gate",
    "style_small_vs_large_20",
    "csi_all_share_ret_20",
    "industry_ret_20_rank",
    "industry_breadth_rank",
]
EARNINGS_VALUE_COLS = [
    "line_a_core_signal",
    "ee301_positive_forecast_follow",
    "ee302_forecast_repair_lowcrowding",
    "ee309_large_positive_forecast_short_hold",
    "ee310_forecast_turnaround_value",
]
UNLOCK_VALUE_COLS = ["sf602_large_unlock_overreaction_repair"]


def rank_pct_by_date(df: pd.DataFrame, col: str) -> pd.Series:
    return df.groupby("trade_date")[col].transform(lambda s: s.rank(pct=True, method="average"))


def compact_panel(panel: pd.DataFrame, value_cols: list[str]) -> pd.DataFrame:
    work = panel[["stock_code", "trade_date"] + value_cols].copy()
    agg = {col: "max" for col in value_cols}
    return work.groupby(["stock_code", "trade_date"], as_index=False).agg(agg)


def zscore_by_date(df: pd.DataFrame, column: str) -> pd.Series:
    grouped = df.groupby("trade_date")[column]
    mean = grouped.transform("mean")
    std = grouped.transform("std").replace(0.0, np.nan)
    return ((df[column] - mean) / std).replace([np.inf, -np.inf], np.nan)


def _merge_recent_event_by_row(
    panel_keys: pd.DataFrame,
    event_df: pd.DataFrame,
    value_cols: list[str],
    prefix: str,
) -> pd.DataFrame:
    left = panel_keys[["row_id", "stock_code", "trade_date"]].copy()
    left["trade_date"] = pd.to_datetime(left["trade_date"]).astype("datetime64[ns]")
    right = event_df[["stock_code", "event_trade_date"] + value_cols].copy()
    right["event_trade_date"] = pd.to_datetime(right["event_trade_date"]).astype("datetime64[ns]")

    merged = pd.merge_asof(
        left.sort_values(["trade_date", "stock_code"]),
        right.sort_values(["event_trade_date", "stock_code"]),
        left_on="trade_date",
        right_on="event_trade_date",
        by="stock_code",
        direction="backward",
    )
    merged = merged.sort_values("row_id").reset_index(drop=True)
    merged = merged.rename(columns={col: f"{prefix}_{col}" for col in value_cols})
    merged = merged.rename(columns={"event_trade_date": f"{prefix}_event_trade_date"})
    return merged


def build_unlock_repair_feature(external: pd.DataFrame) -> pd.DataFrame:
    share_float_path = TRADE_EVENT_DIR / "share_float_daily_2020plus.parquet"
    share_float = pd.read_parquet(share_float_path)
    for col in ["float_share", "float_ratio"]:
        if col in share_float.columns:
            share_float[col] = pd.to_numeric(share_float[col], errors="coerce")

    unlock_base = external[
        [
            "stock_code",
            "trade_date",
            "industry_ret_20_rank",
            "industry_ret_20_z",
            "volatility_20_z",
            "volume_ma20_gap_z",
            "bp_z",
            "short_reversal_5_z",
            "breakout_retest_score_z",
            "close_range_pos_z",
            "mid_size_score_z",
            "amount_ratio_5_20_z",
        ]
    ].copy()
    unlock_base["row_id"] = np.arange(len(unlock_base))

    share_float_daily = share_float.rename(columns={"float_date": "event_trade_date"}).copy()
    share_float_daily["unlock_count"] = 1.0
    share_float_recent = _merge_recent_event_by_row(
        unlock_base[["row_id", "stock_code", "trade_date"]],
        share_float_daily,
        ["float_share", "float_ratio", "unlock_count"],
        "unlock",
    )
    unlock_df = share_float_recent.merge(
        unlock_base.drop(columns=["stock_code", "trade_date"]),
        on="row_id",
        how="left",
    )
    unlock_df["unlock_event_age"] = (unlock_df["trade_date"] - unlock_df["unlock_event_trade_date"]).dt.days
    for col in ["unlock_float_share", "unlock_float_ratio", "unlock_unlock_count"]:
        unlock_df[col] = pd.to_numeric(unlock_df[col], errors="coerce")
        unlock_df[f"{col}_z"] = zscore_by_date(unlock_df, col)

    fresh_unlock = unlock_df["unlock_event_age"].fillna(9999).between(0, 3)
    unlock_lowcrowd = -unlock_df["volume_ma20_gap_z"].fillna(0.0)
    unlock_value = unlock_df["bp_z"].fillna(0.0)
    unlock_reversal = unlock_df["short_reversal_5_z"].fillna(0.0)
    unlock_df["sf602_large_unlock_overreaction_repair"] = np.where(
        fresh_unlock & (unlock_df["unlock_float_ratio"].fillna(-999.0) >= 10.0),
        0.35 * unlock_df["unlock_float_ratio_z"].fillna(0.0) + 0.25 * unlock_reversal + 0.20 * unlock_value + 0.20 * unlock_lowcrowd,
        np.nan,
    )
    return unlock_df[["stock_code", "trade_date", "row_id", "sf602_large_unlock_overreaction_repair"]]


def build_management_increase_follow_feature(external: pd.DataFrame) -> pd.DataFrame:
    holdertrade_path = EVENT_DIR / "holdertrade_daily_2020plus.parquet"
    holdertrade = pd.read_parquet(holdertrade_path, columns=["stock_code", "ann_date", "change_ratio", "holder_type", "in_de"])
    holdertrade["stock_code"] = holdertrade["stock_code"].astype(str).str.upper()
    holdertrade["ann_date"] = pd.to_datetime(holdertrade["ann_date"])
    holdertrade["change_ratio"] = pd.to_numeric(holdertrade["change_ratio"], errors="coerce")
    holdertrade["holder_type"] = holdertrade["holder_type"].astype(str)
    holdertrade["in_de"] = holdertrade["in_de"].astype(str)
    holdertrade = holdertrade[holdertrade["in_de"] == "IN"].copy()
    holdertrade["holder_in_mgmt_flag"] = holdertrade["holder_type"].eq("G").astype(float)
    holder_in = holdertrade.groupby(["stock_code", "ann_date"], as_index=False).agg(
        holder_in_ratio=("change_ratio", "sum"),
        holder_in_mgmt_flag=("holder_in_mgmt_flag", "max"),
    )

    mgmt_base = external[
        [
            "stock_code",
            "trade_date",
            "volatility_20_z",
            "volume_ma20_gap_z",
            "bp_z",
        ]
    ].copy()
    mgmt_base["row_id"] = np.arange(len(mgmt_base))

    holder_recent = _merge_recent_event_by_row(
        mgmt_base[["row_id", "stock_code", "trade_date"]],
        holder_in.rename(columns={"ann_date": "event_trade_date"}),
        ["holder_in_ratio", "holder_in_mgmt_flag"],
        "holder_in",
    )
    mgmt_df = holder_recent.merge(
        mgmt_base.drop(columns=["stock_code", "trade_date"]),
        on="row_id",
        how="left",
    )
    mgmt_df["holder_in_event_age"] = (mgmt_df["trade_date"] - mgmt_df["holder_in_event_trade_date"]).dt.days
    mgmt_df["holder_in_holder_in_ratio"] = pd.to_numeric(mgmt_df["holder_in_holder_in_ratio"], errors="coerce")
    mgmt_df["holder_in_holder_in_ratio_z"] = zscore_by_date(mgmt_df, "holder_in_holder_in_ratio")

    recent_holder_in = mgmt_df["holder_in_event_age"].fillna(9999) <= 60
    lowvol = -mgmt_df["volatility_20_z"].fillna(0.0)
    lowcrowd = -mgmt_df["volume_ma20_gap_z"].fillna(0.0)
    value = mgmt_df["bp_z"].fillna(0.0)
    mgmt_df["ev202_management_increase_follow"] = np.where(
        recent_holder_in & (mgmt_df["holder_in_holder_in_mgmt_flag"].fillna(0.0) > 0.5),
        0.55 * mgmt_df["holder_in_holder_in_ratio_z"].fillna(0.0) + 0.20 * value + 0.15 * lowcrowd + 0.10 * lowvol,
        np.nan,
    )
    return mgmt_df[["stock_code", "trade_date", "row_id", "ev202_management_increase_follow"]]


def build_family_champion_panel_from_base(base: pd.DataFrame) -> pd.DataFrame:
    holder = compact_panel(add_holder_risk_features(base.copy()), HOLDER_VALUE_COLS)
    gc.collect()

    external_full = add_external_tushare_features(base.copy())
    event = compact_panel(build_management_increase_follow_feature(external_full), EVENT_VALUE_COLS)
    unlock = compact_panel(build_unlock_repair_feature(external_full), UNLOCK_VALUE_COLS)
    external = compact_panel(external_full, EXTERNAL_VALUE_COLS)
    del external_full
    gc.collect()

    earnings = compact_panel(add_earnings_event_features(base.copy()), EARNINGS_VALUE_COLS)
    gc.collect()

    df = holder
    for extra in [event, unlock, external, earnings]:
        df = df.merge(extra, on=["stock_code", "trade_date"], how="left")
    del holder, event, unlock, external, earnings
    gc.collect()

    rank_cols = [
        "pr904_high_pledge_overreaction_repair",
        "hn801_holder_concentration_improving",
        "hn805_extreme_holder_decline_breakout",
        "ev202_management_increase_follow",
        "sf602_large_unlock_overreaction_repair",
        "s098_weak_industry_avoidance_overlay",
        "tx205_line_a_style_exposure",
        "line_a_core_signal",
        "ee301_positive_forecast_follow",
        "ee302_forecast_repair_lowcrowding",
        "ee309_large_positive_forecast_short_hold",
        "ee310_forecast_turnaround_value",
    ]
    for col in rank_cols:
        df[f"{col}_rank"] = rank_pct_by_date(df, col)

    pledge = df["pr904_high_pledge_overreaction_repair_rank"].fillna(0.0)
    holder_support = (
        0.55 * df["hn801_holder_concentration_improving_rank"].fillna(0.0)
        + 0.45 * df["hn805_extreme_holder_decline_breakout_rank"].fillna(0.0)
    )
    event_support = (
        0.55 * df["ev202_management_increase_follow_rank"].fillna(0.0)
        + 0.45 * df["sf602_large_unlock_overreaction_repair_rank"].fillna(0.0)
    )
    line_a = df["line_a_core_signal"].fillna(0.0)
    line_a_rank = df["line_a_core_signal_rank"].fillna(0.0)
    ee301 = df["ee301_positive_forecast_follow"].fillna(0.0)
    ee302 = df["ee302_forecast_repair_lowcrowding"].fillna(0.0)
    ee309 = df["ee309_large_positive_forecast_short_hold"].fillna(0.0)
    ee310 = df["ee310_forecast_turnaround_value"].fillna(0.0)
    pr904_raw = df["pr904_high_pledge_overreaction_repair"].fillna(0.0)
    risk_on = df["external_risk_on_gate"].fillna(False)

    q80_pledge = pledge >= 0.80
    df["fam_psu901"] = pledge.where(q80_pledge, other=np.nan) + 0.15 * event_support + 0.15 * holder_support
    df["fam_er907"] = np.where(
        df["ee302_forecast_repair_lowcrowding"].notna(),
        0.60 * ee302 + 0.25 * ee310 + 0.25 * line_a + 0.20 * np.where(risk_on, pr904_raw, 0.0),
        np.nan,
    )
    er906 = np.where(
        df["ee301_positive_forecast_follow"].notna(),
        0.55 * ee301 + 0.30 * ee309 + 0.25 * line_a,
        np.nan,
    )
    er909 = np.where(
        df["ee302_forecast_repair_lowcrowding"].notna(),
        0.50 * ee302 + 0.20 * ee309 + 0.20 * ee310 + 0.25 * line_a + 0.25 * np.where(risk_on, pr904_raw, 0.0),
        np.nan,
    )
    df["fam_ur963"] = pd.concat([pd.Series(er906), pd.Series(df["fam_er907"]), pd.Series(er909)], axis=1).max(axis=1)
    df["fam_ekt901"] = (
        0.45 * df["ev202_management_increase_follow"].fillna(0.0)
        + 0.35 * df["sf602_large_unlock_overreaction_repair"].fillna(0.0)
        + 0.20 * df["s098_weak_industry_avoidance_overlay"].fillna(0.0)
    )
    df["fam_ekt902"] = (
        0.55 * df["ev202_management_increase_follow"].fillna(0.0)
        + 0.25 * df["sf602_large_unlock_overreaction_repair"].fillna(0.0)
        + 0.20 * df["s098_weak_industry_avoidance_overlay"].fillna(0.0)
    )

    family_cols = ["fam_psu901", "fam_er907", "fam_ur963", "fam_ekt901", "fam_ekt902"]
    for col in family_cols:
        df[f"{col}_rank"] = rank_pct_by_date(df, col)

    family_rank_df = df[[f"{col}_rank" for col in family_cols]].fillna(0.0)
    rank_array = family_rank_df.to_numpy(dtype=float)
    rank_sorted = np.sort(rank_array, axis=1)
    max_rank = rank_sorted[:, -1]
    top2_avg = rank_sorted[:, -1] * 0.65 + rank_sorted[:, -2] * 0.35
    count_q90 = (family_rank_df >= 0.90).sum(axis=1)
    count_q95 = (family_rank_df >= 0.95).sum(axis=1)

    df["mfx901_maxrank"] = max_rank
    df["mfx902_top2avg"] = top2_avg
    df["mfx903_sparse95"] = np.where(count_q95 >= 1, max_rank, np.nan)
    df["mfx904_sparse90x2"] = np.where(count_q90 >= 2, top2_avg, np.nan)
    df["mfx905_earn_pledge_only"] = pd.concat(
        [df["fam_psu901_rank"], df["fam_er907_rank"], df["fam_ur963_rank"]],
        axis=1,
    ).max(axis=1)
    df["mfx906_earn_pledge_event"] = np.maximum(df["mfx905_earn_pledge_only"], 0.85 * df["fam_ekt901_rank"])
    df["mfx907_switch"] = np.where(
        df["fam_er907_rank"].fillna(0.0) >= 0.97,
        df["fam_er907_rank"],
        np.where(df["fam_psu901_rank"].fillna(0.0) >= 0.97, df["fam_psu901_rank"], df["fam_ekt901_rank"]),
    )
    df["mfx908_switch_top2"] = np.where(
        df["fam_ur963_rank"].fillna(0.0) >= 0.97,
        df["fam_ur963_rank"],
        np.where(df["fam_psu901_rank"].fillna(0.0) >= 0.97, df["fam_psu901_rank"], df["fam_ekt902_rank"]),
    )
    df["mfx909_maxrank_plus_linea"] = max_rank + 0.10 * line_a_rank
    df["mfx910_meta_conviction"] = max_rank + 0.06 * count_q90 + 0.03 * count_q95

    df["mfx_dyn_exposure"] = pd.Series(count_q95).map({3: 1.0, 2: 0.90, 1: 0.75}).fillna(0.55)
    df["mfx_sparse_exposure"] = pd.Series(count_q95).map({3: 1.0, 2: 0.90, 1: 0.75}).fillna(0.0)
    return df


def build_family_champion_panel(start_date: str = "2020-01-01") -> pd.DataFrame:
    config = ResearchConfig(data_dir=DATA_DIR, output_dir=OUTPUT_DIR, start_date=start_date)
    base = load_dataset(config)
    try:
        return build_family_champion_panel_from_base(base)
    finally:
        del base
        gc.collect()


def build_family_champion_specs() -> list[StrategySpec]:
    return [
        StrategySpec(
            "MFX906_h6_top2",
            "mfx906_earn_pledge_event",
            "earnings + pledge + event champion fusion",
            hold_days=6,
            top_n=2,
            keep_rank=3,
            weighting="signal",
            replace_blocked_buys=True,
            sell_delay_on_limit_down=True,
            max_sell_delay_days=3,
        ),
        StrategySpec("MFX905_h6_top2", "mfx905_earn_pledge_only", "earnings + pledge champion fusion", hold_days=6, top_n=2, keep_rank=3, weighting="signal", replace_blocked_buys=True, sell_delay_on_limit_down=True, max_sell_delay_days=3),
        StrategySpec("MFX906_h6_top1", "mfx906_earn_pledge_event", "earnings + pledge + event top1", hold_days=6, top_n=1, keep_rank=2, replace_blocked_buys=True, sell_delay_on_limit_down=True, max_sell_delay_days=3),
        StrategySpec("MFX907_h6_top1", "mfx907_switch", "family switch top1", hold_days=6, top_n=1, keep_rank=2, replace_blocked_buys=True, sell_delay_on_limit_down=True, max_sell_delay_days=3),
        StrategySpec("MFX903_h6_top1", "mfx903_sparse95", "sparse q95 top1", hold_days=6, top_n=1, keep_rank=2, replace_blocked_buys=True, sell_delay_on_limit_down=True, max_sell_delay_days=3),
        StrategySpec("MFX908_h10_top2", "mfx908_switch_top2", "family switch top2 hold10", hold_days=10, top_n=2, keep_rank=3, weighting="signal", replace_blocked_buys=True, sell_delay_on_limit_down=True, max_sell_delay_days=3),
        StrategySpec("MFX901_h6_top2", "mfx901_maxrank", "max-rank family fusion", hold_days=6, top_n=2, keep_rank=3, weighting="signal", replace_blocked_buys=True, sell_delay_on_limit_down=True, max_sell_delay_days=3),
        StrategySpec("MFX902_h3_top2", "mfx902_top2avg", "top2-average family fusion fast", hold_days=3, top_n=2, keep_rank=2, weighting="signal", replace_blocked_buys=True, sell_delay_on_limit_down=True, max_sell_delay_days=3),
        StrategySpec("MFX906X_h6_top2", "mfx906_earn_pledge_event", "earnings + pledge + event with dynamic exposure", hold_days=6, top_n=2, keep_rank=3, weighting="signal", exposure_col="mfx_dyn_exposure", replace_blocked_buys=True, sell_delay_on_limit_down=True, max_sell_delay_days=3),
        StrategySpec("MFX903X_h6_top1", "mfx903_sparse95", "sparse q95 with sparse exposure", hold_days=6, top_n=1, keep_rank=2, exposure_col="mfx_sparse_exposure", replace_blocked_buys=True, sell_delay_on_limit_down=True, max_sell_delay_days=3),
    ]


def latest_rebalance_slice(panel: pd.DataFrame, spec: StrategySpec) -> pd.DataFrame:
    from TradingMain.state.calendar import load_trading_calendar

    panel_dates = set(pd.to_datetime(panel["trade_date"]).dt.date.unique())
    all_trade_dates = load_trading_calendar()
    valid_dates = [d for d in all_trade_dates if d in panel_dates]
    rebalance_dates = valid_dates[:: spec.hold_days]
    if not rebalance_dates:
        return panel.iloc[0:0].copy()
    latest_rebalance_date = pd.Timestamp(rebalance_dates[-1])
    day = panel[panel["trade_date"] == latest_rebalance_date].copy()
    return day.sort_values(spec.signal_col, ascending=False)
