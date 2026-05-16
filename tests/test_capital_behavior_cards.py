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

from trading_system.context.capital_behavior import (
    build_capital_behavior_cards,
    build_capital_behavior_cards_from_block_trade_and_abnormal_volume,
    build_capital_behavior_cards_from_dragon_tiger_board,
    build_capital_behavior_cards_from_northbound_and_margin_flow,
)
from trading_system.reporting.card_reports import render_capital_behavior_cards_markdown


class CapitalBehaviorCardsTest(unittest.TestCase):
    def test_build_dragon_tiger_cards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "dragon.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "stock_code": "300001.SZ",
                            "net_amount": 680000000,
                            "seat_or_channel": "institution seat",
                            "reason": "price breakout",
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            cards = build_capital_behavior_cards_from_dragon_tiger_board("2026-05-06", path)
            self.assertEqual(len(cards), 1)
            self.assertEqual(cards[0].support_or_distribution, "support")
            self.assertEqual(cards[0].participation_strength, "high")

    def test_build_northbound_and_block_trade_cards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            northbound_path = Path(tmp_dir) / "northbound.json"
            northbound_path.write_text(
                json.dumps(
                    [{"stock_code": "600001.SH", "northbound_net_amount": -180000000, "channel": "northbound"}],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            block_trade_path = Path(tmp_dir) / "block_trade.json"
            block_trade_path.write_text(
                json.dumps(
                    [{"stock_code": "000001.SZ", "premium_pct": 3.2, "amount": 45000000, "abnormal_volume_ratio": 2.4}],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            northbound_cards = build_capital_behavior_cards_from_northbound_and_margin_flow("2026-05-06", northbound_path)
            block_trade_cards = build_capital_behavior_cards_from_block_trade_and_abnormal_volume("2026-05-06", block_trade_path)
            self.assertEqual(northbound_cards[0].support_or_distribution, "distribution")
            self.assertIn("abnormal_turnover", block_trade_cards[0].warning_flags)

    def test_build_aggregate_cards_and_render_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            dragon_path = Path(tmp_dir) / "dragon.json"
            dragon_path.write_text(
                json.dumps([{"stock_code": "300001.SZ", "net_amount": 120000000}], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            northbound_path = Path(tmp_dir) / "northbound.json"
            northbound_path.write_text(
                json.dumps([{"stock_code": "600001.SH", "northbound_net_amount": 90000000}], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            block_trade_path = Path(tmp_dir) / "block_trade.json"
            block_trade_path.write_text(
                json.dumps([{"stock_code": "000001.SZ", "premium_pct": 1.5, "amount": 30000000}], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            cards = build_capital_behavior_cards(
                "2026-05-06",
                dragon_tiger_path=dragon_path,
                northbound_margin_path=northbound_path,
                block_trade_path=block_trade_path,
            )
            self.assertEqual(len(cards), 3)
            markdown = render_capital_behavior_cards_markdown("2026-05-06", cards)
            self.assertIn("Capital Behavior Cards - 2026-05-06", markdown)
            self.assertIn("300001.SZ", markdown)


if __name__ == "__main__":
    unittest.main()
