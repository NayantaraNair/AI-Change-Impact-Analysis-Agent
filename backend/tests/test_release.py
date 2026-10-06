"""Release gates use inline contracts; provider calls are disabled or mocked."""

import json

import pytest

from app import llm
from app.agents import release
from app.contracts import (
    Architecture,
    ComplianceReport,
    Component,
    Conflict,
    FrameworkAssessment,
    GraphEdge,
    GraphNode,
    ImpactGraph,
    RequirementFacts,
    RiskDimension,
    RiskReport,
    TestCase,
    TestPlan,
)


def facts(**overrides):
    values = dict(
        business_summary="Update banking documents", technical_summary="Update document-service",
        business_domain="banking", affected_capabilities=["documents"],
        affected_services=["document-service"], change_type="enhancement",
        touches_customer_data=False, touches_card_data=False, touches_financial_data=False,
        changes_auth_flow=False, changes_external_api_contract=False, changes_db_schema=False,
        ambiguity="low", engineering_scope="Service implementation", source="test-fixture",
    )
    return RequirementFacts(**(values | overrides))


def graph(services=("document-service",), groups=("documents",)):
    return ImpactGraph(
        nodes=[GraphNode(
            id=service, label=service, type="core", hop=0, severity="low",
            x=0, y=0, criticality=4, owner_team="Test team", data_classes=[],
        ) for service in services],
        edges=[], impacted_services=list(services), impacted_databases=[], impacted_apis=[],
        downstream_systems=[], deployment_groups=list(groups),
    )


def risk(**scores):
    values = dict(delivery=20, technical=20, security=20, operational=20, compliance=20, performance=20)
    values.update(scores)
    return RiskReport(
        dimensions=[RiskDimension(
            name=name, score=score, level="high" if score >= 70 else "medium" if score >= 40 else "low",
            factors=[], explanation="Inline fixture",
        ) for name, score in values.items()],
        overall=round(sum(values.values()) / len(values)), highest=max(values, key=values.get),
    )


def test_plan(coverage=1.0, cases=()):
    return TestPlan(tests=list(cases), coverage_estimate=coverage, effort_hours=1,
                    automation_candidates=0, summary="Inline fixture")


test_plan.__test__ = False


def framework(name="PCI DSS", level="low", applicable=True, recommendations=()):
    return FrameworkAssessment(
        framework=name, applicable=applicable, reason="Inline fixture", risk_level=level,
        score=80, findings=[], recommendations=list(recommendations),
    )


def compliance(*frameworks):
    return ComplianceReport(frameworks=list(frameworks), overall_score=80, summary="Inline fixture")


def conflict(index=1):
    return Conflict(
        id=f"conflict-{index}", story_a="ST-107", story_b=f"ST-{111 + index}",
        shared_component="authentication-service", kind="deployment_collision",
        risk="medium", risk_score=50, recommendation="Reserve separate deployment windows with the Identity team",
    )


def decide(**overrides):
    inputs = dict(facts=facts(), graph=graph(), risk=risk(), tests=test_plan(), compliance=compliance(), conflicts=None)
    return release.decide(**(inputs | overrides))


@pytest.mark.parametrize("name", ["delivery", "technical", "security", "operational", "compliance", "performance"])
@pytest.mark.parametrize("score,expected", [(84, "GO_WITH_CONDITIONS"), (85, "NO_GO"), (100, "NO_GO")])
def test_any_dimension_can_block(name, score, expected):
    decision, rules, _, _, _ = decide(risk=risk(**{name: score}))
    assert decision == expected
    assert (f"NO_GO: {name} risk is {score} (>= 85)" in rules) == (score >= 85)


@pytest.mark.parametrize("score,coverage,expected", [
    (69, 0.69, "GO_WITH_CONDITIONS"), (70, 0.69, "NO_GO"),
    (74, 0.62, "NO_GO"), (70, 0.7, "GO_WITH_CONDITIONS"),
    (59, 0.1, "GO"), (60, 1.0, "GO_WITH_CONDITIONS"),
])
def test_highest_risk_and_coverage_boundaries(score, coverage, expected):
    decision, rules, _, _, _ = decide(risk=risk(technical=score), tests=test_plan(coverage))
    assert decision == expected
    if score == 74:
        assert "NO_GO: highest risk 74 with test coverage 62% (< 70%)" in rules


