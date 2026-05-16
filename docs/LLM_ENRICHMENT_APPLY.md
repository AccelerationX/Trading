# LLM Enrichment Apply

## Goal

This layer defines how model output is written back into processed system objects.

It exists so that future live model calls do not need to invent an output format on the fly.

## Flow

```text
structured cards
-> llm_workpacks
-> llm_execution_plan
-> llm_enrichment batch
-> apply back into processed objects
```

## Input Location

The current foundation expects enrichment batches in:

- [workspace/llm_responses](</D:/TradingSystem/workspace/llm_responses>)

Template:

- [llm_enrichment_batch.template.json](</D:/TradingSystem/workspace/templates/llm_enrichment_batch.template.json>)

## Current Supported Targets

- `event_card`
- `theme_card`
- `capital_behavior_card`
- `trade_plan_card`
- `review_memory_entry`

## Current Boundary

This layer can already:

- validate and load enrichment batches
- apply summaries and structured fields back into processed objects
- persist a normalized enrichment archive

It still does not:

- call a live model
- verify semantic quality of the returned answer
- reconcile conflicting enrichments across multiple providers
