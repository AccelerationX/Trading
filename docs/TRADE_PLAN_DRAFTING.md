# Trade Plan Drafting

## Goal

The trade-plan layer converts ranked `candidate_card` objects into actionable plan drafts.

This layer is still advisory.
It does not submit orders.

## Current Rules

The current draft layer decides:

- `buy_pilot`
- `watch_only`
- `avoid`

It does not mirror the full candidate pool anymore.
It only keeps a limited plan universe sized for manual review.
The candidate layer remains broad; the trade-plan layer is intentionally narrow.

It also fills:

- entry condition
- entry zone
- position size rule
- invalidation rule
- holding horizon

## Inputs

The first version consumes:

- `market_regime_snapshot`
- `account_constraints`
- `candidate_cards`

## Design Principle

This layer is intentionally rule-based first.

Later, LLM can rewrite or enrich the wording, but the first plan output must already be:

- auditable
- explainable
- tied to account constraints
- tied to market regime
