from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import trading_system.integrations.domestic_news_sources as domestic_mod
import trading_system.integrations.official_web_sources as official_mod


class DomesticNewsSourcesTest(unittest.TestCase):
    def test_parse_cls_mobile_telegraph(self) -> None:
        html = """
        <div class="telegraph-list">
          <div class="telegraph-item">
            <div class="time">14:35</div>
            <div class="content">【中美会谈】财联社5月17日电，中美会谈取得阶段性进展，消费电子出口链受关注。</div>
          </div>
        </div>
        """
        spec = domestic_mod.DomesticNewsSourceSpec(
            id="cls_telegraph",
            parser_kind="cls_mobile_telegraph",
            url="https://m.cls.cn/telegraph",
            source_name="财联社",
        )
        records = domestic_mod._parse_records(html, trade_date="20260517", spec=spec)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["title"], "中美会谈")
        self.assertIn("consumer_electronics", records[0]["related_industries"])
        self.assertEqual(records[0]["publish_time"], "2026-05-17 14:35:00")

    def test_build_eastmoney_record(self) -> None:
        spec = domestic_mod.DomesticNewsSourceSpec(
            id="eastmoney_fastnews",
            parser_kind="eastmoney_fastnews",
            url="https://kuaixun.eastmoney.com/7_24.html",
            source_name="东方财富",
            options={"fast_column": "102"},
        )
        record = domestic_mod._build_eastmoney_record(
            {
                "title": "半导体产业链景气度回升：多家企业扩产",
                "summary": "机构称设备与存储环节弹性更高。",
                "showTime": "2026-05-17 09:12:30",
                "stockList": ["1.688008", "0.300308", "90.BK1036"],
            },
            trade_date="20260517",
            spec=spec,
        )
        self.assertIsNotNone(record)
        assert record is not None
        self.assertIn("semiconductor", record["related_industries"])
        self.assertEqual(record["stock_code"], "688008.SH")
        self.assertEqual(record["related_stocks"], ["688008.SH", "300308.SZ"])
        self.assertEqual(record["publish_time"], "2026-05-17 09:12:30")

    def test_fetch_eastmoney_fastnews_uses_json_endpoint(self) -> None:
        spec = domestic_mod.DomesticNewsSourceSpec(
            id="eastmoney_fastnews",
            parser_kind="eastmoney_fastnews",
            url="https://kuaixun.eastmoney.com/7_24.html",
            source_name="东方财富",
            options={"page_size": 5},
        )
        with patch.object(
            domestic_mod,
            "_fetch_text",
            return_value='<script>var columns = "102";</script>',
        ), patch.object(
            domestic_mod,
            "_fetch_json",
            return_value={
                "data": {
                    "fastNewsList": [
                        {
                            "title": "机器人景气回暖",
                            "summary": "工业自动化链条活跃。",
                            "showTime": "2026-05-17 10:08:00",
                            "stockList": ["0.300024"],
                        }
                    ]
                }
            },
        ) as fetch_json_mock:
            records = domestic_mod._fetch_eastmoney_fastnews(spec, "20260517")

        self.assertEqual(len(records), 1)
        self.assertIn("robotics", records[0]["related_industries"])
        self.assertEqual(records[0]["stock_code"], "300024.SZ")
        self.assertEqual(fetch_json_mock.call_args.kwargs["params"]["fastColumn"], "102")

    def test_fetch_official_sources_merges_domestic_news_into_financial_wire(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inbox = Path(tmp_dir) / "inbox"
            inbox.mkdir(parents=True, exist_ok=True)
            with patch.object(official_mod, "INBOX_DIR", inbox), patch.object(
                official_mod,
                "load_official_web_source_specs",
                return_value=[],
            ), patch.object(
                official_mod,
                "fetch_domestic_news_source_records",
                return_value=(
                    {
                        "cls_telegraph": [
                            {
                                "source_id": "cls_telegraph",
                                "title": "中美会谈取得阶段性进展",
                                "publish_time": "2026-05-17 14:35:00",
                                "source_url": "https://m.cls.cn/telegraph",
                                "source_name": "财联社",
                                "summary_text": "消费电子出口链受关注",
                                "content_text": "消费电子出口链受关注",
                                "related_industries": ["consumer_electronics"],
                                "related_stocks": [],
                                "stock_code": "",
                                "priority_score": 8,
                            }
                        ]
                    },
                    [],
                ),
            ):
                artifacts, warnings = official_mod.fetch_official_web_sources("20260517")

            self.assertFalse(warnings)
            artifact_ids = {artifact.source_id for artifact in artifacts}
            self.assertIn("cls_telegraph", artifact_ids)
            financial_path = inbox / "financial_news_wire" / "financial_news_wire_20260517.json"
            self.assertTrue(financial_path.exists())
            payload = financial_path.read_text(encoding="utf-8")
            self.assertIn("中美会谈取得阶段性进展", payload)


if __name__ == "__main__":
    unittest.main()