@pytest.mark.parametrize("name", ["GDPR", "PCI DSS", "SOX", "Internal Governance"])
@pytest.mark.parametrize("touch", ["touches_card_data", "changes_auth_flow"])
def test_high_applicable_compliance_blocks_card_or_authentication(name, touch):
    decision, rules, _, _, _ = decide(facts=facts(**{touch: True}), compliance=compliance(framework(name, "high")))
    assert decision == "NO_GO"
    touched = "card data" if touch == "touches_card_data" else "authentication"
    assert f"NO_GO: {name} risk is high and the change touches {touched}" in rules


@pytest.mark.parametrize("level,expected", [(None, "GO"), ("low", "GO"), ("medium", "GO_WITH_CONDITIONS"), ("high", "GO_WITH_CONDITIONS")])
def test_compliance_conditions_without_card_or_authentication(level, expected):
    result = decide(compliance=compliance(framework(level=level, recommendations=["Review PCI evidence with the compliance owner"])))
    assert result[0] == expected
    if expected == "GO_WITH_CONDITIONS":
        assert "Review PCI evidence with the compliance owner" in result[2]


def test_nonapplicable_framework_cannot_block_or_reduce_confidence():
    baseline = decide(facts=facts(touches_card_data=True))
    result = decide(facts=facts(touches_card_data=True), compliance=compliance(framework(level="high", applicable=False)))
    assert result[0] == "GO_WITH_CONDITIONS"  # Rule 4 considers any elevated framework.
    assert all(not rule.startswith("NO_GO") for rule in result[1])
    assert result[3] == baseline[3]


def test_all_firing_rules_are_recorded_in_order_without_weakening_no_go():
    decision, rules, conditions, _, _ = decide(
        facts=facts(touches_card_data=True, changes_auth_flow=True),
        risk=risk(technical=85, security=88), tests=test_plan(0.62),
        compliance=compliance(framework(level="high")), conflicts=[conflict()],
    )
    assert decision == "NO_GO"
    assert rules[:4] == [
        "NO_GO: technical risk is 85 (>= 85)",
        "NO_GO: security risk is 88 (>= 85)",
        "NO_GO: highest risk 88 with test coverage 62% (< 70%)",
        "NO_GO: PCI DSS risk is high and the change touches card data and authentication",
    ]
    assert len(rules) == 7
    assert "Increase test coverage to at least 70% and rerun the release assessment" in conditions


def test_p1_tests_make_risk_conditions_concrete():
    case = TestCase(
        id="SEC-1", title="Check MFA enforcement", type="security", priority="P1",
        covers=["authentication-service"], steps=["Attempt login without MFA"],
        expected="Login denied", source="catalog", automation_candidate=True,
    )
    decision, _, conditions, _, _ = decide(risk=risk(security=60), tests=test_plan(cases=[case]))
    assert decision == "GO_WITH_CONDITIONS"
    assert "Run the P1 security tests on authentication-service before release (SEC-1: Check MFA enforcement)" in conditions


def test_conflict_alone_requires_sequencing_and_reduces_confidence():
    decision, rules, conditions, confidence, _ = decide(conflicts=[conflict()])
    assert decision == "GO_WITH_CONDITIONS"
    assert "deployment collision" in rules[0]
    assert "Sequence deployment of ST-107 and ST-112 (deployment collision on authentication-service)" in conditions
    assert confidence == 83


