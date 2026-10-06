"""Validate shipped fixtures and the offline builder's complete mirrored output."""

import importlib.util
from pathlib import Path

import pytest

from app import config, db
from app.agents import chat
from app.architecture import load_demo_sprint
from app.contracts import ChatRequest, ChatResponse, DemoSprint, SprintAnalysis, StoryAnalysis

ROOT = Path(__file__).resolve().parents[2]
DATA_FIXTURES = ROOT / "data" / "fixtures"
PUBLIC_FIXTURES = ROOT / "frontend" / "public" / "fixtures"
FIXTURE_PATHS = sorted(DATA_FIXTURES.glob("*.json"))
spec = importlib.util.spec_from_file_location("build_fixtures", ROOT / "scripts" / "build_fixtures.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def fixture_schema(name):
    if name == "demo-sprint.json":
        return DemoSprint
    if name == "sprint.json":
        return SprintAnalysis
    if name.startswith("story-"):
        return StoryAnalysis
    if name.startswith("chat-"):
        return ChatResponse
    pytest.fail(f"Unexpected fixture filename: {name}")


@pytest.mark.parametrize("path", FIXTURE_PATHS, ids=[path.name for path in FIXTURE_PATHS])
def test_fixture_validates_and_matches_frontend(path):
    payload = path.read_text(encoding="utf-8")
    fixture_schema(path.name).model_validate_json(payload)
    assert (PUBLIC_FIXTURES / path.name).read_bytes() == path.read_bytes()


async def test_builder_exports_final_analyses_and_all_starters(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "app.db")
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(config, "FIXTURES_DIR", tmp_path / "unused-fixtures")
    monkeypatch.setattr(chat, "_sessions", {})
    directories = (tmp_path / "data", tmp_path / "public")
    for directory in directories:
        directory.mkdir()
        (directory / "stale.json").write_text("{}", encoding="utf-8")
        (directory / "keep.txt").write_text("keep", encoding="utf-8")
    fixtures = await builder.build_fixtures(refresh=True, directories=directories)
    demo = load_demo_sprint()
    sprint = fixtures["sprint.json"]
    expected = {"sprint.json", "demo-sprint.json"}
    expected.update(f"story-{story.id}.json" for story in demo.stories)
    contexts = [("story", story.id) for story in demo.stories] + [("sprint", demo.sprint_id)]
    expected.update(f"chat-{context_id}-{n}.json" for _, context_id in contexts for n in range(5))
    assert set(fixtures) == expected
    assert fixtures["demo-sprint.json"] == demo
    assert sprint.conflicts
    for analysis in sprint.stories:
        assert fixtures[f"story-{analysis.story.id}.json"] == analysis
        assert db.latest_story_analysis(analysis.story.id) == analysis
    for context_type, context_id in contexts:
        for n, question in enumerate(chat.STARTER_QUESTIONS):
            response = await chat.answer(ChatRequest(
                session_id=f"verify-{context_id}-{n}", context_type=context_type,
                context_id=context_id, message=question,
            ))
            assert fixtures[f"chat-{context_id}-{n}.json"] == response
            assert response.provider == "template"
            assert response.answer
    for directory in directories:
        assert {path.name for path in directory.glob("*.json")} == expected
        assert (directory / "keep.txt").read_text(encoding="utf-8") == "keep"
        for name in expected:
            path = directory / name
            fixture_schema(name).model_validate_json(path.read_text(encoding="utf-8"))
            assert path.read_bytes() == (directories[0] / name).read_bytes()


def test_builder_rejects_unsafe_context_ids():
    with pytest.raises(ValueError, match="safe fixture filename"):
        builder._check_id("../outside")
