# One-Click Daily Run

Daily routine is intentionally compressed to four steps:

1. If needed, correct `workspace/portfolio/current_holdings.json` and `workspace/portfolio/system_trade_log.json`
2. Double-click `run_preopen_oneclick.bat`
3. Read the newest file under `outputs/trade_execution/`
4. Trade manually, then fill actual price / actual shares for the new system records

## What the batch file does

`run_preopen_oneclick.bat` now performs:

1. load `.env`
2. refresh live account and holdings state
3. fetch latest available market and text sources
4. run the full assistant pipeline
5. generate:
   - `outputs/trade_execution/trade_execution_<trade_date>.md`
   - `outputs/preopen/preopen_summary_<trade_date>.md`
6. auto-apply the final buy/sell suggestions into:
   - `workspace/portfolio/current_holdings.json`
   - `workspace/portfolio/system_trade_log.json`
7. refresh learning artifacts:
   - `execution_feedback`
   - `execution_behavior`
   - next-day setup policy inputs

## Optional arguments

Normally you do not need any arguments.

Default one-click mode is `stable`.

Reason:

- it keeps the LLM involved in the final daily decision chain
- it is the only mode already verified as practical for repeatable daily preopen use
- `balanced/full` remain available for deeper research runs

## Daily LLM routing policy

The daily one-click flow now uses mixed routing:

- cloud model: core decision refinement
- local model: bulk support analysis

Cloud-first tasks:

- `candidate_diagnosis_agent`
- `trade_plan_refine_agent`

These are the tasks that most directly affect the final trading instruction sheet.

Local-first tasks:

- `event_deepening_agent`
- `theme_deepening_agent`
- `capital_interpret_agent`
- `review_memory_agent`

This keeps the most important final judgment quality high while controlling cloud usage cost.

If cloud routing fails, the runtime will try retries first, then fall back to another available provider.

If needed:

```powershell
run_preopen_oneclick.bat 2026-05-18 full
```

Arguments:

- arg1: optional trade date
- arg2: optional LLM mode, default `stable`
- arg3: optional `llm-limit`

## Which file to read first

Read this first:

- `outputs/trade_execution/trade_execution_<trade_date>.md`

That file is the direct instruction sheet:

- what to buy
- how many shares
- buy zone
- stop loss
- take profit
- how long to hold
- what to sell
- how many shares
- when there is no action

The preopen summary is still generated, but it is now secondary.

## Auto-record behavior

The daily run now assumes suggested trades will be executed.

So after the final instruction sheet is generated, the system will automatically:

- add suggested buys into the holdings file as `pending_fill`
- apply suggested sells to the holdings file
- append detailed execution records into `workspace/portfolio/system_trade_log.json`

This is the default test workflow.

If a rare exception happens, correct:

- `fill_form.execution_status`
- `fill_form.actual_price`
- `fill_form.actual_shares`
- `fill_form.fill_note`

and, if needed, manually fix `current_holdings.json` so it matches reality.

Over time, those corrected execution records are used to improve:

- which setup types get favored or disabled
- how high the action threshold should be
- how much position size a setup is allowed to use
- which setups look good on paper but are hard to execute in reality
