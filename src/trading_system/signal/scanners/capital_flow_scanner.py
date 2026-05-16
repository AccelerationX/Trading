from __future__ import annotations

from trading_system.signal.legacy.capital_flow_core import scan_capital_flow_candidates
from trading_system.signal.scanners.base import ModuleScanner, ModuleSignal
from trading_system.utils.main_board import is_main_board


class CapitalFlowScanner:
    """TM601: Capital-flow aware ranking adjuster.

    Reads northbound + margin flow data from inbox and produces
    ModuleSignal for stocks with notable capital inflow/outflow.
    """

    def __init__(self, *, top_n: int = 10, keep_rank: int = 15) -> None:
        self._top_n = top_n
        self._keep_rank = keep_rank

    @property
    def module_id(self) -> str:
        return "TM601_capital_flow_overlay"

    def is_available(self, trade_date: str) -> bool:
        # Available if northbound_and_margin_flow data exists for the date
        from trading_system.config.paths import INBOX_DIR
        directory = INBOX_DIR / "northbound_and_margin_flow"
        if not directory.exists():
            return False
        exact = directory / f"northbound_and_margin_flow_{trade_date.replace('-', '')}.csv"
        return exact.exists()

    def scan(
        self,
        trade_date: str,
        market_regime,
        account=None,
        universe=None,
    ) -> list[ModuleSignal]:
        candidates = scan_capital_flow_candidates(
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
            sig_type = row.get("signal_type", "watch")
            if not bool(row.get("in_keep_zone", False)):
                continue
            strength = float(row.get("strength_hint", 0.5))
            confidence = min(0.95, max(0.3, 0.5 + strength * 0.3))

            signals.append(
                ModuleSignal(
                    module_id=self.module_id,
                    stock_code=row["stock_code"],
                    trade_date=trade_date,
                    signal_type=sig_type,
                    strength=strength,
                    technical_state=row.get("technical_state", "capital_flow_unknown"),
                    confidence=confidence,
                    metadata={
                        "net_amount": float(row.get("net_amount", 0)),
                        "capital_signal_type": str(row.get("capital_signal_type", "")),
                        "rank_pos": int(row.get("rank_pos", 999)),
                        "in_entry_top_n": bool(row.get("in_entry_top_n", False)),
                        "in_keep_zone": bool(row.get("in_keep_zone", False)),
                    },
                    invalidation_hint="Capital flow reverses direction or drops below 100M threshold",
                    source_refs=["capital_flow_core.py::scan_capital_flow_candidates"],
                )
            )
        return signals


def _factory(config: dict | None = None) -> ModuleScanner:
    config = config or {}
    return CapitalFlowScanner(
        top_n=int(config.get("top_n", 10)),
        keep_rank=int(config.get("keep_rank", 15)),
    )


from trading_system.signal.scanners.registry import register_scanner

register_scanner("TM601_capital_flow_overlay", _factory)
