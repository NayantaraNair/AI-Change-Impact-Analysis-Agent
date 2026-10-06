"""Build demo fixtures from the pipeline and copilot, using configured providers.

Run from backend: uv run python ../scripts/build_fixtures.py [--refresh]
Set LLM_DISABLED=1 for an entirely offline build. For live prose, first run
llm_smoke.py with working keys, then run this script with --refresh.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from pydantic import BaseModel  # noqa: E402

from app import config  # noqa: E402
from app.agents import chat  # noqa: E402
from app.architecture import load_demo_sprint  # noqa: E402
from app.contracts import ChatRequest  # noqa: E402
from app.engine.sprint import analyze_sprint  # noqa: E402

FIXTURE_DIRS = (
    REPO_ROOT / "data" / "fixtures",
    REPO_ROOT / "frontend" / "public" / "fixtures",
)


def _check_id(context_id: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", context_id):
        raise ValueError("Demo context IDs must be safe fixture filename components")


async def build_fixtures(
    *, refresh: bool = False, directories: tuple[Path, ...] = FIXTURE_DIRS,
) -> dict[str, BaseModel]:
    demo = load_demo_sprint()
    _check_id(demo.sprint_id)
    for story in demo.stories:
        _check_id(story.id)

    sprint = await analyze_sprint(
        demo.sprint_id, demo.name, demo.stories, refresh=refresh,
    )
    fixtures: dict[str, BaseModel] = {"demo-sprint.json": demo, "sprint.json": sprint}
    for analysis in sprint.stories:
        # These are the final, post-conflict release assessments.
        fixtures[f"story-{analysis.story.id}.json"] = analysis

    contexts = [("story", story.story.id) for story in sprint.stories]
    contexts.append(("sprint", sprint.sprint_id))
    chat_providers: Counter[str] = Counter()
    session_prefix = uuid4().hex
    for context_type, context_id in contexts:
        for index, question in enumerate(chat.STARTER_QUESTIONS):
            # Each canned answer is an independent first turn.
            response = await chat.answer(ChatRequest(
                session_id=f"fixture-{session_prefix}-{context_type}-{context_id}-{index}",
                context_type=context_type, context_id=context_id, message=question,
            ))
            if response.provider == "none":
                raise RuntimeError(f"No saved analysis for fixture context {context_id}")
            fixtures[f"chat-{context_id}-{index}.json"] = response
            chat_providers[response.provider] += 1

    # Build everything successfully before replacing the previous fixture set.
    serialized = {name: model.model_dump_json(indent=2) + "\n"
                  for name, model in fixtures.items()}
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        for stale in directory.glob("*.json"):
            if stale.is_file():
                stale.unlink()
        for name, payload in serialized.items():
            (directory / name).write_text(payload, encoding="utf-8", newline="\n")

    providers: dict[str, Counter[str]] = defaultdict(Counter)
    for analysis in sprint.stories:
        for stage, provider in analysis.providers_used.items():
            providers[stage][provider] += 1
    print(f"Wrote {len(fixtures)} fixtures to each of {len(directories)} folders.")
    for stage, counts in sorted(providers.items()):
        print(f"{stage}: " + ", ".join(f"{p} ({n})" for p, n in sorted(counts.items())))
    print("chat: " + ", ".join(f"{p} ({n})" for p, n in sorted(chat_providers.items())))
    print("Decisions: " + ", ".join(
        f"{analysis.story.id}={analysis.release.decision}" for analysis in sprint.stories
    ))
    print(f"Conflicts: {len(sprint.conflicts)}")
    if config.llm_disabled() or any(
        provider.endswith("fallback") for counts in providers.values() for provider in counts
    ) or "template" in chat_providers:
        print("fixtures need regenerating with keys")
    return fixtures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Recompute cached pipeline stages")
    args = parser.parse_args()
    asyncio.run(build_fixtures(refresh=args.refresh))


if __name__ == "__main__":
    main()
