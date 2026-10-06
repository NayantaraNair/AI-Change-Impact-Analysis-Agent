"""Sprint orchestration, real disabled-LLM demo, rollups and route integration."""

import asyncio
import json

import httpx
import pytest

from app import config, db, llm
from app.api.main import app
from app.api import routes_sprint
from app.architecture import get_architecture, load_demo_sprint
from app.contracts import Conflict, FrameworkAssessment, SprintAnalysis
from app.engine import sprint
from tests.test_conflicts import analysis, arch  # noqa: F401


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_DISABLED", "1")
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "db" / "app.db")
    monkeypatch.setattr(config, "FIXTURES_DIR", tmp_path / "fixtures")


def conflict(a="A", b="B", component="a", kind="deployment_collision", risk="high"):
    return Conflict(
        id=f"C-{a}-{b}-{component}", story_a=a, story_b=b, shared_component=component,
        kind=kind, risk=risk, risk_score=80 if risk == "high" else 50,
        recommendation="Sequence the releases and run shared regression tests",
    )


@pytest.fixture
async def demo_result():
    demo = load_demo_sprint()
    return await sprint.analyze_sprint(demo.sprint_id, demo.name, demo.stories)


async def test_real_demo_sprint_conflicts_decisions_and_persistence(demo_result):
    demo = load_demo_sprint()
    result = demo_result
    assert len(result.conflicts) >= 2
    assert any(
        {c.story_a, c.story_b} == {"ST-107", "ST-112"}
        and c.shared_component == "authentication-service" and c.kind == "deployment_collision"
        for c in result.conflicts
    )
    decisions = {a.release.decision for a in result.stories}
    assert "NO_GO" in decisions
    assert len(result.stories) == len(demo.stories)
    assert result.kpis == sprint.compute_kpis(result.stories, result.conflicts)
    assert result.summary and "\n" not in result.summary
    assert db.latest_sprint(demo.sprint_id) == result
    for item in result.stories:
        assert db.latest_story_analysis(item.story.id) == item
        applicable = [c for c in result.conflicts if item.story.id in {c.story_a, c.story_b}]
        for c in applicable:
            assert c.recommendation in item.release.conditions
    assert SprintAnalysis.model_validate_json(result.model_dump_json()) == result
    graph = result.conflict_graph
    assert len({n.id for n in graph.nodes}) == len(graph.nodes)
    assert len({e.id for e in graph.edges}) == len(graph.edges)
    assert any(e.conflict for e in graph.edges)
    assert all(e.source != e.target and not e.on_impact_path for e in graph.edges if e.conflict)


@pytest.mark.xfail(strict=True, reason=(
    "Demo architecture groups ST-115 reporting-service and ST-110 risk-engine in data-platform; "
    "the required same-group collision makes the demo's only initial GO conditional."
))
async def test_real_demo_sprint_includes_go(demo_result):
    assert any(item.release.decision == "GO" for item in demo_result.stories)


async def test_story_concurrency_release_only_reassessment_and_persistence(arch, monkeypatch):
    originals = [analysis("A", ["a"], arch), analysis("B", ["b"], arch), analysis("C", ["isolated"], arch)]
    originals_by_id = {a.story.id: a for a in originals}
    started = set()
    all_started = asyncio.Event()
    calls, events = [], []

    async def analyze(story, refresh=False):
        assert refresh is True
        started.add(story.id)
        if len(started) == 3:
            all_started.set()
        await all_started.wait()
        return originals_by_id[story.id]

    assess_release = sprint.release.assess_release

    async def reassess(facts, graph, risk, tests, compliance, *, conflicts, text):
        assert started == {"A", "B", "C"}
        original = next(a for a in originals if a.requirement is facts)
        assert original.story.id in {"A", "B"}
        assert all(original.story.id in {c.story_a, c.story_b} for c in conflicts)
        assert text == (original.release.rollback_plan, original.release.deployment_notes)
        calls.append(original.story.id)
        return await assess_release(facts, graph, risk, tests, compliance, conflicts=conflicts, text=text)

    async def structured(*args, **kwargs):
        pytest.fail("Reassessment must reuse text without structured LLM calls")

    async def prose(system, user, **kwargs):
        assert calls == ["A", "B"]
        assert json.loads(user)["kpis"]["conflicts"] == 1
        return "Summary paragraph.\n\nRelease sequencing is required.", "mock"

    monkeypatch.setattr(sprint.pipeline, "analyze_story", analyze)
    monkeypatch.setattr(sprint, "get_architecture", lambda: arch)
    monkeypatch.setattr(sprint.release, "assess_release", reassess)
    monkeypatch.setattr(llm, "complete_structured", structured)
    monkeypatch.setattr(llm, "complete_text", prose)
    monkeypatch.setattr(db, "save_sprint", lambda result: events.append(("sprint", result)))
    monkeypatch.setattr(db, "save_analysis", lambda result, sprint_id: events.append((sprint_id, result)))
    result = await asyncio.wait_for(sprint.analyze_sprint("S", "Sprint", [a.story for a in originals], refresh=True), 5)
    assert [a.story.id for a in result.stories] == ["A", "B", "C"]
    assert calls == ["A", "B"]
    assert [a.release.decision for a in result.stories] == ["GO_WITH_CONDITIONS", "GO_WITH_CONDITIONS", "GO"]
    assert all(a.release.decision == "GO" for a in originals)
    assert result.stories[2] is originals[2]
    assert result.summary == "Summary paragraph. Release sequencing is required."
    assert events[0] == ("sprint", result)
    assert events[1:] == [("S", item) for item in result.stories]


