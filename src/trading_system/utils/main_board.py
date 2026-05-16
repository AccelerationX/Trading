from __future__ import annotations

import re

MAIN_BOARD_PATTERNS = [
    re.compile(r'^(600|601|603|605)\d{3}\.SH$'),
    re.compile(r'^(000|001|002|003)\d{3}\.SZ$'),
]


def is_main_board(code: str) -> bool:
    return any(pattern.match(code) for pattern in MAIN_BOARD_PATTERNS)
