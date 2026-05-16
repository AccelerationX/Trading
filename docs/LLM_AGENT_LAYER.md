# LLM Agent Layer

## Goal

The LLM layer is designed to sit after structured objects already exist.

It is not responsible for:

- raw source fetching
- raw HTML interpretation without contracts
- direct order submission

It is responsible for:

- deepening event interpretation
- deepening theme and policy mapping
- interpreting capital behavior
- refining trade-plan wording and risk framing
- summarizing review memory

## Design Principle

The assistant should not ask one large model to read everything and decide everything.

Instead, the system should:

1. collect raw data
2. normalize raw data
3. generate rule-based structured objects
4. create focused LLM workpacks
5. let the model enrich one bounded task at a time

## Agent Roles

- `event_deepening_agent`
- `theme_deepening_agent`
- `capital_interpret_agent`
- `trade_plan_refine_agent`
- `review_memory_agent`

## Why Workpacks

Each LLM task should be:

- traceable
- bounded
- replayable
- replaceable

That is why the system generates `llm_workpack` objects before any model is called.

## Not Connected Yet

This layer is designed and scaffolded, but not yet connected to a live model provider.

That is intentional.
Once model choice and API credentials are provided, a provider adapter can be added without redesigning the pipeline.

## Added Foundation

The LLM layer now has two distinct pre-runtime artifacts:

- `llm_workpack`
- `llm_execution_plan`
- `llm_runtime`

`llm_workpack` answers:

- what needs model review
- which prompt family applies
- what bounded payload should be sent

`llm_execution_plan` answers:

- which provider should take the packet
- which model should be used
- whether credentials are present
- whether the packet is blocked before runtime

`llm_runtime` answers:

- whether the route was exported for manual review
- whether a mock provider wrote back contract-shaped results
- which artifact file was generated for each packet

This means model integration can be added later without reworking source ingestion, card generation, packet selection, or enrichment apply contracts.
