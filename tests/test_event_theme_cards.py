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

from trading_system.context.event_cards import (
    build_event_cards_from_structured_announcements,
    build_theme_cards_from_policy_inputs,
)


class EventThemeCardTest(unittest.TestCase):
    def test_build_event_cards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "announcements.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "stock_code": "000001.SZ",
                            "filing_type": "earnings preannouncement",
                            "title": "AI server earnings beat announcement",
                            "summary_text": "The company benefits from AI server demand and data center expansion.",
                            "publish_time": "2026-05-06 20:00:00",
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            cards = build_event_cards_from_structured_announcements("2026-05-06", path)
            self.assertEqual(len(cards), 1)
            self.assertEqual(cards[0].bullish_bearish, "bullish")
            self.assertIn("ai", cards[0].industry_tags)
            self.assertIn("post_close_release", cards[0].risk_flags)

    def test_build_theme_cards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "policy.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "title": "Commercial aerospace innovation action plan",
                            "policy_level": "ministry",
                            "issuing_body": "Ministry of Industry",
                            "publish_time": "2026-05-06 18:00:00",
                            "summary_text": "Support satellite manufacturing, launch services and related AI control systems.",
                            "priority_stocks": ["300001.SZ", "688001.SH"],
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            cards = build_theme_cards_from_policy_inputs("2026-05-06", path)
            self.assertEqual(len(cards), 1)
            self.assertEqual(cards[0].trigger_type, "policy:ministry")
            self.assertIn("commercial_aerospace", cards[0].priority_industries)
            self.assertIn("300001.SZ", cards[0].priority_stocks)
            self.assertNotEqual(cards[0].continuation_guess, "needs_review")


if __name__ == "__main__":
    unittest.main()
