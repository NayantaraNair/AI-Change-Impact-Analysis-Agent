"""OpenAI-compatible provider chain; callers own deterministic NoLLM fallbacks."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from dataclasses import dataclass, replace
from typing import Literal, cast

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI
from openai.types.chat import ChatCompletion
from pydantic import BaseModel, ValidationError

from app import config

logger = logging.getLogger(__name__)
_semaphore = asyncio.Semaphore(4)
_cooldowns: dict[str, float] = {}
_TOOL_NAME = "extract_facts"


class NoLLM(Exception):
    """No configured, enabled provider could produce a valid response."""


@dataclass(frozen=True)
class Provider:
    name: Literal["tokenharbor", "openrouter"]
    base_url: str
    model: str
    tool_only: bool = False

    @property
    def label(self) -> str:
        return f"{self.name}:{self.model}"


# The ":free" Token Harbor routes need no account balance; override with a paid model if you have credit.
TOKENHARBOR_FAST_MODEL = os.getenv("TOKENHARBOR_FAST_MODEL", "deepseek-v4.1-flash:free")
TOKENHARBOR_STRONG_MODEL = os.getenv("TOKENHARBOR_STRONG_MODEL", "deepseek-v4.1-flash:free")

# Free-tier models can take 30-60 s for long structured answers.
LLM_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "60"))

PROVIDERS = (
    Provider("tokenharbor", "https://tokenharbor.ai/v1", TOKENHARBOR_FAST_MODEL),
    Provider(
        "openrouter", "https://openrouter.ai/api/v1",
        "nvidia/nemotron-3-super-120b-a12b:free",
    ),
    Provider(
        "openrouter", "https://openrouter.ai/api/v1",
        "thinkingmachines/inkling:free", tool_only=True,
    ),
    Provider("openrouter", "https://openrouter.ai/api/v1", "openrouter/free"),
)


def providers_configured() -> dict[str, bool]:
    """Report key presence without exposing key values or caching environment state."""
    return {
        "tokenharbor": bool(config.tokenharbor_key()),
        "openrouter": bool(config.openrouter_key()),
    }


def _key(provider: Provider) -> str | None:
    return (
        config.tokenharbor_key()
        if provider.name == "tokenharbor"
        else config.openrouter_key()
    )


def _provider_entries(tier: Literal["fast", "strong"] = "fast") -> tuple[Provider, ...]:
    if tier == "strong":
        return (replace(PROVIDERS[0], model=TOKENHARBOR_STRONG_MODEL), *PROVIDERS[1:])
    return PROVIDERS


class _InvalidResponse(ValueError):
    pass


_FALLBACK_ERRORS = (
    APIStatusError, APIConnectionError, APITimeoutError, TimeoutError,
    json.JSONDecodeError, ValidationError, _InvalidResponse,
)


def _parse_response(
    response: ChatCompletion, schema: type[BaseModel] | None, tool_mode: bool,
) -> BaseModel | str:
    if not response.choices:
        raise _InvalidResponse("No response choices")
    message = response.choices[0].message
    if schema is None:
        if not isinstance(message.content, str) or not message.content.strip():
            raise _InvalidResponse("Empty text response")
        return message.content
    if tool_mode:
        calls = message.tool_calls or []
        matching = [
            call for call in calls
            if getattr(getattr(call, "function", None), "name", None) == _TOOL_NAME
        ]
        if len(matching) != 1:
            raise _InvalidResponse("Expected one extraction tool call")
        content = matching[0].function.arguments
    else:
        content = message.content
    if not isinstance(content, str):
        raise _InvalidResponse("Missing structured response")
    content = content.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*\n?(.*?)\n?\s*```", content, re.DOTALL | re.IGNORECASE)
    if fenced:
        content = fenced.group(1).strip()
    return schema.model_validate(json.loads(content))


async def _complete_provider(
    provider: Provider,
    system: str,
    user: str,
    schema: type[BaseModel] | None,
    max_tokens: int,
    history: list[dict] | None = None,
) -> BaseModel | str:
    """Call one entry directly, including its retry policy (also used by smoke)."""
    if config.llm_disabled():
        raise NoLLM("LLM disabled or no keys configured")
    key = _key(provider)
    if not key:
        raise NoLLM("Provider key missing")

    async with _semaphore:
        # Check after acquiring the slot: another in-flight call may set cooldown.
        if _cooldowns.get(provider.name, 0) > time.monotonic():
            raise NoLLM("Provider cooling down")
        headers = None
        if provider.name == "openrouter":
            headers = {"X-Title": "Change Impact Copilot"}
            referer = os.getenv("OPENROUTER_HTTP_REFERER")
            if referer:
                headers["HTTP-Referer"] = referer
        messages = [{"role": "system", "content": system}]
        json_schema = schema.model_json_schema() if schema is not None else None
        if json_schema is not None:
            messages[0]["content"] += (
                "\nReturn only JSON matching this schema (or use the forced extraction tool):\n"
                + json.dumps(json_schema)
            )
        if history:
            messages.extend(dict(message) for message in history)
        messages.append({"role": "user", "content": user})
        tool_mode = provider.tool_only and schema is not None
        retried_transient = False
        retried_tool = False
        async with AsyncOpenAI(
            api_key=key, base_url=provider.base_url, timeout=LLM_TIMEOUT_S,
            max_retries=0, default_headers=headers,
        ) as client:
            while True:
                request = {
                    "model": provider.model, "messages": messages,
                    "temperature": 0 if schema is not None else 0.3,
                    "max_tokens": max_tokens,
                }
                if json_schema is not None:
                    if tool_mode:
                        request["tools"] = [{"type": "function", "function": {
                            "name": _TOOL_NAME,
                            "description": "Extract categorical facts as structured JSON.",
                            "parameters": json_schema,
                        }}]
                        request["tool_choice"] = {
                            "type": "function", "function": {"name": _TOOL_NAME},
                        }
                    else:
                        request["response_format"] = {"type": "json_schema", "json_schema": {
                            "name": schema.__name__, "schema": json_schema,
                        }}
                started = time.monotonic()
                response = None
                error_class = None
                try:
                    async with asyncio.timeout(LLM_TIMEOUT_S):
                        response = await client.chat.completions.create(**request)
                    return _parse_response(response, schema, tool_mode)
                except _FALLBACK_ERRORS as exc:
                    error_class = type(exc).__name__
                    status = exc.status_code if isinstance(exc, APIStatusError) else None
                    if status in {429, 402}:
                        _cooldowns[provider.name] = time.monotonic() + 60
                    if (
                        status == 400 and provider.name == "tokenharbor"
                        and schema is not None and not tool_mode and not retried_tool
                    ):
                        tool_mode = retried_tool = True
                        continue
                    transient = (
                        status is not None and 500 <= status < 600
                    ) or isinstance(exc, (APITimeoutError, TimeoutError))
                    if transient and not retried_transient:
                        retried_transient = True
                        continue
                    raise
                finally:
                    usage = getattr(response, "usage", None)
                    logger.info(
                        "llm provider=%s model=%s latency_ms=%.1f tokens=%s error=%s",
                        provider.name, provider.model, (time.monotonic() - started) * 1000,
                        usage.model_dump() if usage is not None else None, error_class,
                    )


async def _complete(
    system: str, user: str, schema: type[BaseModel] | None,
    tier: Literal["fast", "strong"], max_tokens: int, history: list[dict] | None = None,
) -> tuple[BaseModel | str, str]:
    if config.llm_disabled() or not any(providers_configured().values()):
        raise NoLLM("LLM disabled or no keys configured")
    for provider in _provider_entries(tier):
        try:
            result = await _complete_provider(provider, system, user, schema, max_tokens, history)
            return result, provider.label
        except (NoLLM, *_FALLBACK_ERRORS):
            continue
    # Do not chain provider errors: SDK exceptions can include request details.
    raise NoLLM("All providers unavailable or returned invalid output") from None


async def complete_structured(
    system: str, user: str, schema: type[BaseModel],
    tier: Literal["fast", "strong"] = "fast", max_tokens: int = 1500,
) -> tuple[BaseModel, str]:
    result, label = await _complete(system, user, schema, tier, max_tokens)
    return cast(BaseModel, result), label


async def complete_text(
    system: str, user: str, history: list[dict] | None = None, max_tokens: int = 800,
) -> tuple[str, str]:
    result, label = await _complete(system, user, None, "fast", max_tokens, history)
    return cast(str, result), label
