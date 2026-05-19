from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path

from trading_system.config.paths import INBOX_DIR, PROCESSED_DATA_DIR
from trading_system.context.cards import MacroEventCard


SOURCE_PRIORITY = {
    "policy_primary_documents": 0.74,
    "financial_news_wire": 0.58,
    "industry_catalyst_calendar": 0.5,
}

MACRO_NOISE_MARKERS: tuple[str, ...] = (
    "VIP资讯",
    "解锁直达",
    "风口研报",
    "电报解读",
    "财联社早知道",
)

COMPANY_NEWS_MARKERS: tuple[str, ...] = (
    "公司",
    "股份",
    "公告",
    "财报",
    "业绩",
    "一季度",
    "半年报",
    "IPO",
    "招股书",
    "董事会",
    "减持",
    "回购",
)


MACRO_EVENT_RULES: list[dict[str, object]] = [
    {
        "event_type": "geopolitical_conflict",
        "bias": "bearish",
        "impact_scope": "global_risk_aversion",
        "beneficiary_industries": ["military", "power_grid"],
        "risk_industries": ["consumer_electronics", "new_energy_vehicle", "semiconductor"],
        "related_markets": ["gold", "oil", "risk_off"],
        "confirmation_signals": ["oil price spike", "gold strength", "global equity weakness"],
        "risk_flags": ["overnight_gap_risk", "headline_acceleration_risk"],
    },
    {
        "event_type": "tariff_or_sanction",
        "bias": "bearish",
        "impact_scope": "global_trade_friction",
        "beneficiary_industries": ["military"],
        "risk_industries": ["consumer_electronics", "new_energy_vehicle", "semiconductor"],
        "related_markets": ["cny", "export_chain", "semiconductor"],
        "confirmation_signals": ["defensive rotation", "export chain weakness", "risk-off index response"],
        "risk_flags": ["policy_escalation_risk"],
    },
    {
        "event_type": "cross_border_diplomacy",
        "bias": "bullish",
        "impact_scope": "macro_cross_border",
        "beneficiary_industries": ["consumer_electronics", "new_energy_vehicle", "semiconductor", "commercial_aerospace"],
        "risk_industries": ["military"],
        "related_markets": ["cny", "hong_kong", "export_chain"],
        "confirmation_signals": ["export chain strength", "offshore yuan strength", "ports and logistics follow-through"],
        "risk_flags": ["headline_reversal_risk"],
    },
    {
        "event_type": "fiscal_or_consumption_stimulus",
        "bias": "bullish",
        "impact_scope": "domestic_demand",
        "beneficiary_industries": ["power_grid", "new_energy_vehicle", "consumer_electronics"],
        "risk_industries": [],
        "related_markets": ["a_share", "domestic_demand"],
        "confirmation_signals": ["policy chain breadth", "cyclical sector follow-through", "volume expansion"],
        "risk_flags": ["priced_in_risk"],
    },
    {
        "event_type": "monetary_easing",
        "bias": "bullish",
        "impact_scope": "liquidity",
        "beneficiary_industries": ["biotech", "consumer_electronics", "new_energy_vehicle", "semiconductor"],
        "risk_industries": [],
        "related_markets": ["a_share", "growth"],
        "confirmation_signals": ["growth index strength", "small cap breadth", "turnover expansion"],
        "risk_flags": ["expectation_gap_risk"],
    },
    {
        "event_type": "market_rule_or_reform",
        "bias": "mixed",
        "impact_scope": "market_structure",
        "beneficiary_industries": ["semiconductor", "commercial_aerospace"],
        "risk_industries": [],
        "related_markets": ["a_share", "small_cap"],
        "confirmation_signals": ["brokerage strength", "restructuring theme breadth", "micro-cap reaction"],
        "risk_flags": ["implementation_uncertainty"],
    },
]


def _macro_processed_dir() -> Path:
    directory = PROCESSED_DATA_DIR / "macro_events"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _latest_file(directory: Path) -> Path | None:
    if not directory.exists():
        return None
    files = sorted(
        [path for path in directory.glob("*.json") if path.is_file()],
        key=lambda path: (path.stat().st_mtime, path.name),
        reverse=True,
    )
    return files[0] if files else None


def _load_json(path: Path) -> list[dict]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return list(payload)


def _slugify(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "_", text).strip("_")[:80] or "macro"


def _combined_text(record: dict) -> str:
    return " ".join(
        str(record.get(key, "")).strip()
        for key in ("title", "summary_text", "content_text")
        if str(record.get(key, "")).strip()
    )


