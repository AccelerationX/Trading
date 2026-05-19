from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from trading_system.config.paths import CONFIGS_DIR


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

INDUSTRY_KEYWORD_MAP: dict[str, tuple[str, ...]] = {
    "ai": ("ai", "人工智能", "算力", "大模型"),
    "semiconductor": ("semiconductor", "chip", "半导体", "芯片", "存储"),
    "robotics": ("robot", "robotics", "机器人", "自动化"),
    "commercial_aerospace": ("aerospace", "satellite", "商业航天", "卫星", "发射"),
    "military": ("defense", "military", "军工", "国防"),
    "new_energy_vehicle": ("ev", "新能源车", "电动车", "汽车产业链", "智能驾驶", "电池"),
    "power_grid": ("power grid", "储能", "电网", "电力"),
    "biotech": ("biotech", "医药", "生物", "创新药", "医疗"),
    "consumer_electronics": ("consumer electronics", "消费电子", "手机", "面板", "苹果链"),
    "software": ("software", "软件", "云", "数据要素", "信创"),
}

PRIORITY_KEYWORDS: tuple[tuple[str, int], ...] = (
    ("中美", 6),
    ("关税", 6),
    ("制裁", 6),
    ("出口管制", 6),
    ("降准", 5),
    ("降息", 5),
    ("政策", 3),
    ("改革", 4),
    ("并购重组", 5),
    ("上市规则", 4),
    ("交易规则", 4),
    ("芯片", 4),
    ("半导体", 4),
    ("算力", 4),
    ("消费电子", 4),
    ("机器人", 4),
    ("新能源车", 4),
    ("军工", 4),
)

TIME_ONLY_PATTERN = re.compile(r"^\d{2}:\d{2}(?::\d{2})?$")
TIME_PREFIX_PATTERN = re.compile(r"^(?P<time>\d{2}:\d{2}(?::\d{2})?)[\s\u3000]*(?P<body>.+)?$")
STOCK_CODE_PATTERN = re.compile(r"\b\d{6}\.(?:SH|SZ|BJ)\b", re.IGNORECASE)
CLS_TITLE_PATTERN = re.compile(r"^[【\[](.*?)[】\]]")
EASTMONEY_COLUMNS_PATTERN = re.compile(r'columns\s*=\s*"(?P<columns>[^"]+)"')
EASTMONEY_A_STOCK_PATTERN = re.compile(r"^(?P<market>[012])\.(?P<code>\d{6})$")


@dataclass(frozen=True)
class DomesticNewsSourceSpec:
    id: str
    parser_kind: str
    url: str
    source_name: str
    enabled: bool = True
    options: dict[str, object] | None = None


def load_domestic_news_source_specs(path: Path | None = None) -> list[DomesticNewsSourceSpec]:
    config_path = path or (CONFIGS_DIR / "domestic_news_source_registry.json")
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    return [
        DomesticNewsSourceSpec(
            id=item["id"],
            parser_kind=item["parser_kind"],
            url=item["url"],
            source_name=item["source_name"],
            enabled=bool(item.get("enabled", True)),
            options=item.get("options"),
        )
        for item in payload["sources"]
    ]


def _fetch_text(url: str, timeout: int = 30) -> str:
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    response.raise_for_status()
    raw = response.content
    encodings: list[str] = []
    header_encoding = (response.encoding or "").strip()
    if header_encoding and header_encoding.lower() != "iso-8859-1":
        encodings.append(header_encoding)
    meta_match = re.search(rb"charset=['\"]?([A-Za-z0-9._-]+)", raw[:4096], re.IGNORECASE)
    if meta_match:
        encodings.append(meta_match.group(1).decode("ascii", errors="ignore"))
    encodings.extend(["utf-8", "gb18030", response.apparent_encoding or ""])

    for encoding in encodings:
        if not encoding:
            continue
        try:
            return raw.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", errors="ignore")


