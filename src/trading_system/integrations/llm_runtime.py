from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib import error, request

from trading_system.config.paths import OUTPUTS_DIR, PROMPTS_DIR, WORKSPACE_DIR
from trading_system.integrations.llm_contracts import LLMWorkPacket
from trading_system.integrations.llm_enrichments import LLMEnrichmentResult
from trading_system.integrations.llm_provider_registry import LLMExecutionRoute, LLMProviderConfig, load_llm_provider_registry


@dataclass(slots=True)
class LLMRuntimeRecord:
    packet_id: str
    provider_id: str
    provider_type: str
    target_object_type: str
    target_object_id: str
    status: str
    artifact_paths: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def llm_request_workspace_dir() -> Path:
    directory = WORKSPACE_DIR / "llm_requests"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _llm_response_workspace_dir() -> Path:
    directory = WORKSPACE_DIR / "llm_responses"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def llm_runtime_output_dir() -> Path:
    directory = OUTPUTS_DIR / "llm_runtime"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _load_prompt_text(prompt_file: str) -> str:
    prompt_path = Path(prompt_file)
    if not prompt_path.is_absolute():
        prompt_path = (PROMPTS_DIR.parent / prompt_file).resolve()
    if not prompt_path.exists():
        return ""
    return prompt_path.read_text(encoding="utf-8")


def _manual_request_payload(packet: LLMWorkPacket, route: LLMExecutionRoute) -> dict:
    return {
        "packet_id": packet.packet_id,
        "agent_id": packet.agent_id,
        "task_id": packet.task_id,
        "provider_id": route.provider_id,
        "provider_type": route.provider_type,
        "model": route.model,
        "target_object_type": packet.target_object_type,
        "target_object_id": packet.target_object_id,
        "expected_output_contract": packet.expected_output_contract,
        "prompt_file": packet.prompt_file,
        "sort_rank": packet.sort_rank,
        "prompt_text": _load_prompt_text(packet.prompt_file),
        "input_refs": list(packet.input_refs),
        "context_payload": dict(packet.context_payload),
        "notes": list(packet.notes),
    }


def _contract_schema(contract_type: str) -> dict:
    if contract_type == "event_card_enrichment":
        structured_payload = {
            "sentiment_verdict": "constructive | bearish | neutral_wait_confirmation",
            "beneficiary_stocks": ["000001.SZ"],
            "risk_notes": ["short sentence"],
        }
    elif contract_type == "theme_card_enrichment":
        structured_payload = {
            "focus_industries": ["industry_tag"],
            "focus_stocks": ["000001.SZ"],
            "tradeability_verdict": "tradable | watch_for_confirmation | weak_tradeability",
        }
    elif contract_type == "capital_behavior_enrichment":
        structured_payload = {
            "interpretation": "short interpretation sentence",
        }
    elif contract_type == "candidate_card_diagnosis":
        structured_payload = {
            "tradeability_verdict": "tradable | watch_only | too_expensive_for_account | needs_more_confirmation",
            "focus_points": ["short focus point"],
            "risk_notes": ["short risk note"],
        }
    elif contract_type == "trade_plan_refinement":
        structured_payload = {
            "execution_watchpoints": ["opening breadth", "leader confirmation"],
        }
    else:
        structured_payload = {
            "pattern_summary": "short reusable lesson",
        }

    return {
        "summary": "short concise summary for trader",
        "confidence": 0.0,
        "structured_payload": structured_payload,
        "citations": ["source or reason"],
        "warnings": ["optional warning"],
    }


