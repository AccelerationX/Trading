from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from trading_system.config.paths import OUTPUTS_DIR, PROCESSED_DATA_DIR
from trading_system.context.cards import CandidateCard, CapitalBehaviorCard, EventCard, ThemeCard, TradePlanCard
from trading_system.integrations.llm_enrichments import (
    LLMEnrichmentResult,
    load_llm_enrichment_results,
    save_llm_enrichment_results,
)
from trading_system.memory.models import ReviewMemoryEntry
from trading_system.reporting.llm_enrichment_reports import render_llm_enrichment_apply_markdown


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return json.loads(path.read_text(encoding="utf-8-sig"))


def _optional_load_cards(path: Path, card_type):
    if not path.exists():
        return []
    return [card_type(**item) for item in list(_load_json(path))]


def _save_cards(path: Path, items: list[object]) -> None:
    path.write_text(json.dumps([asdict(item) for item in items], ensure_ascii=False, indent=2), encoding="utf-8")


def _apply_event_enrichment(card: EventCard, result: LLMEnrichmentResult) -> None:
    payload = result.structured_payload
    if result.summary:
        card.llm_summary = result.summary
    card.llm_confidence = result.confidence
    card.llm_sentiment_verdict = str(payload.get("sentiment_verdict", card.llm_sentiment_verdict or "")).strip()
    card.llm_beneficiary_stocks = list(payload.get("beneficiary_stocks", card.llm_beneficiary_stocks))
    card.llm_risk_notes = list(payload.get("risk_notes", card.llm_risk_notes))


def _apply_theme_enrichment(card: ThemeCard, result: LLMEnrichmentResult) -> None:
    payload = result.structured_payload
    if result.summary:
        card.llm_summary = result.summary
    card.llm_confidence = result.confidence
    card.llm_focus_industries = list(payload.get("focus_industries", card.llm_focus_industries))
    card.llm_focus_stocks = list(payload.get("focus_stocks", card.llm_focus_stocks))
    card.llm_tradeability_verdict = str(payload.get("tradeability_verdict", card.llm_tradeability_verdict or "")).strip()


def _apply_capital_enrichment(card: CapitalBehaviorCard, result: LLMEnrichmentResult) -> None:
    payload = result.structured_payload
    card.llm_summary = result.summary or card.llm_summary
    card.llm_confidence = result.confidence
    card.llm_interpretation = str(payload.get("interpretation", card.llm_interpretation or result.summary or "")).strip()


def _apply_candidate_enrichment(card: CandidateCard, result: LLMEnrichmentResult) -> None:
    payload = result.structured_payload
    if result.summary:
        card.llm_diagnostic_summary = result.summary
    card.llm_confidence = result.confidence
    card.llm_tradeability_verdict = str(payload.get("tradeability_verdict", card.llm_tradeability_verdict or "")).strip()
    card.llm_focus_points = list(payload.get("focus_points", card.llm_focus_points))
    card.llm_risk_notes = list(payload.get("risk_notes", card.llm_risk_notes))


def _apply_trade_plan_enrichment(card: TradePlanCard, result: LLMEnrichmentResult) -> None:
    payload = result.structured_payload
    card.llm_refined_plan = result.summary or card.llm_refined_plan
    card.llm_confidence = result.confidence
    card.llm_execution_watchpoints = list(payload.get("execution_watchpoints", card.llm_execution_watchpoints))


def _apply_review_memory_enrichment(entry: ReviewMemoryEntry, result: LLMEnrichmentResult) -> None:
    payload = result.structured_payload
    entry.llm_pattern_summary = result.summary or str(payload.get("pattern_summary", entry.llm_pattern_summary or "")).strip()
    entry.llm_confidence = result.confidence


def _report_dir() -> Path:
    directory = OUTPUTS_DIR / "llm_enrichment"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _trade_plan_storage_path(trade_date: str) -> Path:
    preferred_path = PROCESSED_DATA_DIR / "trade_plans" / f"trade_plan_cards_{trade_date}.json"
    if preferred_path.exists():
        return preferred_path
    return OUTPUTS_DIR / "trade_plans" / f"trade_plan_cards_{trade_date}.json"


def _load_results_from_paths(paths: list[Path]) -> list[LLMEnrichmentResult]:
    results: list[LLMEnrichmentResult] = []
    for path in paths:
        results.extend(load_llm_enrichment_results("", path))
    return results


