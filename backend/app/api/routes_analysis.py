"""Story analysis and persisted reports."""

import asyncio

from fastapi import APIRouter, HTTPException

from app import db, pipeline
from app.api.fixtures import story_fixture
from app.architecture import get_architecture, load_demo_sprint
from app.contracts import Architecture, DemoSprint, ImpactGraph, StoryAnalysis, StoryInput

router = APIRouter()


@router.post("/analyze", response_model=StoryAnalysis)
async def analyze(story: StoryInput, refresh: bool = False) -> StoryAnalysis:
    fixture = None if refresh else story_fixture(story)
    if fixture is not None:
        # SQLite work belongs off the event loop, including the fixture path.
        await asyncio.to_thread(db.save_analysis, fixture)
        return fixture
    return await pipeline.analyze_story(story, refresh=refresh)


@router.get("/architecture", response_model=Architecture)
def architecture() -> Architecture:
    return get_architecture()


@router.get("/demo-sprint", response_model=DemoSprint)
def demo_sprint() -> DemoSprint:
    return load_demo_sprint()


def _latest(story_id: str) -> StoryAnalysis:
    analysis = db.latest_story_analysis(story_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Story analysis not found")
    return analysis


@router.get("/dependency-graph/{story_id}", response_model=ImpactGraph)
def dependency_graph(story_id: str) -> ImpactGraph:
    return _latest(story_id).graph


@router.get("/report/{story_id}", response_model=StoryAnalysis)
def report(story_id: str) -> StoryAnalysis:
    return _latest(story_id)
