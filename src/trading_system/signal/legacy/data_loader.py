from __future__ import annotations

from pathlib import Path

import pandas as pd

from trading_system.config.paths import PROCESSED_DATA_DIR


# 旧项目 StockHistory CSV 的中文列名到英文的映射
RAW_COLUMN_MAP = {
    "\u80a1\u7968\u4ee3\u7801": "stock_code",
    "\u80a1\u7968\u540d\u79f0": "stock_name",
    "\u4ea4\u6613\u65e5": "trade_date",
    "\u5f00\u76d8\u4ef7": "open",
    "\u6700\u9ad8\u4ef7": "high",
    "\u6700\u4f4e\u4ef7": "low",
    "\u6536\u76d8\u4ef7": "close",
    "\u524d\u6536\u76d8\u4ef7": "prev_close",
    "\u6210\u4ea4\u91cf\uff08\u624b\uff09": "volume",
    "\u6210\u4ea4\u989d\uff08\u5343\u5143\uff09": "amount_k",
    "\u6362\u624b\u7387\uff08%\uff09": "turnover_pct",
    "\u6362\u624b\u7387\uff08%\uff0c\u81ea\u7531\u6d41\u901a\u80a1\uff09": "free_turnover_pct",
    "\u91cf\u6bd4": "volume_ratio",
    "\u5e02\u76c8\u7387\uff08TTM\uff0c\u4e8f\u635f\u4e3a\u7a7a\uff09": "pe_ttm",
    "\u5e02\u51c0\u7387": "pb",
    "\u603b\u5e02\u503c\uff08\u4e07\u5143\uff09": "total_mkt_cap_10k",
    "\u6d41\u901a\u5e02\u503c\uff08\u4e07\u5143\uff09": "float_mkt_cap_10k",
    "\u5f53\u65e5\u6da8\u505c\u4ef7": "limit_up",
    "\u5f53\u65e5\u8dcc\u505c\u4ef7": "limit_down",
}


def _default_cache_path() -> Path:
    directory = PROCESSED_DATA_DIR / "legacy"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "stock_history_panel.parquet"


def stock_history_cache_path() -> Path:
    return _default_cache_path()


def _csv_dir_mtime(data_dir: Path) -> float:
    """获取目录下所有 CSV 的最新修改时间。"""
    mtimes = [p.stat().st_mtime for p in data_dir.glob("*.csv")]
    return max(mtimes) if mtimes else 0.0


def _cache_is_valid(cache_path: Path, data_dir: Path) -> bool:
    if not cache_path.exists():
        return False
    csv_mtime = _csv_dir_mtime(data_dir)
    cache_mtime = cache_path.stat().st_mtime
    return cache_mtime >= csv_mtime


def _load_from_csvs(data_dir: Path) -> pd.DataFrame:
    """从 CSV 文件加载并返回 DataFrame。"""
    csv_files = list(data_dir.glob("*.csv"))
    if not csv_files:
        raise ValueError(f"No CSV files found in {data_dir}")

    frames: list[pd.DataFrame] = []
    for path in csv_files:
        try:
            df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
        except Exception:
            continue
        df.columns = [c.lstrip("\ufeff") for c in df.columns]
        known = {c: RAW_COLUMN_MAP[c] for c in df.columns if c in RAW_COLUMN_MAP}
        if not known:
            continue
        df = df[list(known.keys())].rename(columns=known)
        frames.append(df)

    if not frames:
        raise ValueError("No valid stock history files could be loaded.")

    combined = pd.concat(frames, ignore_index=True)
    combined["trade_date"] = pd.to_datetime(combined["trade_date"], format="%Y%m%d", errors="coerce")
    numeric_cols = [
        "open", "high", "low", "close", "prev_close", "volume", "amount_k",
        "turnover_pct", "volume_ratio", "pe_ttm", "pb",
        "total_mkt_cap_10k", "float_mkt_cap_10k", "limit_up", "limit_down",
    ]
    for col in numeric_cols:
        if col in combined.columns:
            combined[col] = pd.to_numeric(combined[col], errors="coerce")

    combined = combined.dropna(subset=["stock_code", "trade_date", "close"])
    combined = combined.sort_values(["stock_code", "trade_date"]).reset_index(drop=True)
    return combined


def load_stock_history(
    data_dir: Path | str,
    cache_path: Path | str | None = None,
) -> pd.DataFrame:
    """读取旧项目格式的 StockHistory 数据目录，支持 parquet 缓存。

    第一次从 CSV 加载后会自动缓存为 parquet，后续直接读取缓存，
    直到 CSV 目录有更新。
    """
    data_dir = Path(data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(f"Stock history directory not found: {data_dir}")

    cache = Path(cache_path) if cache_path else _default_cache_path()

    if _cache_is_valid(cache, data_dir):
        return pd.read_parquet(cache)

    combined = _load_from_csvs(data_dir)
    cache.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(cache, index=False)
    return combined