def _fetch_json(url: str, params: dict[str, object], timeout: int = 30) -> dict:
    response = requests.get(url, params=params, headers=DEFAULT_HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _clean_lines(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    lines = []
    for line in soup.get_text("\n").splitlines():
        cleaned = re.sub(r"\s+", " ", line).strip()
        if cleaned:
            lines.append(cleaned)
    return lines


def _extract_industry_tags(text: str) -> list[str]:
    lowered = text.lower()
    tags = [
        tag
        for tag, keywords in INDUSTRY_KEYWORD_MAP.items()
        if any(keyword.lower() in lowered for keyword in keywords)
    ]
    return list(dict.fromkeys(tags))


def _priority_score(text: str, *, source_name: str) -> int:
    score = 2
    lowered = text.lower()
    for keyword, weight in PRIORITY_KEYWORDS:
        if keyword.lower() in lowered:
            score += weight
    if source_name == "财联社":
        score += 2
    elif source_name == "东方财富":
        score += 1
    return score


def _normalize_publish_time(raw_time: str, trade_date: str) -> str:
    compact = trade_date.replace("-", "")
    yyyy_mm_dd = f"{compact[:4]}-{compact[4:6]}-{compact[6:8]}"
    text = raw_time.strip()
    if not text:
        return ""
    if re.fullmatch(r"\d{2}:\d{2}(?::\d{2})?", text):
        return f"{yyyy_mm_dd} {text[:5]}:00" if len(text) == 5 else f"{yyyy_mm_dd} {text}"
    if re.fullmatch(r"\d{2}-\d{2}\s+\d{2}:\d{2}", text):
        month_day, hhmm = text.split()
        return f"{compact[:4]}-{month_day} {hhmm}:00"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}", text):
        return f"{text}:00"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}", text):
        return text
    return text


def _split_title_summary(body: str, *, source_name: str) -> tuple[str, str]:
    text = body.strip()
    if not text:
        return "", ""
    match = CLS_TITLE_PATTERN.match(text)
    if match:
        title = match.group(1).strip()
        summary = text[match.end() :].strip(" ：:，,;；")
        return title or text[:24], summary or text
    if "：" in text:
        head, tail = text.split("：", 1)
        if 2 <= len(head) <= 26:
            return head.strip(), tail.strip() or text
    if "，" in text and source_name == "财联社":
        head, tail = text.split("，", 1)
        if 2 <= len(head) <= 30:
            return head.strip(), tail.strip() or text
    title = text[:28].rstrip("，。；;:：")
    return title or text, text


def _build_record(
    *,
    trade_date: str,
    source_id: str,
    source_name: str,
    source_url: str,
    raw_time: str,
    body: str,
) -> dict | None:
    normalized_body = body.strip()
    if len(normalized_body) < 8:
        return None
    title, summary = _split_title_summary(normalized_body, source_name=source_name)
    related_stocks = [code.upper() for code in STOCK_CODE_PATTERN.findall(normalized_body)]
    return {
        "source_id": source_id,
        "title": title,
        "publish_time": _normalize_publish_time(raw_time, trade_date),
        "source_url": source_url,
        "source_name": source_name,
        "summary_text": summary,
        "content_text": normalized_body,
        "related_industries": _extract_industry_tags(normalized_body),
        "related_stocks": list(dict.fromkeys(related_stocks)),
        "stock_code": related_stocks[0].upper() if related_stocks else "",
        "priority_score": _priority_score(normalized_body, source_name=source_name),
    }


def _extract_eastmoney_columns(html: str) -> str:
    match = EASTMONEY_COLUMNS_PATTERN.search(html)
    if match:
        return match.group("columns").strip()
    return "102"


def _normalize_eastmoney_stock(raw_code: str) -> str:
    match = EASTMONEY_A_STOCK_PATTERN.fullmatch(raw_code.strip())
    if not match:
        return ""
    code = match.group("code")
    market = match.group("market")
    if market == "1":
        return f"{code}.SH"
    if market == "0":
        return f"{code}.SZ"
    if market == "2":
        return f"{code}.BJ"
    return ""