def test_confidence_formula_counts_only_applicable_elevated_frameworks_and_all_conflicts():
    report = compliance(
        framework("GDPR", "medium"), framework("PCI DSS", "high"),
        framework("SOX", "low"), framework("Internal Governance", "high", applicable=False),
    )
    result = decide(risk=risk(security=74), tests=test_plan(0.62), compliance=report, conflicts=[conflict(1), conflict(2)])
    assert result[3] == 29  # round(100 - .45*74 - 30*.38 - 5*2 - 8*2)
    assert decide(risk=risk(security=100), tests=test_plan(0), conflicts=[conflict(i) for i in range(10)])[3] == 0
    assert decide(risk=risk(**{name: 0 for name in ("delivery", "technical", "security", "operational", "compliance", "performance")}))[3] == 100


@pytest.mark.parametrize("groups,direct,expected", [(0, 0, "low"), (1, 1, "low"), (2, 1, "medium"), (3, 1, "medium"), (4, 1, "high"), (1, 3, "medium"), (1, 4, "high")])
def test_complexity_uses_maximum_group_or_direct_service_count(groups, direct, expected):
    result = decide(graph=graph(tuple(f"service-{i}" for i in range(direct)), tuple(f"group-{i}" for i in range(groups))))
    assert result[4] == expected


def test_complexity_deduplicates_and_excludes_direct_databases_and_indirect_services():
    impact = graph(("document-service", "reporting-db", "downstream-service", "unaffected"), ("shared", "shared"))
    impact.nodes[1].type = "database"
    impact.nodes[2].hop = 1
    impact.nodes[3].hop = None
    impact.nodes.append(impact.nodes[0].model_copy())
    assert decide(graph=impact)[4] == "low"


def test_decision_uses_dimension_scores_not_stale_overall_or_highest_labels():
    report = risk(security=88).model_copy(update={"overall": 1, "highest": "delivery"})
    assert decide(risk=report)[0] == "NO_GO"
    report = risk().model_copy(update={"overall": 100, "highest": "security"})
    assert decide(risk=report)[0] == "GO"


@pytest.mark.asyncio
async def test_st107_like_change_is_no_go_with_rule_text():
    result, provider = await release.assess_release(
        facts(affected_services=["card-service", "authentication-service"], touches_card_data=True, changes_auth_flow=True),
        graph(("card-service", "authentication-service"), ("cards", "identity")),
        risk(delivery=87, technical=49, security=93, operational=57, compliance=40, performance=59),
        test_plan(0.62), compliance(framework(level="high")),
    )
    assert result.decision == "NO_GO"
    assert "NO_GO: security risk is 93 (>= 85)" in result.triggered_rules
    assert "NO_GO: highest risk 93 with test coverage 62% (< 70%)" in result.triggered_rules
    assert provider == "template-fallback"
    assert "Hold production deployment" in result.deployment_notes[0]


@pytest.mark.asyncio
async def test_st115_like_change_is_go():
    result, provider = await release.assess_release(
        facts(affected_services=["document-service", "reporting-service"]),
        graph(("document-service", "reporting-service"), ("documents", "reporting")),
        risk(delivery=37, technical=22, security=16, operational=35, compliance=5, performance=37),
        test_plan(0.9), compliance(framework("Internal Governance", "low")),
    )
    assert result.decision == "GO"
    assert result.conditions == []
    assert result.confidence == 80
    assert result.rollback_plan and result.deployment_notes
    assert provider == "template-fallback"


def component(node_id, group, kind="core"):
    return Component(id=node_id, name=node_id, type=kind, description="Test component",
                     owner_team="Test team", owner_contact="owner@bank.example", criticality=5,
                     deployment_group=group, sla_tier="tier2")


@pytest.fixture
def deployment_graph(monkeypatch):
    arch = Architecture(components=[
        component("caller", "channels"), component("provider", "services"), component("db", "database", "database"),
    ])
    monkeypatch.setattr(release, "get_architecture", lambda: arch)
    impact = graph(("caller", "provider", "db"), ("channels", "database", "services"))
    impact.nodes[2].type = "database"
    impact.edges = [
        GraphEdge(id="caller-provider", source="caller", target="provider", on_impact_path=True),
        GraphEdge(id="provider-db", source="provider", target="db", on_impact_path=True),
    ]
    return impact


