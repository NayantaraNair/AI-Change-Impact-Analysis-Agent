"""Sprint analysis endpoints with exact-input demo fixture support."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app import db, runs
from app.api.fixtures import demo_backlog_for, sprint_fixture
from app.architecture import demo_backlogs, load_demo_sprint
from app.contracts import SprintAnalysis, SprintRequest, StoryInput
from app.engine import sprint as sprint_engine

router = APIRouter()


def resolve(request: SprintRequest) -> tuple[str, str, list[StoryInput]]:
    """Sprint ID, name and stories for a request; raises 422 on duplicate story IDs."""
    demo = demo_backlog_for(request) or load_demo_sprint()
    stories = request.stories or demo.stories
    if len({story.id for story in stories}) != len(stories):
        raise HTTPException(status_code=422, detail="Story IDs must be unique within a sprint")
    is_demo = stories == demo.stories
    return (
        request.sprint_id or (demo.sprint_id if is_demo else f"sprint-{uuid4().hex}"),
        request.name or (demo.name if is_demo else "Custom sprint"),
        stories,
    )


async def execute(request: SprintRequest, refresh: bool) -> SprintAnalysis:
    fixture = None if refresh else sprint_fixture(request)
    if fixture is not None:
        runs.serve_fixture()
        await asyncio.to_thread(db.save_sprint, fixture)
        return fixture
    sprint_id, name, stories = resolve(request)
    return await sprint_engine.analyze_sprint(sprint_id, name, stories, refresh=refresh)


@router.post("/analyze-sprint", response_model=SprintAnalysis)
async def analyze_sprint(request: SprintRequest, refresh: bool = False) -> SprintAnalysis:
    return await execute(request, refresh)


@router.get("/sprint/{sprint_id}", response_model=SprintAnalysis)
def sprint(sprint_id: str) -> SprintAnalysis:
    analysis = db.latest_sprint(sprint_id)
    if analysis is None and any(backlog.sprint_id == sprint_id for backlog in demo_backlogs()):
        # A fresh database still has the saved demo backlogs.
        analysis = sprint_fixture(SprintRequest(sprint_id=sprint_id))
    if analysis is None:
        raise HTTPException(status_code=404, detail="Sprint analysis not found")
    return analysis
