from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_system.cli.daily_intake import run_daily_intake


class DailyIntakeTest(unittest.TestCase):
    def test_manifest_written_and_file_copied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            inbox_dir = tmp_root / "input" / "market_equity_daily"
            inbox_dir.mkdir(parents=True, exist_ok=True)
            sample_file = inbox_dir / "bars.csv"
            sample_file.write_text("stock_code,trade_date,close\n000001.SZ,2026-01-01,10.0\n", encoding="utf-8")

            endpoints_path = tmp_root / "source_endpoints.json"
            endpoints_path.write_text(
                json.dumps(
                    {
                        "version": "0.1.0",
                        "sources": [
                            {
                                "id": "market_equity_daily",
                                "connector_kind": "file_drop",
                                "enabled": True,
                                "required": True,
                                "input_path": str(inbox_dir),
                                "file_patterns": ["*.csv"],
                                "notes": ""
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            plan_path = tmp_root / "daily_plan.json"
            plan_path.write_text(
                json.dumps(
                    {
                        "version": "0.1.0",
                        "run_name": "test_run",
                        "copy_inputs_to_snapshot": True,
                        "required_source_ids": ["market_equity_daily"],
                        "optional_source_ids": []
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            manifest_path = run_daily_intake(
                run_date="2026-01-01",
                endpoints_config_path=endpoints_path,
                plan_config_path=plan_path,
            )

            self.assertTrue(manifest_path.exists())
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["run_name"], "test_run")
            self.assertEqual(len(payload["entries"]), 1)
            self.assertEqual(payload["entries"][0]["status"], "ready")
            self.assertEqual(payload["entries"][0]["file_count"], 1)
            copied_files = payload["entries"][0]["copied_files"]
            self.assertEqual(len(copied_files), 1)
            self.assertTrue(Path(copied_files[0]).exists())
            status_md_path = manifest_path.parent / "intake_status.md"
            self.assertTrue(status_md_path.exists())


if __name__ == "__main__":
    unittest.main()