def _explicit_industries(record: dict) -> list[str]:
    raw = record.get("related_industries", []) or record.get("industry_tags", []) or []
    return list(dict.fromkeys(str(item).strip() for item in raw if str(item).strip()))


def _keyword_hits(text: str, keywords: tuple[str, ...]) -> int:
    lowered = text.lower()
    return sum(1 for keyword in keywords if keyword.lower() in lowered)


def _title_signature(text: str) -> str:
    cleaned = re.sub(r"^【[^】]{1,24}】", "", text.strip())
    cleaned = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", cleaned)
    return cleaned.lower()


def _has_company_news_bias(text: str) -> bool:
    return any(marker.lower() in text.lower() for marker in COMPANY_NEWS_MARKERS)


def _should_skip_record(source_id: str, record: dict, text: str) -> bool:
    if any(marker in text for marker in MACRO_NOISE_MARKERS):
        return True
    if source_id == "policy_primary_documents":
        priority_score = float(record.get("priority_score", 0) or 0)
        if priority_score < 3 and "通知" not in text and "规则" not in text:
            return True
    return False


def _match_geopolitical_conflict(text: str) -> int:
    region_hits = _keyword_hits(
        text,
        ("伊朗", "以色列", "中东", "乌克兰", "俄罗斯", "霍尔木兹", "oil", "iran", "israel", "ukraine", "russia"),
    )
    conflict_hits = _keyword_hits(
        text,
        ("战争", "空袭", "袭击", "导弹", "停火", "军事行动", "threat", "attack", "missile", "war", "ceasefire"),
    )
    if region_hits >= 1 and conflict_hits >= 1:
        return region_hits + conflict_hits
    return 0


def _match_tariff_or_sanction(text: str) -> int:
    hits = _keyword_hits(
        text,
        ("关税", "制裁", "出口管制", "实体清单", "tariff", "sanction", "export control", "entity list"),
    )
    return hits if hits >= 1 else 0


def _match_cross_border_diplomacy(text: str) -> int:
    country_hits = _keyword_hits(
        text,
        ("中美", "美中", "中国", "美国", "特朗普", "川普", "习近平", "trump", "xi", "china", "u.s.", "us "),
    )
    diplomacy_hits = _keyword_hits(
        text,
        ("会谈", "访问", "峰会", "磋商", "元首会晤", "对话", "经贸磋商", "summit", "visit", "talks", "dialogue", "meeting"),
    )
    if "中美" in text or "美中" in text:
        if diplomacy_hits >= 1:
            return 2 + diplomacy_hits
    if country_hits >= 2 and diplomacy_hits >= 1:
        return country_hits + diplomacy_hits
    if _has_company_news_bias(text):
        return 0
    return 0


def _match_fiscal_or_consumption_stimulus(text: str) -> int:
    policy_hits = _keyword_hits(text, ("专项债", "以旧换新", "消费支持", "刺激", "基建", "财政", "stimulus", "special bond"))
    if policy_hits >= 1:
        return policy_hits
    return 0


def _match_monetary_easing(text: str) -> int:
    hits = _keyword_hits(text, ("降准", "降息", "流动性", "信贷宽松", "rrr cut", "rate cut", "liquidity", "credit easing"))
    return hits if hits >= 1 else 0


def _match_market_rule_or_reform(text: str) -> int:
    hits = _keyword_hits(text, ("上市规则", "交易规则", "并购重组", "listing rules", "trading rules", "m&a"))
    return hits if hits >= 1 else 0


def _match_rule(text: str) -> tuple[dict[str, object], int] | None:
    matchers = {
        "geopolitical_conflict": _match_geopolitical_conflict,
        "tariff_or_sanction": _match_tariff_or_sanction,
        "cross_border_diplomacy": _match_cross_border_diplomacy,
        "fiscal_or_consumption_stimulus": _match_fiscal_or_consumption_stimulus,
        "monetary_easing": _match_monetary_easing,
        "market_rule_or_reform": _match_market_rule_or_reform,
    }
    best_rule: dict[str, object] | None = None
    best_score = 0
    for rule in MACRO_EVENT_RULES:
        score = matchers[str(rule["event_type"])](text)
        if score > best_score:
            best_rule = rule
            best_score = score
    if best_rule is None or best_score <= 0:
        return None
    return best_rule, best_score


def _record_confidence(source_id: str, record: dict, match_score: int) -> float:
    base = SOURCE_PRIORITY.get(source_id, 0.48)
    priority_score = float(record.get("priority_score", 0) or 0)
    confidence = base + min(0.18, priority_score / 40.0) + min(0.18, match_score * 0.05)
    return round(max(0.0, min(1.0, confidence)), 3)


