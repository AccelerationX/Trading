from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_system.utils.main_board import is_main_board


class MainBoardFilterTest(unittest.TestCase):
    def test_sh_main_board(self) -> None:
        self.assertTrue(is_main_board("600000.SH"))
        self.assertTrue(is_main_board("601000.SH"))
        self.assertTrue(is_main_board("603000.SH"))
        self.assertTrue(is_main_board("605000.SH"))

    def test_sz_main_board(self) -> None:
        self.assertTrue(is_main_board("000001.SZ"))
        self.assertTrue(is_main_board("001001.SZ"))
        self.assertTrue(is_main_board("002001.SZ"))
        self.assertTrue(is_main_board("003001.SZ"))

    def test_chi_board_rejected(self) -> None:
        self.assertFalse(is_main_board("300001.SZ"))
        self.assertFalse(is_main_board("301001.SZ"))

    def test_star_board_rejected(self) -> None:
        self.assertFalse(is_main_board("688001.SH"))

    def test_bj_rejected(self) -> None:
        self.assertFalse(is_main_board("430001.BJ"))


if __name__ == "__main__":
    unittest.main()
