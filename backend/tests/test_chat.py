"""Copilot context, templates, citations, memory, and routing without live LLMs."""

import asyncio
import json

import httpx
import pytest

from app import config, db, llm, pipeline
from app.agents import chat
from app.api.main import app
from app.architecture import load_demo_sprint
from app.contracts import ChatRequest, ChatResponse, Conflict, SprintAnalysis, SprintKpis


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_DISABLED", "1")
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "app.db")
    monkeypatch.setattr(config, "FIXTURES_DIR", tmp_path / "fixtures")
    chat._sessions.clear()

    async def unavailable(*args, **kwargs):
        raise llm.NoLLM("LLM disabled in chat tests")

    monkeypatch.setattr(llm, "complete_text", unavailable)
    monkeypatch.setattr(llm, "complete_structured", unavailable)
    yield
    chat._sessions.clear()


@pytest.fixture
async def analysis():
    story = next(story for story in load_demo_sprint().stories if story.id == "ST-107")
    return await pipeline.analyze_story(story)


def request(message, context_id="ST-107", context_type="story", session_id="session"):
    return ChatRequest(
        session_id=session_id, message=message, context_id=context_id, context_type=context_type,
    )


@pytest.fixture
def sprint(analysis):
    safe = analysis.model_copy(deep=True)
    safe.story.id = "ST-115"
    safe.release.decision = "GO"
    safe.release.confidence = 95
    safe.release.triggered_rules = []
    safe.release.conditions = []
    safe.risk.overall = 20
    snapshot = SprintAnalysis(
        sprint_id="sprint-42", name="Sprint 42", stories=[analysis, safe],
        conflicts=[Conflict(
            id="CF-1", story_a="ST-107", story_b="ST-115",
            shared_component="authentication-service", kind="deployment_collision",
            risk="high", risk_score=85, recommendation="Coordinate the identity deployment.",
        )],
        kpis=SprintKpis(
            stories=2, applications_impacted=5, dependencies_impacted=8, conflicts=1,
            compliance_issues=2, testing_effort_hours=10, health_score=40,
            release_confidence=30, high_risk_stories=["ST-107"],
        ),
        conflict_graph=analysis.graph, summary="Identity deployment needs coordination.",
    )
    db.save_sprint(snapshot)
    return snapshot


async def test_st107_release_confidence_mentions_triggered_rule(analysis):
    response = await chat.answer(request("Why is release confidence low?"))
    assert analysis.release.triggered_rules
    assert all(rule in response.answer for rule in analysis.release.triggered_rules)
    assert analysis.release.decision in response.answer
    assert f"{analysis.release.confidence}/100" in response.answer
    assert response.provider == "template"


@pytest.mark.parametrize("message", chat.STARTER_QUESTIONS)
async def test_all_story_starters_are_deterministic_and_normalized(analysis, message):
    expected = await chat.answer(request(message))
    alternate = await chat.answer(request("  " + message.upper().rstrip("?") + "  "))
    assert expected == alternate
    assert expected.provider == "template"
    assert "ST-107" in expected.answer
    assert expected.answer.startswith("- ")
    if message == "What is impacted?":
        assert set(analysis.requirement.affected_services).issubset(expected.cited_nodes)
    if message == "Why is risk high?":
        assert expected.cited_factors
        assert all(label in expected.answer for label in expected.cited_factors)
    if message == "What should be tested?":
        p1_tests = [test for test in analysis.tests.tests if test.priority == "P1"]
        assert p1_tests
        assert all(test.title in expected.answer for test in p1_tests)
    if message == "Which stories are risky?":
        assert "Open the sprint view" in expected.answer
        assert "ST-115" not in expected.answer


async def test_open_questions_need_a_key(analysis):
    response = await chat.answer(request("Who owns the release window?"))
    assert response == ChatResponse(
        answer="The copilot needs an API key for open questions. Add one to .env.",
        cited_nodes=[], cited_factors=[], provider="template",
    )


