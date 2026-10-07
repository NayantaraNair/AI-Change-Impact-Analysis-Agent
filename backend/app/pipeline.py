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

from app import config, db, runs
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
from app.engine.scope import plan_scope
from app.engine.scoring import load_scoring_config, score_risk


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


async def _tracked_stage(directory, stage, schema, inputs, produce, refresh, describe):
    """Run one cached stage and report its source and result to the active run."""
    with runs.stage(stage) as item:
        result, provider, cached = await _cached_stage(
            directory, stage, schema, inputs, produce, refresh,
        )
        runs.describe(item, provider, describe(result), cached=cached)
    return result, provider


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
                return schema.model_validate(cached["output"]), provider, True
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
    return result, provider, False


def _describe_facts(facts: RequirementFacts) -> str:
    services = ", ".join(facts.affected_services) or "no catalog services"
    return f"{facts.change_type.replace('_', ' ')} touching {services}"


def _describe_graph(graph: ImpactGraph) -> str:
    hops = [node.hop for node in graph.nodes if node.hop is not None]
    return (
        f"{len(graph.impacted_services)} of {len(graph.nodes)} components impacted, "
        f"up to {max(hops, default=0)} hops away"
    )


def _describe_risk(risk: RiskReport) -> str:
    highest = next(d for d in risk.dimensions if d.name == risk.highest)
    return f"Highest risk: {highest.name} {highest.score} ({highest.level}); overall {risk.overall}"


def _describe_tests(tests: TestPlan) -> str:
    generated = sum(test.source == "generated" for test in tests.tests)
    return (
        f"{len(tests.tests) - generated} catalog + {generated} new tests, "
        f"{tests.coverage_estimate:.0%} coverage"
    )


def _describe_compliance(report: ComplianceReport) -> str:
    applicable = [f.framework for f in report.frameworks if f.applicable]
    return f"{len(applicable)} of 4 frameworks apply; lowest score {report.overall_score}"


def _describe_release(release: ReleaseAssessment) -> str:
    return f"{release.decision.replace('_', ' ')} at {release.confidence}% confidence"


async def analyze_story(
    story: StoryInput, conflicts: list[Conflict] | None = None, refresh: bool = False,
) -> StoryAnalysis:
    with runs.story_scope(story.id):
        return await _analyze_story(story, conflicts, refresh)


async def _analyze_story(
    story: StoryInput, conflicts: list[Conflict] | None, refresh: bool,
) -> StoryAnalysis:
    started = perf_counter()
    arch, catalog = get_architecture(), get_test_catalog()
    directory = _cache_directory(story)

    async def requirement():
        facts = await analyze_requirement(story, arch)
        return facts, facts.source

    facts, requirement_provider = await _tracked_stage(
        directory, "requirement", RequirementFacts, [story, arch], requirement, refresh,
        _describe_facts,
    )
    with runs.stage("dependency") as item:
        scope = plan_scope(facts, arch, load_scoring_config())
        graph = build_impact_graph(
            facts.affected_services, arch, max_hops=scope.max_hops,
            include_callers=scope.include_callers, blocked=scope.blocked,
            severity_scale=scope.severity_scale,
        )
        runs.describe(item, "deterministic", f"{scope.size.capitalize()} change: {_describe_graph(graph)}")
    with runs.stage("scoring") as item:
        risk = score_risk(facts, graph, arch)
        runs.describe(item, "deterministic", _describe_risk(risk))
    (tests, testing_provider), (compliance, compliance_provider) = await asyncio.gather(
        _tracked_stage(directory, "testing", TestPlan, [facts, graph, risk, catalog],
                       lambda: plan_tests(facts, graph, risk, catalog), refresh,
                       _describe_tests),
        _tracked_stage(directory, "compliance", ComplianceReport, [facts, graph, arch],
                       lambda: assess_compliance(facts, graph, arch), refresh,
                       _describe_compliance),
    )
    release, release_provider = await _tracked_stage(
        directory, "release", ReleaseAssessment,
        [facts, graph, risk, tests, compliance, conflicts],
        lambda: assess_release(facts, graph, risk, tests, compliance,
                               conflicts=conflicts), refresh,
        _describe_release,
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
