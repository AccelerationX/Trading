from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_system.integrations.llm_contracts import load_llm_agent_registry


class LLMContractsTest(unittest.TestCase):
    def test_registry_loads(self) -> None:
        specs = load_llm_agent_registry()
        self.assertGreaterEqual(len(specs), 5)
        self.assertEqual(specs[0].agent_id, "event_deepening_agent")


if __name__ == "__main__":
    unittest.main()