def _build_openai_messages(packet: LLMWorkPacket) -> list[dict]:
    prompt_text = _load_prompt_text(packet.prompt_file).strip()
    schema = _contract_schema(packet.expected_output_contract)
    clean_system_text = (
        "你是中国 A 股交易助手系统中的结构化分析代理。"
        "你必须严格基于输入上下文判断，不要编造事实。"
        "输出必须是单个 JSON 对象，不要使用 Markdown，不要添加解释性前缀。"
    )
    clean_user_text = "\n".join(
        [
            f"task_id: {packet.task_id}",
            f"agent_id: {packet.agent_id}",
            f"target_object_type: {packet.target_object_type}",
            f"target_object_id: {packet.target_object_id}",
            "",
            "task_prompt:",
            prompt_text,
            "",
            "context_payload_json:",
            json.dumps(packet.context_payload, ensure_ascii=False, indent=2),
            "",
            "input_refs:",
            json.dumps(packet.input_refs, ensure_ascii=False),
            "",
            "notes:",
            json.dumps(packet.notes, ensure_ascii=False),
            "",
            "output_requirements:",
            "请返回一个 JSON 对象，字段必须包含 summary, confidence, structured_payload, citations, warnings。",
            "confidence 必须是 0 到 1 之间的数字。",
            "structured_payload 必须符合下面的结构约束。",
            "",
            "structured_payload_schema_example:",
            json.dumps(schema, ensure_ascii=False, indent=2),
        ]
    )
    return [
        {"role": "system", "content": clean_system_text},
        {"role": "user", "content": clean_user_text},
    ]
    system_text = (
        "你是中国A股交易助手系统中的一个结构化分析代理。"
        "你必须严格基于输入上下文做判断，不要编造事实。"
        "输出必须是单个 JSON 对象，不要使用 Markdown，不要添加解释性前缀。"
    )
    user_text = "\n".join(
        [
            f"task_id: {packet.task_id}",
            f"agent_id: {packet.agent_id}",
            f"target_object_type: {packet.target_object_type}",
            f"target_object_id: {packet.target_object_id}",
            "",
            "task_prompt:",
            prompt_text,
            "",
            "context_payload_json:",
            json.dumps(packet.context_payload, ensure_ascii=False, indent=2),
            "",
            "input_refs:",
            json.dumps(packet.input_refs, ensure_ascii=False),
            "",
            "notes:",
            json.dumps(packet.notes, ensure_ascii=False),
            "",
            "output_requirements:",
            "请返回一个 JSON 对象，字段必须包含 summary, confidence, structured_payload, citations, warnings。",
            "confidence 必须是 0 到 1 的数字。",
            "structured_payload 必须符合下面的结构约束。",
            "",
            "structured_payload_schema_example:",
            json.dumps(schema, ensure_ascii=False, indent=2),
        ]
    )
    return [
        {"role": "system", "content": system_text},
        {"role": "user", "content": user_text},
    ]


def _extract_text_content(message_content: object) -> str:
    if isinstance(message_content, str):
        return message_content.strip()
    if isinstance(message_content, list):
        fragments: list[str] = []
        for item in message_content:
            if isinstance(item, dict) and item.get("type") == "text":
                fragments.append(str(item.get("text", "")).strip())
        return "\n".join(fragment for fragment in fragments if fragment).strip()
    return str(message_content or "").strip()


def _extract_json_payload(text: str) -> dict:
    content = text.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines).strip()

    try:
        return dict(json.loads(content))
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            return dict(json.loads(content[start : end + 1]))
        raise


def _normalize_enrichment_result(packet: LLMWorkPacket, payload: dict) -> LLMEnrichmentResult:
    summary = str(payload.get("summary", "")).strip()
    confidence = payload.get("confidence")
    try:
        confidence_value = None if confidence is None else float(confidence)
    except (TypeError, ValueError):
        confidence_value = None
    structured_payload = payload.get("structured_payload", {})
    if not isinstance(structured_payload, dict):
        structured_payload = {}
    citations = payload.get("citations", [])
    warnings = payload.get("warnings", [])
    return LLMEnrichmentResult(
        trade_date=packet.trade_date,
        packet_id=packet.packet_id,
        agent_id=packet.agent_id,
        target_object_type=packet.target_object_type,
        target_object_id=packet.target_object_id,
        contract_type=packet.expected_output_contract,
        summary=summary,
        confidence=confidence_value,
        structured_payload=structured_payload,
        citations=[str(item).strip() for item in citations if str(item).strip()],
        warnings=[str(item).strip() for item in warnings if str(item).strip()],
    )


