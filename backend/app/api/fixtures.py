"""Serve validated, exact-input demo fixtures only in disabled-LLM mode."""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, ValidationError

from app import config
from app.architecture import load_demo_sprint
from app.contracts import SprintAnalysis, SprintRequest, StoryAnalysis, StoryInput


def _load(path: Path, schema: type[BaseModel]):
    try:
        return schema.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, ValidationError):
        return None


def story_fixture(story: StoryInput) -> StoryAnalysis | None:
    if not config.llm_disabled():
        return None
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", story.id) or len(story.id) > 100:
        return None
    analysis = _load(Path(config.FIXTURES_DIR) / f"story-{story.id}.json", StoryAnalysis)
    return analysis if analysis and analysis.story == story else None


def sprint_fixture(request: SprintRequest) -> SprintAnalysis | None:
    if not config.llm_disabled():
        return None
    demo = load_demo_sprint()
    stories = request.stories or demo.stories
    if stories != demo.stories:
        return None
    analysis = _load(Path(config.FIXTURES_DIR) / "sprint.json", SprintAnalysis)
    if analysis is None or [a.story for a in analysis.stories] != demo.stories:
        return None
    return analysis.model_copy(update={
        "sprint_id": request.sprint_id or demo.sprint_id,
        "name": request.name or demo.name,
    })
