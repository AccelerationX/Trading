from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from trading_system.config.paths import CONFIGS_DIR, INBOX_DIR
from trading_system.integrations.domestic_news_sources import fetch_domestic_news_source_records


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

INDUSTRY_KEYWORD_MAP: dict[str, tuple[str, ...]] = {
    "ai": ("ai", "人工智能", "算力", "大模型"),
    "semiconductor": ("半导体", "芯片", "集成电路"),
    "robotics": ("机器人", "自动化"),
    "commercial_aerospace": ("商业航天", "卫星", "航天"),
    "military": ("军工", "国防"),
    "new_energy_vehicle": ("新能源车", "汽车工业", "智能驾驶", "电池"),
    "power_grid": ("电网", "储能", "电力"),
    "biotech": ("医药", "生物", "医疗"),
    "consumer_electronics": ("消费电子", "手机", "家电"),
    "software": ("软件", "信息技术", "数据"),
}

FILING_PRIORITY_KEYWORDS: tuple[tuple[str, int], ...] = (
    ("回购", 5),
    ("增持", 5),
    ("减持", 5),
    ("重大合同", 5),
    ("中标", 5),
    ("业绩预告", 5),
    ("业绩快报", 4),
    ("监管", 5),
    ("处罚", 5),
    ("立案", 5),
    ("停牌", 4),
    ("复牌", 4),
    ("重组", 5),
    ("问询函", 4),
    ("风险提示", 5),
    ("产销快报", 4),
)

NEWS_PRIORITY_KEYWORDS: tuple[tuple[str, int], ...] = (
    ("改革", 4),
    ("征求意见", 4),
    ("指引", 4),
    ("措施", 4),
    ("规则", 4),
    ("上市", 3),
    ("路演", 2),
    ("业绩说明会", 3),
    ("可持续发展", 3),
    ("再融资", 4),
    ("并购", 4),
    ("科技", 2),
    ("机器人", 3),
    ("芯片", 3),
    ("低空", 3),
)


NOISE_NEWS_MARKERS: tuple[str, ...] = (
    "VIP资讯",
    "解锁直达",
    "风口研报",
    "电报解读",
    "点击查看",
    "财联社早知道",
)

SOURCE_QUALITY_WEIGHTS: dict[str, float] = {
    "财联社": 1.0,
    "东方财富": 0.86,
    "上海证券交易所": 0.84,
    "深圳证券交易所": 0.84,
    "巨潮资讯": 0.82,
}


@dataclass(frozen=True)
class OfficialWebSourceSpec:
    id: str
    category: str
    parser_kind: str
    url: str
    issuing_body: str
    policy_level: str
    section_name: str = ""
    enabled: bool = True


@dataclass(slots=True)
class OfficialFetchArtifact:
    source_id: str
    path: Path
    row_count: int
    notes: list[str]


def load_official_web_source_specs(path: Path | None = None) -> list[OfficialWebSourceSpec]:
    config_path = path or (CONFIGS_DIR / "official_web_source_registry.json")
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    return [
        OfficialWebSourceSpec(
            id=item["id"],
            category=item["category"],
            parser_kind=item["parser_kind"],
            url=item["url"],
            issuing_body=item.get("issuing_body", ""),
            policy_level=item.get("policy_level", ""),
            section_name=item.get("section_name", ""),
            enabled=bool(item.get("enabled", True)),
        )
        for item in payload["sources"]
    ]


def _fetch_text(url: str, timeout: int = 30) -> str:
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding or "utf-8"
    return response.text


def _extract_industry_tags(text: str) -> list[str]:
    lowered = text.lower()
    tags = [
        tag
        for tag, keywords in INDUSTRY_KEYWORD_MAP.items()
        if any(keyword.lower() in lowered for keyword in keywords)
    ]
    return tags


def _priority_score(text: str, *, category: str) -> int:
    score = 0
    keyword_map = FILING_PRIORITY_KEYWORDS if category == "exchange_filings" else NEWS_PRIORITY_KEYWORDS
    for keyword, weight in keyword_map:
        if keyword in text:
            score += weight
    return score


def _source_quality(record: dict) -> float:
    source_name = str(record.get("source_name", "") or record.get("issuing_body", "")).strip()
    return SOURCE_QUALITY_WEIGHTS.get(source_name, 0.72)


