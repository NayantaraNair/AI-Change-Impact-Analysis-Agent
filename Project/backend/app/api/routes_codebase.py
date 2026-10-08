"""Codebase impact: map a story onto a real repository's services, files and classes."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app import config, runs
from app.codebase.fetch import RepoError, parse_url
from app.codebase.pipeline import analyze_codebase
from app.contracts import CodebaseAnalysis, CodebaseRequest, RunStarted

router = APIRouter()
FIXTURE = "codebase-demo.json"


def demo_request() -> CodebaseRequest | None:
    path = Path(config.DEMO_CODEBASE_PATH)
    return CodebaseRequest.model_validate(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else None


def codebase_fixture(request: CodebaseRequest) -> CodebaseAnalysis | None:
    if request != demo_request():
        return None
    try:
        analysis = CodebaseAnalysis.model_validate_json((Path(config.FIXTURES_DIR) / FIXTURE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return analysis if analysis.story == request.story and analysis.repo.repo_url == request.repo_url else None


async def execute(request: CodebaseRequest, refresh: bool) -> CodebaseAnalysis:
    fixture = None if refresh else codebase_fixture(request)
    if fixture is not None:
        runs.serve_fixture()
        return fixture
    return await analyze_codebase(request)


def _check(request: CodebaseRequest) -> None:
    try:
        parse_url(request.repo_url)
    except RepoError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.get("/demo-codebase", response_model=CodebaseRequest)
def demo_codebase() -> CodebaseRequest:
    request = demo_request()
    if request is None:
        raise HTTPException(status_code=404, detail="No demo codebase is configured.")
    return request


@router.post("/codebase/analyze", response_model=CodebaseAnalysis)
async def analyze(request: CodebaseRequest, refresh: bool = False) -> CodebaseAnalysis:
    _check(request)
    try:
        return await execute(request, refresh)
    except RepoError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.post("/runs/codebase", response_model=RunStarted, status_code=202)
async def start(request: CodebaseRequest, refresh: bool = False) -> RunStarted:
    _check(request)
    run = runs.launch(
        "codebase", f"{request.story.id}: {request.story.title}", [request.story.id],
        [(request.story.id, stage) for stage in runs.CODEBASE_STAGES],
        lambda: execute(request, refresh),
    )
    return RunStarted(run_id=run.id)
