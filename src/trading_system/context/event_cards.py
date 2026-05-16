from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path

from trading_system.config.paths import INBOX_DIR, PROCESSED_DATA_DIR
from trading_system.context.cards import EventCard, ThemeCard
from trading_system.ingest.simple_tabular import read_records


INDUSTRY_KEYWORD_MAP: dict[str, tuple[str, ...]] = {
    "ai": ("ai", "artificial intelligence", "人工智能", "大模型", "算力"),
    "semiconductor": ("chip", "semiconductor", "芯片", "半导体", "存储"),
    "robotics": ("robot", "robotics", "机器人", "自动化"),
    "commercial_aerospace": ("aerospace", "satellite", "航天", "卫星"),
    "military": ("defense", "军工", "国防"),
    "new_energy_vehicle": ("ev", "new energy vehicle", "新能源车", "汽车电子", "智能驾驶"),
    "power_grid": ("power grid", "smart grid", "电网", "特高压", "储能"),
    "biotech": ("biotech", "生物", "创新药", "医药", "医疗器械"),
    "consumer_electronics": ("consumer electronics", "消费电子", "手机", "面板"),
    "data_center": ("data center", "服务器", "数据中心", "云计算"),
}

EVENT_TYPE_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("earnings_preannouncement", ("业绩预告", "业绩快报", "earnings", "profit alert")),
    ("share_repurchase", ("回购", "repurchase")),
    ("share_reduction", ("减持", "reduction")),
    ("share_increase", ("增持", "increase")),
    ("unlock", ("解禁", "unlock")),
    ("major_contract", ("合同", "中标", "contract", "order win")),
    ("restructuring", ("重组", "并购", "reorganization", "m&a", "merger")),
    ("regulatory_risk", ("立案", "处罚", "监管", "问询", "risk", "investigation")),
    ("trading_halt_resume", ("停牌", "复牌", "halt", "resume")),
]

STRUCTURED_ANNOUNCEMENT_TITLE_MAP = {
    "Major holder share increase": "重要股东增持",
    "Major holder share reduction": "重要股东减持",
}


def _format_structured_announcement_title(title: str, filing_type: str) -> str:
    normalized = str(title or "").strip()
    if normalized in STRUCTURED_ANNOUNCEMENT_TITLE_MAP:
        return STRUCTURED_ANNOUNCEMENT_TITLE_MAP[normalized]
    if normalized.startswith("Share repurchase update "):
        stage = normalized.removeprefix("Share repurchase update ").strip() or "进展"
        return f"股份回购进展：{stage}"
    if normalized:
        return normalized

    filing_map = {
        "share_repurchase": "股份回购进展",
        "share_increase": "重要股东增持",
        "share_reduction": "重要股东减持",
    }
    return filing_map.get(filing_type, filing_type or "announcement")


def _latest_matching_file(directory: Path) -> Path:
    candidates = sorted(
        [
            path
            for pattern in ("*.json", "*.csv")
            for path in directory.glob(pattern)
            if path.is_file()
        ],
        key=lambda path: (path.stat().st_mtime, path.name),
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"No supported input files found in {directory}")
    return candidates[0]


def _slugify(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "_", text).strip("_")
    return slug[:80] or "item"


def _event_processed_dir() -> Path:
    directory = PROCESSED_DATA_DIR / "events"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _theme_processed_dir() -> Path:
    directory = PROCESSED_DATA_DIR / "themes"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _optional_latest_matching_file(directory: Path) -> Path | None:
    candidates = sorted(
        [
            path
            for pattern in ("*.json", "*.csv")
            for path in directory.glob(pattern)
            if path.is_file()
        ],
        key=lambda path: (path.stat().st_mtime, path.name),
        reverse=True,
    )
    return candidates[0] if candidates else None


def _combined_text(record: dict, *keys: str) -> str:
    parts = [str(record.get(key, "")).strip() for key in keys if str(record.get(key, "")).strip()]
    return " ".join(parts)


