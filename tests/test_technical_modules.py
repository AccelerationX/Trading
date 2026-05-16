from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_system.context.cards import MarketRegimeSnapshot
from trading_system.signal.technical_modules import load_technical_modules, recommend_modules_for_regime


class TechnicalModuleTest(unittest.TestCase):
    def test_registry_loads(self) -> None:
        modules = load_technical_modules()
        self.assertGreaterEqual(len(modules), 8)

    def test_recommendations_for_risk_on(self) -> None:
        snapshot = MarketRegimeSnapshot(
            snapshot_id="s1",
            trade_date="2026-05-06",
            market_bias="bullish",
            risk_mode="risk_on",
            breadth_strength="strong",
            limit_up_temperature="hot",
            turnover_regime="high",
            style_lead="small_cap_lead",
            theme_concentration="high",
            confidence=0.75,
            supporting_evidence=[],
        )
        modules = recommend_modules_for_regime(snapshot, can_watch_intraday=False)
        module_ids = {module.module_id for module in modules}
        self.assertIn("TM001_line_a_trend_continuation", module_ids)
        self.assertIn("TM101_behavior_repair_rebound", module_ids)
        self.assertNotIn("TM401_gap_open_anchor", module_ids)


if __name__ == "__main__":
    unittest.main()
