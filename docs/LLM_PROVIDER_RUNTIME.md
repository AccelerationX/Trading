# LLM Provider Runtime

## Goal

This layer sits between:

- `llm_execution_plan`
- `workspace/llm_responses`

It turns provider routes into one of two bounded actions:

- export a manual review batch
- write mock contract responses for closed-loop testing

## Built-in Adapter Types

- `manual_workspace`
  - exports packet batches to `workspace/llm_requests/`
  - does not call a live model
  - useful before credentials are configured

- `mock_contract`
  - writes deterministic synthetic enrichments to `workspace/llm_responses/`
  - useful for pipeline testing and contract verification

## Current Runtime Flow

1. build `llm_workpacks`
2. resolve `llm_execution_plan`
3. execute provider adapters
4. write runtime artifacts
5. optionally apply enrichments back into processed cards

## Current Boundary

This runtime still does not call a real remote model.

That is intentional.
When you later provide a real provider and credentials, a new adapter can be added without changing:

- packet generation
- route planning
- enrichment apply contracts

## Artifacts

- runtime report:
  - `outputs/llm_runtime/llm_runtime_<date>.json`
  - `outputs/llm_runtime/llm_runtime_<date>.md`
- manual batch export:
  - `workspace/llm_requests/llm_request_batch_<date>_<provider>.json`
- mock enrichment output:
  - `workspace/llm_responses/llm_enrichments_<date>.json`