def _normalize_text_contract_result(packet: LLMWorkPacket, content: str) -> LLMEnrichmentResult:
    stripped = content.strip()
    if stripped:
        try:
            payload = _extract_json_payload(stripped)
            return _normalize_enrichment_result(packet, payload)
        except Exception:
            pass
    return LLMEnrichmentResult(
        trade_date=packet.trade_date,
        packet_id=packet.packet_id,
        agent_id=packet.agent_id,
        target_object_type=packet.target_object_type,
        target_object_id=packet.target_object_id,
        contract_type=packet.expected_output_contract,
        summary=content.strip(),
        confidence=None,
        structured_payload=_empty_structured_payload(packet.expected_output_contract),
        citations=[],
        warnings=[],
    )


def _empty_structured_payload(contract_type: str) -> dict:
    schema = _contract_schema(contract_type).get("structured_payload", {})
    payload: dict = {}
    for key, value in schema.items():
        if isinstance(value, list):
            payload[key] = []
        else:
            payload[key] = ""
    return payload


def _provider_map() -> dict[str, LLMProviderConfig]:
    return {provider.provider_id: provider for provider in load_llm_provider_registry()}


def _provider_supports_agent(provider: LLMProviderConfig, agent_id: str) -> bool:
    return not provider.agent_allowlist or agent_id in provider.agent_allowlist


def _resolve_provider_model(provider: LLMProviderConfig, agent_id: str) -> str:
    for override in provider.agent_overrides:
        if override.agent_id == agent_id and override.model:
            return override.model
    return provider.default_model


