from __future__ import annotations

import argparse

from trading_system.cli.build_llm_workpacks import build_llm_workpacks
from trading_system.integrations.llm_profiles import resolve_llm_runtime_profile, supported_llm_modes
from trading_system.integrations.llm_provider_registry import LLMExecutionRoute, load_llm_provider_registry, resolve_llm_execution_routes
from trading_system.integrations.llm_runtime import LLMRuntimeRecord, execute_llm_runtime_with_inputs
from trading_system.reporting.llm_runtime_reports import render_llm_runtime_markdown


def _apply_route_limit(
    routes: list[LLMExecutionRoute],
    *,
    limit: int | None,
    include_remote_providers: bool,
) -> list[LLMExecutionRoute]:
    if limit is None or limit < 0:
        return routes

    if not include_remote_providers:
        counts: dict[str, int] = {}
        limited_routes: list[LLMExecutionRoute] = []
        for route in routes:
            provider_count = counts.get(route.provider_id, 0)
            if provider_count >= limit:
                continue
            counts[route.provider_id] = provider_count + 1
            limited_routes.append(route)
        return limited_routes

    counts: dict[str, int] = {}
    limited_routes: list[LLMExecutionRoute] = []
    for route in routes:
        provider_count = counts.get(route.provider_id, 0)
        if provider_count >= limit:
            continue
        counts[route.provider_id] = provider_count + 1
        limited_routes.append(route)
    return limited_routes


def execute_llm_runtime(
    trade_date: str,
    *,
    mode: str = "full",
    limit: int | None = None,
    include_remote_providers: bool = False,
) -> tuple[str, str, list[LLMRuntimeRecord]]:
    profile = resolve_llm_runtime_profile(mode)
    packets = build_llm_workpacks(trade_date, mode=mode)
    if not profile.execute_runtime:
        json_path, md_path, records = execute_llm_runtime_with_inputs(trade_date, packets, [])
        md_path.write_text(render_llm_runtime_markdown(trade_date, records), encoding="utf-8")
        return str(json_path), str(md_path), records
    providers = load_llm_provider_registry()
    if not include_remote_providers:
        providers = [provider for provider in providers if provider.provider_type != "openai_compatible"]
    routes = resolve_llm_execution_routes(packets, providers)
    effective_limit = limit if limit is not None else profile.default_route_limit_per_provider
    routes = _apply_route_limit(routes, limit=effective_limit, include_remote_providers=include_remote_providers)
    json_path, md_path, records = execute_llm_runtime_with_inputs(
        trade_date,
        packets,
        routes,
        allowed_provider_ids={provider.provider_id for provider in providers},
    )
    md_path.write_text(render_llm_runtime_markdown(trade_date, records), encoding="utf-8")
    return str(json_path), str(md_path), records


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Trade date in YYYY-MM-DD format.")
    parser.add_argument("--mode", choices=supported_llm_modes(), default="full", help="LLM runtime execution mode.")
    parser.add_argument("--limit", type=int, default=None, help="Optional max number of workpack routes to execute.")
    parser.add_argument("--with-remote", action="store_true", help="Include remote providers such as Kimi/OpenAI-compatible routes.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    json_path, md_path, _ = execute_llm_runtime(
        args.date,
        mode=args.mode,
        limit=args.limit,
        include_remote_providers=args.with_remote,
    )
    print(f"llm_runtime_json={json_path}")
    print(f"llm_runtime_md={md_path}")


if __name__ == "__main__":
    main()
