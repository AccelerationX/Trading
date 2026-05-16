from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_system.config.source_registry import SourceTier, load_source_registry


class SourceRegistryTest(unittest.TestCase):
    def test_registry_loads(self) -> None:
        sources = load_source_registry()
        self.assertGreaterEqual(len(sources), 10)

    def test_a_and_b_tiers_exist(self) -> None:
        sources = load_source_registry()
        tiers = {source.tier for source in sources}
        self.assertIn(SourceTier.A, tiers)
        self.assertIn(SourceTier.B, tiers)

    def test_core_source_ids_exist(self) -> None:
        sources = load_source_registry()
        source_ids = {source.id for source in sources}
        expected = {
            "market_equity_daily",
            "exchange_filings",
            "policy_primary_documents",
            "dragon_tiger_board",
            "financial_news_wire",
        }
        self.assertTrue(expected.issubset(source_ids))


if __name__ == "__main__":
    unittest.main()
