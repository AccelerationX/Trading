# Source Integration Runtime

## Current Automatic Sources

The first automated source runtime uses Tushare for the sources that are already structured enough to support the assistant:

- `equity_reference_master`
- `market_equity_daily`
- `market_index_daily`
- `market_breadth_and_limit_structure`
- `company_announcements_structured`
- `dragon_tiger_board`
- `northbound_and_margin_flow`
- `block_trade_and_abnormal_volume`

These collectors write normalized files directly into `data/inbox/...`.

## Current Manual Sources

These sources are still manual for now:

- `policy_primary_documents`
- `industry_catalyst_calendar`
- `exchange_filings`

They are not blocked by code structure.
They simply need a separate collection path or account-backed source later.

## Token Handling

The runtime reads `TUSHARE_TOKEN` from:

1. environment variable
2. local project `.env`
3. `D:\Trading\.env`
4. `D:\TradingMain\.env`

The token is not hardcoded into the repository.

## Runtime Command

Use:

`python scripts/run_fetch_tushare_sources.py --date YYYYMMDD`

This fetches the currently automated Tushare-backed sources and writes a fetch report into:

- `outputs/daily_reports/`
