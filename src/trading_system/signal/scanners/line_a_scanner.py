from __future__ import annotations

from pathlib import Path

import pandas as pd

from trading_system.signal.legacy.data_loader import load_stock_history
from trading_system.signal.legacy.line_a_core import scan_line_a_candidates
from trading_system.signal.scanners.base import ModuleScanner, ModuleSignal
from trading_system.utils.main_board import is_main_board


class LineAScanner:
    """Line-A trend-continuation scanner adapted from legacy research code."""

    def __init__(self, data_dir: str | None = None, strategy: str = "double_q60_top10") -> None:
        self._data_dir = data_dir or r"D:\TradingSystem\data\raw\stock_history"
        self._strategy = strategy
        self._df: pd.DataFrame | None = None

    @property
    def module_id(self) -> str:
        return "TM001_line_a_trend_continuation"

    def is_available(self, trade_date: str) -> bool:
        try:
            data_dir = Path(self._data_dir)
            return data_dir.exists() and any(data_dir.glob("*.csv"))
        except Exception:
            return False

    def _ensure_loaded(self) -> pd.DataFrame:
        if self._df is None:
            self._df = load_stock_history(self._data_dir)
        return self._df

    def _ensure_trade_date_available(self, trade_date: str) -> None:
        df = self._ensure_loaded()
        target_date = pd.to_datetime(trade_date, errors="coerce")
        if pd.isna(target_date):
            raise FileNotFoundError(f"Invalid trade_date for {self.module_id}: {trade_date}")
        available_dates = pd.to_datetime(df["trade_date"], errors="coerce")
        if not available_dates.eq(target_date).any():
            latest = available_dates.max()
            latest_str = latest.strftime("%Y-%m-%d") if pd.notna(latest) else "unknown"
            raise FileNotFoundError(
                f"{self.module_id} missing exact stock_history date {trade_date}; latest local history date is {latest_str}"
            )

    def scan(
        self,
        trade_date: str,
        market_regime,
        account=None,
        universe=None,
    ) -> list[ModuleSignal]:
        self._ensure_trade_date_available(trade_date)
        df = self._ensure_loaded()
        candidates = scan_line_a_candidates(
            df,
            trade_date=trade_date,
            strategy=self._strategy,
        )
        if candidates.empty:
            return []

        allowed_universe = {code.strip().upper() for code in (universe or []) if str(code).strip()}
        if allowed_universe:
            candidates = candidates[candidates["stock_code"].astype(str).str.upper().isin(allowed_universe)]
        if account and getattr(account, "main_board_only", False):
            candidates = candidates[candidates["stock_code"].astype(str).map(is_main_board)]
        if candidates.empty:
            return []

        signals: list[ModuleSignal] = []
        for _, row in candidates.iterrows():
            if not bool(row.get("in_keep_zone", False)):
                continue
            action = row.get("action", "watch")
            if action == "target":
                signal_type = "strong"
                strength = 0.85
            elif action == "watch":
                signal_type = "watch"
                strength = 0.55
            else:
                signal_type = "moderate"
                strength = 0.70

            signals.append(
                ModuleSignal(
                    module_id=self.module_id,
                    stock_code=row["stock_code"],
                    trade_date=str(row["trade_date"].date()) if isinstance(row["trade_date"], pd.Timestamp) else str(row["trade_date"]),
                    signal_type=signal_type,
                    strength=strength,
                    technical_state=row.get("technical_state", "line_a_unknown"),
                    confidence=max(0.55, min(0.95, 0.95 - (int(row.get("rank_pos", 10)) - 1) * 0.05)),
                    metadata={
                        "signal_value": float(row.get("signal", 0)),
                        "rank_pos": int(row.get("rank_pos", 999)),
                        "in_entry_top_n": bool(row.get("in_entry_top_n", False)),
                        "in_keep_zone": bool(row.get("in_keep_zone", False)),
                        "strategy": self._strategy,
                    },
                    invalidation_hint="Drop out of keep_zone or signal turns negative",
                    source_refs=["line_a_core.py::scan_line_a_candidates"],
                )
            )
        return signals


# Register factory
def _factory(config: dict | None = None) -> ModuleScanner:
    config = config or {}
    return LineAScanner(
        data_dir=config.get("data_dir"),
        strategy=str(config.get("strategy", "double_q60_top10")),
    )


from trading_system.signal.scanners.registry import register_scanner

register_scanner("TM001_line_a_trend_continuation", _factory)
