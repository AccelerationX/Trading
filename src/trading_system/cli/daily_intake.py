from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from trading_system.config.paths import CONFIGS_DIR
from trading_system.config.source_inputs import DailyIntakePlan, SourceEndpointConfig, load_daily_intake_plan, load_source_endpoints
from trading_system.ingest.connectors import run_connector
from trading_system.ingest.manifest import DailyIntakeManifest, SourceManifestEntry, write_manifest
from trading_system.ingest.snapshot_store import get_snapshot_dir
from trading_system.reporting.intake_status import render_intake_status_markdown


def _select_sources(endpoints: list[SourceEndpointConfig], plan: DailyIntakePlan) -> list[SourceEndpointConfig]:
    allowed_ids = set(plan.required_source_ids) | set(plan.optional_source_ids)
    selected = [endpoint for endpoint in endpoints if endpoint.id in allowed_ids]
    selected.sort(key=lambda item: (item.id not in plan.required_source_ids, item.id))
    return selected


def run_daily_intake(
    run_date: str,
    endpoints_config_path: Path | None = None,
    plan_config_path: Path | None = None,
) -> Path:
    endpoints = load_source_endpoints(endpoints_config_path)
    plan = load_daily_intake_plan(plan_config_path)
    selected_sources = _select_sources(endpoints, plan)

    snapshot_dir = get_snapshot_dir(run_date)
    manifest = DailyIntakeManifest(
        run_name=plan.run_name,
        run_date=run_date,
        snapshot_dir=str(snapshot_dir),
        required_sources=list(plan.required_source_ids),
        optional_sources=list(plan.optional_source_ids),
    )

    for source in selected_sources:
        result = run_connector(source, run_date=run_date, copy_to_snapshot=plan.copy_inputs_to_snapshot)
        manifest.entries.append(
            SourceManifestEntry(
                source_id=source.id,
                connector_kind=source.connector_kind,
                status=result.status,
                required=source.required or source.id in plan.required_source_ids,
                input_path=str(source.input_path),
                discovered_files=[str(path) for path in result.discovered_files],
                copied_files=[str(path) for path in result.copied_files],
                file_count=len(result.discovered_files),
                notes=result.notes,
            )
        )

    manifest_path = snapshot_dir / "manifest.json"
    write_manifest(manifest, manifest_path)
    status_md_path = snapshot_dir / "intake_status.md"
    status_md_path.write_text(render_intake_status_markdown(manifest), encoding="utf-8")
    return manifest_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat(), help="Run date in YYYY-MM-DD format.")
    parser.add_argument(
        "--endpoints-config",
        default=str(CONFIGS_DIR / "source_endpoints.template.json"),
        help="Path to source endpoints config JSON.",
    )
    parser.add_argument(
        "--plan-config",
        default=str(CONFIGS_DIR / "daily_intake.template.json"),
        help="Path to daily intake plan JSON.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    manifest_path = run_daily_intake(
        run_date=args.date,
        endpoints_config_path=Path(args.endpoints_config),
        plan_config_path=Path(args.plan_config),
    )
    print(f"daily_intake_manifest={manifest_path}")


if __name__ == "__main__":
    main()
