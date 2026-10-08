"""In-memory run tracking for live progress: stages, every LLM attempt and a log.

The active run lives in a context variable, so code deep in the pipeline
(including the LLM provider chain) reports into whichever run started it
without threading it through every call. Outside a run, tracking is a no-op,
which keeps the synchronous endpoints and the tests unchanged.
"""

from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from itertools import count
from uuid import uuid4

from app.contracts import (
    AttemptOutcome, CodebaseAnalysis, LlmAttempt, Run, RunKind, RunLogEntry, SprintAnalysis,
    StageProgress, StoryAnalysis,
)

logger = logging.getLogger(__name__)

STORY_STAGES = ("requirement", "dependency", "scoring", "testing", "compliance", "release")
SPRINT_STAGES = ("conflicts", "recheck", "summary")
STAGE_LABELS = {
    "requirement": "Read the story",
    "dependency": "Map dependencies",
    "scoring": "Score risk",
    "testing": "Plan tests",
    "compliance": "Check compliance",
    "release": "Decide release",
    "conflicts": "Detect conflicts",
    "recheck": "Re-check releases with conflicts",
    "summary": "Write sprint summary",
    "answer": "Answer the question",
    "fetch_repo": "Read the repository",
    "map_services": "Map the story to services",
    "map_files": "Find the files to change",
    "map_classes": "Find classes, APIs and tables",
    "plan_tests": "Plan the developer tests",
}
CODEBASE_STAGES = ("fetch_repo", "map_services", "map_files", "map_classes", "plan_tests")
_MAX_RUNS = 30
_MAX_LOG = 400

_runs: OrderedDict[str, Run] = OrderedDict()
_tasks: set[asyncio.Task] = set()
_attempt_ids = count(1)
_current: ContextVar[Run | None] = ContextVar("current_run", default=None)
_story: ContextVar[str | None] = ContextVar("current_story", default=None)
_stage: ContextVar[str | None] = ContextVar("current_stage", default=None)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ms_since(start: datetime) -> int:
    return max(0, round((_now() - start).total_seconds() * 1000))


def _create(kind: RunKind, title: str, story_ids: list[str], plan: list[tuple[str | None, str]]) -> Run:
    run = Run(
        id=uuid4().hex[:12], kind=kind, status="running", title=title,
        story_ids=story_ids, started_at=_now(), elapsed_ms=0,
        stages=[
            StageProgress(story_id=story_id, stage=stage, label=STAGE_LABELS.get(stage, stage), status="pending")
            for story_id, stage in plan
        ],
        attempts=[], log=[],
    )
    _runs[run.id] = run
    while len(_runs) > _MAX_RUNS:
        _runs.popitem(last=False)
    return run


def story_plan(story_ids: list[str], sprint: bool = False) -> list[tuple[str | None, str]]:
    plan: list[tuple[str | None, str]] = [(sid, stage) for sid in story_ids for stage in STORY_STAGES]
    if sprint:
        plan.extend((None, stage) for stage in SPRINT_STAGES)
    return plan


def _finish(run: Run, story: StoryAnalysis | None = None, sprint: SprintAnalysis | None = None,
            error: str | None = None, codebase: CodebaseAnalysis | None = None) -> None:
    run.finished_at = _now()
    run.status = "failed" if error else "succeeded"
    run.error = error
    run.story_result = story
    run.sprint_result = sprint
    run.codebase_result = codebase
    for stage in run.stages:
        if stage.status == "running":
            stage.status = "failed" if error else "done"
    _log_to(run, "error" if error else "info",
            error or f"Finished in {_ms_since(run.started_at) / 1000:.1f} s")


def launch(kind: RunKind, title: str, story_ids: list[str], plan: list[tuple[str | None, str]],
           work: Callable[[], Awaitable[StoryAnalysis | SprintAnalysis | CodebaseAnalysis]]) -> Run:
    """Start work in the background; the caller polls get(run.id) for progress."""
    run = _create(kind, title, story_ids, plan)

    async def runner() -> None:
        _current.set(run)
        try:
            result = await work()
        except Exception as exc:  # report every failure to the poller
            logger.exception("run %s failed", run.id)
            _finish(run, error=f"The analysis failed: {type(exc).__name__}. Check the backend logs.")
            return
        if isinstance(result, SprintAnalysis):
            _finish(run, sprint=result)
        elif isinstance(result, CodebaseAnalysis):
            _finish(run, codebase=result)
        else:
            _finish(run, story=result)

    task = asyncio.create_task(runner())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return run


@contextmanager
def tracked(kind: RunKind, title: str, story_ids: list[str], plan: list[tuple[str | None, str]]) -> Iterator[Run]:
    """Track work awaited inline (the copilot), so it still shows in the debug history."""
    run = _create(kind, title, story_ids, plan)
    token = _current.set(run)
    try:
        yield run
    except Exception as exc:
        _finish(run, error=f"{type(exc).__name__}")
        raise
    else:
        if run.status == "running":
            _finish(run)
    finally:
        _current.reset(token)


def get(run_id: str) -> Run | None:
    run = _runs.get(run_id)
    return snapshot(run) if run else None


def recent() -> list[Run]:
    """Newest first, without the large result payloads."""
    return [
        snapshot(run).model_copy(update={"story_result": None, "sprint_result": None, "codebase_result": None})
        for run in reversed(_runs.values())
    ]


