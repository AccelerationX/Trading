from __future__ import annotations

import argparse
from pathlib import Path

from trading_system.decision.holdings import default_holdings_path, load_portfolio_snapshot, save_normalized_portfolio_snapshot


def refresh_holdings_snapshot(path: Path | None = None) -> Path:
    snapshot = load_portfolio_snapshot(path=path)
    return save_normalized_portfolio_snapshot(snapshot)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--path",
        default=str(default_holdings_path()),
        help="Path to the editable holdings JSON file.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    output_path = refresh_holdings_snapshot(Path(args.path))
    print(f"holdings_snapshot={output_path}")


if __name__ == "__main__":
    main()
