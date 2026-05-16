# Preopen Summary Layer

This layer is the final user-facing output of the assistant pipeline.

## Goal

After the pipeline finishes, the trader should only need to:

- open one preopen summary page
- review current holdings
- review new ideas and watchlist
- execute trades manually
- update `workspace/portfolio/current_holdings.json` after trading

## Inputs

- normalized account constraints
- current holdings file
- market regime snapshot
- candidate cards
- trade plan cards
- theme cards
- LLM-enriched candidate and trade-plan text when available

## Outputs

- `outputs/preopen/preopen_summary_<trade_date>.json`
- `outputs/preopen/preopen_summary_<trade_date>.md`

## Holdings conventions

Editable holdings file:

- `workspace/portfolio/current_holdings.json`

Template:

- `workspace/templates/portfolio_holdings.template.json`

Each position should provide at least:

- `stock_code`
- `shares`
- `available_shares`
- `cost_basis`

## Summary structure

- market view
- account posture
- current holdings with hold/add/reduce review
- new ideas that are not already held
- watchlist
- focus themes

The summary is intentionally based on the latest completed market session plus overnight structured information. It is a preopen decision aid, not a live intraday monitor.