def snapshot(run: Run) -> Run:
    """Copy with live elapsed times filled in for anything still running."""
    end = run.finished_at
    copy = run.model_copy(deep=True)
    copy.elapsed_ms = round(((end or _now()) - run.started_at).total_seconds() * 1000)
    for stage in copy.stages:
        if stage.status == "running" and stage.started_at:
            stage.elapsed_ms = _ms_since(stage.started_at)
    for attempt in copy.attempts:
        if attempt.outcome == "running":
            attempt.elapsed_ms = _ms_since(attempt.started_at)
    return copy


# ---------------------------------------------------------------- reporting


def current() -> Run | None:
    return _current.get()


@contextmanager
def story_scope(story_id: str) -> Iterator[None]:
    token = _story.set(story_id)
    try:
        yield
    finally:
        _story.reset(token)


def _find_stage(run: Run, stage: str, story_id: str | None) -> StageProgress:
    for item in run.stages:
        if item.stage == stage and item.story_id == story_id:
            return item
    item = StageProgress(story_id=story_id, stage=stage, label=STAGE_LABELS.get(stage, stage), status="pending")
    run.stages.append(item)
    return item


@contextmanager
def stage(name: str, story_id: str | None = ...) -> Iterator[StageProgress | None]:  # type: ignore[assignment]
    """Mark a stage running; it is marked done (or failed) when the block exits.

    LLM attempts made inside the block are attributed to this stage.
    """
    run = _current.get()
    sid = _story.get() if story_id is ... else story_id
    token = _stage.set(name)
    if run is None:
        try:
            yield None
        finally:
            _stage.reset(token)
        return
    item = _find_stage(run, name, sid)
    item.status, item.started_at = "running", _now()
    try:
        yield item
    except BaseException:
        item.status = "failed"
        item.elapsed_ms = _ms_since(item.started_at)
        raise
    else:
        item.status = "done"
        item.elapsed_ms = _ms_since(item.started_at)
    finally:
        _stage.reset(token)


def describe(item: StageProgress | None, provider: str, message: str, cached: bool = False) -> None:
    """Record where a stage's output came from and a one-line result."""
    if item is None:
        return
    if cached:
        item.source = "cache"
    elif provider == "deterministic":
        item.source = "deterministic"
    elif provider == "fixture":
        item.source = "fixture"
    elif provider.endswith("fallback") or provider in {"template", "none"}:
        item.source = "fallback"
    else:
        item.source = "llm"
    item.provider = provider
    item.message = message


def serve_fixture() -> None:
    """The saved demo result answers this run: no stage runs and no model is called."""
    run = _current.get()
    if run is None:
        return
    now = _now()
    for item in run.stages:
        item.status, item.source, item.provider = "done", "fixture", "fixture"
        item.started_at, item.elapsed_ms = now, 0
        item.message = "From the saved demo result"
    _log_to(run, "info", (
        "Unchanged demo input: serving the saved result built earlier with the live models. "
        "No model is called. Edit any field, or re-run live, to analyze it now."
    ))


def log(message: str, level: str = "info", story_id: str | None = ...) -> None:  # type: ignore[assignment]
    run = _current.get()
    if run is not None:
        _log_to(run, level, message, _story.get() if story_id is ... else story_id)


def _log_to(run: Run, level: str, message: str, story_id: str | None = None) -> None:
    run.log.append(RunLogEntry(at=_now(), level=level, story_id=story_id, message=message))
    del run.log[:-_MAX_LOG]


def attempt_started(provider: str, model: str, tier: str, max_tokens: int, timeout_s: float) -> LlmAttempt | None:
    run = _current.get()
    if run is None:
        return None
    attempt = LlmAttempt(
        id=next(_attempt_ids), story_id=_story.get(), stage=_stage.get(), provider=provider,
        model=model, tier=tier, max_tokens=max_tokens, timeout_s=timeout_s,
        started_at=_now(), elapsed_ms=0, outcome="running", detail="Waiting for the model",
    )
    run.attempts.append(attempt)
    return attempt


def attempt_finished(attempt: LlmAttempt | None, outcome: AttemptOutcome, detail: str,
                     usage: dict | None = None) -> None:
    if attempt is None:
        return
    attempt.elapsed_ms = _ms_since(attempt.started_at)
    attempt.outcome = outcome
    attempt.detail = detail
    if usage:
        attempt.prompt_tokens = usage.get("prompt_tokens")
        attempt.completion_tokens = usage.get("completion_tokens")
        details = usage.get("completion_tokens_details") or {}
        attempt.reasoning_tokens = details.get("reasoning_tokens") if isinstance(details, dict) else None
    run = _current.get()
    if run is not None and outcome != "ok":
        where = f"{STAGE_LABELS.get(attempt.stage or '', attempt.stage or 'call')}: " if attempt.stage else ""
        _log_to(run, "warning", f"{where}{attempt.provider} {attempt.model} — {detail}", attempt.story_id)


def attempt_skipped(provider: str, model: str, tier: str, max_tokens: int, timeout_s: float, reason: str) -> None:
    attempt = attempt_started(provider, model, tier, max_tokens, timeout_s)
    if attempt is not None:
        attempt.outcome, attempt.detail = "skipped", reason
