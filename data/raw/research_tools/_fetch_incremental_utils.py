"""通用辅助函数：为 Tushare fetch 模块提供增量更新支持。"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def latest_date_in_parquet(path: Path, date_col: str, fmt: str = "%Y%m%d") -> pd.Timestamp | None:
    """读取 parquet 中指定日期列的最大值。"""
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    if date_col not in df.columns or df.empty:
        return None
    s = pd.to_datetime(df[date_col], errors="coerce", format=fmt)
    return s.max() if not s.dropna().empty else None


def merge_save_parquet(existing: pd.DataFrame, new_df: pd.DataFrame, path: Path) -> pd.DataFrame:
    """合并新旧数据，去重，写回 parquet，返回合并后的 DataFrame。"""
    if new_df.empty:
        return existing
    combined = pd.concat([existing, new_df], ignore_index=True)
    # 去重：保留后出现的（新数据），防止 overlap 时旧数据覆盖
    combined = combined.drop_duplicates(keep="last").reset_index(drop=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(path, index=False)
    return combined