@pytest.mark.parametrize("context_type", ["story", "sprint"])
async def test_missing_context_is_actionable(context_type):
    response = await chat.answer(request("What is impacted?", "missing", context_type))
    assert response == ChatResponse(
        answer="I don't have an analysis for missing yet. Run the analysis first.",
        cited_nodes=[], cited_factors=[], provider="none",
    )


async def test_latest_analysis_wins_over_fixture_and_previous_run(analysis):
    config.FIXTURES_DIR.mkdir()
    (config.FIXTURES_DIR / "story-ST-107.json").write_text(analysis.model_dump_json(), encoding="utf-8")
    updated = analysis.model_copy(deep=True)
    updated.release.triggered_rules = ["Latest saved release blocker"]
    db.save_analysis(updated)
    response = await chat.answer(request("Why is release confidence low?"))
    assert "Latest saved release blocker" in response.answer
    assert all(rule not in response.answer for rule in analysis.release.triggered_rules)


async def test_story_fixture_fallback_validates_identity(analysis, monkeypatch):
    monkeypatch.setattr(db, "latest_story_analysis", lambda _: None)
    config.FIXTURES_DIR.mkdir()
    fixture_path = config.FIXTURES_DIR / "story-ST-107.json"
    fixture_path.write_text(analysis.model_dump_json(), encoding="utf-8")
    assert (await chat.answer(request("What is impacted?"))).provider == "template"
    mismatched = analysis.model_copy(deep=True)
    mismatched.story.id = "ST-115"
    fixture_path.write_text(mismatched.model_dump_json(), encoding="utf-8")
    assert (await chat.answer(request("What is impacted?"))).provider == "none"
    fixture_path.write_text("not valid JSON", encoding="utf-8")
    assert (await chat.answer(request("What is impacted?"))).provider == "none"
    assert (await chat.answer(request("What is impacted?", "../ST-107"))).provider == "none"


@pytest.mark.parametrize("message", chat.STARTER_QUESTIONS)
async def test_sprint_starters_include_only_recorded_data(sprint, message):
    response = await chat.answer(request(message, sprint.sprint_id, "sprint"))
    assert response.provider == "template"
    assert "ST-107" in response.answer
    if message == "Which stories are risky?":
        assert "ST-115" not in response.answer
        assert sprint.stories[0].release.decision in response.answer
    if message == "Why is release confidence low?":
        assert "release confidence 30/100" in response.answer
        assert "deployment_collision" in response.answer
        assert "authentication-service" in response.cited_nodes
        assert sprint.conflicts[0].recommendation in response.answer


async def test_sprint_fixture_fallback_validates_identity(sprint, monkeypatch):
    monkeypatch.setattr(db, "latest_sprint", lambda _: None)
    config.FIXTURES_DIR.mkdir()
    (config.FIXTURES_DIR / "sprint.json").write_text(sprint.model_dump_json(), encoding="utf-8")
    assert (await chat.answer(request("Which stories are risky?", "sprint-42", "sprint"))).provider == "template"
    assert (await chat.answer(request("Which stories are risky?", "sprint-99", "sprint"))).provider == "none"


@pytest.mark.parametrize("message", [chat.STARTER_QUESTIONS[-1], "An open question"])
async def test_nollm_fallback_with_enabled_configuration(analysis, monkeypatch, message):
    monkeypatch.setattr(config, "llm_disabled", lambda: False)

    async def unavailable(*args, **kwargs):
        raise llm.NoLLM("Mock provider unavailable")

    monkeypatch.setattr(llm, "complete_text", unavailable)
    response = await chat.answer(request(message))
    assert response.provider == "template"
    assert response.answer == chat._template(message, analysis)


