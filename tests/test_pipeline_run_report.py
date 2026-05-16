from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_system.reporting.pipeline_run_report import render_pipeline_run_report


class PipelineRunReportTest(unittest.TestCase):
    def test_render_pipeline_run_report(self) -> None:
        report = render_pipeline_run_report(
            "2026-05-06",
            stage_outputs=[
                ("account_refresh", "completed", [Path("data/processed/account/active_account_constraints.json")]),
                ("event_theme_cards", "skipped", []),
            ],
            warnings=["event_theme_cards skipped: missing input"],
        )
        self.assertIn("Assistant Pipeline Run - 2026-05-06", report)
        self.assertIn("account_refresh", report)
        self.assertIn("event_theme_cards skipped: missing input", report)


if __name__ == "__main__":
    unittest.main()
