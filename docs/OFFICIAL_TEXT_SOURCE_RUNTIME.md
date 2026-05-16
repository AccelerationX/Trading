# Official Text Source Runtime

## Goal

This layer adds non-Tushare official text sources to the assistant.

## Current Sources

- National Development and Reform Commission notice page
- Ministry of Industry and Information Technology RSS subscription page
- National Bureau of Statistics latest-release RSS
- CNInfo latest announcement feed
- Shanghai Stock Exchange hot-topic feed
- Shenzhen Stock Exchange exchange-news feed

These sources feed:

- `policy_primary_documents`
- `industry_catalyst_calendar`
- `exchange_filings`
- `financial_news_wire`

## Runtime Command

`python scripts/run_fetch_official_text_sources.py --date YYYYMMDD`

## Current Scope

This layer is designed for:

- policy and regulation monitoring
- macro and industry catalyst monitoring
- exchange filing feed collection
- official market-news text collection
- high-trust official text collection

It does not yet replace:

- stable full-text exchange PDF/API collection
- commercial real-time mainstream market news
- account-backed commercial feeds