def _news_signature(text: str) -> str:
    cleaned = str(text).strip()
    cleaned = re.sub(r"^【[^】]{1,24}】", "", cleaned)
    for marker in NOISE_NEWS_MARKERS:
        cleaned = cleaned.replace(marker, "")
    cleaned = re.sub(r"[>\-—:：,，。\s]+", "", cleaned)
    cleaned = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", cleaned)
    return cleaned.lower()


def _is_noise_news_record(record: dict) -> bool:
    title = str(record.get("title", "")).strip()
    summary = str(record.get("summary_text", "")).strip()
    text = f"{title} {summary}"
    if any(marker in text for marker in NOISE_NEWS_MARKERS):
        return True
    if len(_news_signature(title)) < 8:
        return True
    return False


def _is_similar_news_title(left: str, right: str) -> bool:
    left_sig = _news_signature(left)
    right_sig = _news_signature(right)
    if not left_sig or not right_sig:
        return False
    if left_sig == right_sig:
        return True
    if len(left_sig) >= 10 and len(right_sig) >= 10 and (left_sig in right_sig or right_sig in left_sig):
        return True
    return SequenceMatcher(a=left_sig, b=right_sig).ratio() >= 0.78


def _prefer_news_record(left: dict, right: dict) -> dict:
    def sort_key(record: dict) -> tuple[float, int, str, int]:
        return (
            _source_quality(record),
            int(record.get("priority_score", 0) or 0),
            str(record.get("publish_time", "")),
            len(str(record.get("summary_text", "")).strip()),
        )

    return left if sort_key(left) >= sort_key(right) else right


