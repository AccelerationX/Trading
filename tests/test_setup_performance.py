from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_system.cli.build_setup_performance import build_setup_performance_cli
from trading_system.context.cards import CandidateCard, TradePlanCard
from trading_system.evaluation.setup_performance import build_setup_performance
from trading_system.reporting.setup_performance_reports import render_setup_performance_markdown


class SetupPerformanceTest(unittest.TestCase):
    def test_build_setup_performance(self) -> None:
        history = pd.DataFrame(
            [
                {"stock_code": "000001.SZ", "trade_date": "2026-05-06", "close": 10.0, "high": 10.2, "low": 9.8},
                {"stock_code": "000001.SZ", "trade_date": "2026-05-07", "close": 10.5, "high": 10.7, "low": 10.0},
                {"stock_code": "000001.SZ", "trade_date": "2026-05-08", "close": 10.8, "high": 11.0, "low": 10.3},
                {"stock_code": "000001.SZ", "trade_date": "2026-05-09", "close": 10.4, "high": 10.9, "low": 10.1},
                {"stock_code": "000001.SZ", "trade_date": "2026-05-10", "close": 10.9, "high": 11.2, "low": 10.2},
                {"stock_code": "000001.SZ", "trade_date": "2026-05-11", "close": 11.0, "high": 11.1, "low": 10.8},
            ]
        )
        payload = build_setup_performance(
            "2026-05-06_to_2026-05-06",
            candidate_cards=[
                CandidateCard(
                    candidate_id="c1",
                    stock_code="000001.SZ",
                    trade_date="2026-05-06",
                    candidate_source="full_resonance",
                    candidate_score=0.84,
                    fusion_score=0.84,
                    fusion_verdict="actionable",
                    setup_type="leader_acceleration",
                    setup_confidence=0.82,
                )
            ],
            trade_plan_cards=[
                TradePlanCard(
                    plan_id="p1",
                    trade_date="2026-05-06",
                    stock_code="000001.SZ",
                    action="buy_pilot",
                    priority_rank=1,
                    rationale="x",
                    entry_condition="y",
                    setup_type="leader_acceleration",
                )
            ],
            history=history,
        )
        self.assertEqual(payload["setup_count"], 1)
        self.assertEqual(payload["setup_summary"][0]["setup_type"], "leader_acceleration")
        self.assertEqual(payload["setup_summary"][0]["buy_pilot_count"], 1)
        self.assertAlmostEqual(payload["setup_evaluations"][0]["forward_returns"]["1d"], 0.05, places=4)
        self.assertAlmostEqual(payload["setup_evaluations"][0]["forward_returns"]["5d"], 0.10, places=4)

    def test_render_setup_performance_markdown(self) -> None:
        markdown = render_setup_performance_markdown(
            "2026-05-06_to_2026-05-07",
            {
                "candidate_count": 2,
                "trade_plan_count": 1,
                "evaluated_setup_count": 2,
                "setup_count": 1,
                "setup_summary": [
                    {
                        "setup_type": "leader_acceleration",
                        "sample_count": 2,
                        "buy_pilot_count": 1,
                        "watch_only_count": 1,
                        "actionable_count": 1,
                        "avg_candidate_score": 0.8,
                        "avg_setup_confidence": 0.75,
                        "avg_mfe_5d": 0.09,
                        "avg_mae_5d": -0.03,
                        "buy_pilot_horizons": {
                            "3d": {"sample_count": 1, "avg_return": 0.08, "win_rate": 1.0, "hit_rate_3pct": 1.0}
                        },
                    }
                ],
            },
        )
        self.assertIn("Setup Performance - 2026-05-06_to_2026-05-07", markdown)
        self.assertIn("leader_acceleration", markdown)

    def test_build_setup_performance_cli_uses_archived_cards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            processed = root / "processed"
            outputs = root / "outputs"
            (processed / "candidates").mkdir(parents=True, exist_ok=True)
            (processed / "evaluation").mkdir(parents=True, exist_ok=True)
            (outputs / "trade_plans").mkdir(parents=True, exist_ok=True)
            (outputs / "analysis").mkdir(parents=True, exist_ok=True)

            (processed / "candidates" / "candidate_cards_2026-05-06.json").write_text(
                json.dumps(
                    [
                        {
                            "candidate_id": "c1",
                            "stock_code": "000001.SZ",
                            "trade_date": "2026-05-06",
                            "candidate_source": "full_resonance",
                            "candidate_score": 0.84,
                            "fusion_score": 0.84,
                            "fusion_verdict": "actionable",
                            "setup_type": "leader_acceleration",
                            "setup_confidence": 0.82,
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (outputs / "trade_plans" / "trade_plan_cards_2026-05-06.json").write_text(
                json.dumps(
                    [
                        {
                            "plan_id": "p1",
                            "trade_date": "2026-05-06",
                            "stock_code": "000001.SZ",
                            "action": "buy_pilot",
                            "priority_rank": 1,
                            "rationale": "x",
                            "entry_condition": "y",
                            "setup_type": "leader_acceleration",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            history = pd.DataFrame(
                [
                    {"stock_code": "000001.SZ", "trade_date": "2026-05-06", "close": 10.0, "high": 10.2, "low": 9.8},
                    {"stock_code": "000001.SZ", "trade_date": "2026-05-07", "close": 10.5, "high": 10.7, "low": 10.0},
                    {"stock_code": "000001.SZ", "trade_date": "2026-05-08", "close": 10.8, "high": 11.0, "low": 10.3},
                    {"stock_code": "000001.SZ", "trade_date": "2026-05-09", "close": 10.4, "high": 10.9, "low": 10.1},
                ]
            )

            with patch("trading_system.cli.build_setup_performance.PROCESSED_DATA_DIR", processed), patch(
                "trading_system.cli.build_setup_performance.OUTPUTS_DIR", outputs
            ), patch("trading_system.cli.build_setup_performance.load_stock_history", return_value=history):
                json_path, md_path = build_setup_performance_cli("2026-05-06", lookback_trade_days=5)

            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["setup_summary"][0]["setup_type"], "leader_acceleration")


if __name__ == "__main__":
    unittest.main()