def _split_multi_value(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    parts = re.split(r"[,\|;/，；、\s]+", text)
    return [part.strip() for part in parts if part.strip()]


def _extract_stock_codes(record: dict, *keys: str) -> list[str]:
    stock_codes: list[str] = []
    for key in keys:
        stock_codes.extend(_split_multi_value(record.get(key)))
    normalized = [code.upper() for code in stock_codes if code]
    return list(dict.fromkeys(normalized))


def _extract_industry_tags(record: dict, text: str) -> list[str]:
    explicit_tags: list[str] = []
    for key in ("industry_tags", "related_industries", "industry", "theme_tags"):
        explicit_tags.extend(_split_multi_value(record.get(key)))

    matched_tags: list[str] = []
    lowered = text.lower()
    for tag, keywords in INDUSTRY_KEYWORD_MAP.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            matched_tags.append(tag)
    return list(dict.fromkeys(explicit_tags + matched_tags))


def _extract_beneficiary_chain(record: dict) -> list[str]:
    chain = []
    for key in ("beneficiary_chain", "beneficiaries", "issuing_body", "summary_tags"):
        chain.extend(_split_multi_value(record.get(key)))
    return list(dict.fromkeys(chain))


def _infer_event_type(record: dict) -> str:
    text = _combined_text(record, "filing_type", "title", "summary_text").lower()
    for event_type, keywords in EVENT_TYPE_KEYWORDS:
        if any(keyword.lower() in text for keyword in keywords):
            return event_type
    return "general_company_event"


def _infer_bullish_bearish(event_type: str, title_text: str) -> tuple[str, float]:
    positive_types = {"earnings_preannouncement", "share_repurchase", "share_increase", "major_contract", "restructuring"}
    negative_types = {"share_reduction", "unlock", "regulatory_risk"}

    if event_type in positive_types:
        return "bullish", 0.72
    if event_type in negative_types:
        return "bearish", 0.72

    lowered = title_text.lower()
    if any(keyword in lowered for keyword in ("增长", "预增", "回购", "中标", "增持", "improve", "win", "beat")):
        return "bullish", 0.62
    if any(keyword in lowered for keyword in ("减持", "立案", "处罚", "亏损", "下修", "risk", "warning")):
        return "bearish", 0.62
    return "mixed", 0.48


def _infer_impact_horizon(event_type: str, text: str) -> str:
    lowered = text.lower()
    if event_type in {"share_repurchase", "share_reduction", "share_increase", "unlock"}:
        return "multi_day"
    if event_type in {"earnings_preannouncement", "major_contract", "restructuring"}:
        return "multi_day_to_medium_term"
    if event_type == "regulatory_risk":
        return "immediate_to_multi_day"
    if any(keyword in lowered for keyword in ("three year", "长期", "中长期", "capacity expansion")):
        return "medium_term"
    return "needs_review"


def _infer_novelty_score(record: dict, event_type: str) -> float:
    if str(record.get("is_incremental", "")).lower() in {"1", "true", "yes"}:
        return 0.82
    if event_type in {"earnings_preannouncement", "restructuring", "major_contract"}:
        return 0.68
    if event_type in {"share_repurchase", "share_increase"}:
        return 0.6
    return 0.5


def _infer_event_risk_flags(event_type: str, publish_time: str, title_text: str) -> list[str]:
    flags = ["needs_llm_review"]
    lowered = title_text.lower()
    if event_type in {"share_reduction", "unlock", "regulatory_risk"}:
        flags.append("negative_event_check")
    if event_type == "restructuring":
        flags.append("complex_event")
    if publish_time and any(token in publish_time for token in ("15:", "16:", "17:", "18:", "19:", "20:", "21:")):
        flags.append("post_close_release")
    if any(keyword in lowered for keyword in ("预计", "可能", "拟", "proposal", "draft")):
        flags.append("proposal_stage")
    return list(dict.fromkeys(flags))


def _infer_theme_trigger_type(record: dict) -> str:
    policy_level = str(record.get("policy_level", "")).strip().lower()
    issuing_body = str(record.get("issuing_body", "")).strip().lower()
    if policy_level:
        return f"policy:{policy_level}"
    if any(token in issuing_body for token in ("state council", "国务院")):
        return "policy:state_council"
    if any(token in issuing_body for token in ("ministry", "部", "委")):
        return "policy:ministry"
    if any(token in issuing_body for token in ("province", "省", "市")):
        return "policy:local"
    return "policy:unspecified"


def _infer_theme_continuation(record: dict, text: str) -> str:
    explicit = str(record.get("continuation_guess", "")).strip()
    if explicit:
        return explicit
    lowered = text.lower()
    if any(keyword in lowered for keyword in ("three year", "五年", "规划", "plan", "roadmap", "action plan")):
        return "medium_term_policy_line"
    if any(keyword in lowered for keyword in ("accelerate", "推广", "试点", "support")):
        return "multi_day_follow_up"
    return "needs_review"


def _infer_theme_confirmations(industry_tags: list[str], continuation_guess: str) -> list[str]:
    confirmations = ["sector strength", "leader stock confirmation", "volume expansion"]
    if industry_tags:
        confirmations.append(f"industry mapping: {', '.join(industry_tags[:3])}")
    if continuation_guess != "needs_review":
        confirmations.append("follow-up policy or company confirmation")
    return confirmations


def _infer_theme_contra_risks(trigger_type: str, title_text: str) -> list[str]:
    risks = ["policy priced in", "weak market confirmation", "theme diffusion too broad"]
    lowered = title_text.lower()
    if trigger_type == "policy:local":
        risks.append("local policy may have narrow impact")
    if any(keyword in lowered for keyword in ("draft", "征求意见", "意见稿")):
        risks.append("policy still at draft stage")
    return list(dict.fromkeys(risks))


def build_event_cards_from_structured_announcements(trade_date: str, path: Path | None = None) -> list[EventCard]:
    source_path = path or _latest_matching_file(INBOX_DIR / "company_announcements_structured")
    records = [{**record, "__source_ref": str(source_path)} for record in read_records(source_path)]
    exchange_filings_path = None if path is not None else _optional_latest_matching_file(INBOX_DIR / "exchange_filings")
    if exchange_filings_path is not None:
        records.extend({**record, "__source_ref": str(exchange_filings_path)} for record in read_records(exchange_filings_path))
    cards: list[EventCard] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for idx, record in enumerate(records, start=1):
        filing_type = str(record.get("filing_type", "")).strip()
        title = _format_structured_announcement_title(str(record.get("title", "")).strip(), filing_type)
        combined_text = " ".join(part for part in (filing_type, title, str(record.get("summary_text", "")).strip()) if part)
        stock_codes = _extract_stock_codes(record, "stock_code", "ts_code", "related_stocks", "stock_codes")
        if not stock_codes and not title and not filing_type:
            continue
        dedupe_stock = stock_codes[0] if stock_codes else "unknown"
        dedupe_key = (dedupe_stock, title or filing_type, str(record.get("publish_time", "")).strip())
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)

        event_type = _infer_event_type(record)
        bullish_bearish, event_strength = _infer_bullish_bearish(event_type, combined_text)
        publish_time = str(record.get("publish_time", "")).strip()
        industry_tags = _extract_industry_tags(record, combined_text)
        risk_flags = _infer_event_risk_flags(event_type, publish_time, combined_text)
        card = EventCard(
            event_id=f"{trade_date}_{(stock_codes[0] if stock_codes else 'unknown')}_{idx}_{_slugify(title or filing_type)}",
            event_type=event_type,
            event_title=title or filing_type or "announcement",
            stock_codes=stock_codes,
            industry_tags=industry_tags,
            publish_time=publish_time,
            bullish_bearish=bullish_bearish,
            impact_horizon=_infer_impact_horizon(event_type, combined_text),
            event_strength=event_strength,
            novelty_score=_infer_novelty_score(record, event_type),
            is_official=True,
            core_claim=title or filing_type or "official announcement needs review",
            risk_flags=risk_flags,
            source_refs=[str(record.get("__source_ref", source_path))],
            llm_summary="Draft card generated from structured announcement input. LLM should verify the true beneficiaries, timing scope, and risk qualifiers.",
        )
        cards.append(card)
    return cards


