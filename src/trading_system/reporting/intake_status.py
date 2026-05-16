from __future__ import annotations

from trading_system.ingest.manifest import DailyIntakeManifest


def render_intake_status_markdown(manifest: DailyIntakeManifest) -> str:
    required_missing = [
        entry for entry in manifest.entries if entry.required and entry.status != "ready"
    ]
    optional_ready = [
        entry for entry in manifest.entries if (not entry.required) and entry.status == "ready"
    ]

    lines = [
        f"# Daily Intake Status - {manifest.run_date}",
        "",
        "## Summary",
        f"- run_name: `{manifest.run_name}`",
        f"- snapshot_dir: `{manifest.snapshot_dir}`",
        f"- required_source_count: `{len(manifest.required_sources)}`",
        f"- optional_source_count: `{len(manifest.optional_sources)}`",
        f"- required_not_ready: `{len(required_missing)}`",
        f"- optional_ready: `{len(optional_ready)}`",
        "",
        "## Required Sources",
    ]

    required_entries = [entry for entry in manifest.entries if entry.required]
    if not required_entries:
        lines.append("- none")
    else:
        for entry in required_entries:
            lines.append(
                f"- {entry.source_id}: status `{entry.status}`, files `{entry.file_count}`, path `{entry.input_path}`"
            )

    lines.extend(["", "## Optional Sources"])
    optional_entries = [entry for entry in manifest.entries if not entry.required]
    if not optional_entries:
        lines.append("- none")
    else:
        for entry in optional_entries:
            lines.append(
                f"- {entry.source_id}: status `{entry.status}`, files `{entry.file_count}`, path `{entry.input_path}`"
            )

    lines.extend(["", "## Notes"])
    any_notes = False
    for entry in manifest.entries:
        if not entry.notes:
            continue
        any_notes = True
        lines.append(f"- {entry.source_id}: {'; '.join(entry.notes)}")
    if not any_notes:
        lines.append("- none")

    return "\n".join(lines) + "\n"
