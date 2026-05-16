# Source Status

## Fully Automated Now

These sources already have working collectors:

- `equity_reference_master`
- `market_equity_daily`
- `market_index_daily`
- `market_breadth_and_limit_structure`
- `company_announcements_structured`
- `dragon_tiger_board`
- `northbound_and_margin_flow`
- `block_trade_and_abnormal_volume`
- `policy_primary_documents`
- `industry_catalyst_calendar`
- `exchange_filings`
- `financial_news_wire`

## Current Authentication Need

No extra login is needed for the current automated layer.

Current automated sources use:

- your `TUSHARE_TOKEN`
- public official government pages
- public official RSS-style pages

## Still Not Automated

These sources are still not fully solved:

- `exchange_filings` stable full-text PDF/API payloads
- mainstream commercial finance news wires
- commercial paid feeds

## Likely Future Login Needs

You may need an account later if we want:

- higher-quality real-time mainstream finance news
- full official exchange filing APIs with stable machine endpoints
- commercial terminal-grade feeds

## Practical Meaning

The assistant now already has:

- market data
- trade-event data
- capital-behavior data
- official policy data
- official macro and industry catalyst data

The biggest remaining gap is not raw market data anymore.
The biggest remaining gap is stable full-text filings and higher-quality real-time news flow.
