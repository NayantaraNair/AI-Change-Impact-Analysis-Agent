"""Explicit live diagnostic: run from backend with uv run python ../scripts/llm_smoke.py."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from pydantic import BaseModel

from app import llm


class SmokeFacts(BaseModel):
    ok: bool


async def main() -> None:
    print("provider | model | ok/fail | latency | error class")
    for provider in llm.PROVIDERS:
        started = time.monotonic()
        status, error = "ok", "-"
        try:
            result = await llm._complete_provider(
                provider, "Extract the requested JSON fact.",
                'Return {"ok": true}.', SmokeFacts, 64,
            )
            if not result.ok:
                status, error = "fail", "UnexpectedValue"
        except Exception as exc:
            status, error = "fail", type(exc).__name__
        print(
            f"{provider.name} | {provider.model} | {status} | "
            f"{time.monotonic() - started:.3f}s | {error}"
        )


if __name__ == "__main__":
    asyncio.run(main())
