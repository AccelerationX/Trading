from __future__ import annotations

from pathlib import Path

import pandas as pd

from trading_system.signal.legacy.data_loader import load_stock_history
from trading_system.signal.legacy.group_rotation_core import scan_group_rotation_candidates
from trading_system.signal.scanners.base import ModuleScanner, ModuleSignal
from trading_system.utils.main_board import is_main_board


class GroupRotationScanner:
    """TM201: Group rotation scanner — pick strongest latent groups first, then rank inside."""

    def __init__(self, data_dir: str | None = None, *, top_n: int = 8, keep_rank: int = 10) -> None:
        self._data_dir = data_dir or r"D:\TradingSystem\data\raw\stock_history"
        self._top_n = top_n
        self._keep_rank = keep_rank
        self._df: pd.DataFrame | None = None

    @property
    def module_id(self) -> str:
        return "TM201_group_rotation_repair"

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
        candidates = scan_group_rotation_candidates(
            df,
            trade_date=trade_date,
            top_n=self._top_n,
            keep_rank=self._keep_rank,
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
            sig_type = row.get("signal_type", "watch")
            if sig_type == "strong":
                strength = 0.80
            elif sig_type == "moderate":
                strength = 0.65
            else:
                strength = 0.45

            confidence = min(0.95, 0.55 + float(row.get("rotation_repair_signal", 0)) * 0.15)
            confidence = max(0.3, min(0.95, confidence))

            signals.append(
                ModuleSignal(
                    module_id=self.module_id,
                    stock_code=row["stock_code"],
                    trade_date=str(row["trade_date"].date()) if isinstance(row["trade_date"], pd.Timestamp) else str(row["trade_date"]),
                    signal_type=sig_type,
                    strength=strength,
                    technical_state=f"group_{row.get('latent_group', 'unknown')}_rotation",
                    confidence=confidence,
                    metadata={
                        "rotation_repair_signal": float(row.get("rotation_repair_signal", 0)),
                        "latent_group": int(row.get("latent_group", -1)),
                        "rank_pos": int(row.get("rank_pos", 999)),
                        "in_entry_top_n": bool(row.get("in_entry_top_n", False)),
                        "in_keep_zone": bool(row.get("in_keep_zone", False)),
                    },
                    invalidation_hint="Group momentum reverses or stock drops out of keep_zone",
                    source_refs=["group_rotation_core.py::scan_group_rotation_candidates"],
                )
            )
        return signals


def _factory(config: dict | None = None) -> ModuleScanner:
    config = config or {}
    return GroupRotationScanner(
        data_dir=config.get("data_dir"),
        top_n=int(config.get("top_n", 8)),
        keep_rank=int(config.get("keep_rank", 10)),
    )


from trading_system.signal.scanners.registry import register_scanner

register_scanner("TM201_group_rotation_repair", _factory)
