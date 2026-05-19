from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from trading_system.config.paths import CONFIGS_DIR, INBOX_DIR, OUTPUTS_DIR, PROCESSED_DATA_DIR, WORKSPACE_DIR
from trading_system.integrations.domestic_news_sources import load_domestic_news_source_specs
from trading_system.integrations.llm_provider_registry import load_llm_provider_registry


@dataclass(frozen=True)
class ArtifactCheck:
    name: str
    latest_date: str | None
    path: str | None
    exists: bool


def _daily_report_dir() -> Path:
    directory = OUTPUTS_DIR / "daily_reports"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _latest_dated_file(directory: Path, prefix: str, suffix: str) -> tuple[str | None, Path | None]:
    if not directory.exists():
        return None, None
    pattern = re.compile(rf"{re.escape(prefix)}_(\d{{8}}|\d{{4}}-\d{{2}}-\d{{2}}){re.escape(suffix)}$", re.IGNORECASE)
    dated: list[tuple[str, str, Path]] = []
    for path in directory.glob(f"{prefix}_*{suffix}"):
        match = pattern.match(path.name)
        if not match:
            continue
        raw_date = match.group(1)
        normalized_date = raw_date.replace("-", "")
        dated.append((normalized_date, raw_date, path))
    if not dated:
        return None, None
    _, latest_date, latest_path = sorted(dated, key=lambda item: item[0], reverse=True)[0]
    return latest_date, latest_path


def _build_artifact_checks() -> list[ArtifactCheck]:
    checks = [
        ("market_equity_daily", INBOX_DIR / "market_equity_daily", "market_equity_daily", ".csv"),
        ("financial_news_wire", INBOX_DIR / "financial_news_wire", "financial_news_wire", ".json"),
        ("policy_primary_documents", INBOX_DIR / "policy_primary_documents", "policy_primary_documents", ".json"),
        ("exchange_filings", INBOX_DIR / "exchange_filings", "exchange_filings", ".json"),
        ("macro_event_cards", PROCESSED_DATA_DIR / "macro_events", "macro_event_cards", ".json"),
        ("candidate_cards", PROCESSED_DATA_DIR / "candidates", "candidate_cards", ".json"),
        ("trade_plan_cards", OUTPUTS_DIR / "trade_plans", "trade_plan_cards", ".json"),
        ("setup_performance", PROCESSED_DATA_DIR / "evaluation", "setup_performance", ".json"),
        ("execution_feedback", PROCESSED_DATA_DIR / "evaluation", "execution_feedback", ".json"),
        ("execution_behavior", PROCESSED_DATA_DIR / "evaluation", "execution_behavior", ".json"),
        ("preopen_summary", OUTPUTS_DIR / "preopen", "preopen_summary", ".json"),
        ("trade_execution_sheet", OUTPUTS_DIR / "trade_execution", "trade_execution", ".json"),
        ("system_trade_log", WORKSPACE_DIR / "portfolio", "system_trade_log", ".json"),
    ]
    result: list[ArtifactCheck] = []
    for name, directory, prefix, suffix in checks:
        latest_date, latest_path = _latest_dated_file(directory, prefix, suffix)
        result.append(
            ArtifactCheck(
                name=name,
                latest_date=latest_date,
                path=str(latest_path) if latest_path is not None else None,
                exists=latest_path is not None,
            )
        )
    return result


def _domestic_news_status() -> dict:
    specs = load_domestic_news_source_specs(CONFIGS_DIR / "domestic_news_source_registry.json")
    enabled = [spec.id for spec in specs if spec.enabled]
    disabled = [spec.id for spec in specs if not spec.enabled]
    return {
        "enabled_count": len(enabled),
        "enabled_sources": enabled,
        "disabled_sources": disabled,
    }


def _llm_status() -> dict:
    providers = load_llm_provider_registry()
    enabled = [provider.provider_id for provider in providers if provider.enabled]
    remote_enabled = [
        provider.provider_id
        for provider in providers
        if provider.enabled and provider.provider_type == "openai_compatible"
    ]
    local_enabled = [
        provider.provider_id
        for provider in providers
        if provider.enabled and provider.provider_type in {"local_ollama", "ollama_chat"}
    ]
    other_enabled = [
        f"{provider.provider_id} ({provider.provider_type})"
        for provider in providers
        if provider.enabled and provider.provider_type not in {"openai_compatible", "local_ollama", "ollama_chat"}
    ]
    return {
        "enabled_count": len(enabled),
        "enabled_providers": enabled,
        "remote_enabled": remote_enabled,
        "local_enabled": local_enabled,
        "other_enabled": other_enabled,
    }


