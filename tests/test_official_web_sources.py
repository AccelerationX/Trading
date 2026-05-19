from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_system.integrations.official_web_sources import (
    OfficialWebSourceSpec,
    _dedupe_news_records,
    _parse_cninfo_latest_announcements,
    _parse_miit_rrs_section,
    _parse_ndrc_notice_list,
    _parse_rss_xml,
    _parse_sse_hot_topics,
    _parse_szse_exchange_news,
)


class OfficialWebSourcesTest(unittest.TestCase):
    def test_parse_ndrc_notice_list(self) -> None:
        html = """
        <html><body>
        <ul>
          <li><a href="/xwdt/tzgg/202604/t20260430_123.html">关于推动低空经济发展的通知</a>2026/04/30</li>
        </ul>
        </body></html>
        """
        spec = OfficialWebSourceSpec(
            id="ndrc_notice_policy",
            category="policy_primary_documents",
            parser_kind="ndrc_notice_list",
            url="https://www.ndrc.gov.cn/xwdt/tzgg/",
            issuing_body="国家发展改革委",
            policy_level="ministry",
        )
        records = _parse_ndrc_notice_list(html, spec)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["issuing_body"], "国家发展改革委")

    def test_parse_miit_section(self) -> None:
        html = """
        <html><body>
        文件发布
        工业和信息化部关于人工智能产业发展的通知 04-28
        中华人民共和国工业和信息化部公告2026年第9号 04-20
        互动交流
        </body></html>
        """
        spec = OfficialWebSourceSpec(
            id="miit_file_release",
            category="policy_primary_documents",
            parser_kind="miit_rrs_section",
            url="https://www.miit.gov.cn/RRSdy/",
            issuing_body="工业和信息化部",
            policy_level="ministry",
            section_name="文件发布",
        )
        records = _parse_miit_rrs_section(html, spec)
        self.assertGreaterEqual(len(records), 1)
        self.assertEqual(records[0]["policy_level"], "ministry")

    def test_parse_rss_xml(self) -> None:
        xml = """
        <rss><channel>
          <item>
            <title>2026年4月软件业运行情况</title>
            <link>https://www.stats.gov.cn/item1</link>
            <pubDate>Wed, 30 Apr 2026 00:00:00 GMT</pubDate>
          </item>
        </channel></rss>
        """
        spec = OfficialWebSourceSpec(
            id="stats_latest_release",
            category="industry_catalyst_calendar",
            parser_kind="rss_xml",
            url="https://www.stats.gov.cn/sj/zxfb/rss.xml",
            issuing_body="国家统计局",
            policy_level="national",
        )
        records = _parse_rss_xml(xml, spec)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["source_name"], "国家统计局")

    def test_parse_cninfo_latest_announcements(self) -> None:
        html = """
        <table>
          <tr><th>代码</th><th>简称</th><th>公告标题</th><th>日期</th></tr>
          <tr>
            <td>000625</td><td>长安汽车</td>
            <td><a href="/new/disclosure/detail">关于以集中竞价交易方式回购公司股份的进展公告</a></td>
            <td>05-06</td>
          </tr>
        </table>
        """
        spec = OfficialWebSourceSpec(
            id="cninfo_latest_announcements",
            category="exchange_filings",
            parser_kind="cninfo_latest_announcements",
            url="https://www.cninfo.com.cn/?lang=zh",
            issuing_body="巨潮资讯",
            policy_level="official_platform",
        )
        records = _parse_cninfo_latest_announcements(html, spec)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["stock_code"], "000625.SZ")
        self.assertGreater(records[0]["priority_score"], 0)

    def test_parse_sse_hot_topics(self) -> None:
        html = """
        <html><body>
        热点动态
        上海证券交易所推出优化再融资一揽子措施
        2026-02-09
        上交所新增发布三项可持续发展报告编制应用指引
        2026-01-30
        各栏更新
        </body></html>
        """
        spec = OfficialWebSourceSpec(
            id="sse_hot_topics",
            category="financial_news_wire",
            parser_kind="sse_hot_topics",
            url="https://www.sse.com.cn/",
            issuing_body="上海证券交易所",
            policy_level="exchange",
        )
        records = _parse_sse_hot_topics(html, spec)
        self.assertEqual(len(records), 2)
        self.assertIn("再融资", records[0]["title"])

    def test_parse_szse_exchange_news(self) -> None:
        html = """
        <html><body>
        深交所要闻
        ### 深圳证券交易所推出优化再融资一揽子措施
        ### 关于*ST立方股票交易的风险提示
        更多
        深交所公告
        </body></html>
        """
        spec = OfficialWebSourceSpec(
            id="szse_exchange_news",
            category="financial_news_wire",
            parser_kind="szse_exchange_news",
            url="https://www.szse.cn/index/",
            issuing_body="深圳证券交易所",
            policy_level="exchange",
        )
        records = _parse_szse_exchange_news(html, spec)
        self.assertEqual(len(records), 2)
        self.assertIn("风险提示", records[1]["title"])

    def test_dedupe_news_records_filters_noise_and_prefers_higher_quality(self) -> None:
        records = [
            {
                "title": "VIP资讯 解锁直达> 【风口研报·公司】AI ASIC芯片预期差",
                "publish_time": "2026-05-17 17:42:00",
                "source_name": "财联社",
                "summary_text": "解锁直达",
                "priority_score": 9,
            },
            {
                "title": "长鑫科技：一季度营收同比增长719.13% 净利润330亿元",
                "publish_time": "2026-05-17 17:33:00",
                "source_name": "财联社",
                "summary_text": "财联社版本",
                "priority_score": 7,
            },
            {
                "title": "【长鑫科技：一季度营收同比增长719.13% 净利润330亿元】",
                "publish_time": "2026-05-17 17:34:03",
                "source_name": "东方财富",
                "summary_text": "东方财富版本",
                "priority_score": 7,
            },
        ]
        deduped = _dedupe_news_records(records)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["source_name"], "财联社")
        self.assertIn("长鑫科技", deduped[0]["title"])


if __name__ == "__main__":
    unittest.main()