def _build_macro_summary(rule: dict[str, object], record: dict) -> str:
    title = str(record.get("title", "")).strip() or "macro headline"
    event_type_map = {
        "geopolitical_conflict": "地缘冲突",
        "tariff_or_sanction": "关税或制裁",
        "cross_border_diplomacy": "跨境外交",
        "fiscal_or_consumption_stimulus": "财政或消费刺激",
        "monetary_easing": "货币宽松",
        "market_rule_or_reform": "市场规则或改革",
    }
    scope_map = {
        "global_risk_aversion": "全球风险偏好",
        "global_trade_friction": "全球贸易摩擦",
        "macro_cross_border": "跨境宏观环境",
        "domestic_demand": "内需预期",
        "liquidity": "流动性环境",
        "market_structure": "市场结构",
    }
    event_type = event_type_map.get(str(rule.get("event_type", "")).strip(), str(rule.get("event_type", "")).strip())
    scope = scope_map.get(str(rule.get("impact_scope", "")).strip(), str(rule.get("impact_scope", "")).strip())
    beneficiaries = "、".join(rule.get("beneficiary_industries", [])[:4]) or "无"
    risks = "、".join(rule.get("risk_industries", [])[:4]) or "无"
    return f"{title} 被归类为{event_type}，主要影响{scope}。受益方向关注：{beneficiaries}；承压方向关注：{risks}。"


def _iter_macro_source_records() -> list[tuple[str, Path, dict]]:
    records: list[tuple[str, Path, dict]] = []
    for source_id in ("policy_primary_documents", "financial_news_wire", "industry_catalyst_calendar"):
        path = _latest_file(INBOX_DIR / source_id)
        if path is None:
            continue
        for record in _load_json(path):
            records.append((source_id, path, record))
    return records


def build_macro_event_cards(trade_date: str) -> list[MacroEventCard]:
    draft_cards: list[tuple[MacroEventCard, str, str]] = []
    for idx, (source_id, path, record) in enumerate(_iter_macro_source_records(), start=1):
        text = _combined_text(record)
        if not text or _should_skip_record(source_id, record, text):
            continue
        matched = _match_rule(text)
        if matched is None:
            continue
        rule, match_score = matched
        confidence = _record_confidence(source_id, record, match_score)
        if confidence < 0.62:
            continue
        title = str(record.get("title", "")).strip() or str(rule["event_type"])
        publish_time = str(record.get("publish_time", "")).strip()
        beneficiary_industries = list(dict.fromkeys(_explicit_industries(record) + list(rule.get("beneficiary_industries", []))))
        card = MacroEventCard(
            macro_event_id=f"{trade_date}_{idx}_{_slugify(title)}",
            event_type=str(rule["event_type"]),
            title=title,
            publish_time=publish_time,
            source_name=str(record.get("source_name", "") or record.get("issuing_body", "")).strip(),
            source_url=str(record.get("source_url", "")).strip(),
            source_kind=source_id,
            bias=str(rule["bias"]),
            impact_scope=str(rule["impact_scope"]),
            confidence=confidence,
            beneficiary_industries=beneficiary_industries,
            risk_industries=list(rule.get("risk_industries", [])),
            related_markets=list(rule.get("related_markets", [])),
            confirmation_signals=list(rule.get("confirmation_signals", [])),
            risk_flags=list(rule.get("risk_flags", [])),
            summary=_build_macro_summary(rule, record),
            source_refs=[str(path)],
        )
        draft_cards.append((card, _title_signature(title), publish_time[:10]))

    deduped: list[MacroEventCard] = []
    seen_meta: list[tuple[str, str, str]] = []
    for card, signature, trade_day in sorted(
        draft_cards,
        key=lambda item: ((item[0].confidence or 0.0), item[0].publish_time, item[0].title),
        reverse=True,
    ):
        duplicate = False
        for event_type, existing_signature, existing_day in seen_meta:
            if event_type != card.event_type or trade_day != existing_day:
                continue
            if signature == existing_signature or (signature and existing_signature and (signature in existing_signature or existing_signature in signature)):
                duplicate = True
                break
        if duplicate:
            continue
        seen_meta.append((card.event_type, signature, trade_day))
        deduped.append(card)
    return deduped[:8]


def save_macro_event_cards(trade_date: str, cards: list[MacroEventCard], path: Path | None = None) -> Path:
    output_path = path or (_macro_processed_dir() / f"macro_event_cards_{trade_date}.json")
    output_path.write_text(json.dumps([asdict(card) for card in cards], ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
