"""FastAPI contracts, demo fixtures, and persisted reports in no-key mode."""

import asyncio
from itertools import combinations

import pytest
from fastapi.testclient import TestClient

from app import config, db, pipeline
from app.api.main import app
from app.architecture import get_architecture, get_test_catalog, load_demo_sprint
from app.contracts import ChatResponse, ImpactGraph, SprintAnalysis, StoryAnalysis
from tests.test_pipeline import isolated, runs, stages, story  # noqa: F401


@pytest.fixture
def client(isolated):
    with TestClient(app) as test_client:
        yield test_client


def test_health_startup_architecture_and_cors(client, monkeypatch):
    monkeypatch.setattr(config, "tokenharbor_key", lambda: "configured-test-value")
    monkeypatch.setattr(config, "openrouter_key", lambda: None)
    health = client.get("/health").json()
    assert health == {
        "status": "ok", "providers_configured": {"tokenharbor": True, "openrouter": False},
        "llm_disabled": True,
    }
    assert app.state.architecture is get_architecture()
    assert app.state.test_catalog is get_test_catalog()
    assert client.get("/architecture").json() == get_architecture().model_dump(mode="json")
    for origin in ["http://localhost:3000", "http://100.64.0.10:3000"]:
        response = client.options("/analyze", headers={
            "Origin": origin, "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        })
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "*"
        assert "access-control-allow-credentials" not in response.headers


def test_st107_analyze_and_reports_without_llm(client, story):
    response = client.post("/analyze", json=story.model_dump(mode="json"))
    assert response.status_code == 200, response.text
    result = StoryAnalysis.model_validate(response.json())
    assert result.story == story
    assert len(result.risk.dimensions) == 6
    assert result.providers_used["dependency"] == result.providers_used["scoring"] == "deterministic"
    assert StoryAnalysis.model_validate(client.get(f"/report/{story.id}").json()) == result
    assert ImpactGraph.model_validate(client.get(f"/dependency-graph/{story.id}").json()) == result.graph
    assert len(runs()) == 1


def test_refresh_parameter_and_validation(client, story, stages):
    for url in ["/analyze", "/analyze", "/analyze?refresh=true"]:
        assert client.post(url, json=story.model_dump(mode="json")).status_code == 200
    assert all(count == 2 for count in stages["calls"].values())
    assert len(runs()) == 3
    assert client.post("/analyze", json={"id": "missing-fields"}).status_code == 422
    assert client.post("/analyze?refresh=invalid", json=story.model_dump(mode="json")).status_code == 422


def test_missing_reports_are_json_404(client):
    for url in ["/report/missing", "/dependency-graph/missing", "/sprint/missing"]:
        response = client.get(url)
        assert response.status_code == 404
        assert response.headers["content-type"] == "application/json"
        assert "detail" in response.json()


def test_demo_sprint_and_chat_route(client):
    assert client.get("/demo-sprint").json() == load_demo_sprint().model_dump(mode="json")
    response = client.post("/chat", json={
        "session_id": "session", "message": "Why is this high risk?",
        "context_type": "story", "context_id": "ST-NONE",
    })
    assert response.status_code == 200
    answer = ChatResponse.model_validate(response.json())
    assert "ST-NONE" in answer.answer
    assert answer.provider == "none"


def test_story_fixture_exact_match_saved_and_refreshable(client, story, stages):
    fixture = asyncio.run(pipeline.analyze_story(story))
    fixture = fixture.model_copy(update={"providers_used": {"requirement": "fixture:real"}})
    config.FIXTURES_DIR.mkdir()
    (config.FIXTURES_DIR / f"story-{story.id}.json").write_text(fixture.model_dump_json(), encoding="utf-8")
    stages["calls"].clear()
    response = client.post("/analyze", json=story.model_dump(mode="json"))
    assert StoryAnalysis.model_validate(response.json()) == fixture
    assert not stages["calls"]
    assert db.latest_story_analysis(story.id) == fixture
    assert client.get(f"/report/{story.id}").json() == fixture.model_dump(mode="json")
    refreshed = client.post("/analyze?refresh=true", json=story.model_dump(mode="json"))
    assert refreshed.json()["providers_used"]["requirement"] == "mock:fast"
    assert stages["calls"]["requirement"] == 1
    changed = story.model_copy(update={"acceptance_criteria": ["Changed input"]})
    assert client.post("/analyze", json=changed.model_dump(mode="json")).json()["story"] == changed.model_dump(mode="json")
    assert stages["calls"]["requirement"] == 2


def test_fixtures_ignored_when_enabled_or_invalid(client, story, stages, monkeypatch):
    fixture = asyncio.run(pipeline.analyze_story(story))
    config.FIXTURES_DIR.mkdir()
    path = config.FIXTURES_DIR / f"story-{story.id}.json"
    path.write_text(fixture.model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(config, "llm_disabled", lambda: False)
    stages["calls"].clear()
    response = client.post("/analyze", json=story.model_dump(mode="json"))
    assert response.status_code == 200
    assert len(runs()) == 2
    monkeypatch.setattr(config, "llm_disabled", lambda: True)
    path.write_text("invalid fixture", encoding="utf-8")
    response = client.post("/analyze", json=story.model_dump(mode="json"))
    assert response.status_code == 200
    assert len(runs()) == 3


def test_sprint_persistence_kpis_and_union(client, stages):
    response = client.post("/analyze-sprint", json={})
    assert response.status_code == 200, response.text
    result = SprintAnalysis.model_validate(response.json())
    demo = load_demo_sprint()
    assert result.sprint_id == demo.sprint_id
    assert [a.story for a in result.stories] == demo.stories
    # The mocked stages give every story the same three directly changed services.
    assert [
        (c.story_a, c.story_b, c.kind, c.shared_component, c.risk_score, c.risk)
        for c in result.conflicts
    ] == [
        (a, b, kind, component, 100, "high")
        for a, b in combinations(sorted(s.id for s in demo.stories), 2)
        for kind, component in [
            ("deployment_collision", "authentication-service"),
            ("shared_api_change", "mobile-banking"),
        ]
    ]
    assert result.kpis.model_dump() == {
        "stories": 6, "applications_impacted": 17, "dependencies_impacted": 18,
        "conflicts": 30, "compliance_issues": 0, "testing_effort_hours": 21.0,
        "health_score": 0, "release_confidence": 0,
        "high_risk_stories": [s.id for s in demo.stories],
    }
    assert len(result.conflict_graph.nodes) == len({n.id for n in result.conflict_graph.nodes})
    assert {n.id for n in result.conflict_graph.nodes} == {
        n.id for a in result.stories for n in a.graph.nodes
    }
    assert {e.id for e in result.conflict_graph.edges} == {
        e.id for a in result.stories for e in a.graph.edges
    }
    # Shared roots produce conflicts without self-loop graph edges.
    assert all(not edge.conflict for edge in result.conflict_graph.edges)
    assert SprintAnalysis.model_validate(client.get(f"/sprint/{demo.sprint_id}").json()) == result
    saved_runs = runs()
    assert len(saved_runs) == 2 * len(demo.stories)
    # Reassessment changes the release payload, so save_sprint adds a final run.
    for analysis in result.stories:
        story_runs = [run for run in saved_runs if run.story_id == analysis.story.id]
        assert {run.sprint_id for run in story_runs} == {None, demo.sprint_id}
        original, = [run for run in story_runs if run.sprint_id is None]
        final, = [run for run in story_runs if run.sprint_id == demo.sprint_id]
        assert original.payload["release"]["confidence"] == 20
        assert final.payload == analysis.model_dump(mode="json")
        assert db.latest_story_analysis(analysis.story.id) == analysis


def test_custom_sprint_and_latest_snapshot(client, story, stages):
    request = {"sprint_id": "custom", "name": "My sprint", "stories": [story.model_dump(mode="json")]}
    first = client.post("/analyze-sprint", json=request)
    assert first.status_code == 200
    assert first.json()["name"] == "My sprint"
    request["name"] = "Updated sprint"
    second = client.post("/analyze-sprint", json=request)
    assert second.status_code == 200
    assert client.get("/sprint/custom").json() == second.json()
    assert len(runs()) == 2


def test_demo_sprint_fixture_saved_only_for_exact_demo(client, stages):
    initial = client.post("/analyze-sprint", json={}).json()
    fixture = SprintAnalysis.model_validate(initial).model_copy(update={"summary": "Real fixture prose"})
    config.FIXTURES_DIR.mkdir()
    (config.FIXTURES_DIR / "sprint.json").write_text(fixture.model_dump_json(), encoding="utf-8")
    stages["calls"].clear()
    for request in [{}, {"stories": [s.model_dump(mode="json") for s in load_demo_sprint().stories]}]:
        response = client.post("/analyze-sprint", json=request)
        assert response.json()["summary"] == "Real fixture prose"
        assert not stages["calls"]
    assert client.get(f"/sprint/{fixture.sprint_id}").json()["summary"] == "Real fixture prose"
    custom = client.post("/analyze-sprint", json={"sprint_id": "renamed", "name": "Named demo"})
    assert custom.json()["summary"] == "Real fixture prose"
    assert db.latest_sprint("renamed").name == "Named demo"
    changed = load_demo_sprint().stories[0].model_copy(update={"title": "Changed"})
    response = client.post("/analyze-sprint", json={"stories": [changed.model_dump(mode="json")]})
    assert response.json()["summary"] != "Real fixture prose"
    assert stages["calls"]["requirement"] == 1
    refreshed = client.post("/analyze-sprint?refresh=true", json={})
    assert refreshed.json()["summary"] != "Real fixture prose"
