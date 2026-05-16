from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from trading_system.context.cards import MarketRegimeSnapshot
from trading_system.decision.account import AccountConstraints


@dataclass(frozen=True)
class ModuleSignal:
    """单一模块产生的原始信号，尚未与事件/主题/账户约束融合。"""

    module_id: str
    stock_code: str
    trade_date: str
    signal_type: str  # "strong", "moderate", "watch", "avoid"
    strength: float  # 0.0 ~ 1.0
    technical_state: str
    confidence: float = 1.0  # 0.0 ~ 1.0，数据完整度
    metadata: dict = field(default_factory=dict)
    invalidation_hint: str = ""
    source_refs: list[str] = field(default_factory=list)


@runtime_checkable
class ModuleScanner(Protocol):
    """技术模块扫描器协议。每个被推荐的模块应有一个对应的实现。"""

    @property
    def module_id(self) -> str:
        ...

    def is_available(self, trade_date: str) -> bool:
        """检查所需数据是否到位。"""
        ...

    def scan(
        self,
        trade_date: str,
        market_regime: MarketRegimeSnapshot,
        account: AccountConstraints | None = None,
        universe: list[str] | None = None,
    ) -> list[ModuleSignal]:
        """扫描当日市场，返回信号列表。"""
        ...
