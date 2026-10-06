"""Concrete JSON round-trips for every shared model, including nested analyses."""

from datetime import datetime, timezone
import inspect

import pytest
from pydantic import BaseModel

from app import contracts as c


def samples() -> list[BaseModel]:
    api = c.ApiEndpoint(id="accounts.read", method="GET", path="/accounts", description="Read accounts", external=True)
    component = c.Component(
        id="accounts", name="Accounts", type="core", description="Account ledger",
        owner_team="Ledger", owner_contact="ledger@example.test", criticality=9,
        data_classes=["financial", "pii"], apis=[api], upstream=["mobile"],
        downstream=["ledger-db"], deployment_group="ledger", sla_tier="tier1",
    )
    architecture = c.Architecture(components=[component])
    catalog = c.CatalogTest(
        id="CAT-1", title="Read account", type="api", services=[component.id],
        apis=[api.id], automated=True, duration_min=5,
    )
    story = c.StoryInput(
        id="ST-1", title="Change account response", description="Expose account status",
        type="change_request", acceptance_criteria=["Status returned"],
    )
    demo = c.DemoSprint(sprint_id="SP-1", name="Ledger sprint", stories=[story])
    facts = c.RequirementFacts(
        business_summary="Show status", technical_summary="Extend response",
        business_domain="Accounts", affected_capabilities=["Account inquiry"],
        affected_services=[component.id], change_type="enhancement",
        touches_customer_data=True, touches_card_data=False, touches_financial_data=True,
        changes_auth_flow=False, changes_external_api_contract=True, changes_db_schema=False,
        ambiguity="low", engineering_scope="Account API", source="keyword-fallback",
    )
    node = c.GraphNode(
        id=component.id, label=component.name, type=component.type, hop=0, severity="high",
        x=100.5, y=200.25, criticality=9, owner_team="Ledger", data_classes=["financial"],
    )
    edge = c.GraphEdge(id="accounts-db", source=component.id, target="ledger-db", on_impact_path=True, conflict=True)
    graph = c.ImpactGraph(
        nodes=[node], edges=[edge], impacted_services=[component.id],
        impacted_databases=["ledger-db"], impacted_apis=[api.id], downstream_systems=["ledger-db"],
        deployment_groups=["ledger"],
    )
    factor = c.RiskFactor(label="External contract", points=20, node_ids=[component.id])
    dimension = c.RiskDimension(name="technical", score=20, level="low", factors=[factor], explanation="Contract tests needed")
    risk = c.RiskReport(dimensions=[dimension], overall=20, highest="technical")
    case = c.TestCase(
        id="TC-1", title="Account response", type="api", priority="P1", covers=[component.id],
        steps=["Request accounts"], expected="Status included", source="catalog", automation_candidate=True,
    )
    plan = c.TestPlan(tests=[case], coverage_estimate=0.8, effort_hours=1.5, automation_candidates=1, summary="Verify contract")
    finding = c.ComplianceFinding(text="Customer data processed", node_ids=[component.id])
    framework = c.FrameworkAssessment(
        framework="GDPR", applicable=True, reason="PII", risk_level="medium", score=75,
        findings=[finding], recommendations=["Verify access controls"],
    )
    compliance = c.ComplianceReport(frameworks=[framework], overall_score=75, summary="Review access")
    release = c.ReleaseAssessment(
        confidence=80, decision="GO_WITH_CONDITIONS", triggered_rules=["External contract changed"],
        conditions=["Contract tests pass"], complexity="medium", rollback_plan=["Revert response"],
        deployment_notes=["Deploy ledger group"],
    )
    analysis = c.StoryAnalysis(
        story=story, requirement=facts, graph=graph, risk=risk, tests=plan,
        compliance=compliance, release=release, providers_used={"requirement": "keyword-fallback"},
        duration_ms=123, created_at=datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc),
    )
    conflict = c.Conflict(
        id="CF-1", story_a=story.id, story_b="ST-2", shared_component=component.id,
        kind="shared_api_change", risk="medium", risk_score=50, recommendation="Coordinate contract changes",
    )
    kpis = c.SprintKpis(
        stories=1, applications_impacted=1, dependencies_impacted=1, conflicts=1,
        compliance_issues=1, testing_effort_hours=1.5, health_score=75, release_confidence=80,
        high_risk_stories=[story.id],
    )
    sprint = c.SprintAnalysis(
        sprint_id=demo.sprint_id, name=demo.name, stories=[analysis], conflicts=[conflict],
        kpis=kpis, conflict_graph=graph, summary="Coordinate API rollout",
    )
    request = c.SprintRequest(sprint_id=demo.sprint_id, name=demo.name, stories=[story])
    chat_request = c.ChatRequest(session_id="SESSION-1", message="Why this risk?", context_type="story", context_id=story.id)
    chat_response = c.ChatResponse(answer="The API contract changes", cited_nodes=[component.id], cited_factors=[factor.label], provider="deterministic")
    return [
        api, component, architecture, catalog, story, demo, facts, node, edge, graph,
        factor, dimension, risk, case, plan, finding, framework, compliance, release,
        analysis, conflict, kpis, sprint, request, chat_request, chat_response,
    ]


SAMPLES = samples()


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda model: type(model).__name__)
def test_contract_round_trip(sample):
    model = type(sample)
    assert model.model_validate_json(sample.model_dump_json()) == sample
    assert model.model_validate(sample.model_dump(mode="json")) == sample


def test_samples_cover_every_contract_model():
    models = {
        model for _, model in inspect.getmembers(c, inspect.isclass)
        if issubclass(model, BaseModel) and model.__module__ == c.__name__
    }
    assert {type(sample) for sample in SAMPLES} == models


@pytest.mark.parametrize("sample", [
    c.SprintRequest(),
    c.GraphNode(id="other", label="Other", type="platform", hop=None, severity=None,
                x=0, y=0, criticality=1, owner_team="Platform", data_classes=[]),
    c.FrameworkAssessment(framework="PCI DSS", applicable=False, reason="No card data",
                          risk_level=None, score=None, findings=[], recommendations=[]),
], ids=lambda model: type(model).__name__)
def test_nullable_contract_fields_round_trip(sample):
    assert type(sample).model_validate_json(sample.model_dump_json()) == sample
