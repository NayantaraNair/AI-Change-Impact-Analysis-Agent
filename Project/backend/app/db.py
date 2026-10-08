"""SQLite persistence for stories, sprint snapshots, and every analysis run."""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from threading import Lock
from uuid import uuid4

from sqlalchemy import JSON, Column
from sqlmodel import Field, Session, SQLModel, create_engine, select

from app import config
from app.contracts import SprintAnalysis, StoryAnalysis

_initialization_lock = Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Sprint(SQLModel, table=True):
    __tablename__ = "sprint"

    id: str = Field(primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=_now)
    payload: dict = Field(sa_column=Column(JSON, nullable=False))


class Story(SQLModel, table=True):
    __tablename__ = "story"

    id: str = Field(primary_key=True)
    payload: dict = Field(sa_column=Column(JSON, nullable=False))


class AnalysisRun(SQLModel, table=True):
    __tablename__ = "analysis_run"

    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    story_id: str = Field(foreign_key="story.id", index=True)
    sprint_id: str | None = Field(default=None, foreign_key="sprint.id", index=True)
    created_at: datetime = Field(default_factory=_now, index=True)
    payload: dict = Field(sa_column=Column(JSON, nullable=False))


@lru_cache(maxsize=8)
def _engine_for(path: str):
    return create_engine(
        f"sqlite:///{Path(path).as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )


def _engine():
    # Resolve at call time: tests and deployments may change DB_PATH.
    path = Path(config.DB_PATH).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = _engine_for(str(path))
    # Concurrent pipelines may save before an API lifespan has initialized SQLite.
    with _initialization_lock:
        SQLModel.metadata.create_all(engine)
    return engine


def init_db() -> None:
    _engine()


def _save_story(session: Session, analysis: StoryAnalysis) -> None:
    story = session.get(Story, analysis.story.id)
    payload = analysis.story.model_dump(mode="json")
    if story is None:
        story = Story(id=analysis.story.id, payload=payload)
    else:
        story.payload = payload
    session.add(story)


def save_analysis(analysis: StoryAnalysis, sprint_id: str | None = None) -> None:
    with Session(_engine()) as session:
        _save_story(session, analysis)
        session.add(AnalysisRun(
            story_id=analysis.story.id,
            sprint_id=sprint_id,
            payload=analysis.model_dump(mode="json"),
        ))
        session.commit()


def latest_story_analysis(story_id: str) -> StoryAnalysis | None:
    with Session(_engine()) as session:
        run = session.exec(
            select(AnalysisRun)
            .where(AnalysisRun.story_id == story_id)
            .order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc())
            .limit(1)
        ).first()
        return StoryAnalysis.model_validate(run.payload) if run else None


def save_sprint(sprint: SprintAnalysis) -> None:
    with Session(_engine()) as session:
        record = session.get(Sprint, sprint.sprint_id)
        payload = sprint.model_dump(mode="json")
        if record is None:
            record = Sprint(id=sprint.sprint_id, name=sprint.name, payload=payload)
        else:
            record.name = sprint.name
            record.created_at = _now()
            record.payload = payload
        session.add(record)
        session.flush()
        for analysis in sprint.stories:
            _save_story(session, analysis)
            story_payload = analysis.model_dump(mode="json")
            latest = session.exec(
                select(AnalysisRun)
                .where(AnalysisRun.story_id == analysis.story.id)
                .order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc())
                .limit(1)
            ).first()
            # Link a run just produced by the pipeline rather than saving it twice.
            if latest and latest.payload == story_payload and latest.sprint_id is None:
                latest.sprint_id = sprint.sprint_id
                session.add(latest)
            else:
                session.add(AnalysisRun(
                    story_id=analysis.story.id,
                    sprint_id=sprint.sprint_id,
                    payload=story_payload,
                ))
        session.commit()


def latest_sprint(sprint_id: str) -> SprintAnalysis | None:
    with Session(_engine()) as session:
        record = session.get(Sprint, sprint_id)
        return SprintAnalysis.model_validate(record.payload) if record else None
