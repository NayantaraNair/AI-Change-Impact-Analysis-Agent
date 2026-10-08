"""Default to deterministic mode; provider tests explicitly enable mocked clients."""

import pytest


@pytest.fixture(autouse=True)
def disable_live_llm(monkeypatch):
    monkeypatch.setenv("LLM_DISABLED", "1")
