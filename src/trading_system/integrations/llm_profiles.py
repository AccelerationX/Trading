from __future__ import annotations

from dataclasses import dataclass


LLM_PACKET_FAMILIES = (
    "event",
    "theme",
    "capital",
    "candidate",
    "trade_plan",
    "review_memory",
)


@dataclass(frozen=True)
class LLMRuntimeProfile:
    mode: str
    description: str
    execute_runtime: bool
    default_route_limit_per_provider: int | None
    packet_budget_by_family: dict[str, int]


_FULL_PACKET_BUDGET = {
    "event": 120,
    "theme": 40,
    "capital": 80,
    "candidate": 20,
    "trade_plan": 20,
    "review_memory": 50,
}


_PROFILES = {
    "off": LLMRuntimeProfile(
        mode="off",
        description="Builds lightweight LLM artifacts but skips runtime execution.",
        execute_runtime=False,
        default_route_limit_per_provider=0,
        packet_budget_by_family={
            "event": 4,
            "theme": 2,
            "capital": 3,
            "candidate": 4,
            "trade_plan": 3,
            "review_memory": 0,
        },
    ),
    "stable": LLMRuntimeProfile(
        mode="stable",
        description="Default live mode for daily use with strict packet budgets and bounded runtime.",
        execute_runtime=True,
        default_route_limit_per_provider=8,
        packet_budget_by_family={
            "event": 2,
            "theme": 1,
            "capital": 2,
            "candidate": 4,
            "trade_plan": 4,
            "review_memory": 0,
        },
    ),
    "balanced": LLMRuntimeProfile(
        mode="balanced",
        description="Broader coverage for research-heavy days with moderate runtime control.",
        execute_runtime=True,
        default_route_limit_per_provider=12,
        packet_budget_by_family={
            "event": 6,
            "theme": 3,
            "capital": 4,
            "candidate": 8,
            "trade_plan": 8,
            "review_memory": 2,
        },
    ),
    "full": LLMRuntimeProfile(
        mode="full",
        description="Full packet inventory for exhaustive research runs.",
        execute_runtime=True,
        default_route_limit_per_provider=None,
        packet_budget_by_family=dict(_FULL_PACKET_BUDGET),
    ),
}


def supported_llm_modes() -> tuple[str, ...]:
    return tuple(_PROFILES.keys())


def resolve_llm_runtime_profile(mode: str | None) -> LLMRuntimeProfile:
    normalized = (mode or "stable").strip().lower()
    if normalized not in _PROFILES:
        normalized = "stable"
    return _PROFILES[normalized]
