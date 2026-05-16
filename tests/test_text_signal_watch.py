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

import trading_system.reporting.text_signal_watch as watch_mod


class TextSignalWatchTest(unittest.TestCase):
    def setUp(self) -> None:
        self.original_inbox_dir = watch_mod.INBOX_DIR
        self.original_outputs_dir = watch_mod.OUTPUTS_DIR

    def tearDown(self) -> None:
        watch_mod.INBOX_DIR = self.original_inbox_dir
        watch_mod.OUTPUTS_DIR = self.original_outputs_dir

    def test_build_text_signal_watch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            inbox = root / "inbox"
            outputs = root / "outputs"
            for source_id in ("exchange_filings", "policy_primary_documents", "financial_news_wire", "industry_catalyst_calendar"):
                (inbox / source_id).mkdir(parents=True, exist_ok=True)
            outputs.mkdir(parents=True, exist_ok=True)

            (inbox / "exchange_filings" / "exchange_filings_20260506.json").write_text(
                json.dumps(
                    [
                        {
                            "stock_code": "000625.SZ",
                            "title": "关于股份回购进展公告",
                            "publish_time": "2026-05-06",
                            "source_url": "https://example.com/1",
                            "summary_text": "回购进展",
                            "priority_score": 5,
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (inbox / "financial_news_wire" / "financial_news_wire_20260506.json").write_text(
                json.dumps(
                    [
                        {
                            "title": "深交所推出优化再融资一揽子措施",
                            "publish_time": "2026-05-06",
                            "source_url": "https://example.com/2",
                            "content_text": "优化再融资一揽子措施",
                            "related_industries": [],
                            "priority_score": 4,
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (inbox / "policy_primary_documents" / "policy_primary_documents_20260506.json").write_text(
                json.dumps([], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (inbox / "industry_catalyst_calendar" / "industry_catalyst_calendar_20260506.json").write_text(
                json.dumps([], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            watch_mod.INBOX_DIR = inbox
            watch_mod.OUTPUTS_DIR = outputs
            json_path, md_path = watch_mod.build_text_signal_watch("2026-05-06")
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload[0]["source_id"], "exchange_filings")
            self.assertGreater(payload[0]["priority_score"], payload[1]["priority_score"])


if __name__ == "__main__":
    unittest.main()
