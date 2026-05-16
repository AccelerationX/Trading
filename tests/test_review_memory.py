from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_system.memory.review_memory import build_review_memory_entries
from trading_system.reporting.memory_reports import render_review_memory_markdown


class ReviewMemoryTest(unittest.TestCase):
    def test_build_review_memory_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            review_path = Path(tmp_dir) / "review_1.md"
            review_path.write_text(
                "\n".join(
                    [
                        "# Trade Review",
                        "",
                        "- Trade date: 2026-05-06",
                        "- Stock: 300001.SZ",
                        "- Action: buy",
                        "- Position size: 20%",
                        "- Why I executed: Event-driven breakout after policy support.",
                        "- Why I ignored any system suggestion: none",
                        "- What happened afterward: The trade worked and expanded with theme confirmation.",
                        "- What I learned: Only push size after the first pullback confirms.",
                    ]
                ),
                encoding="utf-8",
            )
            entries = build_review_memory_entries(Path(tmp_dir))
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].outcome_tag, "positive")
            self.assertIn("event_driven", entries[0].setup_tags)
            self.assertIn("Only push size", entries[0].actionable_rule)

    def test_render_review_memory_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            review_path = Path(tmp_dir) / "review_1.md"
            review_path.write_text(
                "\n".join(
                    [
                        "# Trade Review",
                        "",
                        "- Trade date: 2026-05-06",
                        "- Stock: 300001.SZ",
                        "- Action: buy",
                        "- Why I executed: Trend breakout.",
                        "- What happened afterward: Failed and hit stop.",
                        "- What I learned: Respect the weak breadth signal.",
                    ]
                ),
                encoding="utf-8",
            )
            entries = build_review_memory_entries(Path(tmp_dir))
            markdown = render_review_memory_markdown(entries)
            self.assertIn("Review Memory Entries", markdown)
            self.assertIn("300001.SZ", markdown)


if __name__ == "__main__":
    unittest.main()
