# Live Account Workflow

This document defines how to connect a real manual-trading account to the system.

## Editable files

The system reads two user-maintained files:

- `data/inbox/account_constraints/live_personal_account.json`
- `workspace/portfolio/current_holdings.json`
- `workspace/portfolio/system_trade_log.json`

The first file tells the system what the account is allowed to do.
The second file is now the working holdings state used by the next run.
The third file stores the system-generated trade records and the fields you may need to fill after execution.

## Current live profile

Current account assumptions:

- total capital: `43300 CNY`
- current cash: `43300 CNY`
- current positions: `none`
- market scope: `main board only`
- style: `small_capital_aggressive`

## Account constraints file

Keep the account file aligned with real constraints:

- `capital_total`: total account equity
- `single_trade_capital_max`: the most capital the system may plan for one new idea
- `max_holdings`: maximum total simultaneous holdings
- `max_new_positions_per_day`: how many new names can be opened in one day
- `main_board_only`: keep `true` for SH `600/601/603/605` and SZ `000/001/002/003`

For a small aggressive account, the current default profile uses:

- `max_holdings = 4`
- `max_new_positions_per_day = 2`

That keeps the system from diluting into too many mediocre names.

## Holdings file

`current_holdings.json` is no longer purely manual.

After the daily run, the system will automatically:

- add suggested buys as pending holdings
- reduce/remove suggested sells from holdings
- keep an idempotent record of which suggestions were already applied

This means the file becomes the working state for the next analysis pass.
If a rare exception happens, you can still edit it manually.

Fields:

- `cash_cny`: current cash after trading
- `positions`: current holdings
- `available_shares`: sellable shares
- `cost_basis`: average holding cost
- `execution_status`: normally blank for confirmed positions, `pending_fill` for newly auto-recorded suggestions
- `planned_trade_date`: which trade date created the auto-recorded position
- `source_record_id`: link back to the system trade log
- `applied_system_record_ids`: idempotency keys that prevent duplicate auto-application on re-runs

## System trade log

`workspace/portfolio/system_trade_log.json` is now the primary execution log.

The system auto-fills:

- trade date
- stock code
- buy or sell direction
- suggested shares
- setup type
- reason
- stop loss / take profit
- source instruction file

You mainly fill or correct:

- `fill_form.actual_shares`
- `fill_form.actual_price`
- `fill_form.execution_status`
- `fill_form.fill_note`

The file is now intentionally split into:

- `fill_form`: editable area
- `suggestion`: system-generated suggestion snapshot
- `context`: system-generated reasoning context

So in normal use, you should only edit `fill_form`.

Suggested `execution_status` values:

- `pending_fill`
- `filled`
- `partial`
- `cancelled`
- `skipped`

Once those fields are filled over time, the pipeline can summarize real setup performance into `execution_feedback`, which is the first layer of learning from your actual trades rather than only from theoretical forward returns.

It will also build `execution_behavior`, which focuses on:

- fill rate
- skip/cancel rate
- partial-fill rate
- average buy slippage

The system now uses both:

- `setup_performance`: theoretical forward-return quality
- `execution_feedback`: real realized PnL by setup
- `execution_behavior`: real executability by setup

to adjust later setup thresholds and position caps.

Empty-account example:

```json
{
  "as_of": "2026-05-17",
  "broker": "",
  "cash_cny": 43300.0,
  "positions": [],
  "notes": "Flat account."
}
```

Single-position example:

```json
{
  "as_of": "2026-05-18",
  "broker": "",
  "cash_cny": 30100.0,
  "positions": [
    {
      "stock_code": "600000.SH",
      "stock_name": "浦发银行",
      "shares": 1000,
      "available_shares": 1000,
      "cost_basis": 13.20,
      "notes": "pilot position"
    }
  ],
  "notes": ""
}
```

## Daily operating routine

### Before the preopen run

1. If you had a special execution result yesterday, correct:
   - `workspace/portfolio/current_holdings.json`
   - `workspace/portfolio/system_trade_log.json`
2. If total capital or risk preference changed, update `data/inbox/account_constraints/live_personal_account.json`.
3. Run:

```powershell
python scripts/run_refresh_live_state.py
```

This normalizes both files into the processed layer used by the pipeline.

### Run the full assistant pipeline

Use the normal one-click or pipeline entry.

The system will then:

- filter non-main-board names
- size plans against your real capital
- suppress ideas that are too expensive for one board lot
- produce hold/add/reduce reviews for already held names
- produce new-entry plans only when the market gate allows them

### After trading

Normal case:

- the system has already written the suggested trades into holdings and trade log
- you only need to fill the actual price and actual shares in `system_trade_log.json`
- if needed, adjust `cost_basis` and `cash_cny` in `current_holdings.json`

Exception case:

- if a suggested trade did not execute, change the trade log status to `cancelled` or `skipped`
- if it partially executed, change it to `partial` and fill `actual_shares`
- then manually correct `current_holdings.json` so it matches reality

The next run will automatically treat those names as current holdings and generate:

- `hold_or_add`
- `hold_and_observe`
- `reduce_or_exit_review`

instead of treating them as fresh ideas.

## What the system can help manage

With the two files kept current, the system can already help with:

- whether a held name still has system support
- whether a held name should be held, observed, reduced, or reviewed for exit
- whether a new idea is too concentrated for the account
- whether one board lot already exceeds budget
- whether the account is over-allocating to one setup type

## Important limitation

The system assumes suggested trades are executed by default.

That matches the current testing workflow, but if a special case happens and you do not correct the files, later holdings management and learning will drift away from reality.

For now, the workflow is semi-automatic:

- the system writes the default execution state
- you correct only the exceptions and actual fills
- the system evaluates around that updated truth

That is enough to make preopen holding management and future execution learning usable without adding broker automation.
