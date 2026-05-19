from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_system.context.event_cards import (
    build_event_cards_from_structured_announcements,
    build_theme_cards_from_policy_inputs,
)
from trading_system.context.macro_event_cards import build_macro_event_cards


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

    def test_build_macro_event_cards_classifies_cross_border_diplomacy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inbox = Path(tmp_dir)
            for folder in ("policy_primary_documents", "financial_news_wire", "industry_catalyst_calendar"):
                (inbox / folder).mkdir(parents=True, exist_ok=True)
                (inbox / folder / f"{folder}_20260506.json").write_text("[]", encoding="utf-8")
            (inbox / "financial_news_wire" / "financial_news_wire_20260506.json").write_text(
                json.dumps(
                    [
                        {
                            "title": "特朗普访华前瞻：中美经贸磋商有望取得阶段性进展",
                            "publish_time": "2026-05-06 08:30:00",
                            "source_name": "财联社",
                            "summary_text": "此次会谈可能改善出口链和消费电子预期。",
                            "priority_score": 8,
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            with patch("trading_system.context.macro_event_cards.INBOX_DIR", inbox):
                cards = build_macro_event_cards("2026-05-06")
            self.assertEqual(len(cards), 1)
            self.assertEqual(cards[0].event_type, "cross_border_diplomacy")
            self.assertEqual(cards[0].bias, "bullish")
            self.assertIn("consumer_electronics", cards[0].beneficiary_industries)

    def test_build_macro_event_cards_does_not_misclassify_company_chip_story(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inbox = Path(tmp_dir)
            for folder in ("policy_primary_documents", "financial_news_wire", "industry_catalyst_calendar"):
                (inbox / folder).mkdir(parents=True, exist_ok=True)
                (inbox / folder / f"{folder}_20260506.json").write_text("[]", encoding="utf-8")
            (inbox / "financial_news_wire" / "financial_news_wire_20260506.json").write_text(
                json.dumps(
                    [
                        {
                            "title": "“中国刻蚀机之父”称国内设备能力继续提升",
                            "publish_time": "2026-05-06 09:15:00",
                            "source_name": "东方财富",
                            "summary_text": "半导体设备和公司产业链持续受关注。",
                            "priority_score": 6,
                            "related_industries": ["semiconductor"],
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            with patch("trading_system.context.macro_event_cards.INBOX_DIR", inbox):
                cards = build_macro_event_cards("2026-05-06")
            self.assertEqual(cards, [])

    def test_build_macro_event_cards_classifies_geopolitical_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inbox = Path(tmp_dir)
            for folder in ("policy_primary_documents", "financial_news_wire", "industry_catalyst_calendar"):
                (inbox / folder).mkdir(parents=True, exist_ok=True)
                (inbox / folder / f"{folder}_20260506.json").write_text("[]", encoding="utf-8")
            (inbox / "financial_news_wire" / "financial_news_wire_20260506.json").write_text(
                json.dumps(
                    [
                        {
                            "title": "伊朗军方：若美国再次发起军事行动将面临进攻性回应",
                            "publish_time": "2026-05-06 18:24:07",
                            "source_name": "东方财富",
                            "summary_text": "中东局势升级风险推升油价与避险情绪。",
                            "priority_score": 7,
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            with patch("trading_system.context.macro_event_cards.INBOX_DIR", inbox):
                cards = build_macro_event_cards("2026-05-06")
            self.assertEqual(len(cards), 1)
            self.assertEqual(cards[0].event_type, "geopolitical_conflict")
            self.assertEqual(cards[0].bias, "bearish")


if __name__ == "__main__":
    unittest.main()
