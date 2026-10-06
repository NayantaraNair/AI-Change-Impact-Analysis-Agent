"""Pipeline cache, orchestration, and SQLite integration tests; no provider calls."""

import asyncio
import hashlib
import json
from collections import Counter

import pytest
from sqlmodel import Session, select

from app import config, db, pipeline
from app.architecture import load_demo_sprint
from app.contracts import (
    ComplianceReport, Conflict, ReleaseAssessment, RequirementFacts, StoryAnalysis, TestPlan,
)


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "db" / "app.db")
    monkeypatch.setattr(config, "FIXTURES_DIR", tmp_path / "fixtures")
    return tmp_path


@pytest.fixture
def story():
    return next(s for s in load_demo_sprint().stories if s.id == "ST-107")


@pytest.fixture
def stages(monkeypatch):
    state = {"calls": Counter(), "provider": "mock:fast", "conflicts": None}

    async def requirement(story, arch):
        state["calls"]["requirement"] += 1
        return RequirementFacts(
            business_summary=story.title, technical_summary=story.description,
            business_domain="cards", affected_capabilities=["card control"],
            affected_services=["mobile-banking", "card-service", "authentication-service"],
            change_type="new_feature", touches_customer_data=True, touches_card_data=True,
            touches_financial_data=False, changes_auth_flow=True,
            changes_external_api_contract=True, changes_db_schema=False,
            ambiguity="low", engineering_scope="Step-up authenticated card control.",
            source=state["provider"],
        )

    async def testing(facts, graph, risk, catalog):
        state["calls"]["testing"] += 1
        return TestPlan(
            tests=[], coverage_estimate=0, effort_hours=3.5,
            automation_candidates=0, summary="Mock test plan",
        ), state["provider"]

    async def compliance(facts, graph, arch):
        state["calls"]["compliance"] += 1
        return ComplianceReport(
            frameworks=[], overall_score=55, summary="Mock compliance assessment",
        ), state["provider"]

    async def release(facts, graph, risk, tests, compliance, conflicts=None, text=None):
        state["calls"]["release"] += 1
        state["conflicts"] = conflicts
        state["text"] = text
        return ReleaseAssessment(
            confidence=20, decision="NO_GO", triggered_rules=["security_blocker"],
            conditions=["Resolve security blockers"], complexity="high",
            rollback_plan=["Restore previous version"], deployment_notes=[],
        ), state["provider"]

    monkeypatch.setattr(pipeline, "analyze_requirement", requirement)
    monkeypatch.setattr(pipeline, "plan_tests", testing)
    monkeypatch.setattr(pipeline, "assess_compliance", compliance)
    monkeypatch.setattr(pipeline, "assess_release", release)
    return state


def runs():
    with Session(db._engine()) as session:
        return session.exec(select(db.AnalysisRun)).all()


async def test_cache_refresh_and_every_run_saved(isolated, story, stages):
    first = await pipeline.analyze_story(story)
    second = await pipeline.analyze_story(story)
    assert StoryAnalysis.model_validate_json(first.model_dump_json()) == first
    assert first.duration_ms >= 0
    assert first.created_at.tzinfo is not None
    assert first.providers_used == {
        "requirement": "mock:fast", "dependency": "deterministic",
        "scoring": "deterministic", "testing": "mock:fast",
        "compliance": "mock:fast", "release": "mock:fast",
    }
    assert stages["calls"] == dict.fromkeys(["requirement", "testing", "compliance", "release"], 1)
    digest = hashlib.sha256(story.model_dump_json().encode()).hexdigest()[:12]
    directory = config.CACHE_DIR / story.id / digest
    assert {p.name for p in directory.iterdir()} == {
        "requirement.json", "testing.json", "compliance.json", "release.json",
    }
    assert json.loads((directory / "requirement.json").read_text())["provider"] == "mock:fast"
    assert first.risk == second.risk
    assert len(runs()) == 2
    assert db.latest_story_analysis(story.id) == second
    refreshed = await pipeline.analyze_story(story, refresh=True)
    assert all(count == 2 for count in stages["calls"].values())
    assert len(runs()) == 3
    assert db.latest_story_analysis(story.id) == refreshed


async def test_changed_story_and_conflicts_invalidate_correct_stages(isolated, story, stages):
    await pipeline.analyze_story(story)
    conflict = Conflict(
        id="CF-1", story_a=story.id, story_b="ST-112",
        shared_component="authentication-service", kind="deployment_collision",
        risk="high", risk_score=85, recommendation="Coordinate deployments",
    )
    await pipeline.analyze_story(story, conflicts=[conflict])
    assert stages["calls"]["release"] == 2
    assert stages["calls"]["requirement"] == stages["calls"]["testing"] == 1
    assert stages["conflicts"] == [conflict]
    changed = story.model_copy(update={"description": story.description + " New scope."})
    await pipeline.analyze_story(changed)
    assert stages["calls"]["requirement"] == 2
    assert len(list((config.CACHE_DIR / story.id).iterdir())) == 2


