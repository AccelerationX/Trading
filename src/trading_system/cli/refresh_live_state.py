from __future__ import annotations

from pathlib import Path

from trading_system.decision.account import (
    load_active_account_constraints,
    save_normalized_account_constraints,
)
from trading_system.decision.holdings import (
    default_holdings_path,
    load_portfolio_snapshot,
    save_normalized_portfolio_snapshot,
)


def refresh_live_state(holdings_path: Path | None = None) -> tuple[Path, Path]:
    account = load_active_account_constraints()
    account_output = save_normalized_account_constraints(account)
    snapshot = load_portfolio_snapshot(holdings_path or default_holdings_path())
    holdings_output = save_normalized_portfolio_snapshot(snapshot)
    return account_output, holdings_output


def main() -> None:
    account_output, holdings_output = refresh_live_state()
    print(f"account_constraints_json={account_output}")
    print(f"holdings_snapshot_json={holdings_output}")


if __name__ == "__main__":
    main()
