from __future__ import annotations

import json
from pathlib import Path

from trading_system.config.paths import INBOX_DIR, OUTPUTS_DIR


SOURCE_BASE_SCORE = {
    "exchange_filings": 100,
    "policy_primary_documents": 80,
    "financial_news_wire": 60,
    "industry_catalyst_calendar": 50,
}


def _load_json(path: Path) -> list[dict]:
    try:
        return list(json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError:
        return list(json.loads(path.read_text(encoding="utf-8-sig")))


def _latest_file(source_id: str) -> Path | None:
    directory = INBOX_DIR / source_id
    if not directory.exists():
        return None
    files = sorted(
        [path for path in directory.glob("*.json") if path.is_file()],
        key=lambda path: (path.stat().st_mtime, path.name),
        reverse=True,
    )
    return files[0] if files else None


def _record_score(source_id: str, record: dict) -> int:
    base = SOURCE_BASE_SCORE.get(source_id, 0)
    explicit = int(record.get("priority_score", 0) or 0)
    industry_bonus = len(record.get("related_industries", []) or []) * 3
    stock_bonus = 2 if record.get("stock_code") else 0
    return base + explicit + industry_bonus + stock_bonus


def _normalized_watch_record(source_id: str, record: dict) -> dict:
    title = str(record.get("title", "")).strip()
    publish_time = str(record.get("publish_time", "")).strip()
    related_industries = list(record.get("related_industries", []) or [])
    related_stocks = []
    if record.get("stock_code"):
        related_stocks.append(str(record["stock_code"]).strip().upper())
    related_stocks.extend(str(item).strip().upper() for item in record.get("related_stocks", []) or [] if str(item).strip())
    return {
        "source_id": source_id,
        "priority_score": _record_score(source_id, record),
        "publish_time": publish_time,
        "title": title,
        "stock_code": str(record.get("stock_code", "")).strip().upper(),
        "related_industries": list(dict.fromkeys(related_industries)),
        "related_stocks": list(dict.fromkeys(related_stocks)),
        "source_url": str(record.get("source_url", "")).strip(),
        "summary_text": str(record.get("summary_text", "")).strip() or str(record.get("content_text", "")).strip(),
    }


def build_text_signal_watch(trade_date: str) -> tuple[Path, Path]:
    watch_records: list[dict] = []
    for source_id in ("exchange_filings", "policy_primary_documents", "financial_news_wire", "industry_catalyst_calendar"):
        path = _latest_file(source_id)
        if path is None:
            continue
        for record in _load_json(path):
            title = str(record.get("title", "")).strip()
            if not title:
                continue
            watch_records.append(_normalized_watch_record(source_id, record))

    watch_records.sort(
        key=lambda item: (int(item["priority_score"]), item["publish_time"], item["title"]),
        reverse=True,
    )
    watch_records = watch_records[:60]

    output_dir = OUTPUTS_DIR / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"text_signal_watch_{trade_date}.json"
    md_path = output_dir / f"text_signal_watch_{trade_date}.md"
    json_path.write_text(json.dumps(watch_records, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [f"# Text Signal Watch - {trade_date}", ""]
    if not watch_records:
        lines.append("- none")
    else:
        for item in watch_records:
            lines.append(f"## {item['source_id']} | score={item['priority_score']}")
            lines.append(f"- title: {item['title']}")
            if item["publish_time"]:
                lines.append(f"- publish_time: {item['publish_time']}")
            if item["stock_code"]:
                lines.append(f"- stock_code: {item['stock_code']}")
            if item["related_industries"]:
                lines.append(f"- related_industries: {', '.join(item['related_industries'])}")
            if item["related_stocks"]:
                lines.append(f"- related_stocks: {', '.join(item['related_stocks'])}")
            if item["summary_text"]:
                lines.append(f"- summary: {item['summary_text']}")
            if item["source_url"]:
                lines.append(f"- source_url: {item['source_url']}")
            lines.append("")
    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, md_path
