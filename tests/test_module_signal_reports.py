from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_system.reporting.module_signal_reports import render_module_signals_markdown
from trading_system.signal.scanners.base import ModuleSignal


class ModuleSignalReportsTest(unittest.TestCase):
    def test_render_module_signals_markdown(self) -> None:
        markdown = render_module_signals_markdown(
            "2026-05-06",
            [
                ModuleSignal(
                    module_id="TM002_breakout_and_relative_strength",
                    stock_code="000001.SZ",
                    trade_date="2026-05-06",
                    signal_type="strong",
                    strength=0.8,
                    technical_state="rel_strength_outperform",
                    confidence=0.9,
                    invalidation_hint="fade",
                    source_refs=["rel_strength_core"],
                )
            ],
        )
        self.assertIn("Module Signals - 2026-05-06", markdown)
        self.assertIn("TM002_breakout_and_relative_strength", markdown)
        self.assertIn("000001.SZ", markdown)


if __name__ == "__main__":
    unittest.main()
