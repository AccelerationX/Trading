import _bootstrap

_bootstrap.bootstrap()

from trading_system.cli.sync_trade_execution_to_live_state import main


if __name__ == "__main__":
    main()
