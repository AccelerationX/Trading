from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from trading_system.cli.apply_llm_enrichments import apply_llm_enrichments
from trading_system.cli.build_analysis_bundle import build_analysis_bundle
from trading_system.cli.build_capital_behavior_cards import build_capital_behavior_cards_cli
from trading_system.cli.build_candidate_cards import build_candidate_cards_from_bundle
from trading_system.cli.build_execution_feedback import build_execution_feedback_cli
from trading_system.cli.build_execution_behavior import build_execution_behavior_cli
from trading_system.cli.build_event_and_theme_cards import build_event_and_theme_cards
from trading_system.cli.build_trade_execution_sheet import build_trade_execution_sheet
from trading_system.cli.build_module_evaluation import build_module_evaluation_cli
from trading_system.cli.build_setup_performance import build_setup_performance_cli
from trading_system.cli.build_llm_workpacks import build_llm_workpacks_cli
from trading_system.cli.build_market_regime import build_market_regime
from trading_system.cli.build_review_memory import build_review_memory_cli
from trading_system.cli.build_preopen_summary import build_preopen_summary
from trading_system.cli.sync_trade_execution_to_live_state import sync_trade_execution_to_live_state
from trading_system.cli.build_text_signal_watch import build_text_signal_watch_cli
from trading_system.cli.build_trade_plan_cards import build_trade_plan_cards_cli
from trading_system.cli.daily_intake import run_daily_intake
from trading_system.cli.execute_llm_runtime import execute_llm_runtime
from trading_system.cli.fetch_official_text_sources import fetch_official_text_sources
from trading_system.cli.fetch_tushare_sources import fetch_tushare_supported_sources
from trading_system.cli.plan_llm_execution import plan_llm_execution
from trading_system.cli.sync_stock_history import sync_stock_history_from_market_daily
from trading_system.cli.refresh_holdings_snapshot import refresh_holdings_snapshot
from trading_system.config.paths import INBOX_DIR, OUTPUTS_DIR
from trading_system.decision.account import load_active_account_constraints, save_normalized_account_constraints
from trading_system.integrations.llm_profiles import resolve_llm_runtime_profile, supported_llm_modes
from trading_system.integrations.llm_provider_registry import load_llm_provider_registry
from trading_system.reporting.pipeline_run_report import render_pipeline_run_report


@dataclass(frozen=True)
class MarketDataPrecheckResult:
    requested_trade_date: str
    requested_weekday: str
    latest_local_market_date: str | None
    fetched_market_date: str | None
    effective_trade_date: str
    source_fetch_status: str
    strict_market_date: bool
    used_source_fetch_market_date: bool
    warnings: tuple[str, ...]


def _daily_report_dir() -> Path:
    directory = OUTPUTS_DIR / "daily_reports"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _format_compact_trade_date(value: str) -> str:
    compact = value.replace("-", "")
    return f"{compact[:4]}-{compact[4:6]}-{compact[6:]}"


def _run_account_refresh() -> Path:
    account = load_active_account_constraints()
    return save_normalized_account_constraints(account)


def _has_enabled_remote_llm_provider() -> bool:
    return any(
        provider.enabled and provider.provider_type == "openai_compatible"
        for provider in load_llm_provider_registry()
    )


def _available_local_market_dates() -> list[str]:
    market_dir = INBOX_DIR / "market_equity_daily"
    pattern = re.compile(r"market_equity_daily_(\d{8})\.csv$", re.IGNORECASE)
    dates: list[str] = []
    if not market_dir.exists():
        return dates
    for path in market_dir.glob("market_equity_daily_*.csv"):
        match = pattern.match(path.name)
        if match:
            dates.append(match.group(1))
    return sorted(set(dates))


def _resolve_effective_trade_date(requested_trade_date: str) -> tuple[str, str | None]:
    compact_requested = requested_trade_date.replace("-", "")
    available_dates = _available_local_market_dates()
    if not available_dates:
        return requested_trade_date, None
    if compact_requested in available_dates:
        return _format_compact_trade_date(compact_requested), None

    eligible_dates = [item for item in available_dates if item <= compact_requested]
    fallback_date = eligible_dates[-1] if eligible_dates else available_dates[-1]
    effective = _format_compact_trade_date(fallback_date)
    warning = (
        f"trade_date_fallback: requested {requested_trade_date}, "
        f"but local market cache is unavailable for that date; using {effective}"
    )
    return effective, warning