def _build_route_for_provider(
    packet: LLMWorkPacket,
    provider: LLMProviderConfig,
    environ: dict[str, str],
) -> LLMExecutionRoute | None:
    if not provider.enabled or not _provider_supports_agent(provider, packet.agent_id):
        return None
    model = _resolve_provider_model(provider, packet.agent_id)
    api_key_required = bool(provider.api_key_env)
    api_base_required = bool(provider.api_base_env) and not provider.api_base_default
    api_key_present = bool(provider.api_key_env and environ.get(provider.api_key_env))
    api_base_present = bool(provider.api_base_env and environ.get(provider.api_base_env))
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
    return LLMExecutionRoute(
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


def _resolve_api_base(route: LLMExecutionRoute, provider: LLMProviderConfig, environ: dict[str, str]) -> str:
    if route.api_base_env and environ.get(route.api_base_env):
        return str(environ[route.api_base_env]).rstrip("/")
    if route.api_base_default:
        return route.api_base_default.rstrip("/")
    return provider.api_base_default.rstrip("/")


def _call_openai_compatible_provider(
    packet: LLMWorkPacket,
    route: LLMExecutionRoute,
    provider: LLMProviderConfig,
    environ: dict[str, str],
) -> LLMEnrichmentResult:
    api_key = environ.get(route.api_key_env, "")
    if not api_key:
        raise RuntimeError("missing_api_key")

    base_url = _resolve_api_base(route, provider, environ)
    if not base_url:
        raise RuntimeError("missing_api_base")

    payload = {
        "model": route.model,
        "messages": _build_openai_messages(packet),
        "temperature": 1,
        "max_tokens": 1200,
        "stream": False,
    }
    if route.output_mode == "json_contract":
        payload["response_format"] = {"type": "json_object"}

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url=f"{base_url}/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=max(10, route.timeout_seconds or 90)) as resp:
            raw = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if route.output_mode == "json_contract" and exc.code == 400:
            fallback_payload = dict(payload)
            fallback_payload.pop("response_format", None)
            fallback_body = json.dumps(fallback_payload, ensure_ascii=False).encode("utf-8")
            fallback_req = request.Request(
                url=f"{base_url}/chat/completions",
                data=fallback_body,
                headers=req.headers,
                method="POST",
            )
            with request.urlopen(fallback_req, timeout=max(10, route.timeout_seconds or 90)) as resp:
                raw = resp.read().decode("utf-8")
        else:
            raise RuntimeError(f"http_error_{exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"url_error: {exc}") from exc

    response_payload = json.loads(raw)
    choice = (response_payload.get("choices") or [{}])[0]
    message = choice.get("message", {})
    content = _extract_text_content(message.get("content", ""))
    if route.output_mode == "text_contract":
        return _normalize_text_contract_result(packet, content)
    try:
        normalized = _normalize_enrichment_result(packet, _extract_json_payload(content))
    except Exception:
        normalized = LLMEnrichmentResult(
            trade_date=packet.trade_date,
            packet_id=packet.packet_id,
            agent_id=packet.agent_id,
            target_object_type=packet.target_object_type,
            target_object_id=packet.target_object_id,
            contract_type=packet.expected_output_contract,
            summary=content.strip(),
            confidence=None,
            structured_payload=_empty_structured_payload(packet.expected_output_contract),
            citations=[],
            warnings=["non_json_response_fallback"],
        )
    if not normalized.warnings:
        normalized.warnings = []
    return normalized


def _call_ollama_provider(
    packet: LLMWorkPacket,
    route: LLMExecutionRoute,
    provider: LLMProviderConfig,
    environ: dict[str, str],
) -> LLMEnrichmentResult:
    base_url = _resolve_api_base(route, provider, environ)
    if not base_url:
        raise RuntimeError("missing_api_base")

    payload = {
        "model": route.model,
        "messages": _build_openai_messages(packet),
        "stream": False,
        "options": {
            "temperature": 0.2,
        },
    }
    if route.output_mode == "json_contract":
        payload["format"] = "json"

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url=f"{base_url}/api/chat",
        data=body,
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=max(10, route.timeout_seconds or 120)) as resp:
            raw = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"http_error_{exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"url_error: {exc}") from exc

    response_payload = json.loads(raw)
    message = response_payload.get("message", {})
    content = _extract_text_content(message.get("content", ""))
    try:
        normalized = _normalize_enrichment_result(packet, _extract_json_payload(content))
    except Exception:
        normalized = LLMEnrichmentResult(
            trade_date=packet.trade_date,
            packet_id=packet.packet_id,
            agent_id=packet.agent_id,
            target_object_type=packet.target_object_type,
            target_object_id=packet.target_object_id,
            contract_type=packet.expected_output_contract,
            summary=content.strip(),
            confidence=None,
            structured_payload=_empty_structured_payload(packet.expected_output_contract),
            citations=[],
            warnings=["non_json_response_fallback"],
        )
    if not normalized.warnings:
        normalized.warnings = []
    return normalized


def _call_live_provider_once(
    packet: LLMWorkPacket,
    route: LLMExecutionRoute,
    provider: LLMProviderConfig,
    environ: dict[str, str],
) -> LLMEnrichmentResult:
    if route.provider_type == "openai_compatible":
        return _call_openai_compatible_provider(packet, route, provider, environ)
    if route.provider_type in {"ollama_chat", "local_ollama"}:
        return _call_ollama_provider(packet, route, provider, environ)
    raise RuntimeError(f"unsupported_live_provider_type:{route.provider_type}")


def _call_live_provider_with_retries(
    packet: LLMWorkPacket,
    route: LLMExecutionRoute,
    provider: LLMProviderConfig,
    environ: dict[str, str],
) -> tuple[LLMEnrichmentResult, list[str]]:
    total_attempts = max(1, int(route.max_retries or 0) + 1)
    last_error: Exception | None = None
    for attempt in range(1, total_attempts + 1):
        try:
            result = _call_live_provider_once(packet, route, provider, environ)
            notes: list[str] = []
            if attempt > 1:
                notes.append(f"retry_success_attempt={attempt}")
            return result, notes
        except Exception as exc:  # pragma: no cover - exercised by higher-level tests
            last_error = exc
    raise RuntimeError(
        f"provider_failed_after_retries:{provider.provider_id}: attempts={total_attempts}: {last_error}"
    )


def _iter_fallback_routes(
    packet: LLMWorkPacket,
    providers: dict[str, LLMProviderConfig],
    environ: dict[str, str],
    *,
    exclude_provider_id: str,
    allowed_provider_ids: set[str] | None,
) -> list[tuple[LLMProviderConfig, LLMExecutionRoute]]:
    fallback_routes: list[tuple[LLMProviderConfig, LLMExecutionRoute]] = []
    for provider in providers.values():
        if provider.provider_id == exclude_provider_id:
            continue
        if allowed_provider_ids is not None and provider.provider_id not in allowed_provider_ids:
            continue
        route = _build_route_for_provider(packet, provider, environ)
        if route is None or route.status != "ready":
            continue
        fallback_routes.append((provider, route))
    return fallback_routes


def _mock_result_for_packet(packet: LLMWorkPacket) -> LLMEnrichmentResult:
    payload: dict
    summary: str
    if packet.target_object_type == "event_card":
        summary = "Mock review: official event recognized. Confirm market follow-through before acting."
        payload = {
            "sentiment_verdict": "constructive",
            "beneficiary_stocks": list(packet.context_payload.get("stock_codes", []))[:2],
            "risk_notes": ["mock_result", "confirm sector follow-through"],
        }
    elif packet.target_object_type == "theme_card":
        summary = "Mock review: theme is tradable only if breadth confirms and a clear leader emerges."
        payload = {
            "focus_industries": list(packet.context_payload.get("priority_industries", []))[:3],
            "focus_stocks": list(packet.context_payload.get("priority_stocks", []))[:3],
            "tradeability_verdict": "watch_for_confirmation",
        }
    elif packet.target_object_type == "capital_behavior_card":
        summary = "Mock review: capital behavior looks notable but still needs price confirmation."
        payload = {
            "interpretation": "mock_capital_support_needs_price_confirmation",
        }
    elif packet.target_object_type == "candidate_card":
        summary = "Mock review: candidate is interesting, but only tradable if the technical trigger and account fit both hold."
        payload = {
            "tradeability_verdict": "needs_more_confirmation",
            "focus_points": ["opening strength", "event follow-through", "account position concentration"],
            "risk_notes": ["mock_result", "account fit must be checked before acting"],
        }
    elif packet.target_object_type == "trade_plan_card":
        summary = "Mock review: start small and add only after opening strength and theme confirmation."
        payload = {
            "execution_watchpoints": ["opening breadth", "leader confirmation", "volume retention"],
        }
    else:
        summary = "Mock review: pattern noted for future retrieval."
        payload = {
            "pattern_summary": "mock_memory_pattern_summary",
        }

    return LLMEnrichmentResult(
        trade_date=packet.trade_date,
        packet_id=packet.packet_id,
        agent_id=packet.agent_id,
        target_object_type=packet.target_object_type,
        target_object_id=packet.target_object_id,
        contract_type=packet.expected_output_contract,
        summary=summary,
        confidence=0.55,
        structured_payload=payload,
        citations=["mock_contract_provider"],
        warnings=["synthetic_result_not_for_live_trading"],
    )


def _save_results_batch(trade_date: str, provider_id: str, results: list[LLMEnrichmentResult]) -> Path:
    output_path = _llm_response_workspace_dir() / f"llm_enrichments_{trade_date}_{provider_id}.json"
    output_path.write_text(
        json.dumps([asdict(item) for item in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def execute_llm_runtime_with_inputs(
    trade_date: str,
    packets: list[LLMWorkPacket],
    routes: list[LLMExecutionRoute],
    *,
    allowed_provider_ids: set[str] | None = None,
) -> tuple[Path, Path, list[LLMRuntimeRecord]]:
    packet_map = {packet.packet_id: packet for packet in packets}
    records: list[LLMRuntimeRecord] = []
    providers = _provider_map()
    environ = dict(os.environ)

    manual_batches: dict[str, list[dict]] = {}
    mock_results: dict[str, list[LLMEnrichmentResult]] = {}
    live_results: dict[str, list[tuple[LLMEnrichmentResult, list[str]]]] = {}

    for route in routes:
        packet = packet_map.get(route.packet_id)
        if packet is None:
            records.append(
                LLMRuntimeRecord(
                    packet_id=route.packet_id,
                    provider_id=route.provider_id,
                    provider_type=route.provider_type,
                    target_object_type="unknown",
                    target_object_id="unknown",
                    status="skipped",
                    notes=["missing_workpacket"],
                )
            )
            continue

        if route.status != "ready":
            records.append(
                LLMRuntimeRecord(
                    packet_id=route.packet_id,
                    provider_id=route.provider_id,
                    provider_type=route.provider_type,
                    target_object_type=packet.target_object_type,
                    target_object_id=packet.target_object_id,
                    status="skipped",
                    notes=[f"route_status={route.status}", *list(route.notes)],
                )
            )
            continue

        if route.provider_type == "manual_workspace":
            manual_batches.setdefault(route.provider_id, []).append(_manual_request_payload(packet, route))
        elif route.provider_type == "openai_compatible":
            provider = providers.get(route.provider_id)
            if provider is None:
                records.append(
                    LLMRuntimeRecord(
                        packet_id=route.packet_id,
                        provider_id=route.provider_id,
                        provider_type=route.provider_type,
                        target_object_type=packet.target_object_type,
                        target_object_id=packet.target_object_id,
                        status="skipped",
                        notes=["missing_provider_config"],
                    )
                )
                continue
            try:
                result, runtime_notes = _call_live_provider_with_retries(packet, route, provider, environ)
                live_results.setdefault(route.provider_id, []).append((result, ["provider_response_written", *runtime_notes]))
            except Exception as exc:
                fallback_used = False
                for fallback_provider, fallback_route in _iter_fallback_routes(
                    packet,
                    providers,
                    environ,
                    exclude_provider_id=route.provider_id,
                    allowed_provider_ids=allowed_provider_ids,
                ):
                    try:
                        result, runtime_notes = _call_live_provider_with_retries(
                            packet,
                            fallback_route,
                            fallback_provider,
                            environ,
                        )
                        live_results.setdefault(fallback_provider.provider_id, []).append(
                            (
                                result,
                                [
                                    "provider_response_written",
                                    f"fallback_from={route.provider_id}",
                                    *runtime_notes,
                                ],
                            )
                        )
                        fallback_used = True
                        break
                    except Exception:
                        continue
                if not fallback_used:
                    records.append(
                        LLMRuntimeRecord(
                            packet_id=route.packet_id,
                            provider_id=route.provider_id,
                            provider_type=route.provider_type,
                            target_object_type=packet.target_object_type,
                            target_object_id=packet.target_object_id,
                            status="failed",
                            notes=[str(exc)],
                        )
                    )
        elif route.provider_type == "ollama_chat":
            provider = providers.get(route.provider_id)
            if provider is None:
                records.append(
                    LLMRuntimeRecord(
                        packet_id=route.packet_id,
                        provider_id=route.provider_id,
                        provider_type=route.provider_type,
                        target_object_type=packet.target_object_type,
                        target_object_id=packet.target_object_id,
                        status="skipped",
                        notes=["missing_provider_config"],
                    )
                )
                continue
            try:
                result, runtime_notes = _call_live_provider_with_retries(packet, route, provider, environ)
                live_results.setdefault(route.provider_id, []).append((result, ["provider_response_written", *runtime_notes]))
            except Exception as exc:
                fallback_used = False
                for fallback_provider, fallback_route in _iter_fallback_routes(
                    packet,
                    providers,
                    environ,
                    exclude_provider_id=route.provider_id,
                    allowed_provider_ids=allowed_provider_ids,
                ):
                    try:
                        result, runtime_notes = _call_live_provider_with_retries(
                            packet,
                            fallback_route,
                            fallback_provider,
                            environ,
                        )
                        live_results.setdefault(fallback_provider.provider_id, []).append(
                            (
                                result,
                                [
                                    "provider_response_written",
                                    f"fallback_from={route.provider_id}",
                                    *runtime_notes,
                                ],
                            )
                        )
                        fallback_used = True
                        break
                    except Exception:
                        continue
                if not fallback_used:
                    records.append(
                        LLMRuntimeRecord(
                            packet_id=route.packet_id,
                            provider_id=route.provider_id,
                            provider_type=route.provider_type,
                            target_object_type=packet.target_object_type,
                            target_object_id=packet.target_object_id,
                            status="failed",
                            notes=[str(exc)],
                        )
                    )
        elif route.provider_type == "mock_contract":
            mock_results.setdefault(route.provider_id, []).append(_mock_result_for_packet(packet))
        else:
            records.append(
                LLMRuntimeRecord(
                    packet_id=route.packet_id,
                    provider_id=route.provider_id,
                    provider_type=route.provider_type,
                    target_object_type=packet.target_object_type,
                    target_object_id=packet.target_object_id,
                    status="skipped",
                    notes=["unsupported_provider_type"],
                )
            )

    for provider_id, batch in manual_batches.items():
        batch_path = llm_request_workspace_dir() / f"llm_request_batch_{trade_date}_{provider_id}.json"
        batch_path.write_text(json.dumps(batch, ensure_ascii=False, indent=2), encoding="utf-8")
        for item in batch:
            records.append(
                LLMRuntimeRecord(
                    packet_id=item["packet_id"],
                    provider_id=provider_id,
                    provider_type="manual_workspace",
                    target_object_type=item["target_object_type"],
                    target_object_id=item["target_object_id"],
                    status="exported_for_manual",
                    artifact_paths=[str(batch_path)],
                    notes=["batch_exported"],
                )
            )

    for provider_id, results in mock_results.items():
        response_path = _save_results_batch(trade_date, provider_id, results)
        for result in results:
            records.append(
                LLMRuntimeRecord(
                    packet_id=result.packet_id,
                    provider_id=provider_id,
                    provider_type="mock_contract",
                    target_object_type=result.target_object_type,
                    target_object_id=result.target_object_id,
                    status="completed",
                    artifact_paths=[str(response_path)],
                    notes=["mock_response_written"],
                )
            )

    for provider_id, results in live_results.items():
        response_path = _save_results_batch(trade_date, provider_id, [item[0] for item in results])
        provider_type = providers.get(provider_id).provider_type if providers.get(provider_id) else "openai_compatible"
        for result, runtime_notes in results:
            records.append(
                LLMRuntimeRecord(
                    packet_id=result.packet_id,
                    provider_id=provider_id,
                    provider_type=provider_type,
                    target_object_type=result.target_object_type,
                    target_object_id=result.target_object_id,
                    status="completed",
                    artifact_paths=[str(response_path)],
                    notes=runtime_notes,
                )
            )

    records.sort(key=lambda item: (item.status, item.provider_id, item.packet_id))

    output_dir = llm_runtime_output_dir()
    json_path = output_dir / f"llm_runtime_{trade_date}.json"
    md_path = output_dir / f"llm_runtime_{trade_date}.md"
    json_path.write_text(json.dumps([asdict(item) for item in records], ensure_ascii=False, indent=2), encoding="utf-8")
    return json_path, md_path, records
