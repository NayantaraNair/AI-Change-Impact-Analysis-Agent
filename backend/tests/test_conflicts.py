"""Conflict rules use categorical facts and architecture, never provider output."""

from datetime import datetime, timezone

import pytest

from app.contracts import (
    ApiEndpoint, Architecture, ComplianceReport, Component, ReleaseAssessment,
    RequirementFacts, RiskReport, StoryAnalysis, StoryInput, TestPlan,
)
from app.engine.conflicts import detect_conflicts
from app.engine.dependency import build_impact_graph


def component(node_id, group="core", criticality=5, **kwargs):
    return Component(
        id=node_id, name=node_id, type=kwargs.pop("type", "core"),
        description="Test component", owner_team="Test team", owner_contact="test@example.test",
        criticality=criticality, deployment_group=group, sla_tier="tier2", **kwargs,
    )


@pytest.fixture
def arch():
    return Architecture(components=[
        component("a", criticality=8, downstream=["db"]),
        component("b", criticality=6, downstream=["db"]),
        component("auth", group="identity", criticality=10, apis=[ApiEndpoint(
            id="login", method="POST", path="/login", description="Login", external=True,
        )]),
        component("db", group="data", criticality=9, type="database"),
        component("isolated", group="separate"),
    ])


def analysis(story_id, direct, arch, *, decision="GO", **facts):
    requirement = RequirementFacts(
        business_summary="Test change", technical_summary="Test scope", business_domain="test",
        affected_capabilities=[], affected_services=direct, change_type="enhancement",
        touches_customer_data=False, touches_card_data=False, touches_financial_data=False,
        changes_auth_flow=False, changes_external_api_contract=False, changes_db_schema=False,
        ambiguity="low", engineering_scope="Test scope", source="test",
    ).model_copy(update=facts)
    return StoryAnalysis(
        story=StoryInput(id=story_id, title="Test change", description="Test scope"),
        requirement=requirement, graph=build_impact_graph(direct, arch),
        risk=RiskReport(dimensions=[], overall=20, highest="technical"),
        tests=TestPlan(tests=[], coverage_estimate=1, effort_hours=2.5,
                       automation_candidates=0, summary="Tests"),
        compliance=ComplianceReport(frameworks=[], overall_score=100, summary="Compliant"),
        release=ReleaseAssessment(
            confidence=90, decision=decision, triggered_rules=[], conditions=[], complexity="low",
            rollback_plan=["Restore previous version"], deployment_notes=["Deploy behind a flag"],
        ), providers_used={"release": "test"}, duration_ms=0, created_at=datetime.now(timezone.utc),
    )


def test_exact_component_collision_is_canonical_and_deduplicated(arch):
    a, b = analysis("A", ["auth"], arch), analysis("B", ["auth"], arch)
    before = a.model_dump()
    conflicts = detect_conflicts([b, a, a], arch)
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert (conflict.story_a, conflict.story_b, conflict.shared_component) == ("A", "B", "auth")
    assert conflict.id == "C-A-B-auth"
    assert conflict.kind == "deployment_collision"
    assert conflict.risk_score == 80 and conflict.risk == "high"
    assert all(term in conflict.recommendation for term in ["A", "B", "auth", "regression"])
    assert a.model_dump() == before
    assert detect_conflicts([a, b], arch) == conflicts


def test_different_roots_same_group_choose_most_critical_root(arch):
    conflicts = detect_conflicts([analysis("A", ["a"], arch), analysis("B", ["b"], arch)], arch)
    assert [(c.kind, c.shared_component, c.risk_score) for c in conflicts] == [
        ("deployment_collision", "a", 72),
    ]


def test_representative_ties_are_stable_and_exact_collisions_are_retained(arch):
    arch.components[1].criticality = 8
    stories = [analysis("A", ["a", "b"], arch), analysis("B", ["a", "b"], arch)]
    assert [(c.kind, c.shared_component) for c in detect_conflicts(stories, arch)] == [
        ("deployment_collision", "a"), ("deployment_collision", "b"),
    ]