def _extract_market_equity_date(paths: list[Path]) -> str | None:
    pattern = re.compile(r"market_equity_daily_(\d{8})\.csv$", re.IGNORECASE)
    for path in paths:
        match = pattern.match(path.name)
        if match:
            return match.group(1)
    return None


def _extract_market_equity_date_from_fetch_reports(paths: list[Path]) -> str | None:
    for path in paths:
        if path.suffix.lower() != ".json":
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        artifacts = payload.get("artifacts", [])
        for artifact in artifacts:
            if artifact.get("source_id") != "market_equity_daily":
                continue
            artifact_path = Path(str(artifact.get("path", "")))
            extracted = _extract_market_equity_date([artifact_path])
            if extracted:
                return extracted
    return None


def _build_market_data_precheck(
    requested_trade_date: str,
    *,
    source_fetch_status: str,
    source_artifacts: list[Path],
    strict_market_date: bool,
) -> MarketDataPrecheckResult:
    requested_weekday = date.fromisoformat(requested_trade_date).strftime("%A")
    available_dates = _available_local_market_dates()
    latest_local_market_date = available_dates[-1] if available_dates else None
    fetched_market_date = _extract_market_equity_date(source_artifacts) or _extract_market_equity_date_from_fetch_reports(source_artifacts)
    warnings: list[str] = []
    compact_requested = requested_trade_date.replace("-", "")
    used_source_fetch_market_date = False

    if fetched_market_date:
        effective_trade_date = _format_compact_trade_date(fetched_market_date)
        used_source_fetch_market_date = True
        if fetched_market_date == compact_requested:
            if requested_weekday in {"Saturday", "Sunday"}:
                warnings.append(
                    f"trade_date_non_trading_day: requested {requested_trade_date} is {requested_weekday}, "
                    f"but fresh market data resolved to {effective_trade_date}"
                )
        else:
            if requested_weekday in {"Saturday", "Sunday"}:
                warnings.append(
                    f"trade_date_non_trading_day: requested {requested_trade_date} is {requested_weekday}; "
                    f"using latest open market session {effective_trade_date}"
                )
            else:
                warnings.append(
                    f"trade_date_source_fetch_adjusted: requested {requested_trade_date}, "
                    f"fresh market data resolved to latest open market session {effective_trade_date}"
                )
    else:
        effective_trade_date, fallback_warning = _resolve_effective_trade_date(requested_trade_date)
        if fallback_warning:
            if requested_weekday in {"Saturday", "Sunday"}:
                warnings.append(
                    f"trade_date_non_trading_day: requested {requested_trade_date} is {requested_weekday}; "
                    f"using latest local market cache {effective_trade_date}"
                )
            warnings.append(fallback_warning)
        elif requested_weekday in {"Saturday", "Sunday"}:
            warnings.append(
                f"trade_date_non_trading_day: requested {requested_trade_date} is {requested_weekday}; "
                f"using latest local market cache {effective_trade_date}"
            )

    if strict_market_date and not fetched_market_date and compact_requested != effective_trade_date.replace("-", ""):
        raise RuntimeError(
            "strict_market_date_failed: fresh market_equity_daily was not refreshed to the latest open session. "
            "Re-run with --with-source-fetch after fixing Tushare connectivity."
        )

    return MarketDataPrecheckResult(
        requested_trade_date=requested_trade_date,
        requested_weekday=requested_weekday,
        latest_local_market_date=_format_compact_trade_date(latest_local_market_date) if latest_local_market_date else None,
        fetched_market_date=_format_compact_trade_date(fetched_market_date) if fetched_market_date else None,
        effective_trade_date=effective_trade_date,
        source_fetch_status=source_fetch_status,
        strict_market_date=strict_market_date,
        used_source_fetch_market_date=used_source_fetch_market_date,
        warnings=tuple(warnings),
    )


