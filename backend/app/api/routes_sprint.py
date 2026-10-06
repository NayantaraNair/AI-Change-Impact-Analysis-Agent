"""Runnable sprint integration stand-in; T12 supplies conflict detection."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app import db, pipeline
from app.api.fixtures import sprint_fixture
from app.architecture import get_architecture, load_demo_sprint
from app.contracts import ImpactGraph, SprintAnalysis, SprintKpis, SprintRequest
from app.engine.dependency import build_impact_graph

router = APIRouter()


def _union_graph(analyses) -> ImpactGraph:
    if not analyses:
        return build_impact_graph([], get_architecture())
    nodes, edges = {}, {}
    fields = (
        "impacted_services", "impacted_databases", "impacted_apis",
        "downstream_systems", "deployment_groups",
    )
    summaries = {field: set() for field in fields}
    for analysis in analyses:
        for node in analysis.graph.nodes:
            previous = nodes.get(node.id)
            if previous is None or (
                node.hop is not None and (previous.hop is None or node.hop < previous.hop)
            ):
                nodes[node.id] = node
        for edge in analysis.graph.edges:
            previous = edges.get(edge.id)
            edges[edge.id] = edge.model_copy(update={
                "on_impact_path": edge.on_impact_path or bool(previous and previous.on_impact_path),
                "conflict": False,
            })
        for field in fields:
            summaries[field].update(getattr(analysis.graph, field))
    return ImpactGraph(
        nodes=[nodes[key] for key in sorted(nodes)],
        edges=[edges[key] for key in sorted(edges)],
        **{field: sorted(values) for field, values in summaries.items()},
    )


@router.post("/analyze-sprint", response_model=SprintAnalysis)
async def analyze_sprint(request: SprintRequest, refresh: bool = False) -> SprintAnalysis:
    fixture = None if refresh else sprint_fixture(request)
    if fixture is not None:
        await asyncio.to_thread(db.save_sprint, fixture)
        return fixture
    demo = load_demo_sprint()
    stories = request.stories or demo.stories
    is_demo = stories == demo.stories
    analyses = await asyncio.gather(*(
        pipeline.analyze_story(story, refresh=refresh) for story in stories
    ))
    graph = _union_graph(analyses)
    count = len(analyses)
    kpis = SprintKpis(
        stories=count,
        applications_impacted=sum(n.hop is not None and n.type != "database" for n in graph.nodes),
        dependencies_impacted=len(graph.downstream_systems), conflicts=0,
        compliance_issues=sum(
            f.applicable and (f.risk_level == "high" or (f.score is not None and f.score < 70))
            for a in analyses for f in a.compliance.frameworks
        ),
        testing_effort_hours=round(sum(a.tests.effort_hours for a in analyses), 2),
        health_score=round(sum(100 - a.risk.overall for a in analyses) / count) if count else 100,
        release_confidence=round(sum(a.release.confidence for a in analyses) / count) if count else 0,
        high_risk_stories=[a.story.id for a in analyses if a.risk.overall >= 70],
    )
    result = SprintAnalysis(
        sprint_id=request.sprint_id or (demo.sprint_id if is_demo else f"sprint-{uuid4().hex}"),
        name=request.name or (demo.name if is_demo else "Custom sprint"),
        stories=analyses, conflicts=[], kpis=kpis, conflict_graph=graph,
        summary=f"Analyzed {count} stories. Cross-story conflict detection is not wired yet.",
    )
    await asyncio.to_thread(db.save_sprint, result)
    return result


@router.get("/sprint/{sprint_id}", response_model=SprintAnalysis)
def sprint(sprint_id: str) -> SprintAnalysis:
    analysis = db.latest_sprint(sprint_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Sprint analysis not found")
    return analysis