def build_system_selfcheck_payload(run_date: str) -> dict:
    artifact_checks = _build_artifact_checks()
    artifact_map = {item.name: item for item in artifact_checks}
    latest_market = artifact_map.get("market_equity_daily", ArtifactCheck("", None, None, False)).latest_date
    latest_news = artifact_map.get("financial_news_wire", ArtifactCheck("", None, None, False)).latest_date
    latest_preopen = artifact_map.get("preopen_summary", ArtifactCheck("", None, None, False)).latest_date

    warnings: list[str] = []
    if not latest_market:
        warnings.append("核心行情缓存缺失：market_equity_daily 不存在。")
    if not latest_news:
        warnings.append("新闻快讯缓存缺失：financial_news_wire 不存在。")
    if latest_market and latest_preopen and latest_market != latest_preopen.replace("-", ""):
        warnings.append(
            f"盘前摘要使用日期与最新行情缓存不一致：market={latest_market}, preopen={latest_preopen}"
        )
    if latest_market and latest_news and latest_news < latest_market:
        warnings.append(f"新闻快讯日期早于行情缓存：news={latest_news}, market={latest_market}")

    return {
        "run_date": run_date,
        "artifact_checks": [asdict(item) for item in artifact_checks],
        "domestic_news": _domestic_news_status(),
        "llm": _llm_status(),
        "warnings": warnings,
    }


def render_system_selfcheck_markdown(payload: dict) -> str:
    lines = [
        f"# 系统自检 - {payload.get('run_date', '')}",
        "",
        "## 核心产物",
    ]
    for item in payload.get("artifact_checks", []):
        status = "正常" if item.get("exists") else "缺失"
        lines.append(
            f"- {item.get('name')}: `{status}` / latest=`{item.get('latest_date') or 'none'}`"
            + (f" / {item.get('path')}" if item.get("path") else "")
        )

    domestic_news = dict(payload.get("domestic_news", {}))
    lines.extend(
        [
            "",
            "## 国内新闻源",
            f"- 已启用数量：`{domestic_news.get('enabled_count', 0)}`",
            f"- 已启用：`{', '.join(domestic_news.get('enabled_sources', [])) or 'none'}`",
            f"- 已停用：`{', '.join(domestic_news.get('disabled_sources', [])) or 'none'}`",
        ]
    )

    llm = dict(payload.get("llm", {}))
    lines.extend(
        [
            "",
            "## LLM 状态",
            f"- 已启用 Provider 数量：`{llm.get('enabled_count', 0)}`",
            f"- 本地 Provider：`{', '.join(llm.get('local_enabled', [])) or 'none'}`",
            f"- 远程 Provider：`{', '.join(llm.get('remote_enabled', [])) or 'none'}`",
            f"- 其他 Provider：`{', '.join(llm.get('other_enabled', [])) or 'none'}`",
        ]
    )

    warnings = list(payload.get("warnings", []))
    lines.extend(["", "## 告警"])
    if not warnings:
        lines.append("- 无")
    else:
        for item in warnings:
            lines.append(f"- {item}")
    return "\n".join(lines).rstrip() + "\n"


def save_system_selfcheck_payload(run_date: str, payload: dict) -> tuple[Path, Path]:
    compact = run_date.replace("-", "")
    json_path = _daily_report_dir() / f"system_selfcheck_{compact}.json"
    md_path = _daily_report_dir() / f"system_selfcheck_{compact}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_system_selfcheck_markdown(payload), encoding="utf-8")
    return json_path, md_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat(), help="Run date in YYYY-MM-DD format.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    payload = build_system_selfcheck_payload(args.date)
    json_path, md_path = save_system_selfcheck_payload(args.date, payload)
    print(f"system_selfcheck_json={json_path}")
    print(f"system_selfcheck_md={md_path}")


if __name__ == "__main__":
    main()