def _write_market_data_precheck(precheck: MarketDataPrecheckResult) -> tuple[Path, Path]:
    json_path = _daily_report_dir() / f"market_data_precheck_{precheck.requested_trade_date}.json"
    md_path = _daily_report_dir() / f"market_data_precheck_{precheck.requested_trade_date}.md"
    payload = {
        "requested_trade_date": precheck.requested_trade_date,
        "requested_weekday": precheck.requested_weekday,
        "latest_local_market_date": precheck.latest_local_market_date,
        "fetched_market_date": precheck.fetched_market_date,
        "effective_trade_date": precheck.effective_trade_date,
        "source_fetch_status": precheck.source_fetch_status,
        "strict_market_date": precheck.strict_market_date,
        "used_source_fetch_market_date": precheck.used_source_fetch_market_date,
        "warnings": list(precheck.warnings),
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"# Market Data Precheck - {precheck.requested_trade_date}",
        "",
        f"- requested_trade_date: `{precheck.requested_trade_date}`",
        f"- requested_weekday: `{precheck.requested_weekday}`",
        f"- latest_local_market_date: `{precheck.latest_local_market_date or 'none'}`",
        f"- fetched_market_date: `{precheck.fetched_market_date or 'none'}`",
        f"- effective_trade_date: `{precheck.effective_trade_date}`",
        f"- source_fetch_status: `{precheck.source_fetch_status}`",
        f"- strict_market_date: `{precheck.strict_market_date}`",
        f"- used_source_fetch_market_date: `{precheck.used_source_fetch_market_date}`",
        "",
        "## Warnings",
    ]
    if not precheck.warnings:
        lines.append("- none")
    else:
        for warning in precheck.warnings:
            lines.append(f"- {warning}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def _run_source_fetch_best_effort(requested_trade_date: str) -> tuple[str, list[Path], list[str]]:
    compact = requested_trade_date.replace("-", "")
    artifacts: list[Path] = []
    warnings: list[str] = []

    try:
        tushare_json, tushare_md = fetch_tushare_supported_sources(compact)
        artifacts.extend([tushare_json, tushare_md])
    except Exception as exc:
        warnings.append(f"source_fetch_tushare_failed: {exc}")

    try:
        official_json, official_md = fetch_official_text_sources(compact)
        artifacts.extend([official_json, official_md])
    except Exception as exc:
        warnings.append(f"source_fetch_official_failed: {exc}")

    if artifacts and warnings:
        return "partial", artifacts, warnings
    if artifacts:
        return "completed", artifacts, warnings
    return "skipped", artifacts, warnings


def run_assistant_pipeline(
    trade_date: str,
    *,
    include_intake: bool = False,
    include_source_fetch: bool = False,
    include_live_llm: bool = False,
    llm_mode: str = "stable",
    strict_market_date: bool = False,
    live_llm_limit: int | None = None,
) -> tuple[Path, list[tuple[str, str, list[Path]]], list[str]]:
    stage_outputs: list[tuple[str, str, list[Path]]] = []
    warnings: list[str] = []
    requested_trade_date = trade_date
    llm_profile = resolve_llm_runtime_profile(llm_mode)
    source_status = "not_requested"
    source_artifacts: list[Path] = []

    if include_source_fetch:
        source_status, source_artifacts, source_warnings = _run_source_fetch_best_effort(requested_trade_date)
        stage_outputs.append(("source_fetch", source_status, source_artifacts))
        warnings.extend(source_warnings)

    precheck = _build_market_data_precheck(
        requested_trade_date,
        source_fetch_status=source_status,
        source_artifacts=source_artifacts,
        strict_market_date=strict_market_date,
    )
    precheck_json, precheck_md = _write_market_data_precheck(precheck)
    stage_outputs.append(("market_data_precheck", "completed", [precheck_json, precheck_md]))
    warnings.extend(precheck.warnings)
    trade_date = precheck.effective_trade_date

    if include_intake:
        manifest_path = run_daily_intake(run_date=trade_date)
        stage_outputs.append(("daily_intake", "completed", [manifest_path]))

    account_path = _run_account_refresh()
    stage_outputs.append(("account_refresh", "completed", [account_path]))

    market_json, market_md = build_market_regime(trade_date)
    stage_outputs.append(("market_regime", "completed", [market_json, market_md]))

    try:
        event_json, theme_json, macro_json, event_md, theme_md, macro_md = build_event_and_theme_cards(trade_date)
        stage_outputs.append(("event_theme_cards", "completed", [event_json, theme_json, macro_json, event_md, theme_md, macro_md]))
    except FileNotFoundError as exc:
        warnings.append(f"event_theme_cards skipped: {exc}")
        stage_outputs.append(("event_theme_cards", "skipped", []))

    text_watch_json, text_watch_md = build_text_signal_watch_cli(trade_date)
    stage_outputs.append(("text_signal_watch", "completed", [text_watch_json, text_watch_md]))

    try:
        capital_json, capital_md = build_capital_behavior_cards_cli(trade_date)
        stage_outputs.append(("capital_behavior_cards", "completed", [capital_json, capital_md]))
    except FileNotFoundError as exc:
        warnings.append(f"capital_behavior_cards skipped: {exc}")
        stage_outputs.append(("capital_behavior_cards", "skipped", []))

    bundle_json, bundle_md = build_analysis_bundle(trade_date)
    stage_outputs.append(("analysis_bundle", "completed", [bundle_json, bundle_md]))

    try:
        stock_history_sync_json, stock_history_sync_md = sync_stock_history_from_market_daily(
            trade_date.replace("-", ""),
            sync_mode="cache_only",
        )
        stage_outputs.append(("stock_history_sync", "completed", [stock_history_sync_json, stock_history_sync_md]))
    except FileNotFoundError as exc:
        warnings.append(f"stock_history_sync skipped: {exc}")
        stage_outputs.append(("stock_history_sync", "skipped", []))

    candidate_json, candidate_md, module_signal_json, module_signal_md, candidate_warnings = build_candidate_cards_from_bundle(
        trade_date,
        refresh_bundle=False,
    )
    stage_outputs.append(("module_signals", "completed", [module_signal_json, module_signal_md]))
    stage_outputs.append(("candidate_cards", "completed", [candidate_json, candidate_md]))
    warnings.extend(candidate_warnings)

    plan_json, plan_md = build_trade_plan_cards_cli(trade_date)
    stage_outputs.append(("trade_plan_cards", "completed", [plan_json, plan_md]))

    try:
        module_eval_json, module_eval_md = build_module_evaluation_cli(trade_date)
        stage_outputs.append(("module_evaluation", "completed", [module_eval_json, module_eval_md]))
    except FileNotFoundError as exc:
        warnings.append(f"module_evaluation skipped: {exc}")
        stage_outputs.append(("module_evaluation", "skipped", []))

    try:
        setup_eval_json, setup_eval_md = build_setup_performance_cli(trade_date)
        stage_outputs.append(("setup_performance", "completed", [setup_eval_json, setup_eval_md]))
    except FileNotFoundError as exc:
        warnings.append(f"setup_performance skipped: {exc}")
        stage_outputs.append(("setup_performance", "skipped", []))

    memory_json, memory_md = build_review_memory_cli()
    stage_outputs.append(("review_memory", "completed", [memory_json, memory_md]))

    holdings_path = refresh_holdings_snapshot()
    stage_outputs.append(("holdings_refresh", "completed", [holdings_path]))

    preopen_json, preopen_md = build_preopen_summary(trade_date)
    stage_outputs.append(("preopen_summary_baseline", "completed", [preopen_json, preopen_md]))

    trade_exec_json, trade_exec_md = build_trade_execution_sheet(trade_date)
    stage_outputs.append(("trade_execution_sheet_baseline", "completed", [trade_exec_json, trade_exec_md]))

    llm_workpack_json, llm_workpack_md = build_llm_workpacks_cli(trade_date, mode=llm_profile.mode)
    stage_outputs.append(("llm_workpacks", "completed", [llm_workpack_json, llm_workpack_md]))

    llm_execution_json, llm_execution_md = plan_llm_execution(trade_date, mode=llm_profile.mode)
    stage_outputs.append(("llm_execution_plan", "completed", [llm_execution_json, llm_execution_md]))

    if llm_profile.execute_runtime:
        llm_runtime_json, llm_runtime_md, llm_runtime_records = execute_llm_runtime(
            trade_date,
            mode=llm_profile.mode,
            limit=live_llm_limit,
            include_remote_providers=include_live_llm,
        )
        stage_outputs.append(("llm_runtime", "completed", [Path(llm_runtime_json), Path(llm_runtime_md)]))
        if _has_enabled_remote_llm_provider() and not include_live_llm:
            warnings.append("remote_llm_runtime_skipped: local providers executed, but remote providers require --with-live-llm")

        runtime_completed = any(record.status == "completed" for record in llm_runtime_records)
        if runtime_completed:
            runtime_result_paths = sorted(
                {
                    Path(path)
                    for record in llm_runtime_records
                    if record.status == "completed"
                    for path in record.artifact_paths
                }
            )
            try:
                llm_enrichment_json, llm_enrichment_md = apply_llm_enrichments(
                    trade_date,
                    source_paths=runtime_result_paths or None,
                )
                stage_outputs.append(("llm_enrichment_apply", "completed", [llm_enrichment_json, llm_enrichment_md]))
            except FileNotFoundError as exc:
                warnings.append(f"llm_enrichment_apply skipped: {exc}")
                stage_outputs.append(("llm_enrichment_apply", "skipped", []))
        else:
            warnings.append("llm_enrichment_apply skipped: no completed runtime enrichments")
            stage_outputs.append(("llm_enrichment_apply", "skipped", []))
    else:
        warnings.append(f"llm_runtime skipped: llm_mode={llm_profile.mode}")
        stage_outputs.append(("llm_runtime", "skipped", []))
        warnings.append(f"llm_enrichment_apply skipped: llm_mode={llm_profile.mode}")
        stage_outputs.append(("llm_enrichment_apply", "skipped", []))

    preopen_json, preopen_md = build_preopen_summary(trade_date)
    stage_outputs.append(("preopen_summary", "completed", [preopen_json, preopen_md]))

    trade_exec_json, trade_exec_md = build_trade_execution_sheet(trade_date)
    stage_outputs.append(("trade_execution_sheet", "completed", [trade_exec_json, trade_exec_md]))

    auto_holdings_json, system_trade_log_json, holdings_snapshot_json = sync_trade_execution_to_live_state(
        trade_date,
        trade_execution_path=trade_exec_json,
    )
    stage_outputs.append(
        (
            "live_trade_state_sync",
            "completed",
            [auto_holdings_json, system_trade_log_json, holdings_snapshot_json],
        )
    )

    execution_feedback_json, execution_feedback_md = build_execution_feedback_cli(trade_date)
    stage_outputs.append(("execution_feedback", "completed", [execution_feedback_json, execution_feedback_md]))

    execution_behavior_json, execution_behavior_md = build_execution_behavior_cli(trade_date)
    stage_outputs.append(("execution_behavior", "completed", [execution_behavior_json, execution_behavior_md]))

    report_path = _daily_report_dir() / f"assistant_pipeline_run_{trade_date}.md"
    report_path.write_text(
        render_pipeline_run_report(
            trade_date=trade_date,
            stage_outputs=stage_outputs,
            warnings=warnings,
        ),
        encoding="utf-8",
    )
    return report_path, stage_outputs, warnings


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat(), help="Trade date in YYYY-MM-DD format.")
    parser.add_argument("--with-source-fetch", action="store_true", help="Fetch current Tushare-backed sources before the pipeline.")
    parser.add_argument("--with-intake", action="store_true", help="Run daily intake before the assistant pipeline.")
    parser.add_argument("--strict-market-date", action="store_true", help="Fail if fresh market daily data cannot be refreshed to the latest open session.")
    parser.add_argument("--with-live-llm", action="store_true", help="Allow the pipeline to call enabled remote LLM providers.")
    parser.add_argument("--llm-mode", choices=supported_llm_modes(), default="stable", help="LLM execution mode for the assistant pipeline.")
    parser.add_argument("--llm-limit", type=int, default=None, help="Optional limit for live LLM workpacks during pipeline execution.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    report_path, stage_outputs, warnings = run_assistant_pipeline(
        args.date,
        include_intake=args.with_intake,
        include_source_fetch=args.with_source_fetch,
        include_live_llm=args.with_live_llm,
        llm_mode=args.llm_mode,
        strict_market_date=args.strict_market_date,
        live_llm_limit=args.llm_limit,
    )
    print(f"assistant_pipeline_report={report_path}")
    print(f"assistant_pipeline_stage_count={len(stage_outputs)}")
    print(f"assistant_pipeline_warning_count={len(warnings)}")


if __name__ == "__main__":
    main()