def test_kpi_exact_formula_and_distinct_dependency_count(arch):
    first = analysis("A", ["a"], arch, decision="NO_GO")
    second = analysis("B", ["b"], arch)
    first.risk.overall, second.risk.overall = 80, 20
    first.release.confidence, second.release.confidence = 20, 81
    first.compliance.frameworks = [
        FrameworkAssessment(framework=name, applicable=applicable, reason="Test", risk_level=level,
                            score=90, findings=[], recommendations=[])
        for name, applicable, level in [
            ("GDPR", True, "medium"), ("SOX", True, "high"),
            ("PCI DSS", False, "high"), ("Internal Governance", True, "low"),
        ]
    ]
    kpis = sprint.compute_kpis([first, second], [conflict(), conflict(component="db", risk="medium")])
    assert kpis.model_dump() == {
        "stories": 2, "applications_impacted": 2, "dependencies_impacted": 1,
        "conflicts": 2, "compliance_issues": 2, "testing_effort_hours": 5.0,
        "health_score": 60, "release_confidence": 50, "high_risk_stories": ["A"],
    }
    first.risk.overall = 20
    assert sprint.compute_kpis([first], []).high_risk_stories == ["A"]
    assert sprint.compute_kpis([second], [conflict() for _ in range(50)]).health_score == 0
    empty = sprint.compute_kpis([], [])
    assert empty.health_score == 100 and empty.release_confidence == 0


def test_union_merges_hops_severity_edges_and_summaries_independently(arch):
    first, second = analysis("A", ["a"], arch), analysis("B", ["b"], arch)
    node_a = next(n for n in second.graph.nodes if n.id == "a")
    node_a.hop, node_a.severity = 3, "high"
    next(n for n in first.graph.nodes if n.id == "a").severity = "low"
    first.graph.edges[0].on_impact_path = False
    second.graph.edges[0].on_impact_path = True
    before = first.model_dump()
    merged = sprint.union_graph([first, second], [conflict()], arch)
    union_a = next(n for n in merged.nodes if n.id == "a")
    assert union_a.hop == 0 and union_a.severity == "high"
    assert next(e for e in merged.edges if e.id == first.graph.edges[0].id).on_impact_path
    assert {(e.source, e.target) for e in merged.edges if e.conflict} == {("b", "a")}
    assert all(not e.on_impact_path and e.source != e.target for e in merged.edges if e.conflict)
    for field in ["impacted_services", "impacted_databases", "impacted_apis", "downstream_systems", "deployment_groups"]:
        assert getattr(merged, field) == sorted(set(getattr(first.graph, field)) | set(getattr(second.graph, field)))
    assert first.model_dump() == before
    assert sprint.union_graph([second, first], [conflict()], arch) == merged