def build_theme_cards_from_policy_inputs(trade_date: str, path: Path | None = None) -> list[ThemeCard]:
    policy_source_path = path or _latest_matching_file(INBOX_DIR / "policy_primary_documents")
    records = [{**record, "__source_ref": str(policy_source_path)} for record in read_records(policy_source_path)]
    catalyst_source_path = None if path is not None else _optional_latest_matching_file(INBOX_DIR / "industry_catalyst_calendar")
    if catalyst_source_path is not None:
        records.extend({**record, "__source_ref": str(catalyst_source_path)} for record in read_records(catalyst_source_path))
    news_source_path = None if path is not None else _optional_latest_matching_file(INBOX_DIR / "financial_news_wire")
    if news_source_path is not None:
        news_records = [
            {**record, "__source_ref": str(news_source_path)}
            for record in read_records(news_source_path)
            if _extract_industry_tags(record, _combined_text(record, "title", "content_text", "summary_text"))
            or float(record.get("priority_score", 0) or 0) >= 3
        ]
        records.extend(news_records)
    cards: list[ThemeCard] = []
    seen_keys: set[tuple[str, str]] = set()
    for idx, record in enumerate(records, start=1):
        title = str(record.get("title", "")).strip()
        if not title:
            continue
        dedupe_key = (title, str(record.get("publish_time", "")).strip())
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        summary_text = str(record.get("summary_text", "")).strip()
        combined_text = _combined_text(record, "title", "summary_text", "issuing_body", "policy_level")
        industry_tags = _extract_industry_tags(record, combined_text)
        priority_stocks = _extract_stock_codes(record, "priority_stocks", "related_stocks", "beneficiary_stocks")
        continuation_guess = _infer_theme_continuation(record, combined_text)
        trigger_type = _infer_theme_trigger_type(record)
        cards.append(
            ThemeCard(
                theme_id=f"{trade_date}_{idx}_{_slugify(title)}",
                theme_name=title,
                trigger_type=trigger_type,
                trigger_time=str(record.get("publish_time", "")).strip(),
                beneficiary_chain=_extract_beneficiary_chain(record),
                priority_industries=industry_tags,
                priority_stocks=priority_stocks,
                continuation_guess=continuation_guess,
                market_confirmation_needed=_infer_theme_confirmations(industry_tags, continuation_guess),
                contra_risks=_infer_theme_contra_risks(trigger_type, combined_text),
                source_refs=[str(record.get("__source_ref", policy_source_path))],
                llm_summary=summary_text or "Draft theme card generated from policy input. LLM should map the policy to concrete industries, chains, and likely beneficiary stocks.",
            )
        )
    return cards


def save_event_cards(trade_date: str, cards: list[EventCard], path: Path | None = None) -> Path:
    output_path = path or (_event_processed_dir() / f"event_cards_{trade_date}.json")
    output_path.write_text(json.dumps([asdict(card) for card in cards], ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def save_theme_cards(trade_date: str, cards: list[ThemeCard], path: Path | None = None) -> Path:
    output_path = path or (_theme_processed_dir() / f"theme_cards_{trade_date}.json")
    output_path.write_text(json.dumps([asdict(card) for card in cards], ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
