"""Provider policy tests use only mocked SDK clients, never network calls."""

import asyncio
import runpy
from collections import defaultdict, deque
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from openai import APIConnectionError, APIStatusError, APITimeoutError
from pydantic import BaseModel

from app import llm


class Facts(BaseModel):
    affected: bool


def response(content='{"affected": true}', *, tool=False, choices=True):
    calls = [SimpleNamespace(function=SimpleNamespace(
        name="extract_facts", arguments=content,
    ))] if tool else None
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(
            content=None if tool else content, tool_calls=calls,
        ))] if choices else [],
        usage=SimpleNamespace(model_dump=lambda: {"total_tokens": 12}),
    )


def http_error(status):
    return APIStatusError(
        "mock error", response=httpx.Response(status, request=httpx.Request("POST", "https://mock.invalid")),
        body=None,
    )


@pytest.fixture
def mock_chain(monkeypatch):
    monkeypatch.setenv("LLM_DISABLED", "0")
    monkeypatch.setenv("TOKENHARBOR_API_KEY", "fake-tokenharbor-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-openrouter-key")
    monkeypatch.setattr(llm, "_cooldowns", {})
    monkeypatch.setattr(llm, "_semaphore", asyncio.Semaphore(4))
    outcomes = defaultdict(deque)
    calls, clients = [], []

    async def create(**kwargs):
        calls.append(kwargs)
        queue = outcomes[kwargs["model"]]
        if not queue:
            raise AssertionError(f"Unexpected call to {kwargs['model']}")
        outcome = queue.popleft()
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def factory(**kwargs):
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.chat.completions.create.side_effect = create
        clients.append(kwargs)
        return client

    monkeypatch.setattr(llm, "AsyncOpenAI", factory)
    return SimpleNamespace(outcomes=outcomes, calls=calls, clients=clients)


async def extract():
    return await llm.complete_structured("Extract facts.", "A change.", Facts)


@pytest.mark.parametrize("status", [429, 402, 401, 403])
async def test_http_errors_move_to_next_provider(mock_chain, status):
    first, second = llm.PROVIDERS[:2]
    mock_chain.outcomes[first.model].append(http_error(status))
    mock_chain.outcomes[second.model].append(response())
    facts, label = await extract()
    assert facts == Facts(affected=True)
    assert label == second.label
    assert [call["model"] for call in mock_chain.calls] == [first.model, second.model]
    assert (first.name in llm._cooldowns) == (status in {429, 402})


@pytest.mark.parametrize("content", ["not json", '{"affected": "not-a-bool"}'])
async def test_invalid_json_or_validation_moves_to_next_provider(mock_chain, content):
    first, second = llm.PROVIDERS[:2]
    mock_chain.outcomes[first.model].append(response(content))
    mock_chain.outcomes[second.model].append(response())
    assert (await extract())[1] == second.label
    assert len(mock_chain.calls) == 2