def _build_eastmoney_record(
    item: dict,
    *,
    trade_date: str,
    spec: DomesticNewsSourceSpec,
) -> dict | None:
    title = str(item.get("title", "")).strip()
    summary = str(item.get("summary", "")).strip() or title
    publish_time = _normalize_publish_time(str(item.get("showTime", "")).strip(), trade_date)
    if not title or not publish_time:
        return None

    content_text = summary if summary.startswith("【") else f"【{title}】{summary}"
    related_stocks = [
        normalized
        for normalized in (_normalize_eastmoney_stock(raw_code) for raw_code in item.get("stockList", []))
        if normalized
    ]
    related_industries = _extract_industry_tags(f"{title} {summary}")
    return {
        "source_id": spec.id,
        "title": title,
        "publish_time": publish_time,
        "source_url": spec.url,
        "source_name": spec.source_name,
        "summary_text": summary,
        "content_text": content_text,
        "related_industries": related_industries,
        "related_stocks": list(dict.fromkeys(related_stocks)),
        "stock_code": related_stocks[0] if related_stocks else "",
        "priority_score": _priority_score(f"{title} {summary}", source_name=spec.source_name),
    }


def _fetch_eastmoney_fastnews(spec: DomesticNewsSourceSpec, trade_date: str) -> list[dict]:
    options = spec.options or {}
    landing_html = _fetch_text(spec.url)
    columns = str(options.get("fast_column") or _extract_eastmoney_columns(landing_html))
    page_size = int(options.get("page_size", 40))
    api_url = str(options.get("api_url") or "https://np-weblist.eastmoney.com/comm/web/getFastNewsList")
    payload = _fetch_json(
        api_url,
        params={
            "client": "web",
            "biz": "web_724",
            "fastColumn": columns,
            "sortEnd": "",
            "pageSize": page_size,
            "req_trace": str(int(time.time() * 1000)),
        },
    )
    items = payload.get("data", {}).get("fastNewsList", [])
    records = [
        record
        for record in (_build_eastmoney_record(item, trade_date=trade_date, spec=spec) for item in items)
        if record is not None
    ]

    deduped: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for record in records:
        key = (record["title"], record["publish_time"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def _parse_time_feed(html: str, *, trade_date: str, spec: DomesticNewsSourceSpec) -> list[dict]:
    lines = _clean_lines(html)
    records: list[dict] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        body_from_line = ""
        raw_time = ""
        prefix_match = TIME_PREFIX_PATTERN.match(line)
        if prefix_match:
            raw_time = prefix_match.group("time")
            body_from_line = (prefix_match.group("body") or "").strip()
        elif TIME_ONLY_PATTERN.fullmatch(line):
            raw_time = line
        if not raw_time:
            idx += 1
            continue

        body_parts: list[str] = []
        if body_from_line:
            body_parts.append(body_from_line)

        lookahead = idx + 1
        while lookahead < len(lines):
            candidate = lines[lookahead]
            if TIME_ONLY_PATTERN.fullmatch(candidate) or TIME_PREFIX_PATTERN.match(candidate):
                break
            if len(body_parts) >= 3:
                break
            body_parts.append(candidate)
            lookahead += 1

        record = _build_record(
            trade_date=trade_date,
            source_id=spec.id,
            source_name=spec.source_name,
            source_url=spec.url,
            raw_time=raw_time,
            body=" ".join(body_parts).strip(),
        )
        if record is not None:
            records.append(record)
        idx = max(idx + 1, lookahead)

    deduped: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for record in records:
        key = (record["title"], record["publish_time"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped[:80]


def _parse_records(html: str, *, trade_date: str, spec: DomesticNewsSourceSpec) -> list[dict]:
    if spec.parser_kind in {"cls_mobile_telegraph", "ths_fastnews"}:
        return _parse_time_feed(html, trade_date=trade_date, spec=spec)
    raise ValueError(f"Unsupported parser_kind: {spec.parser_kind}")


def fetch_domestic_news_source_records(trade_date: str) -> tuple[dict[str, list[dict]], list[str]]:
    records_by_source: dict[str, list[dict]] = {}
    warnings: list[str] = []
    for spec in load_domestic_news_source_specs():
        if not spec.enabled:
            continue
        try:
            if spec.parser_kind == "eastmoney_fastnews":
                records_by_source[spec.id] = _fetch_eastmoney_fastnews(spec, trade_date)
                continue
            html = _fetch_text(spec.url)
            records_by_source[spec.id] = _parse_records(html, trade_date=trade_date, spec=spec)
        except Exception as exc:
            warnings.append(f"{spec.id} skipped: {exc}")
    return records_by_source, warnings
