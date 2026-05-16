from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from trading_system.config.paths import INBOX_DIR
from trading_system.utils.main_board import is_main_board

DEFAULT_TOP_N = 10
DEFAULT_KEEP_RANK = 15


def _load_latest_northbound_margin_file(trade_date: str) -> pd.DataFrame | None:
    """从 inbox 读取最新的 northbound_and_margin_flow 数据。"""
    directory = INBOX_DIR / "northbound_and_margin_flow"
    if not directory.exists():
        return None

    # 尝试精确匹配日期
    exact = directory / f"northbound_and_margin_flow_{trade_date.replace('-', '')}.csv"
    if exact.exists():
        return pd.read_csv(exact, encoding="utf-8-sig")
    return None


def scan_capital_flow_candidates(
    trade_date: str,
    top_n: int = DEFAULT_TOP_N,
    keep_rank: int = DEFAULT_KEEP_RANK,
) -> pd.DataFrame:
    """
    资金流扫描器：读取北向+融资融券数据，按 net_amount 排序分级。

    Returns DataFrame with columns:
        stock_code, trade_date, net_amount, capital_signal_type,
        rank_pos, signal_type, strength_hint, technical_state
    """
    df = _load_latest_northbound_margin_file(trade_date)
    if df is None or df.empty:
        return pd.DataFrame()

    # 标准化列名
    df["stock_code"] = df["stock_code"].astype(str).str.strip().str.upper()
    df["net_amount"] = pd.to_numeric(df.get("net_amount"), errors="coerce").fillna(0.0)

    # 只保留 A 股主板
    df = df[df["stock_code"].apply(is_main_board)].copy()
    if df.empty:
        return pd.DataFrame()

    # 按 stock_code + capital_signal_type 去重，取最新 net_amount
    # margin_detail 用 net_amount（融资净买入）
    # hk_hold 用 ratio（北向持仓比例），这里 net_amount 已经映射好
    df = df.sort_values(["stock_code", "capital_signal_type"]).drop_duplicates(subset=["stock_code"], keep="last")

    # 按 net_amount 排序
    df = df.sort_values("net_amount", ascending=False).reset_index(drop=True)
    df["rank_pos"] = np.arange(1, len(df) + 1)
    df["in_entry_top_n"] = df["rank_pos"] <= top_n
    df["in_keep_zone"] = df["rank_pos"] <= keep_rank

    # 信号分级（按排名百分位，避免绝对阈值因数据量级失效）
    n = len(df)

    def _classify(row: pd.Series) -> tuple[str, str, float]:
        rank = int(row.get("rank_pos", n))
        rank_pct = rank / n
        if rank_pct <= 0.05:
            return "strong", "high_capital_inflow", 0.85
        if rank_pct <= 0.15:
            return "moderate", "medium_capital_inflow", 0.65
        if rank_pct <= 0.50:
            return "watch", "low_capital_inflow", 0.45
        if row.get("net_amount", 0) <= 0:
            return "avoid", "capital_outflow", 0.25
        return "watch", "neutral_flow", 0.40

    classifications = df.apply(_classify, axis=1)
    df["signal_type"] = [c[0] for c in classifications]
    df["technical_state"] = [c[1] for c in classifications]
    df["strength_hint"] = [c[2] for c in classifications]

    cols = [
        "stock_code", "trade_date", "net_amount", "capital_signal_type",
        "rank_pos", "in_entry_top_n", "in_keep_zone",
        "signal_type", "technical_state", "strength_hint",
    ]
    available_cols = [c for c in cols if c in df.columns]
    return df[available_cols]
