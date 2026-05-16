from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from trading_system.cli.build_llm_workpacks import build_llm_workpacks
from trading_system.config.paths import OUTPUTS_DIR
from trading_system.integrations.llm_provider_registry import load_llm_provider_registry, resolve_llm_execution_routes
from trading_system.reporting.llm_execution_reports import render_llm_execution_plan_markdown


def llm_execution_output_dir() -> Path:
    directory = OUTPUTS_DIR / "llm_execution"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def plan_llm_execution(trade_date: str) -> tuple[Path, Path]:
    packets = build_llm_workpacks(trade_date)
    providers = load_llm_provider_registry()
    routes = resolve_llm_execution_routes(packets, providers)
    output_dir = llm_execution_output_dir()
    json_path = output_dir / f"llm_execution_plan_{trade_date}.json"
    md_path = json_path.with_suffix(".md")
    json_path.write_text(json.dumps([asdict(route) for route in routes], ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_llm_execution_plan_markdown(trade_date, routes), encoding="utf-8")
    return json_path, md_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Trade date in YYYY-MM-DD format.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    json_path, md_path = plan_llm_execution(args.date)
    print(f"llm_execution_plan_json={json_path}")
    print(f"llm_execution_plan_md={md_path}")


if __name__ == "__main__":
    main()
