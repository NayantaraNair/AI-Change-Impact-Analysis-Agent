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

from app import config, runs
from app.contracts import AttemptOutcome

logger = logging.getLogger(__name__)
MAX_CONCURRENT_CALLS = 4  # stays under free-tier rate limits
_semaphore = asyncio.Semaphore(MAX_CONCURRENT_CALLS)
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

# Free-tier reasoning models run at ~85 tokens/s, so a 6000-token structured
# answer needs 70 s or more before any queueing on the provider side.
LLM_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "180"))

# Output-token caps per stage. Reasoning models spend part of the budget
# thinking before they answer, so a tight cap truncates the JSON and wastes the call.
MAX_TOKENS = {
    "requirement": 4000,
    "testing": 8000,
    "compliance": 6000,
    "release": 8000,
    "summary": 2000,
    "chat": 2000,
}

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


def cooldown_remaining(name: str) -> int:
    return max(0, round(_cooldowns.get(name, 0) - time.monotonic()))


def _describe_failure(
    exc: Exception, response: ChatCompletion | None, max_tokens: int,
) -> tuple[AttemptOutcome, str]:
    """Plain-language reason a provider's answer was not used."""
    choices = getattr(response, "choices", None) or []
    truncated = bool(choices) and getattr(choices[0], "finish_reason", None) == "length"
    if isinstance(exc, (APITimeoutError, TimeoutError)):
        return "timeout", f"Timed out after {LLM_TIMEOUT_S:.0f} s"
    if isinstance(exc, APIStatusError):
        status = exc.status_code
        if status == 429:
            return "rate_limited", "Rate limited (429); skipping this provider for 60 s"
        if status == 402:
            return "rate_limited", "Out of credit (402); skipping this provider for 60 s"
        if status in {401, 403}:
            return "http_error", f"Rejected the request ({status}); check the key or model access"
        if 500 <= status < 600:
            return "http_error", f"Provider server error ({status})"
        return "http_error", f"Provider rejected the request ({status})"
    if isinstance(exc, APIConnectionError):
        return "connection_error", "Couldn't connect to the provider"
    if truncated:
        if isinstance(exc, _InvalidResponse):
            return "truncated", f"Spent the whole {max_tokens}-token budget (reasoning) without an answer"
        return "truncated", f"Cut off at the {max_tokens}-token limit before the JSON was complete"
    if isinstance(exc, json.JSONDecodeError):
        return "invalid_json", "Returned text that isn't valid JSON"
    if isinstance(exc, ValidationError):
        return "schema_mismatch", "Returned JSON without the expected fields"
    return "empty", str(exc) or "Returned an empty answer"


async def _complete_provider(
    provider: Provider,
    system: str,
    user: str,
    schema: type[BaseModel] | None,
    max_tokens: int,
    history: list[dict] | None = None,
    tier: Literal["fast", "strong"] = "fast",
) -> BaseModel | str:
    """Call one entry directly, including its retry policy (also used by smoke)."""
    if config.llm_disabled():
        raise NoLLM("LLM disabled or no keys configured")
    key = _key(provider)
    if not key:
        runs.attempt_skipped(provider.name, provider.model, tier, max_tokens, LLM_TIMEOUT_S,
                             f"No {provider.name} API key configured")
        raise NoLLM("Provider key missing")

    async with _semaphore:
        # Check after acquiring the slot: another in-flight call may set cooldown.
        if _cooldowns.get(provider.name, 0) > time.monotonic():
            runs.attempt_skipped(
                provider.name, provider.model, tier, max_tokens, LLM_TIMEOUT_S,
                f"Cooling down after a rate limit ({cooldown_remaining(provider.name)} s left)",
            )
            raise NoLLM("Provider cooling down")
        headers = None
        if provider.name == "openrouter":
            headers = {"X-Title": "ImpactIQ"}
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
                attempt = runs.attempt_started(
                    provider.name, provider.model, tier, max_tokens, LLM_TIMEOUT_S,
                )
                try:
                    async with asyncio.timeout(LLM_TIMEOUT_S):
                        response = await client.chat.completions.create(**request)
                    parsed = _parse_response(response, schema, tool_mode)
                    runs.attempt_finished(
                        attempt, "ok", f"Answered in {time.monotonic() - started:.0f} s",
                        _usage(response),
                    )
                    return parsed
                except _FALLBACK_ERRORS as exc:
                    error_class = type(exc).__name__
                    outcome, detail = _describe_failure(exc, response, max_tokens)
                    runs.attempt_finished(attempt, outcome, detail, _usage(response))
                    status = exc.status_code if isinstance(exc, APIStatusError) else None
                    if status in {429, 402}:
                        _cooldowns[provider.name] = time.monotonic() + 60
                    if (
                        status == 400 and provider.name == "tokenharbor"
                        and schema is not None and not tool_mode and not retried_tool
                    ):
                        tool_mode = retried_tool = True
                        continue
                    # A timed-out provider is likely to be slow again: move on
                    # rather than spend another full timeout on it.
                    transient = status is not None and 500 <= status < 600
                    if transient and not retried_transient:
                        retried_transient = True
                        continue
                    raise
                finally:
                    if attempt is not None and attempt.outcome == "running":
                        runs.attempt_finished(attempt, "empty", "Cancelled before the model answered")
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
        runs.log("No model is configured (LLM disabled or no API keys); using the built-in fallback")
        raise NoLLM("LLM disabled or no keys configured")
    for provider in _provider_entries(tier):
        try:
            result = await _complete_provider(
                provider, system, user, schema, max_tokens, history, tier,
            )
            return result, provider.label
        except (NoLLM, *_FALLBACK_ERRORS):
            continue
    runs.log("Every model in the chain failed; using the built-in fallback", "warning")
    # Do not chain provider errors: SDK exceptions can include request details.
    raise NoLLM("All providers unavailable or returned invalid output") from None


def _usage(response: ChatCompletion | None) -> dict | None:
    usage = getattr(response, "usage", None)
    return usage.model_dump() if usage is not None else None


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