async def test_changed_architecture_invalidates_cache(isolated, story, stages, monkeypatch):
    await pipeline.analyze_story(story)
    arch = pipeline.get_architecture().model_copy(deep=True)
    arch.components[0].description += " Revised architecture."
    monkeypatch.setattr(pipeline, "get_architecture", lambda: arch)
    await pipeline.analyze_story(story)
    assert stages["calls"]["requirement"] == 2
    assert stages["calls"]["compliance"] == 2


async def test_fallback_cache_is_not_pinned_when_llm_enabled(isolated, story, stages, monkeypatch):
    stages["provider"] = "keyword-fallback"
    await pipeline.analyze_story(story)
    assert len(list(config.CACHE_DIR.rglob("*.json"))) == 4
    monkeypatch.setattr(config, "llm_disabled", lambda: False)
    await pipeline.analyze_story(story)
    assert all(count == 2 for count in stages["calls"].values())
    assert not list(config.CACHE_DIR.rglob("*.json"))
    stages["provider"] = "mock:recovered"
    recovered = await pipeline.analyze_story(story)
    assert recovered.providers_used["requirement"] == "mock:recovered"
    assert len(list(config.CACHE_DIR.rglob("*.json"))) == 4
    await pipeline.analyze_story(story)
    assert all(count == 3 for count in stages["calls"].values())


async def test_corrupt_cache_is_recomputed(isolated, story, stages):
    await pipeline.analyze_story(story)
    for path in config.CACHE_DIR.rglob("*.json"):
        path.write_text("{ broken", encoding="utf-8")
    await pipeline.analyze_story(story)
    assert all(count == 2 for count in stages["calls"].values())
    assert all(json.loads(path.read_text())["provider"] == "mock:fast" for path in config.CACHE_DIR.rglob("*.json"))


async def test_stage_order_and_testing_compliance_concurrency(isolated, story, stages, monkeypatch):
    testing_started, compliance_started = asyncio.Event(), asyncio.Event()
    events = []
    original_requirement = pipeline.analyze_requirement
    original_dependency = pipeline.build_impact_graph
    original_scoring = pipeline.score_risk
    original_testing = pipeline.plan_tests
    original_compliance = pipeline.assess_compliance
    original_release = pipeline.assess_release

    async def requirement(*args):
        events.append("requirement")
        return await original_requirement(*args)

    def dependency(*args):
        events.append("dependency")
        return original_dependency(*args)

    def scoring(*args):
        events.append("scoring")
        return original_scoring(*args)

    async def testing(*args):
        events.append("testing")
        testing_started.set()
        await compliance_started.wait()
        return await original_testing(*args)

    async def compliance(*args):
        events.append("compliance")
        compliance_started.set()
        await testing_started.wait()
        return await original_compliance(*args)

    async def release(*args, **kwargs):
        events.append("release")
        assert testing_started.is_set() and compliance_started.is_set()
        return await original_release(*args, **kwargs)

    for name, value in [
        ("analyze_requirement", requirement), ("build_impact_graph", dependency),
        ("score_risk", scoring), ("plan_tests", testing),
        ("assess_compliance", compliance), ("assess_release", release),
    ]:
        monkeypatch.setattr(pipeline, name, value)
    await asyncio.wait_for(pipeline.analyze_story(story), timeout=5)
    assert events[:3] == ["requirement", "dependency", "scoring"]
    assert set(events[3:5]) == {"testing", "compliance"}
    assert events[-1] == "release"


async def test_runtime_paths_and_safe_story_id(isolated, story, stages, monkeypatch):
    await pipeline.analyze_story(story)
    monkeypatch.setattr(config, "DB_PATH", isolated / "new-db" / "other.db")
    monkeypatch.setattr(config, "CACHE_DIR", isolated / "new-cache")
    assert db.latest_story_analysis(story.id) is None
    hostile = story.model_copy(update={"id": "../../escaped"})
    result = await pipeline.analyze_story(hostile)
    assert db.latest_story_analysis(hostile.id) == result
    assert len(list(config.CACHE_DIR.rglob("*.json"))) == 4
    assert not (isolated / "escaped").exists()


async def test_agent_errors_are_not_hidden(isolated, story, stages, monkeypatch):
    async def failed(*args):
        raise RuntimeError("stage failed")

    monkeypatch.setattr(pipeline, "analyze_requirement", failed)
    with pytest.raises(RuntimeError, match="stage failed"):
        await pipeline.analyze_story(story)
    assert db.latest_story_analysis(story.id) is None


async def test_concurrent_standalone_runs_initialize_db(isolated, story, stages):
    inputs = [story.model_copy(update={"id": f"concurrent-{index}"}) for index in range(4)]
    results = await asyncio.gather(*(pipeline.analyze_story(item) for item in inputs))
    assert len(runs()) == len(inputs)
    assert all(db.latest_story_analysis(result.story.id) == result for result in results)


@pytest.mark.parametrize("story_id", ["CON", "nul.json", "LPT1", "ends-in-dot."])
async def test_windows_reserved_ids_are_safe(isolated, story, stages, story_id):
    result = await pipeline.analyze_story(story.model_copy(update={"id": story_id}))
    assert result.story.id == story_id
    assert next(config.CACHE_DIR.iterdir()).name.startswith("id-")
