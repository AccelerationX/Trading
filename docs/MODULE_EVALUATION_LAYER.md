# Module Evaluation Layer

## Goal

This layer evaluates daily `module_signals` after they are generated.

It is not a backtest engine.
It is a lightweight daily effectiveness snapshot for:

- which modules fired
- how many names they covered
- which names entered `candidate_cards`
- which names survived into `trade_plan_cards`
- what the close-to-close forward returns looked like over `1d / 3d / 5d`

## Why It Exists

The technical module layer is now active.
Without a feedback layer, we would repeat the old pattern of “the module feels useful” without measuring:

- breadth versus precision
- which modules are too wide
- which modules only work in certain market regimes
- which modules are more useful for a small manual account

## Current Output

For each trade date, the layer writes:

- `data/processed/evaluation/module_evaluation_<date>.json`
- `outputs/analysis/module_evaluation_<date>.md`

The payload includes:

- signal-level evaluation rows
- per-module summary
- candidate overlap count
- trade-plan overlap count
- forward return summary by horizon

## Backfill Mode

Daily same-day evaluation is structurally incomplete for forward returns.
So the layer also supports a backfill mode:

- scans enabled modules across the last `N` trade dates
- computes realized `1d / 3d / 5d` close-to-close follow-through
- summarizes module breadth and hit quality across the sampled window

Entry point:

- `python scripts/run_backfill_module_evaluation.py --date 2026-05-06 --lookback-trade-days 10`

## Current Scope

This is intentionally simple:

- uses local stock history only
- evaluates close-to-close forward returns
- does not simulate execution
- does not estimate slippage
- does not replace later strategy validation

The purpose is ranking module usefulness, not declaring a module “tradable” by itself.