def _dedupe_news_records(records: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    for record in records:
        if _is_noise_news_record(record):
            continue
        replaced = False
        for idx, existing in enumerate(deduped):
            if str(record.get("publish_time", ""))[:10] != str(existing.get("publish_time", ""))[:10]:
                continue
            if not _is_similar_news_title(str(record.get("title", "")), str(existing.get("title", ""))):
                continue
            deduped[idx] = _prefer_news_record(record, existing)
            replaced = True
            break
        if not replaced:
            deduped.append(record)
    return deduped


def _write_json_records(source_id: str, trade_date: str, records: list[dict]) -> OfficialFetchArtifact:
    directory = INBOX_DIR / source_id
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{source_id}_{trade_date}.json"
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return OfficialFetchArtifact(source_id=source_id, path=path, row_count=len(records), notes=[])


def _normalize_date(raw: str) -> str:
    text = raw.strip()
    if not text:
        return ""
    if re.match(r"^\d{4}/\d{2}/\d{2}$", text):
        return text.replace("/", "-")
    if re.match(r"^\d{2}-\d{2}$", text):
        return f"2026-{text}"
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        return text
    try:
        return parsedate_to_datetime(text).strftime("%Y-%m-%d")
    except Exception:
        return text


def _parse_ndrc_notice_list(html: str, spec: OfficialWebSourceSpec) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[str] = set()
    for link in soup.find_all("a", href=True):
        title = link.get_text(" ", strip=True)
        href = urljoin(spec.url, link["href"])
        parent_text = link.parent.get_text(" ", strip=True) if link.parent else ""
        match = re.search(r"(\d{4}/\d{2}/\d{2})", parent_text)
        if not title or not match or title in seen:
            continue
        seen.add(title)
        records.append(
            {
                "title": title,
                "policy_level": spec.policy_level,
                "issuing_body": spec.issuing_body,
                "publish_time": _normalize_date(match.group(1)),
                "source_url": href,
                "summary_text": f"{spec.issuing_body}通知公告",
            }
        )
        if len(records) >= 30:
            break
    return records


def _parse_miit_rrs_section(html: str, spec: OfficialWebSourceSpec) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    text_lines = [line.strip() for line in soup.get_text("\n").splitlines() if line.strip()]
    records: list[dict] = []
    in_section = False
    stop_markers = {"互动交流", "统计分析", "工信动态", "部领导活动", "什么是RSS？"}
    for line in text_lines:
        if line == spec.section_name:
            in_section = True
            continue
        if in_section and line in stop_markers and line != spec.section_name:
            break
        if not in_section:
            continue
        match = re.match(r"(.+?)\s+(\d{2}-\d{2})$", line)
        if not match:
            continue
        title = match.group(1).strip()
        publish_time = _normalize_date(match.group(2))
        record = {
            "title": title,
            "publish_time": publish_time,
            "source_url": spec.url,
            "summary_text": f"{spec.issuing_body}{spec.section_name}",
        }
        if spec.category == "policy_primary_documents":
            record.update(
                {
                    "policy_level": spec.policy_level,
                    "issuing_body": spec.issuing_body,
                }
            )
        else:
            record.update(
                {
                    "source_name": spec.issuing_body,
                    "catalyst_type": f"official_{spec.section_name}",
                    "related_industries": _extract_industry_tags(title),
                    "related_stocks": [],
                }
            )
        records.append(record)
        if len(records) >= 20:
            break
    return records


def _parse_rss_xml(xml_text: str, spec: OfficialWebSourceSpec) -> list[dict]:
    root = ET.fromstring(xml_text)
    items = root.findall(".//item")
    records: list[dict] = []
    for item in items[:20]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = _normalize_date(item.findtext("pubDate") or "")
        if not title:
            continue
        if spec.category == "policy_primary_documents":
            records.append(
                {
                    "title": title,
                    "policy_level": spec.policy_level,
                    "issuing_body": spec.issuing_body,
                    "publish_time": pub_date,
                    "source_url": link,
                    "summary_text": f"{spec.issuing_body}RSS",
                }
            )
        else:
            records.append(
                {
                    "title": title,
                    "publish_time": pub_date,
                    "source_name": spec.issuing_body,
                    "catalyst_type": "official_rss_release",
                    "related_industries": _extract_industry_tags(title),
                    "related_stocks": [],
                    "summary_text": f"{spec.issuing_body}RSS",
                    "source_url": link,
                }
            )
    return records


def _parse_cninfo_latest_announcements(html: str, spec: OfficialWebSourceSpec) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    for row in soup.find_all("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["td", "th"])]
        if len(cells) < 4:
            continue
        stock_code = cells[0].strip().upper()
        if not re.fullmatch(r"\d{6}", stock_code):
            continue
        stock_name = cells[1].strip()
        title = cells[2].strip()
        publish_time = _normalize_date(cells[3].strip())
        link = row.find("a", href=True)
        source_url = urljoin(spec.url, link["href"]) if link else spec.url
        key = (stock_code, title, publish_time)
        if key in seen:
            continue
        seen.add(key)
        records.append(
            {
                "stock_code": f"{stock_code}.SH" if stock_code.startswith(("6", "9")) else f"{stock_code}.SZ",
                "stock_name": stock_name,
                "title": title,
                "publish_time": publish_time,
                "source_url": source_url,
                "full_text_path": source_url,
                "source_name": spec.issuing_body,
                "summary_text": title,
                "priority_score": _priority_score(title, category=spec.category),
            }
        )
    return records


def _parse_sse_hot_topics(html: str, spec: OfficialWebSourceSpec) -> list[dict]:
    text_lines = [line.strip() for line in BeautifulSoup(html, "html.parser").get_text("\n").splitlines() if line.strip()]
    records: list[dict] = []
    try:
        start = text_lines.index("热点动态") + 1
    except ValueError:
        return records
    idx = start
    while idx < len(text_lines) - 1:
        title = text_lines[idx]
        if title in {"各栏更新", "热门栏目", "本所网站"}:
            break
        next_line = text_lines[idx + 1]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", next_line):
            records.append(
                {
                    "title": title,
                    "publish_time": _normalize_date(next_line),
                    "source_url": spec.url,
                    "source_name": spec.issuing_body,
                    "content_text": title,
                    "related_industries": _extract_industry_tags(title),
                    "priority_score": _priority_score(title, category=spec.category),
                }
            )
            idx += 2
            continue
        idx += 1
    return records[:20]


def _parse_szse_exchange_news(html: str, spec: OfficialWebSourceSpec) -> list[dict]:
    text_lines = [line.strip() for line in BeautifulSoup(html, "html.parser").get_text("\n").splitlines() if line.strip()]
    records: list[dict] = []
    try:
        start = next(
            idx + 1 for idx, line in enumerate(text_lines) if line in {"深交所要闻", "深交所要闻更多", "本所要闻"}
        )
    except StopIteration:
        return records

    for line in text_lines[start:]:
        if line in {"更多", "深交所公告", "上市公司公告", "新闻发布会", "在线招聘"}:
            break
        title = line.lstrip("#").strip()
        if len(title) < 6:
            continue
        records.append(
            {
                "title": title,
                "publish_time": "",
                "source_url": spec.url,
                "source_name": spec.issuing_body,
                "content_text": title,
                "related_industries": _extract_industry_tags(title),
                "priority_score": _priority_score(title, category=spec.category),
            }
        )
        if len(records) >= 20:
            break
    return records


def _parse_records(html_or_xml: str, spec: OfficialWebSourceSpec) -> list[dict]:
    if spec.parser_kind == "ndrc_notice_list":
        return _parse_ndrc_notice_list(html_or_xml, spec)
    if spec.parser_kind == "miit_rrs_section":
        return _parse_miit_rrs_section(html_or_xml, spec)
    if spec.parser_kind == "rss_xml":
        return _parse_rss_xml(html_or_xml, spec)
    if spec.parser_kind == "cninfo_latest_announcements":
        return _parse_cninfo_latest_announcements(html_or_xml, spec)
    if spec.parser_kind == "sse_hot_topics":
        return _parse_sse_hot_topics(html_or_xml, spec)
    if spec.parser_kind == "szse_exchange_news":
        return _parse_szse_exchange_news(html_or_xml, spec)
    raise ValueError(f"Unsupported parser_kind: {spec.parser_kind}")


def _sort_and_trim(records: list[dict], *, category: str) -> list[dict]:
    limits = {
        "policy_primary_documents": 40,
        "industry_catalyst_calendar": 30,
        "exchange_filings": 120,
        "financial_news_wire": 40,
    }

    def key_func(record: dict) -> tuple[float, int, str, str]:
        return (
            _source_quality(record) if category == "financial_news_wire" else 0.0,
            int(record.get("priority_score", 0)),
            str(record.get("publish_time", "")),
            str(record.get("title", "")),
        )

    ordered = sorted(records, key=key_func, reverse=True)
    return ordered[: limits.get(category, 50)]


def fetch_official_web_sources(trade_date: str) -> tuple[list[OfficialFetchArtifact], list[str]]:
    policy_records: list[dict] = []
    catalyst_records: list[dict] = []
    filing_records: list[dict] = []
    news_records: list[dict] = []
    warnings: list[str] = []
    artifacts: list[OfficialFetchArtifact] = []

    for spec in load_official_web_source_specs():
        if not spec.enabled:
            continue
        try:
            text = _fetch_text(spec.url)
            parsed = _parse_records(text, spec)
            if spec.category == "policy_primary_documents":
                policy_records.extend(parsed)
            elif spec.category == "industry_catalyst_calendar":
                catalyst_records.extend(parsed)
            elif spec.category == "exchange_filings":
                filing_records.extend(parsed)
            elif spec.category == "financial_news_wire":
                news_records.extend(parsed)
        except Exception as exc:
            warnings.append(f"{spec.id} skipped: {exc}")

    domestic_records_by_source, domestic_warnings = fetch_domestic_news_source_records(trade_date)
    warnings.extend(domestic_warnings)
    for source_id, records in domestic_records_by_source.items():
        artifact = _write_json_records(source_id, trade_date, records)
        artifact.notes.append("source=domestic_news_scrape")
        artifacts.append(artifact)
        news_records.extend(records)

    def dedupe(records: list[dict], key_fields: tuple[str, ...]) -> list[dict]:
        seen: set[tuple[str, ...]] = set()
        output: list[dict] = []
        for record in records:
            key = tuple(str(record.get(field, "")) for field in key_fields)
            if key in seen:
                continue
            seen.add(key)
            output.append(record)
        return output

    policy_records = _sort_and_trim(dedupe(policy_records, ("title", "publish_time", "issuing_body")), category="policy_primary_documents")
    catalyst_records = _sort_and_trim(dedupe(catalyst_records, ("title", "publish_time", "source_name")), category="industry_catalyst_calendar")
    filing_records = _sort_and_trim(dedupe(filing_records, ("stock_code", "title", "publish_time")), category="exchange_filings")
    news_records = _sort_and_trim(_dedupe_news_records(news_records), category="financial_news_wire")

    artifacts.extend([
        _write_json_records("policy_primary_documents", trade_date, policy_records),
        _write_json_records("industry_catalyst_calendar", trade_date, catalyst_records),
        _write_json_records("exchange_filings", trade_date, filing_records),
        _write_json_records("financial_news_wire", trade_date, news_records),
    ])
    artifact_map = {artifact.source_id: artifact for artifact in artifacts}
    artifact_map["policy_primary_documents"].notes.append("source=official_web")
    artifact_map["industry_catalyst_calendar"].notes.append("source=official_web")
    artifact_map["exchange_filings"].notes.append("source=official_platform")
    artifact_map["financial_news_wire"].notes.append("source=exchange_news+domestic_scrape")
    return artifacts, warnings
