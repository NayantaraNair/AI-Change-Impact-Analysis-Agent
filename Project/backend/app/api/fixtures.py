"""Serve saved demo results for unchanged demo input.

Fixtures are built with the live LLM chain (scripts/build_fixtures.py), so the
demo stories answer instantly in every mode. `?refresh=true` runs the pipeline.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, ValidationError

from app import config
from app.architecture import demo_backlogs, load_demo_sprint
from app.contracts import DemoSprint, SprintAnalysis, SprintRequest, StoryAnalysis, StoryInput


def _load(path: Path, schema: type[BaseModel]):
    try:
        return schema.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, ValidationError):
        return None


def story_fixture(story: StoryInput) -> StoryAnalysis | None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", story.id) or len(story.id) > 100:
        return None
    analysis = _load(Path(config.FIXTURES_DIR) / f"story-{story.id}.json", StoryAnalysis)
    return analysis if analysis and analysis.story == story else None


def _fixture_name(backlog: DemoSprint) -> str:
    return "sprint.json" if backlog.sprint_id == load_demo_sprint().sprint_id else f"{backlog.sprint_id}.json"


def demo_backlog_for(request: SprintRequest) -> DemoSprint | None:
    """The demo backlog a request asks for: by its stories, or by ID with no stories."""
    for backlog in demo_backlogs():
        if request.stories == backlog.stories or (
            not request.stories and request.sprint_id == backlog.sprint_id
        ):
            return backlog
    if not request.stories:
        return load_demo_sprint()
    return None


def sprint_fixture(request: SprintRequest) -> SprintAnalysis | None:
    backlog = demo_backlog_for(request)
    if backlog is None:
        return None
    analysis = _load(Path(config.FIXTURES_DIR) / _fixture_name(backlog), SprintAnalysis)
    if analysis is None or [a.story for a in analysis.stories] != backlog.stories:
        return None
    return analysis.model_copy(update={
        "sprint_id": request.sprint_id or backlog.sprint_id,
        "name": request.name or backlog.name,
    })
