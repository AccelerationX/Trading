# LLM Execution Plan

## Goal

This layer turns `llm_workpack` objects into execution-ready route plans before any live model is called.

It exists to answer these questions clearly:

- which packet should go to which agent
- which provider should handle that agent
- which model should be used
- whether credentials are present
- whether the packet is ready or still blocked

## Design

The route planner does not call an API.

It only resolves:

1. `workpack -> provider`
2. `provider -> model`
3. `provider config -> credential readiness`
4. `provider capability -> output mode`

## Status Values

- `ready`
- `missing_credentials`
- `disabled`

## Current Registry

The system now includes:

- [llm_agent_registry.json](</D:/TradingSystem/configs/llm_agent_registry.json>)
- [llm_provider_registry.json](</D:/TradingSystem/configs/llm_provider_registry.json>)
- [llm_provider.template.json](</D:/TradingSystem/configs/llm_provider.template.json>)

## Current Boundary

This is still a foundation layer.

It does not yet:

- call a live model
- persist model responses back into cards
- manage retry queues across days

But once a real model and API key are provided, this route plan can be used directly without redesigning packet generation.

The next layer after this is:

- [LLM_PROVIDER_RUNTIME.md](</D:/TradingSystem/docs/LLM_PROVIDER_RUNTIME.md>)