def test_indirect_overlap_and_separate_groups_do_not_conflict(arch):
    assert detect_conflicts([
        analysis("A", ["a"], arch), analysis("B", ["isolated"], arch),
    ], arch) == []
    assert detect_conflicts([analysis("A", [], arch), analysis("B", [], arch)], arch) == []
    assert detect_conflicts([], arch) == []


def test_missing_deployment_group_produces_parallel_modification(arch):
    arch.components[-1].deployment_group = ""
    conflicts = detect_conflicts([
        analysis("A", ["isolated"], arch), analysis("B", ["isolated"], arch),
    ], arch)
    assert len(conflicts) == 1 and conflicts[0].kind == "parallel_modification"


@pytest.mark.parametrize("schema_a,schema_b,kind", [
    (False, False, "shared_database"), (True, False, "shared_database"),
    (False, True, "shared_database"), (True, True, "schema_contention"),
])
def test_direct_database_change(arch, schema_a, schema_b, kind):
    conflicts = detect_conflicts([
        analysis("A", ["db"], arch, changes_db_schema=schema_a),
        analysis("B", ["db"], arch, changes_db_schema=schema_b),
    ], arch)
    assert {(c.shared_component, c.kind) for c in conflicts} == {
        ("db", "deployment_collision"), ("db", kind),
    }


@pytest.mark.parametrize("schema_a,schema_b,expected", [
    (False, False, False), (True, False, False), (False, True, False), (True, True, True),
])
def test_shared_nearby_database_requires_both_schema_flags(arch, schema_a, schema_b, expected):
    conflicts = detect_conflicts([
        analysis("A", ["a"], arch, changes_db_schema=schema_a),
        analysis("B", ["b"], arch, changes_db_schema=schema_b),
    ], arch)
    databases = [c for c in conflicts if c.shared_component == "db"]
    assert bool(databases) == expected
    if expected:
        assert len(databases) == 1 and databases[0].kind == "schema_contention"


@pytest.mark.parametrize("hop", [2, None])
def test_far_or_unimpacted_database_is_excluded(arch, hop):
    first = analysis("A", ["a"], arch, changes_db_schema=True)
    second = analysis("B", ["b"], arch, changes_db_schema=True)
    next(n for n in second.graph.nodes if n.id == "db").hop = hop
    assert all(c.shared_component != "db" for c in detect_conflicts([first, second], arch))


@pytest.mark.parametrize("external,flag_a,flag_b,expected", [
    (True, True, True, True), (False, True, True, False),
    (True, False, True, False), (True, True, False, False),
])
def test_api_contract_requires_external_api_and_both_flags(arch, external, flag_a, flag_b, expected):
    arch.components[2].apis[0].external = external
    conflicts = detect_conflicts([
        analysis("A", ["auth"], arch, changes_external_api_contract=flag_a),
        analysis("B", ["auth"], arch, changes_external_api_contract=flag_b),
    ], arch)
    assert any(c.kind == "shared_api_change" for c in conflicts) == expected
    assert len({(c.story_a, c.story_b, c.shared_component, c.kind) for c in conflicts}) == len(conflicts)


@pytest.mark.parametrize("criticality,decision,auth,score,level", [
    (1, "GO", False, 44, "medium"), (7, "GO", False, 68, "medium"),
    (8, "GO", False, 72, "high"), (5, "NO_GO", False, 80, "high"),
    (5, "GO", True, 70, "high"), (10, "NO_GO", True, 100, "high"),
])
def test_risk_formula_bonuses_and_clamp(arch, criticality, decision, auth, score, level):
    arch.components[2].criticality = criticality
    conflicts = detect_conflicts([
        analysis("A", ["auth"], arch),
        analysis("B", ["auth"], arch, decision=decision, changes_auth_flow=auth),
    ], arch)
    assert len(conflicts) == 1
    assert (conflicts[0].risk_score, conflicts[0].risk) == (score, level)