def test_union_shared_root_skips_self_loops_and_schema_conflicts_connect_roots(arch):
    first, second = analysis("A", ["auth"], arch), analysis("B", ["auth"], arch)
    merged = sprint.union_graph([first, second], [conflict(component="auth")], arch)
    assert not any(e.conflict for e in merged.edges)
    first, second = analysis("A", ["a"], arch), analysis("B", ["b"], arch)
    schema = conflict(component="db", kind="schema_contention")
    merged = sprint.union_graph([first, second], [schema, schema], arch)
    assert len({e.id for e in merged.edges}) == len(merged.edges)
    assert {(e.source, e.target) for e in merged.edges if e.conflict} == {("a", "db"), ("b", "db")}


async def test_empty_sprint_fallback_and_persistence():
    result = await sprint.analyze_sprint("empty", "Empty", [])
    assert result.stories == result.conflicts == []
    assert result.kpis.health_score == 100
    assert "No cross-story conflicts" in result.summary
    assert all(n.hop is None for n in result.conflict_graph.nodes)
    assert db.latest_sprint("empty") == result


async def test_blank_summary_uses_template_and_unexpected_errors_propagate(monkeypatch):
    async def blank(*args, **kwargs):
        return "   \n ", "mock"

    monkeypatch.setattr(llm, "complete_text", blank)
    result = await sprint.analyze_sprint("blank", "Blank", [])
    assert "Analyzed 0 stories" in result.summary

    async def failed(*args, **kwargs):
        raise RuntimeError("summary failed")

    monkeypatch.setattr(llm, "complete_text", failed)
    with pytest.raises(RuntimeError, match="summary failed"):
        await sprint.analyze_sprint("error", "Error", [])
    assert db.latest_sprint("error") is None


async def test_failures_propagate_without_saving_sprint(arch, monkeypatch):
    item = analysis("A", ["a"], arch)

    async def failed(*args, **kwargs):
        raise RuntimeError("upstream failed")

    monkeypatch.setattr(sprint.pipeline, "analyze_story", failed)
    with pytest.raises(RuntimeError, match="upstream failed"):
        await sprint.analyze_sprint("failed", "Failed", [item.story])
    assert db.latest_sprint("failed") is None
    with pytest.raises(ValueError, match="unique"):
        await sprint.analyze_sprint("duplicate", "Duplicate", [item.story, item.story])


async def test_routes_use_fixture_hook_and_forward_refresh(monkeypatch):
    demo = load_demo_sprint()
    originals = [analysis(item.id, ["document-service"], get_architecture()) for item in demo.stories]
    for item, story in zip(originals, demo.stories):
        item.story = story
    result = SprintAnalysis(
        sprint_id=demo.sprint_id, name=demo.name, stories=originals, conflicts=[],
        kpis=sprint.compute_kpis(originals, []),
        conflict_graph=sprint.union_graph(originals, [], get_architecture()), summary="Fixture summary",
    )
    config.FIXTURES_DIR.mkdir()
    (config.FIXTURES_DIR / "sprint.json").write_text(result.model_dump_json(), encoding="utf-8")
    calls = []

    async def analyze(sprint_id, name, stories, *, refresh=False):
        calls.append((sprint_id, name, stories, refresh))
        updated = result.model_copy(update={"sprint_id": sprint_id, "name": name, "summary": "Fresh summary"})
        db.save_sprint(updated)
        return updated

    monkeypatch.setattr(routes_sprint.sprint_engine, "analyze_sprint", analyze)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/analyze-sprint", json={"sprint_id": "named", "name": "Named"})
        assert response.status_code == 200 and response.json()["summary"] == "Fixture summary"
        assert not calls
        assert (await client.get("/sprint/named")).json() == response.json()
        response = await client.post("/analyze-sprint?refresh=true", json={})
        assert response.json()["summary"] == "Fresh summary"
        assert calls[-1] == (demo.sprint_id, demo.name, demo.stories, True)
        story = demo.stories[0].model_copy(update={"title": "Custom title"})
        response = await client.post("/analyze-sprint", json={"stories": [story.model_dump(mode="json")]})
        assert response.status_code == 200
        assert calls[-1][0].startswith("sprint-") and calls[-1][1:] == ("Custom sprint", [story], False)
        duplicate = await client.post("/analyze-sprint", json={"stories": [story.model_dump()] * 2})
        assert duplicate.status_code == 422
        assert (await client.get("/sprint/missing")).status_code == 404
        assert (await client.post("/analyze-sprint?refresh=bad", json={})).status_code == 422