def apply_llm_enrichments(trade_date: str, source_paths: list[Path] | None = None) -> tuple[Path, Path]:
    results = _load_results_from_paths(source_paths) if source_paths else load_llm_enrichment_results(trade_date)
    event_path = PROCESSED_DATA_DIR / "events" / f"event_cards_{trade_date}.json"
    theme_path = PROCESSED_DATA_DIR / "themes" / f"theme_cards_{trade_date}.json"
    capital_path = PROCESSED_DATA_DIR / "capital" / f"capital_behavior_cards_{trade_date}.json"
    candidate_path = PROCESSED_DATA_DIR / "candidates" / f"candidate_cards_{trade_date}.json"
    trade_plan_path = _trade_plan_storage_path(trade_date)
    memory_path = PROCESSED_DATA_DIR / "memory" / "review_memory_entries.json"

    event_cards = _optional_load_cards(event_path, EventCard)
    theme_cards = _optional_load_cards(theme_path, ThemeCard)
    capital_cards = _optional_load_cards(capital_path, CapitalBehaviorCard)
    candidate_cards = _optional_load_cards(candidate_path, CandidateCard)
    trade_plan_cards = _optional_load_cards(trade_plan_path, TradePlanCard)
    memory_entries = _optional_load_cards(memory_path, ReviewMemoryEntry)

    event_map = {card.event_id: card for card in event_cards}
    theme_map = {card.theme_id: card for card in theme_cards}
    capital_map = {card.card_id: card for card in capital_cards}
    candidate_map = {card.candidate_id: card for card in candidate_cards}
    trade_plan_map = {card.plan_id: card for card in trade_plan_cards}
    memory_map = {entry.memory_id: entry for entry in memory_entries}

    applied_counts = {"event_card": 0, "theme_card": 0, "capital_behavior_card": 0, "candidate_card": 0, "trade_plan_card": 0, "review_memory_entry": 0}
    skipped: list[str] = []

    for result in results:
        if result.target_object_type == "event_card":
            card = event_map.get(result.target_object_id)
            if card is None:
                skipped.append(f"missing event_card: {result.target_object_id}")
                continue
            _apply_event_enrichment(card, result)
            applied_counts["event_card"] += 1
        elif result.target_object_type == "theme_card":
            card = theme_map.get(result.target_object_id)
            if card is None:
                skipped.append(f"missing theme_card: {result.target_object_id}")
                continue
            _apply_theme_enrichment(card, result)
            applied_counts["theme_card"] += 1
        elif result.target_object_type == "capital_behavior_card":
            card = capital_map.get(result.target_object_id)
            if card is None:
                skipped.append(f"missing capital_behavior_card: {result.target_object_id}")
                continue
            _apply_capital_enrichment(card, result)
            applied_counts["capital_behavior_card"] += 1
        elif result.target_object_type == "candidate_card":
            card = candidate_map.get(result.target_object_id)
            if card is None:
                skipped.append(f"missing candidate_card: {result.target_object_id}")
                continue
            _apply_candidate_enrichment(card, result)
            applied_counts["candidate_card"] += 1
        elif result.target_object_type == "trade_plan_card":
            card = trade_plan_map.get(result.target_object_id)
            if card is None:
                skipped.append(f"missing trade_plan_card: {result.target_object_id}")
                continue
            _apply_trade_plan_enrichment(card, result)
            applied_counts["trade_plan_card"] += 1
        elif result.target_object_type == "review_memory_entry":
            entry = memory_map.get(result.target_object_id)
            if entry is None:
                skipped.append(f"missing review_memory_entry: {result.target_object_id}")
                continue
            _apply_review_memory_enrichment(entry, result)
            applied_counts["review_memory_entry"] += 1
        else:
            skipped.append(f"unsupported target_object_type: {result.target_object_type}")

    if event_cards:
        _save_cards(event_path, event_cards)
    if theme_cards:
        _save_cards(theme_path, theme_cards)
    if capital_cards:
        _save_cards(capital_path, capital_cards)
    if candidate_cards:
        _save_cards(candidate_path, candidate_cards)
    if trade_plan_cards:
        _save_cards(trade_plan_path, trade_plan_cards)
    if memory_entries:
        _save_cards(memory_path, memory_entries)

    enrichment_json = save_llm_enrichment_results(trade_date, results)
    report_path = _report_dir() / f"llm_enrichment_apply_{trade_date}.md"
    report_path.write_text(
        render_llm_enrichment_apply_markdown(trade_date, results, applied_counts, skipped),
        encoding="utf-8",
    )
    return enrichment_json, report_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Trade date in YYYY-MM-DD format.")
    parser.add_argument("--source", action="append", default=[], help="Optional explicit enrichment batch path. Repeatable.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    source_paths = [Path(item) for item in args.source]
    json_path, md_path = apply_llm_enrichments(args.date, source_paths=source_paths or None)
    print(f"llm_enrichment_json={json_path}")
    print(f"llm_enrichment_md={md_path}")


if __name__ == "__main__":
    main()
