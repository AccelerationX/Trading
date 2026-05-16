from __future__ import annotations

from trading_system.decision.account import load_active_account_constraints, save_normalized_account_constraints


def main() -> None:
    account = load_active_account_constraints()
    output_path = save_normalized_account_constraints(account)
    print(f"account_constraints_json={output_path}")


if __name__ == "__main__":
    main()
