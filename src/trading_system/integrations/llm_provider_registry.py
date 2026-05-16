from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from trading_system.config.paths import CONFIGS_DIR
from trading_system.integrations.llm_contracts import LLMWorkPacket


@dataclass(frozen=True)
class LLMProviderOverride:
    agent_id: str
    model: str


@dataclass(frozen=True)
class LLMProviderConfig:
    provider_id: str
    enabled: bool
    provider_type: str
    default_model: str
    api_key_env: str
    api_base_env: str
    api_base_default: str
    timeout_seconds: int
    max_retries: int
    supports_json_mode: bool
    agent_overrides: tuple[LLMProviderOverride, ...]
    agent_allowlist: tuple[str, ...]


@dataclass(frozen=True)
class LLMExecutionRoute:
    packet_id: str
    agent_id: str
    provider_id: str
    provider_type: str
    model: str
    status: str
    api_key_env: str
    api_key_present: bool
    api_base_env: str
    api_base_present: bool
    api_base_default: str
    timeout_seconds: int
    max_retries: int
    output_mode: str
    notes: tuple[str, ...]


def load_llm_provider_registry(path: Path | None = None) -> list[LLMProviderConfig]:
    config_path = path or (CONFIGS_DIR / "llm_provider_registry.json")
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    providers: list[LLMProviderConfig] = []
    for item in payload.get("providers", []):
        overrides = tuple(
            LLMProviderOverride(
                agent_id=override["agent_id"],
                model=override.get("model", ""),
            )
            for override in item.get("agent_overrides", [])
        )
        providers.append(
            LLMProviderConfig(
                provider_id=item["provider_id"],
                enabled=bool(item.get("enabled", False)),
                provider_type=item["provider_type"],
                default_model=item.get("default_model", ""),
                api_key_env=item.get("api_key_env", ""),
                api_base_env=item.get("api_base_env", ""),
                api_base_default=item.get("api_base_default", ""),
                timeout_seconds=int(item.get("timeout_seconds", 90)),
                max_retries=int(item.get("max_retries", 2)),
                supports_json_mode=bool(item.get("supports_json_mode", True)),
                agent_overrides=overrides,
                agent_allowlist=tuple(item.get("agent_allowlist", [])),
            )
        )
    return providers


def _resolve_provider_model(provider: LLMProviderConfig, agent_id: str) -> str:
    for override in provider.agent_overrides:
        if override.agent_id == agent_id and override.model:
            return override.model
    return provider.default_model


def _provider_supports_agent(provider: LLMProviderConfig, agent_id: str) -> bool:
    return not provider.agent_allowlist or agent_id in provider.agent_allowlist


def resolve_llm_execution_routes(
    packets: list[LLMWorkPacket],
    providers: list[LLMProviderConfig],
    environ: dict[str, str] | None = None,
) -> list[LLMExecutionRoute]:
    env = environ or dict(os.environ)
    routes: list[LLMExecutionRoute] = []
    enabled_providers = [provider for provider in providers if provider.enabled]

    for packet in packets:
        if not enabled_providers:
            routes.append(
                LLMExecutionRoute(
                    packet_id=packet.packet_id,
                    agent_id=packet.agent_id,
                    provider_id="",
                    provider_type="",
                    model="",
                    status="disabled",
                    api_key_env="",
                    api_key_present=False,
                    api_base_env="",
                    api_base_present=False,
                    api_base_default="",
                    timeout_seconds=0,
                    max_retries=0,
                    output_mode="json_contract",
                    notes=("no_enabled_provider",),
                )
            )
            continue

        matching_providers = [provider for provider in enabled_providers if _provider_supports_agent(provider, packet.agent_id)]
        if not matching_providers:
            routes.append(
                LLMExecutionRoute(
                    packet_id=packet.packet_id,
                    agent_id=packet.agent_id,
                    provider_id="",
                    provider_type="",
                    model="",
                    status="disabled",
                    api_key_env="",
                    api_key_present=False,
                    api_base_env="",
                    api_base_present=False,
                    api_base_default="",
                    timeout_seconds=0,
                    max_retries=0,
                    output_mode="json_contract",
                    notes=("no_matching_provider",),
                )
            )
            continue

        provider = matching_providers[0]
        model = _resolve_provider_model(provider, packet.agent_id)
        api_key_required = bool(provider.api_key_env)
        api_base_required = bool(provider.api_base_env) and not provider.api_base_default
        api_key_present = bool(provider.api_key_env and env.get(provider.api_key_env))
        api_base_present = bool(provider.api_base_env and env.get(provider.api_base_env))
        credentials_ready = (not api_key_required or api_key_present) and (not api_base_required or api_base_present)
        status = "ready" if credentials_ready and model else "missing_credentials"
        notes: list[str] = []
        if not model:
            notes.append("missing_model")
        if api_key_required and not api_key_present:
            notes.append("missing_api_key")
        if api_base_required and not api_base_present:
            notes.append("missing_api_base")
        if not api_key_required:
            notes.append("no_api_key_required")
        routes.append(
            LLMExecutionRoute(
                packet_id=packet.packet_id,
                agent_id=packet.agent_id,
                provider_id=provider.provider_id,
                provider_type=provider.provider_type,
                model=model,
                status=status,
                api_key_env=provider.api_key_env,
                api_key_present=api_key_present,
                api_base_env=provider.api_base_env,
                api_base_present=api_base_present,
                api_base_default=provider.api_base_default,
                timeout_seconds=provider.timeout_seconds,
                max_retries=provider.max_retries,
                output_mode="json_contract" if provider.supports_json_mode else "text_contract",
                notes=tuple(notes),
            )
        )

    return routes