@pytest.mark.asyncio
async def test_no_llm_templates_order_groups_and_cover_flags_migrations_and_comms(deployment_graph):
    rollback, notes, provider = await release.write_plans(facts(changes_db_schema=True), deployment_graph, "GO_WITH_CONDITIONS")
    assert provider == "template-fallback"
    deployments = [note for note in notes if note.startswith("Deploy ")]
    assert [note.split()[1] for note in deployments] == ["database", "services", "channels"]
    flags = [step for step in rollback if "feature flags" in step]
    assert [step.split(":")[0] for step in flags] == ["channels", "services", "database"]
    migration = [step for step in rollback if "roll back the DB migration" in step]
    assert len(migration) == 1 and migration[0].startswith("database:")
    assert any("backups" in note for note in notes)
    assert any("monitor" in note for note in notes)
    assert any("stakeholders" in note for note in notes)


@pytest.mark.asyncio
async def test_fallback_without_schema_change_omits_migration_rollback(deployment_graph):
    rollback, notes, _ = await release.write_plans(facts(), deployment_graph, "GO")
    assert all("migration" not in step for step in rollback + notes)


def test_dependency_cycles_have_stable_group_order(deployment_graph):
    deployment_graph.edges.append(GraphEdge(id="db-caller", source="db", target="caller", on_impact_path=True))
    expected = release._deployment_context(deployment_graph)
    deployment_graph.nodes.reverse()
    deployment_graph.edges.reverse()
    deployment_graph.deployment_groups.reverse()
    assert release._deployment_context(deployment_graph) == expected
    assert expected[0] == ["channels", "database", "services"]


@pytest.mark.asyncio
async def test_strong_provider_writes_only_prose_and_cannot_change_decision(monkeypatch, deployment_graph):
    calls = []

    async def complete_structured(system, user, schema, tier="fast", max_tokens=1500):
        calls.append((system, json.loads(user), schema, tier))
        assert set(schema.model_fields) == {"rollback_plan", "deployment_notes"}
        return schema(rollback_plan=["Model rollback prose"], deployment_notes=["Model deployment prose"]), "mock:strong"

    monkeypatch.setattr(llm, "complete_structured", complete_structured)
    result, provider = await release.assess_release(facts(), deployment_graph, risk(security=88), test_plan(), compliance())
    assert result.decision == "NO_GO"
    assert result.confidence == 60
    assert result.rollback_plan == ["Model rollback prose"]
    assert result.deployment_notes == ["Model deployment prose"]
    assert provider == "mock:strong"
    assert len(calls) == 1 and calls[0][3] == "strong"
    assert calls[0][1]["decision"] == "NO_GO"
    assert calls[0][1]["deployment_order"] == ["database", "services", "channels"]


@pytest.mark.asyncio
async def test_reused_text_reruns_gates_with_conflicts_without_llm(monkeypatch):
    async def unexpected_call(*args, **kwargs):
        pytest.fail("Reused text must not trigger another provider call")

    monkeypatch.setattr(llm, "complete_structured", unexpected_call)
    cached = (["Existing rollback"], ["Existing notes"])
    result, provider = await release.assess_release(facts(), graph(), risk(), test_plan(), compliance(), [conflict()], text=cached)
    assert result.decision == "GO_WITH_CONDITIONS"
    assert result.confidence == 83
    assert (result.rollback_plan, result.deployment_notes) == cached
    assert provider == "reused"
    assert cached == (["Existing rollback"], ["Existing notes"])


@pytest.mark.asyncio
async def test_explicit_empty_cached_lists_are_still_reused(monkeypatch):
    async def unexpected_call(*args, **kwargs):
        pytest.fail("An explicit cached tuple must be reused")

    monkeypatch.setattr(llm, "complete_structured", unexpected_call)
    result, provider = await release.assess_release(facts(), graph(), risk(), test_plan(), compliance(), text=([], []))
    assert result.rollback_plan == result.deployment_notes == []
    assert provider == "reused"
