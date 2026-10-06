"""Sprint analysis endpoints with exact-input demo fixture support."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app import db
from app.api.fixtures import sprint_fixture
from app.architecture import load_demo_sprint
from app.contracts import SprintAnalysis, SprintRequest
from app.engine import sprint as sprint_engine

router = APIRouter()


@router.post("/analyze-sprint", response_model=SprintAnalysis)
async def analyze_sprint(request: SprintRequest, refresh: bool = False) -> SprintAnalysis:
    fixture = None if refresh else sprint_fixture(request)
    if fixture is not None:
        await asyncio.to_thread(db.save_sprint, fixture)
        return fixture
    demo = load_demo_sprint()
    stories = request.stories or demo.stories
    if len({story.id for story in stories}) != len(stories):
        raise HTTPException(status_code=422, detail="Story IDs must be unique within a sprint")
    is_demo = stories == demo.stories
    return await sprint_engine.analyze_sprint(
        request.sprint_id or (demo.sprint_id if is_demo else f"sprint-{uuid4().hex}"),
        request.name or (demo.name if is_demo else "Custom sprint"),
        stories, refresh=refresh,
    )


@router.get("/sprint/{sprint_id}", response_model=SprintAnalysis)
def sprint(sprint_id: str) -> SprintAnalysis:
    analysis = db.latest_sprint(sprint_id)
    if analysis is None and sprint_id == load_demo_sprint().sprint_id:
        # A fresh database still has the saved demo sprint.
        analysis = sprint_fixture(SprintRequest(sprint_id=sprint_id))
    if analysis is None:
        raise HTTPException(status_code=404, detail="Sprint analysis not found")
    return analysis
