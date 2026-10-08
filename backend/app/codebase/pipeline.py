"""Codebase impact run: fetch -> services -> files -> classes/APIs/tables -> tests."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

from app import runs
from app.codebase.agent import derive_impacts, map_files, map_services, plan_dev_tests
from app.codebase.fetch import fetch_repo
from app.codebase.index import build_index
from app.contracts import CodebaseAnalysis, CodebaseRequest, RepoIndex

_INDEX_TTL_S = 600
_indexes: dict[str, tuple[float, RepoIndex]] = {}
_lock = asyncio.Lock()


async def load_index(repo_url: str) -> tuple[RepoIndex, bool]:
    """Index a repository, reusing one fetched in the last ten minutes."""
    async with _lock:
        cached = _indexes.get(repo_url)
        if cached and time.monotonic() - cached[0] < _INDEX_TTL_S:
            return cached[1], True
    files = await fetch_repo(repo_url)
    index = build_index(repo_url, files.ref.ref, files.ref.path, files.tree, files.texts, files.truncated)
    async with _lock:
        _indexes[repo_url] = (time.monotonic(), index)
        while len(_indexes) > 10:
            _indexes.pop(next(iter(_indexes)))
    return index, False


async def analyze_codebase(request: CodebaseRequest) -> CodebaseAnalysis:
    started = time.perf_counter()
    story = request.story
    with runs.story_scope(story.id):
        with runs.stage("fetch_repo") as item:
            index, cached = await load_index(request.repo_url)
            runs.describe(item, "deterministic", (
                f"{'Reused' if cached else 'Read'} {len(index.tree)} files; indexed {len(index.files)} source files "
                f"in {len(index.services)} services" + (" (capped)" if index.truncated else "")
            ))
        with runs.stage("map_services") as item:
            services, service_provider = await map_services(story, index)
            runs.describe(item, service_provider, "Services to change: " + (", ".join(name for name, _ in services) or "none found"))
        with runs.stage("map_files") as item:
            picks, file_provider = await map_files(story, index, [name for name, _ in services])
            runs.describe(item, file_provider, f"{len(picks)} files to change")
        with runs.stage("map_classes") as item:
            files, impacts = derive_impacts(index, services, picks)
            classes = sum(len(impact.classes) for impact in impacts)
            apis = sum(len(impact.apis) for impact in impacts)
            tables = sorted({table for impact in impacts for table in impact.tables})
            runs.describe(item, "deterministic", f"{classes} classes, {apis} APIs, {len(tables)} tables" + (f": {', '.join(tables[:4])}" if tables else ""))
        with runs.stage("plan_tests") as item:
            tests, test_provider = await plan_dev_tests(story, impacts)
            runs.describe(item, test_provider, f"{len(tests)} tests: " + ", ".join(sorted({test.category for test in tests})))
    summary = (
        f"Changes {len(impacts)} service{'s' if len(impacts) != 1 else ''} "
        f"({', '.join(impact.service for impact in impacts) or 'none'}): {len(files)} files, "
        f"{classes} classes, {apis} APIs and {len(tables)} database tables."
    )
    return CodebaseAnalysis(
        story=story, repo=index, summary=summary, services=impacts, files=files, tests=tests,
        providers_used={
            "fetch_repo": "deterministic", "map_services": service_provider, "map_files": file_provider,
            "map_classes": "deterministic", "plan_tests": test_provider,
        },
        duration_ms=round((time.perf_counter() - started) * 1000),
        created_at=datetime.now(timezone.utc),
    )