async def test_llm_uses_compressed_context_and_extracts_citations(analysis, monkeypatch):
    label = analysis.risk.dimensions[0].factors[0].label
    node_id = analysis.requirement.affected_services[0]
    calls = []

    async def complete(system, user, history=None, max_tokens=800):
        calls.append((system, user, history, max_tokens))
        return f"- {label}: `{node_id}`.", "mock:copilot"

    monkeypatch.setattr(config, "llm_disabled", lambda: False)
    monkeypatch.setattr(llm, "complete_text", complete)
    response = await chat.answer(request("An open question"))
    assert response.provider == "mock:copilot"
    assert response.cited_nodes == [node_id]
    assert label in response.cited_factors
    system, user, history, tokens = calls[0]
    assert system.startswith("Answer only from the analysis context. Cite factor labels and component IDs.")
    context = json.loads(system.split("Analysis context (JSON):\n", 1)[1])
    assert context["release"]["triggered_rules"] == analysis.release.triggered_rules
    assert context["compliance"] == analysis.compliance.model_dump()
    assert all(test["priority"] == "P1" for test in context["tests"]["p1_tests"])
    assert all(len(dimension["top_factors"]) <= 3 for dimension in context["risk"]["dimensions"])
    assert "nodes" not in context["impact"]
    assert "acceptance_criteria" not in context
    assert (user, history, tokens) == ("An open question", [], 800)


async def test_sprint_prompt_includes_conflicts_and_decisions(sprint, monkeypatch):
    async def complete(system, user, **kwargs):
        context = json.loads(system.split("Analysis context (JSON):\n", 1)[1])
        assert context["conflicts"] == [conflict.model_dump() for conflict in sprint.conflicts]
        assert context["kpis"] == sprint.kpis.model_dump()
        assert [story["release"]["decision"] for story in context["stories"]] == [
            story.release.decision for story in sprint.stories
        ]
        return "The context contains two stories.", "mock:copilot"

    monkeypatch.setattr(config, "llm_disabled", lambda: False)
    monkeypatch.setattr(llm, "complete_text", complete)
    assert (await chat.answer(request("Which stories are risky?", "sprint-42", "sprint"))).provider == "mock:copilot"


async def test_ten_turn_history_isolated_by_session_and_context(analysis, monkeypatch):
    calls = []

    async def complete(system, user, history=None, **kwargs):
        calls.append(history)
        return f"Answer to {user}", "mock:copilot"

    monkeypatch.setattr(config, "llm_disabled", lambda: False)
    monkeypatch.setattr(llm, "complete_text", complete)
    for index in range(12):
        await chat.answer(request(f"Question {index}"))
    assert len(calls[10]) == len(calls[11]) == 20
    assert calls[11][0] == {"role": "user", "content": "Question 1"}
    assert calls[11][-1] == {"role": "assistant", "content": "Answer to Question 10"}
    assert len(chat._sessions["session"].history) == 20
    await chat.answer(request("Other session", session_id="other"))
    assert calls[-1] == []
    other = analysis.model_copy(deep=True)
    other.story.id = "ST-115"
    db.save_analysis(other)
    await chat.answer(request("Other context", "ST-115"))
    assert calls[-1] == []


async def test_concurrent_requests_preserve_complete_turns(analysis, monkeypatch):
    histories = []

    async def complete(system, user, history=None, **kwargs):
        histories.append(history)
        await asyncio.sleep(0)
        return f"Answer to {user}", "mock:copilot"

    monkeypatch.setattr(config, "llm_disabled", lambda: False)
    monkeypatch.setattr(llm, "complete_text", complete)
    await asyncio.gather(chat.answer(request("First")), chat.answer(request("Second")))
    assert histories == [[], [
        {"role": "user", "content": "First"},
        {"role": "assistant", "content": "Answer to First"},
    ]]


def test_citations_match_whole_ids_and_deduplicate(analysis):
    node_id = analysis.requirement.affected_services[0]
    label = analysis.risk.dimensions[0].factors[0].label
    nodes, factors = chat._citations(f"{node_id} {node_id} {label.upper()} {label}", analysis)
    assert nodes == [node_id]
    assert factors.count(label) == 1
    assert chat._citations(f"prefix{node_id}suffix", analysis)[0] == []


async def test_post_chat_routes_to_copilot_and_validates_requests(analysis):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        req = request("Why is release confidence low?")
        response = await client.post("/chat", json=req.model_dump())
        assert response.status_code == 200
        result = ChatResponse.model_validate(response.json())
        assert result.provider == "template"
        assert analysis.release.triggered_rules[0] in result.answer
        assert (await client.post("/chat", json={"message": "Missing fields"})).status_code == 422
