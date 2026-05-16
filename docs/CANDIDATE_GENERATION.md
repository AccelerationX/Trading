# Candidate Generation

## Goal

The candidate layer is the first stock-level fusion layer in the assistant.

It does not generate final buy or sell instructions.
It converts upstream context into a ranked candidate list that can later feed:

- trade-plan drafting
- LLM explanation
- manual pre-open review

## Current Inputs

The first implementation consumes:

- `market_regime_snapshot`
- `account_constraints`
- `technical_module_recommendation`
- `event_cards`
- `theme_cards`

Capital-behavior inputs are optional and will be folded in when available.

## Candidate Logic

The current version builds candidates from:

- direct stock references in `event_cards`
- direct stock references in `theme_cards.priority_stocks`

Each candidate is scored on:

- `event_support_score`
- `theme_alignment_score`
- `capital_confirmation_score`
- `market_fit_score`
- `account_fit_score`

These scores are fused into `candidate_score`.

## Why This Layer Matters

This is where the assistant starts turning mixed upstream information into one stock-level object.

Before this layer:

- market context exists
- event interpretation exists
- theme interpretation exists
- technical playbook selection exists

After this layer:

- each stock has one unified candidate object
- the object already carries supporting evidence
- the object is ready for later trade-plan drafting

## Current Limits

The first candidate layer still has gaps:

- no full per-stock technical-bar scoring yet
- no full capital-flow confirmation yet
- no intraday timing yet
- no final position-size decision yet

That is intentional.
This layer is meant to be the bridge from context to stock-level judgment, not the final order layer.
