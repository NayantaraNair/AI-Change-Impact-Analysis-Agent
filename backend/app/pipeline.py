"""Story orchestration with validated, atomic, input-sensitive stage caches."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from app import config, db
from app.agents.compliance import assess_compliance
from app.agents.release import assess_release
from app.agents.requirement import analyze_requirement
from app.agents.testing import plan_tests
from app.architecture import get_architecture, get_test_catalog
from app.contracts import (
    Architecture, CatalogTest, ComplianceReport, Conflict, ImpactGraph,
    ReleaseAssessment, RequirementFacts, RiskReport, StoryAnalysis, StoryInput,
    TestCase, TestPlan,
)
from app.engine.dependency import build_impact_graph
from app.engine.scoring import score_risk


def _jsonable(value):
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def _fingerprint(inputs) -> str:
    encoded = json.dumps(_jsonable(inputs), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _cache_directory(story: StoryInput) -> Path:
    story_hash = hashlib.sha256(story.model_dump_json().encode("utf-8")).hexdigest()[:12]
    # Keep ordinary IDs readable while preventing arbitrary IDs escaping CACHE_DIR.
    safe_id = story.id
    reserved = {"CON", "PRN", "AUX", "NUL"} | {
        f"{prefix}{number}" for prefix in ("COM", "LPT") for number in range(1, 10)
    }
    if (
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", safe_id)
        or len(safe_id) > 100 or safe_id.endswith(".")
        or safe_id.split(".", 1)[0].upper() in reserved
    ):
        safe_id = "id-" + hashlib.sha256(safe_id.encode("utf-8")).hexdigest()
    return Path(config.CACHE_DIR) / safe_id / story_hash


async def _cached_stage(directory, stage, schema, inputs, produce, refresh):
    path = directory / f"{stage}.json"
    fingerprint = _fingerprint(inputs)
    if not refresh:
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            provider = cached["provider"]
            if (
                cached["input_hash"] == fingerprint
                and isinstance(provider, str)
                and (config.llm_disabled() or not provider.endswith("fallback"))
            ):
                return schema.model_validate(cached["output"]), provider
        except (OSError, ValueError, KeyError, TypeError, ValidationError):
            pass

    result, provider = await produce()
    result = schema.model_validate(result)
    if config.llm_disabled() or not provider.endswith("fallback"):
        directory.mkdir(parents=True, exist_ok=True)
        temporary = directory / f".{stage}-{uuid4().hex}.tmp"
        try:
            temporary.write_text(json.dumps({
                "input_hash": fingerprint, "provider": provider,
                "output": result.model_dump(mode="json"),
            }, ensure_ascii=False), encoding="utf-8")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    else:
        # A refreshed outage must not leave an older success as the current cache.
        path.unlink(missing_ok=True)
    return result, provider


async def analyze_story(
    story: StoryInput, conflicts: list[Conflict] | None = None, refresh: bool = False,
) -> StoryAnalysis:
    started = perf_counter()
    arch, catalog = get_architecture(), get_test_catalog()
    directory = _cache_directory(story)

    async def requirement():
        facts = await analyze_requirement(story, arch)
        return facts, facts.source

    facts, requirement_provider = await _cached_stage(
        directory, "requirement", RequirementFacts, [story, arch], requirement, refresh,
    )
    graph = build_impact_graph(facts.affected_services, arch)
    risk = score_risk(facts, graph, arch)
    (tests, testing_provider), (compliance, compliance_provider) = await asyncio.gather(
        _cached_stage(directory, "testing", TestPlan, [facts, graph, risk, catalog],
                      lambda: plan_tests(facts, graph, risk, catalog), refresh),
        _cached_stage(directory, "compliance", ComplianceReport, [facts, graph, arch],
                      lambda: assess_compliance(facts, graph, arch), refresh),
    )
    release, release_provider = await _cached_stage(
        directory, "release", ReleaseAssessment,
        [facts, graph, risk, tests, compliance, conflicts],
        lambda: assess_release(facts, graph, risk, tests, compliance,
                               conflicts=conflicts), refresh,
    )
    analysis = StoryAnalysis(
        story=story, requirement=facts, graph=graph, risk=risk, tests=tests,
        compliance=compliance, release=release,
        providers_used={
            "requirement": requirement_provider, "dependency": "deterministic",
            "scoring": "deterministic", "testing": testing_provider,
            "compliance": compliance_provider, "release": release_provider,
        },
        duration_ms=max(0, round((perf_counter() - started) * 1000)),
        created_at=datetime.now(timezone.utc),
    )
    await asyncio.to_thread(db.save_analysis, analysis)
    return analysis
