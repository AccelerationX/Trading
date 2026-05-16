from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class SourceMetadata:
    source_record_id: str
    source_family: str
    source_name: str
    source_url: str = ""
    publish_time: str = ""
    known_time: str = ""
    market_phase: str = ""
    trade_date_scope: str = ""
    trust_level: str = ""
    raw_payload_path: str = ""


@dataclass(slots=True)
class MarketBarRecord:
    metadata: SourceMetadata
    stock_code: str
    trade_date: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    prev_close: float | None = None
    volume: float | None = None
    amount: float | None = None
    turnover_pct: float | None = None
    volume_ratio: float | None = None
    limit_up_price: float | None = None
    limit_down_price: float | None = None


@dataclass(slots=True)
class MarketBreadthRecord:
    metadata: SourceMetadata
    trade_date: str
    up_count: int | None = None
    down_count: int | None = None
    flat_count: int | None = None
    limit_up_count: int | None = None
    limit_down_count: int | None = None
    broken_limit_up_count: int | None = None
    max_board_height: int | None = None
    total_turnover: float | None = None


@dataclass(slots=True)
class FilingRecord:
    metadata: SourceMetadata
    stock_code: str
    stock_name: str = ""
    filing_type: str = ""
    title: str = ""
    full_text_path: str = ""
    summary_text: str = ""


@dataclass(slots=True)
class PolicyRecord:
    metadata: SourceMetadata
    policy_id: str
    title: str
    policy_level: str = ""
    issuing_body: str = ""
    full_text_path: str = ""
    summary_text: str = ""


@dataclass(slots=True)
class CapitalFlowRecord:
    metadata: SourceMetadata
    stock_code: str
    trade_date: str
    capital_signal_type: str
    net_amount: float | None = None
    buy_amount: float | None = None
    sell_amount: float | None = None
    seat_or_channel: str = ""
    reason: str = ""


@dataclass(slots=True)
class NewsRecord:
    metadata: SourceMetadata
    news_id: str
    title: str
    content_text: str
    related_stocks: list[str] = field(default_factory=list)
    related_industries: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ManualNoteRecord:
    metadata: SourceMetadata
    note_id: str
    note_type: str
    author: str
    content_text: str
    related_stocks: list[str] = field(default_factory=list)
    related_themes: list[str] = field(default_factory=list)
