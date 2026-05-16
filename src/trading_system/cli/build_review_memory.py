from __future__ import annotations

import argparse
from pathlib import Path

from trading_system.config.paths import OUTPUTS_DIR
from trading_system.memory.review_memory import build_review_memory_entries, save_review_memory_entries
from trading_system.reporting.memory_reports import render_review_memory_markdown


def _daily_report_dir() -> Path:
    directory = OUTPUTS_DIR / "daily_reports"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def build_review_memory_cli() -> tuple[Path, Path]:
    entries = build_review_memory_entries()
    json_path = save_review_memory_entries(entries)
    md_path = _daily_report_dir() / "review_memory_entries.md"
    md_path.write_text(render_review_memory_markdown(entries), encoding="utf-8")
    return json_path, md_path


def build_arg_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser()


def main() -> None:
    parser = build_arg_parser()
    parser.parse_args()
    json_path, md_path = build_review_memory_cli()
    print(f"review_memory_json={json_path}")
    print(f"review_memory_md={md_path}")


if __name__ == "__main__":
    main()
