from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_system.context.cards import CandidateCard, MarketRegimeSnapshot, TradePlanCard
from trading_system.evaluation.module_signal_evaluation import build_module_signal_evaluation
from trading_system.reporting.module_evaluation_reports import render_module_evaluation_markdown
from trading_system.signal.scanners.base import ModuleSignal


class ModuleSignalEvaluationTest(unittest.TestCase):
    def test_build_module_signal_evaluation(self) -> None:
        history = pd.DataFrame(
            [
                {"stock_code": "000001.SZ", "trade_date": "2026-05-06", "close": 10.0},
                {"stock_code": "000001.SZ", "trade_date": "2026-05-07", "close": 10.5},
                {"stock_code": "000001.SZ", "trade_date": "2026-05-08", "close": 10.8},
                {"stock_code": "000001.SZ", "trade_date": "2026-05-09", "close": 10.4},
                {"stock_code": "000001.SZ", "trade_date": "2026-05-10", "close": 10.9},
                {"stock_code": "000001.SZ", "trade_date": "2026-05-11", "close": 11.0},
            ]
        )
        payload = build_module_signal_evaluation(
            "2026-05-06",
            module_signals=[
                ModuleSignal(
                    module_id="TM001_line_a_trend_continuation",
                    stock_code="000001.SZ",
                    trade_date="2026-05-06",
                    signal_type="strong",
                    strength=0.85,
                    confidence=0.9,
                    technical_state="line_a_top_entry",
                )
            ],
            history=history,
            market_regime=MarketRegimeSnapshot(
                snapshot_id="s1",
                trade_date="2026-05-06",
                market_bias="bullish",
                risk_mode="risk_on",
                breadth_strength="strong",
                limit_up_temperature="warm",
                turnover_regime="high",
                style_lead="large_cap_lead",
                theme_concentration="high",
                supporting_evidence=[],
            ),
            candidate_cards=[
                CandidateCard(
                    candidate_id="c1",
                    stock_code="000001.SZ",
                    trade_date="2026-05-06",
                    candidate_source="module_direct",
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
                )
            ],
        )
        self.assertEqual(payload["signal_count"], 1)
        self.assertEqual(payload["module_count"], 1)
        self.assertEqual(payload["module_summary"][0]["candidate_overlap_count"], 1)
        self.assertEqual(payload["module_summary"][0]["trade_plan_overlap_count"], 1)
        self.assertAlmostEqual(payload["signal_evaluations"][0]["forward_returns"]["1d"], 0.05, places=4)
        self.assertAlmostEqual(payload["signal_evaluations"][0]["forward_returns"]["5d"], 0.10, places=4)

    def test_render_module_evaluation_markdown(self) -> None:
        markdown = render_module_evaluation_markdown(
            "2026-05-06",
            {
                "signal_count": 1,
                "module_count": 1,
                "candidate_count": 1,
                "trade_plan_count": 1,
                "market_regime": {"risk_mode": "risk_on", "style_lead": "large_cap_lead", "theme_concentration": "high"},
                "module_summary": [
                    {
                        "module_id": "TM001_line_a_trend_continuation",
                        "signal_count": 1,
                        "unique_stock_count": 1,
                        "candidate_overlap_count": 1,
                        "trade_plan_overlap_count": 1,
                        "avg_strength": 0.85,
                        "avg_confidence": 0.9,
                        "signal_type_counts": {"strong": 1},
                        "horizons": {
                            "1d": {"sample_count": 1, "avg_return": 0.05, "win_rate": 1.0, "hit_rate_3pct": 1.0}
                        },
                    }
                ],
            },
        )
        self.assertIn("Module Evaluation - 2026-05-06", markdown)
        self.assertIn("TM001_line_a_trend_continuation", markdown)


if __name__ == "__main__":
    unittest.main()