async def test_no_keys_raises_without_client(monkeypatch, mock_chain):
    monkeypatch.delenv("TOKENHARBOR_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert llm.providers_configured() == {"tokenharbor": False, "openrouter": False}
    with pytest.raises(llm.NoLLM):
        await extract()
    assert not mock_chain.clients


async def test_disabled_raises_without_client(monkeypatch, mock_chain):
    monkeypatch.setenv("LLM_DISABLED", "1")
    with pytest.raises(llm.NoLLM):
        await extract()
    with pytest.raises(llm.NoLLM):
        await llm.complete_text("system", "user")
    assert not mock_chain.clients


async def test_missing_key_skips_provider_and_keys_are_read_at_call_time(monkeypatch, mock_chain):
    first, second = llm.PROVIDERS[:2]
    monkeypatch.delenv("TOKENHARBOR_API_KEY")
    mock_chain.outcomes[second.model].append(response())
    assert (await extract())[1] == second.label
    monkeypatch.setenv("TOKENHARBOR_API_KEY", "updated-fake-key")
    mock_chain.outcomes[first.model].append(response())
    assert (await extract())[1] == first.label
    assert mock_chain.clients[-1]["api_key"] == "updated-fake-key"


@pytest.mark.parametrize("status", [429, 402])
async def test_cooldown_expires_after_sixty_seconds(monkeypatch, mock_chain, status):
    now = [100.0]
    monkeypatch.setattr(llm.time, "monotonic", lambda: now[0])
    first, second = llm.PROVIDERS[:2]
    mock_chain.outcomes[first.model].extend([http_error(status), response()])
    mock_chain.outcomes[second.model].extend([response(), response()])
    assert (await extract())[1] == second.label
    now[0] = 159.9
    assert (await extract())[1] == second.label
    now[0] = 160.0
    assert (await extract())[1] == first.label
    assert [call["model"] for call in mock_chain.calls] == [
        first.model, second.model, second.model, first.model,
    ]


async def test_openrouter_quota_cools_all_models(mock_chain, monkeypatch):
    monkeypatch.delenv("TOKENHARBOR_API_KEY")
    mock_chain.outcomes[llm.PROVIDERS[1].model].append(http_error(429))
    with pytest.raises(llm.NoLLM):
        await extract()
    assert len(mock_chain.calls) == 1


@pytest.mark.parametrize("retry_succeeds", [True, False])
async def test_5xx_retries_same_provider_once(mock_chain, retry_succeeds):
    first, second = llm.PROVIDERS[:2]
    error = http_error(503)
    mock_chain.outcomes[first.model].extend([error, response() if retry_succeeds else error])
    if not retry_succeeds:
        mock_chain.outcomes[second.model].append(response())
    assert (await extract())[1] == (first.label if retry_succeeds else second.label)
    assert [call["model"] for call in mock_chain.calls][:2] == [first.model, first.model]
    assert len(mock_chain.calls) == (2 if retry_succeeds else 3)
    assert mock_chain.clients[0]["max_retries"] == 0
    assert mock_chain.clients[0]["timeout"] == llm.LLM_TIMEOUT_S


@pytest.mark.parametrize("error_kind", ["sdk_timeout", "deadline"])
async def test_timeout_moves_to_next_provider_without_retry(mock_chain, error_kind):
    first, second = llm.PROVIDERS[:2]
    mock_chain.outcomes[first.model].append({
        "sdk_timeout": APITimeoutError(request=httpx.Request("POST", "https://mock.invalid")),
        "deadline": TimeoutError(),
    }[error_kind])
    mock_chain.outcomes[second.model].append(response())
    assert (await extract())[1] == second.label
    assert [call["model"] for call in mock_chain.calls] == [first.model, second.model]


async def test_connection_error_does_not_retry(mock_chain):
    first, second = llm.PROVIDERS[:2]
    mock_chain.outcomes[first.model].append(APIConnectionError(
        request=httpx.Request("POST", "https://mock.invalid"),
    ))
    mock_chain.outcomes[second.model].append(response())
    assert (await extract())[1] == second.label
    assert len(mock_chain.calls) == 2


async def test_tokenharbor_400_switches_to_forced_tool_call(mock_chain):
    first = llm.PROVIDERS[0]
    mock_chain.outcomes[first.model].extend([http_error(400), response(tool=True)])
    assert (await extract())[1] == first.label
    initial, retry = mock_chain.calls
    assert initial["response_format"]["type"] == "json_schema"
    assert "response_format" not in retry
    assert retry["tool_choice"] == {"type": "function", "function": {"name": "extract_facts"}}
    assert retry["tools"][0]["function"]["parameters"] == Facts.model_json_schema()
    assert retry["temperature"] == 0
    assert '"properties"' in retry["messages"][0]["content"]


async def test_tool_retry_failure_moves_on(mock_chain):
    first, second = llm.PROVIDERS[:2]
    mock_chain.outcomes[first.model].extend([http_error(400), http_error(400)])
    mock_chain.outcomes[second.model].append(response())
    assert (await extract())[1] == second.label
    assert len(mock_chain.calls) == 3


async def test_missing_forced_tool_output_moves_on(monkeypatch, mock_chain):
    monkeypatch.delenv("TOKENHARBOR_API_KEY")
    second, third, fourth = llm.PROVIDERS[1:]
    mock_chain.outcomes[second.model].append(response("invalid"))
    mock_chain.outcomes[third.model].append(response())
    mock_chain.outcomes[fourth.model].append(response())
    assert (await extract())[1] == fourth.label


async def test_openrouter_400_does_not_retry_tool_mode(monkeypatch, mock_chain):
    monkeypatch.delenv("TOKENHARBOR_API_KEY")
    second, third = llm.PROVIDERS[1:3]
    mock_chain.outcomes[second.model].append(http_error(400))
    mock_chain.outcomes[third.model].append(response(tool=True))
    assert (await extract())[1] == third.label
    assert len(mock_chain.calls) == 2


async def test_inkling_tool_only_and_openrouter_headers(monkeypatch, mock_chain):
    monkeypatch.delenv("TOKENHARBOR_API_KEY")
    monkeypatch.setenv("OPENROUTER_HTTP_REFERER", "https://copilot.example")
    second, third = llm.PROVIDERS[1:3]
    mock_chain.outcomes[second.model].append(response("invalid"))
    mock_chain.outcomes[third.model].append(response(tool=True))
    assert (await extract())[1] == third.label
    assert "response_format" not in mock_chain.calls[1]
    assert "tool_choice" in mock_chain.calls[1]
    assert mock_chain.clients[-1]["default_headers"] == {
        "X-Title": "Change Impact Copilot", "HTTP-Referer": "https://copilot.example",
    }


async def test_free_router_is_last_fallback(mock_chain):
    for provider in llm.PROVIDERS[:-1]:
        mock_chain.outcomes[provider.model].append(response("invalid", tool=provider.tool_only))
    mock_chain.outcomes[llm.PROVIDERS[-1].model].append(response())
    assert (await extract())[1] == llm.PROVIDERS[-1].label
    assert "response_format" in mock_chain.calls[-1]


async def test_exhaustion_raises_nollm(mock_chain):
    for provider in llm.PROVIDERS:
        mock_chain.outcomes[provider.model].append(response(choices=False))
    with pytest.raises(llm.NoLLM, match="All providers") as error:
        await extract()
    assert error.value.__cause__ is None


async def test_code_fences_and_safe_logging(mock_chain, caplog):
    mock_chain.outcomes[llm.PROVIDERS[0].model].append(response('```json\n{"affected": true}\n```'))
    with caplog.at_level("INFO", logger="app.llm"):
        facts, _ = await llm.complete_structured("PRIVATE-SYSTEM", "PRIVATE-USER", Facts)
    assert facts.affected
    assert "total_tokens" in caplog.text and "latency_ms" in caplog.text
    for secret in ["PRIVATE-SYSTEM", "PRIVATE-USER", "fake-tokenharbor-key"]:
        assert secret not in caplog.text


async def test_strong_tier_uses_strong_model(mock_chain):
    mock_chain.outcomes["deepseek-v4.1-flash:free"].append(response())
    assert (await llm.complete_structured("system", "user", Facts, tier="strong"))[1] == "tokenharbor:deepseek-v4.1-flash:free"


async def test_text_temperature_and_history(mock_chain):
    mock_chain.outcomes[llm.PROVIDERS[0].model].append(response("Explanation."))
    history = [{"role": "assistant", "content": "Earlier answer"}]
    text, label = await llm.complete_text("system", "user", history, max_tokens=50)
    request = mock_chain.calls[0]
    assert text == "Explanation." and label == llm.PROVIDERS[0].label
    assert request["messages"] == [{"role": "system", "content": "system"}, *history, {"role": "user", "content": "user"}]
    assert request["temperature"] == 0.3 and request["max_tokens"] == 50
    assert "tools" not in request and "response_format" not in request
    assert history == [{"role": "assistant", "content": "Earlier answer"}]


async def test_empty_text_moves_to_next_provider(mock_chain):
    first, second = llm.PROVIDERS[:2]
    mock_chain.outcomes[first.model].append(response(" "))
    mock_chain.outcomes[second.model].append(response("Answer"))
    assert await llm.complete_text("system", "user") == ("Answer", second.label)


async def test_smoke_calls_each_entry_directly_and_prints_only_error_class(monkeypatch, capsys):
    script = Path(__file__).resolve().parents[2] / "scripts" / "llm_smoke.py"
    namespace = runpy.run_path(str(script), run_name="smoke_test")
    called = []

    async def direct(provider, system, user, schema, max_tokens):
        called.append(provider)
        if provider == llm.PROVIDERS[0]:
            raise ValueError("PRIVATE-EXCEPTION-DETAIL")
        return schema(ok=True)

    monkeypatch.setattr(llm, "_complete_provider", direct)
    await namespace["main"]()
    output = capsys.readouterr().out
    assert called == list(llm.PROVIDERS)
    assert len(output.splitlines()) == 5
    assert "ValueError" in output and "PRIVATE-EXCEPTION-DETAIL" not in output
    assert output.count(" | ok | ") == 3


async def test_concurrency_limited_to_four(mock_chain, monkeypatch):
    active = maximum = 0
    four_started, release = asyncio.Event(), asyncio.Event()

    async def create(**kwargs):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        if active == 4:
            four_started.set()
        try:
            await release.wait()
            return response()
        finally:
            active -= 1

    def factory(**kwargs):
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.chat.completions.create.side_effect = create
        return client

    monkeypatch.setattr(llm, "AsyncOpenAI", factory)
    tasks = [asyncio.create_task(extract()) for _ in range(8)]
    try:
        await asyncio.wait_for(four_started.wait(), timeout=2)
        assert active == 4
    finally:
        release.set()
        await asyncio.gather(*tasks)
    assert maximum == 4
