"""Background runs: live stage progress, LLM attempt attribution and the debug view."""

import time

import pytest
from fastapi.testclient import TestClient

from app import llm, pipeline
from app import runs as tracker
from app.api.main import app
from app.architecture import load_demo_sprint
from app.contracts import StoryAnalysis
from tests.test_llm import Facts, mock_chain, response  # noqa: F401
from tests.test_pipeline import isolated, story  # noqa: F401


@pytest.fixture
def client(isolated):  # noqa: F811
    with TestClient(app) as test_client:
        yield test_client


def wait(client, run_id, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = client.get(f"/runs/{run_id}").json()
        if run["status"] != "running":
            return run
        time.sleep(0.05)
    raise AssertionError("run did not finish")


def test_story_run_reports_every_stage_and_its_source(client, story):  # noqa: F811
    started = client.post("/runs/story", json=story.model_dump(mode="json"))
    assert started.status_code == 202
    run = wait(client, started.json()["run_id"])
    assert run["status"] == "succeeded" and run["kind"] == "story"
    stages = {item["stage"]: item for item in run["stages"]}
    assert list(stages) == list(tracker.STORY_STAGES)
    assert all(item["status"] == "done" and item["story_id"] == story.id for item in stages.values())
    assert stages["dependency"]["source"] == stages["scoring"]["source"] == "deterministic"
    # No keys in tests: model stages fall back to built-in text, and the run says so.
    assert stages["requirement"]["source"] == "fallback"
    assert "components impacted" in stages["dependency"]["message"]
    assert any("No model is configured" in entry["message"] for entry in run["log"])
    result = StoryAnalysis.model_validate(run["story_result"])
    assert result.story == story
    assert run["finished_at"] and run["elapsed_ms"] >= 0


def test_unchanged_demo_story_run_serves_the_saved_result(client, story, isolated):  # noqa: F811
    import asyncio
    fixture = asyncio.run(pipeline.analyze_story(story))
    (isolated / "fixtures").mkdir()
    (isolated / "fixtures" / f"story-{story.id}.json").write_text(fixture.model_dump_json(), encoding="utf-8")
    run = wait(client, client.post("/runs/story", json=story.model_dump(mode="json")).json()["run_id"])
    assert {item["source"] for item in run["stages"]} == {"fixture"}
    assert run["attempts"] == []
    assert any("saved result" in entry["message"] for entry in run["log"])


def test_sprint_run_tracks_each_story_and_sprint_stages(client):
    demo = load_demo_sprint()
    run = wait(client, client.post("/runs/sprint", json={}).json()["run_id"], timeout=60)
    assert run["status"] == "succeeded", run["error"]
    assert run["story_ids"] == [s.id for s in demo.stories]
    sprint_stages = {item["stage"]: item for item in run["stages"] if item["story_id"] is None}
    assert set(sprint_stages) == set(tracker.SPRINT_STAGES)
    assert "conflicts between stories" in sprint_stages["conflicts"]["message"]
    assert all(item["status"] == "done" for item in run["stages"])
    assert run["sprint_result"]["kpis"]["stories"] == len(demo.stories)


def test_bad_input_is_rejected_before_a_run_starts(client, story):  # noqa: F811
    body = {"stories": [story.model_dump(mode="json")] * 2}
    assert client.post("/runs/sprint", json=body).status_code == 422
    assert client.get("/runs/not-a-run").status_code == 404


def test_recent_runs_omit_results_and_include_chat(client, story):  # noqa: F811
    wait(client, client.post("/runs/story", json=story.model_dump(mode="json")).json()["run_id"])
    client.post("/chat", json={
        "session_id": "s", "message": "What is impacted?", "context_type": "story", "context_id": story.id,
    })
    recent = client.get("/runs").json()
    assert [item["kind"] for item in recent[:2]] == ["chat", "story"]
    assert all(item["story_result"] is None for item in recent)


def test_debug_describes_the_chain_without_keys(client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-value-never-returned")
    info = client.get("/debug")
    assert info.status_code == 200
    body = info.json()
    assert [p["model"] for p in body["providers"]] == [p.model for p in llm.PROVIDERS]
    assert body["timeout_s"] == llm.LLM_TIMEOUT_S and body["max_tokens"] == llm.MAX_TOKENS
    assert "secret-value-never-returned" not in info.text


async def test_attempts_are_attributed_with_plain_reasons(mock_chain):  # noqa: F811
    first, second, third = llm.PROVIDERS[:3]
    mock_chain.outcomes[first.model].append(TimeoutError())
    truncated = response("{\"affected\": tr")
    truncated.choices[0].finish_reason = "length"
    mock_chain.outcomes[second.model].append(truncated)
    mock_chain.outcomes[third.model].append(response(tool=True))
    with tracker.tracked("story", "t", ["ST-1"], tracker.story_plan(["ST-1"])) as run:
        with tracker.story_scope("ST-1"), tracker.stage("requirement") as item:
            _, label = await llm.complete_structured("Extract.", "A change.", Facts, max_tokens=99)
            tracker.describe(item, label, "done")
    outcomes = [(a.provider, a.outcome) for a in run.attempts]
    assert outcomes == [("tokenharbor", "timeout"), ("openrouter", "truncated"), ("openrouter", "ok")]
    assert all(a.stage == "requirement" and a.story_id == "ST-1" for a in run.attempts)
    assert run.attempts[0].detail == f"Timed out after {llm.LLM_TIMEOUT_S:.0f} s"
    assert "99-token limit" in run.attempts[1].detail
    stage = next(s for s in run.stages if s.stage == "requirement")
    assert stage.source == "llm" and stage.provider == third.label
    assert sum(entry.level == "warning" for entry in run.log) == 2


async def test_tracking_is_a_no_op_outside_a_run(mock_chain):  # noqa: F811
    mock_chain.outcomes[llm.PROVIDERS[0].model].append(response())
    assert tracker.current() is None
    _, label = await llm.complete_structured("Extract.", "A change.", Facts)
    assert label == llm.PROVIDERS[0].label
