from __future__ import annotations

import json
from pathlib import Path

from trading_system.config.paths import OUTPUTS_DIR


RISK_KEYWORDS = (
    "风险",
    "减持",
    "质押",
    "监管",
    "问询",
    "处罚",
    "异常波动",
    "澄清",
    "终止",
    "亏损",
    "下滑",
    "延期",
    "冻结",
)

POSITIVE_KEYWORDS = (
    "回购",
    "增持",
    "中标",
    "订单",
    "突破",
    "预增",
    "增长",
    "支持",
    "发布",
    "落地",
    "修订",
    "改善",
)


def _load_json(path: Path) -> list[dict]:
    try:
        return list(json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError:
        return list(json.loads(path.read_text(encoding="utf-8-sig")))


def load_text_signal_watch(trade_date: str) -> list[dict]:
    path = OUTPUTS_DIR / "analysis" / f"text_signal_watch_{trade_date}.json"
    if not path.exists():
        return []
    return _load_json(path)


def _normalize_stock_code(stock_code: str) -> str:
    return str(stock_code or "").strip().upper()


def _normalized_industries(industry_tags: list[str] | None) -> set[str]:
    return {str(tag).strip().lower() for tag in (industry_tags or []) if str(tag).strip()}


def find_relevant_text_signals(
    text_watch_records: list[dict],
    *,
    stock_code: str = "",
    industry_tags: list[str] | None = None,
    limit: int = 3,
) -> list[dict]:
    normalized_code = _normalize_stock_code(stock_code)
    normalized_industries = _normalized_industries(industry_tags)
    ranked: list[tuple[int, dict]] = []

    for record in text_watch_records:
        score = 0
        record_code = _normalize_stock_code(record.get("stock_code", ""))
        related_stocks = {_normalize_stock_code(item) for item in record.get("related_stocks", []) or []}
        related_industries = _normalized_industries(list(record.get("related_industries", []) or []))

        if normalized_code and record_code == normalized_code:
            score += 50
        elif normalized_code and normalized_code in related_stocks:
            score += 35

        industry_overlap = normalized_industries & related_industries
        if industry_overlap:
            score += 12 + 5 * len(industry_overlap)

        if score <= 0:
            continue

        score += int(record.get("priority_score", 0) or 0)
        ranked.append((score, record))

    ranked.sort(
        key=lambda item: (
            item[0],
            int(item[1].get("priority_score", 0) or 0),
            str(item[1].get("publish_time", "")),
            str(item[1].get("title", "")),
        ),
        reverse=True,
    )
    return [record for _, record in ranked[:limit]]


def text_signal_bias(records: list[dict]) -> float:
    if not records:
        return 0.0

    score = 0.0
    for record in records:
        text = f"{record.get('title', '')} {record.get('summary_text', '')}".lower()
        positive_hits = sum(1 for token in POSITIVE_KEYWORDS if token in text)
        risk_hits = sum(1 for token in RISK_KEYWORDS if token in text)
        score += positive_hits * 1.0
        score -= risk_hits * 1.25

    bounded = max(-1.0, min(1.0, score / max(2.0, len(records) * 2.0)))
    return round(bounded, 3)


def text_signal_focus_summary(records: list[dict], *, limit: int = 2) -> str:
    titles = [str(record.get("title", "")).strip() for record in records if str(record.get("title", "")).strip()]
    return " | ".join(titles[:limit])
