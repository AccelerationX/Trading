from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_system.cli import run_system_selfcheck
from trading_system.cli.run_system_selfcheck import ArtifactCheck


class SystemSelfcheckTest(unittest.TestCase):
    def test_latest_dated_file_picks_latest_supported_format(self) -> None:
        with TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            (directory / "candidate_cards_20260515.json").write_text("{}", encoding="utf-8")
            (directory / "candidate_cards_2026-05-16.json").write_text("{}", encoding="utf-8")

            latest_date, latest_path = run_system_selfcheck._latest_dated_file(
                directory, "candidate_cards", ".json"
            )

            self.assertEqual(latest_date, "2026-05-16")
            self.assertEqual(latest_path, directory / "candidate_cards_2026-05-16.json")

    def test_build_system_selfcheck_payload_builds_warning_summary(self) -> None:
        artifact_checks = [
            ArtifactCheck("market_equity_daily", "20260515", "market.csv", True),
            ArtifactCheck("financial_news_wire", "20260514", "news.json", True),
            ArtifactCheck("execution_feedback", "2026-05-15", "execution_feedback.json", True),
            ArtifactCheck("execution_behavior", "2026-05-15", "execution_behavior.json", True),
            ArtifactCheck("preopen_summary", "2026-05-15", "preopen.json", True),
            ArtifactCheck("trade_execution_sheet", "2026-05-15", "trade_execution.json", True),
            ArtifactCheck("system_trade_log", "2026-05-15", "system_trade_log.json", True),
        ]
        with patch.object(run_system_selfcheck, "_build_artifact_checks", return_value=artifact_checks):
            with patch.object(
                run_system_selfcheck,
                "_domestic_news_status",
                return_value={"enabled_count": 2, "enabled_sources": ["cls"], "disabled_sources": ["ths"]},
            ):
                with patch.object(
                    run_system_selfcheck,
                    "_llm_status",
                    return_value={
                        "enabled_count": 1,
                        "local_enabled": ["ollama"],
                        "remote_enabled": [],
                        "other_enabled": [],
                    },
                ):
                    payload = run_system_selfcheck.build_system_selfcheck_payload("2026-05-17")

        self.assertEqual(payload["run_date"], "2026-05-17")
        self.assertEqual(len(payload["artifact_checks"]), 7)
        self.assertIn("新闻快讯日期早于行情缓存", payload["warnings"][0])

    def test_render_and_save_system_selfcheck_outputs(self) -> None:
        payload = {
            "run_date": "2026-05-17",
            "artifact_checks": [
                {"name": "market_equity_daily", "latest_date": "20260515", "path": "market.csv", "exists": True}
            ],
            "domestic_news": {
                "enabled_count": 2,
                "enabled_sources": ["cls_telegraph", "eastmoney_fastnews"],
                "disabled_sources": ["ths_news"],
            },
            "llm": {
                "enabled_count": 1,
                "local_enabled": ["ollama_main"],
                "remote_enabled": [],
                "other_enabled": [],
            },
            "warnings": [],
        }

        markdown = run_system_selfcheck.render_system_selfcheck_markdown(payload)
        self.assertIn("# 系统自检 - 2026-05-17", markdown)
        self.assertIn("## 国内新闻源", markdown)
        self.assertIn("## LLM 状态", markdown)

        with TemporaryDirectory() as temp_dir:
            daily_dir = Path(temp_dir)
            with patch.object(run_system_selfcheck, "_daily_report_dir", return_value=daily_dir):
                json_path, md_path = run_system_selfcheck.save_system_selfcheck_payload("2026-05-17", payload)

            saved_payload = json.loads(json_path.read_text(encoding="utf-8"))
            saved_markdown = md_path.read_text(encoding="utf-8")

        self.assertEqual(saved_payload["run_date"], "2026-05-17")
        self.assertIn("系统自检", saved_markdown)


if __name__ == "__main__":
    unittest.main()
