"""Background runs with live progress, plus the debug view of the model chain.

POST starts the work and returns a run ID at once; the client polls
GET /runs/{id} for stages, every LLM attempt and the log, and finally the result.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException

from app import config, llm, runs
from app.api import routes_analysis, routes_sprint
from app.contracts import DebugInfo, ProviderInfo, Run, RunStarted, SprintRequest, StoryInput

router = APIRouter()


@router.post("/runs/story", response_model=RunStarted, status_code=202)
async def start_story(story: StoryInput, refresh: bool = False) -> RunStarted:
    run = runs.launch(
        "story", f"{story.id}: {story.title}", [story.id], runs.story_plan([story.id]),
        lambda: routes_analysis.execute(story, refresh),
    )
    return RunStarted(run_id=run.id)


@router.post("/runs/sprint", response_model=RunStarted, status_code=202)
async def start_sprint(request: SprintRequest, refresh: bool = False) -> RunStarted:
    _, name, stories = routes_sprint.resolve(request)  # reject bad input before starting
    ids = [story.id for story in stories]
    run = runs.launch(
        "sprint", name, ids, runs.story_plan(ids, sprint=True),
        lambda: routes_sprint.execute(request, refresh),
    )
    return RunStarted(run_id=run.id)


@router.get("/runs", response_model=list[Run])
def recent_runs() -> list[Run]:
    return runs.recent()


@router.get("/runs/{run_id}", response_model=Run)
def get_run(run_id: str) -> Run:
    run = runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found. Runs are kept in memory and reset when the backend restarts.")
    return run


@router.get("/debug", response_model=DebugInfo)
def debug() -> DebugInfo:
    configured = llm.providers_configured()
    fixtures = Path(config.FIXTURES_DIR)
    return DebugInfo(
        llm_disabled=config.llm_disabled(),
        providers=[
            ProviderInfo(
                order=index, name=provider.name, model=provider.model,
                host=urlparse(provider.base_url).netloc,
                configured=configured.get(provider.name, False),
                tool_calling_only=provider.tool_only,
                cooling_down_s=llm.cooldown_remaining(provider.name),
            )
            for index, provider in enumerate(llm.PROVIDERS, start=1)
        ],
        strong_tier_model=llm.TOKENHARBOR_STRONG_MODEL,
        timeout_s=llm.LLM_TIMEOUT_S,
        max_concurrent_calls=llm.MAX_CONCURRENT_CALLS,
        max_tokens=llm.MAX_TOKENS,
        cache_enabled=True,
        fixtures_available=sorted(path.stem for path in fixtures.glob("*.json")) if fixtures.is_dir() else [],
    )
