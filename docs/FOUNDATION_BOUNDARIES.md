# Foundation Boundaries

## What Counts As Foundation

Before live LLM execution is attached, the system foundation should cover:

- source collection
- source provenance
- normalized inbox files
- processed structured objects
- candidate generation
- trade-plan drafting
- review-memory generation
- LLM task contracts

## What Is Still Allowed Before Live LLM

The system can already:

- fetch data automatically
- rank candidates
- draft rule-based plans
- prepare LLM workpacks

## What Is Intentionally Deferred

- live model invocation
- automatic prompt execution
- automatic post-processing of model outputs into final cards
- any trading action based only on unreviewed model output

## Why This Order Matters

If the model is connected too early:

- bad sources become confident mistakes
- raw HTML becomes fragile prompt noise
- failures become hard to audit

If the model is connected after the foundation:

- every task has a bounded context
- every output can be checked against upstream objects
- human review remains straightforward
