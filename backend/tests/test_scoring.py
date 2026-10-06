"""Risk scoring tests use inline facts/graphs and never invoke an LLM."""

from __future__ import annotations

import pytest

from app.contracts import Architecture, Component, GraphNode, ImpactGraph, RequirementFacts
from app.engine.scoring import DIMENSION_ORDER, load_scoring_config, score_risk


def facts(**overrides) -> RequirementFacts:
    values = dict(
        business_summary="Update a banking capability",
        technical_summary="Update the affected services",
        business_domain="banking",
        affected_capabilities=[],
        affected_services=[],
        change_type="enhancement",
        touches_customer_data=False,
        touches_card_data=False,
        touches_financial_data=False,
        changes_auth_flow=False,
        changes_external_api_contract=False,
        changes_db_schema=False,
        ambiguity="low",
        engineering_scope="Service implementation",
        source="test-fixture",
    )
    values.update(overrides)
    return RequirementFacts(**values)


def component(node_id, *, criticality=5, data_classes=(), kind="core", team=None, group=None):
    return Component(
        id=node_id, name=node_id, type=kind, description="Test component",
        owner_team=team or f"team-{node_id}", owner_contact="test@bank.example",
        criticality=criticality, data_classes=list(data_classes),
        deployment_group=group or f"deploy-{node_id}", sla_tier="tier2",
    )


def graph_for(arch: Architecture, hops: dict[str, int | None]) -> ImpactGraph:
    nodes = [
        GraphNode(
            id=c.id, label=c.name, type=c.type, hop=hops.get(c.id),
            severity="low" if hops.get(c.id) is not None else None,
            x=0, y=0, criticality=c.criticality, owner_team=c.owner_team,
            data_classes=c.data_classes,
        )
        for c in arch.components
    ]
    impacted = [c for c in arch.components if hops.get(c.id) is not None]
    return ImpactGraph(
        nodes=nodes, edges=[],
        impacted_services=[c.id for c in impacted if c.type != "database"],
        impacted_databases=[c.id for c in impacted if c.type == "database"],
        impacted_apis=[],
        downstream_systems=[c.id for c in impacted if hops[c.id] > 0],
        deployment_groups=sorted({c.deployment_group for c in impacted}),
    )


@pytest.fixture
def st107():
    arch = Architecture(components=[
        component("card-service", criticality=10, data_classes=["card"]),
        component("authentication-service", criticality=10, data_classes=["pii"], kind="platform"),
        component("mobile-banking", criticality=8, kind="channel"),
        component("api-gateway", criticality=9, kind="platform"),
        component("card-db", criticality=9, data_classes=["card", "pii"], kind="database"),
        component("transaction-db", criticality=9, data_classes=["financial"], kind="database"),
        component("audit-db", criticality=7, data_classes=["audit"], kind="database"),
        component("unaffected-service", data_classes=["pii", "card", "financial", "audit"]),
    ])
    graph = graph_for(arch, {
        "card-service": 0, "authentication-service": 0,
        "mobile-banking": 0, "api-gateway": 0,
        "card-db": 1, "transaction-db": 1, "audit-db": 2,
    })
    requirement = facts(
        affected_services=["card-service", "authentication-service", "mobile-banking", "api-gateway"],
        touches_card_data=True, changes_auth_flow=True,
        changes_external_api_contract=True, change_type="integration_change",
    )
    return requirement, graph, arch


@pytest.fixture
def st115():
    arch = Architecture(components=[
        component("document-service", criticality=4),
        component("reporting-service", criticality=5),
        component("reporting-db", criticality=6, data_classes=["financial"], kind="database"),
        component("audit-db", criticality=7, data_classes=["audit"], kind="database"),
    ])
    graph = graph_for(arch, {
        "document-service": 0, "reporting-service": 0,
        "reporting-db": 1, "audit-db": 1,
    })
    return facts(affected_services=["document-service", "reporting-service"]), graph, arch


def dimensions(report):
    return {dimension.name: dimension for dimension in report.dimensions}


def factor_map(dimension):
    return {factor.label: factor for factor in dimension.factors}


def test_st107_security_is_high_and_factors_are_traceable(st107):
    report = score_risk(*st107)
    security = dimensions(report)["security"]
    assert security.score == 93
    assert security.level == "high"
    factors = factor_map(security)
    assert factors["card data"].node_ids == ["card-db", "card-service"]
    assert factors["critical identity path"].node_ids == ["api-gateway", "authentication-service"]
    assert "card data (+25)" in security.explanation
    assert "auth flow change (+25)" in security.explanation
    assert "authentication-service" in security.explanation
    for dimension in report.dimensions:
        assert dimension.factors[0].label == "baseline"
        assert dimension.factors[0].node_ids == []
        assert sum(f.points for f in dimension.factors) == dimension.score
        for factor in dimension.factors[1:]:
            assert factor.node_ids
            assert "unaffected-service" not in factor.node_ids


def test_st115_every_dimension_stays_low(st115):
    report = score_risk(*st115)
    # Compliance: baseline 5 + nearby financial 8 + nearby audit 6.
    assert [d.score for d in report.dimensions] == [16, 19, 22, 35, 5, 37]
    assert all(d.score < 40 and d.level == "low" for d in report.dimensions)


def test_determinism_dimension_order_and_overall(st107):
    report = score_risk(*st107)
    assert report == score_risk(*st107)
    assert tuple(d.name for d in report.dimensions) == DIMENSION_ORDER
    # Compliance: 5 + direct PII 20 + direct card 30 + nearby financial 8;
    # audit data at hop 2 is excluded. Overall averages the top three scores.
    assert [d.score for d in report.dimensions] == [93, 63, 49, 57, 40, 59]
    assert report.overall == 72
    assert report.highest == "security"


def test_clamping_preserves_original_factor_points(st107):
    requirement, graph, arch = st107
    requirement = requirement.model_copy(update={"touches_customer_data": True})
    security = dimensions(score_risk(requirement, graph, arch))["security"]
    assert sum(f.points for f in security.factors) == 113
    assert security.score == 100
    assert "high (100)" in security.explanation


def zero_weights(value):
    if isinstance(value, dict):
        return {key: zero_weights(item) for key, item in value.items()}
    return 0 if isinstance(value, int) else value


@pytest.mark.parametrize("score,level", [(0, "low"), (39, "low"), (40, "medium"), (69, "medium"), (70, "high"), (100, "high")])
def test_level_boundaries_and_custom_config(score, level):
    cfg = zero_weights(load_scoring_config())
    cfg["security"]["base"] = score
    arch = Architecture(components=[])
    report = score_risk(facts(), graph_for(arch, {}), arch, cfg)
    security = dimensions(report)["security"]
    assert security.score == score
    assert security.level == level
    assert security.explanation == f"Security risk is {level} ({score}) because baseline (+{score})."


def test_lower_clamp_and_highest_tie_are_deterministic():
    cfg = zero_weights(load_scoring_config())
    cfg["security"]["base"] = -10
    arch = Architecture(components=[])
    report = score_risk(facts(), graph_for(arch, {}), arch, cfg)
    assert dimensions(report)["security"].score == 0
    assert dimensions(report)["security"].factors[0].points == -10
    assert report.overall == 0
    assert report.highest == "security"


@pytest.mark.parametrize("change_type,points", [("new_feature", 10), ("integration_change", 10), ("refactor", 15), ("enhancement", 0)])
def test_technical_change_types_and_schema(st115, change_type, points):
    requirement, graph, arch = st115
    requirement = requirement.model_copy(update={"change_type": change_type, "changes_db_schema": True})
    scored = dimensions(score_risk(requirement, graph, arch))
    assert scored["technical"].score == 22 + 20 + points
    assert scored["compliance"].score == 29  # 5 + 8 + 6 + schema change 10
    assert factor_map(scored["technical"])["database schema change"].node_ids == ["audit-db", "reporting-db"]


def test_hop_one_only_pii_uses_nearby_compliance_weight():
    arch = Architecture(components=[
        component("changed"),
        component("customer-db", data_classes=["pii"], kind="database"),
    ])
    graph = graph_for(arch, {"changed": 0, "customer-db": 1})
    compliance = dimensions(score_risk(facts(affected_services=["changed"]), graph, arch))["compliance"]
    assert compliance.score == 13  # baseline 5 + nearby PII 8
    assert [(f.label, f.points, f.node_ids) for f in compliance.factors] == [
        ("baseline", 5, []),
        ("nearby pii data", 8, ["customer-db"]),
    ]
    assert load_scoring_config()["compliance"]["nearby"]["pii"] == 8


def test_caps_and_distinct_counts():
    arch = Architecture(components=[component(f"service-{i}", criticality=10) for i in range(16)])
    graph = graph_for(arch, {c.id: 0 if i < 6 else 2 for i, c in enumerate(arch.components)})
    graph.downstream_systems *= 2
    graph.deployment_groups *= 2
    scored = dimensions(score_risk(facts(), graph, arch))
    assert factor_map(scored["security"])["blast radius size"].points == 10
    assert factor_map(scored["technical"])["direct services"].points == 30
    assert factor_map(scored["operational"])["downstream systems"].points == 20
    assert factor_map(scored["operational"])["deployment groups"].points == 6
    assert factor_map(scored["delivery"])["owner coordination"].points == 15 * 4
    assert scored["delivery"].score == 100


@pytest.mark.parametrize("hop,identity_points,nearby_points", [(0, 10, 2), (1, 10, 2), (2, 0, 2), (3, 0, 0), (None, 0, 0)])
def test_security_hop_cutoffs(hop, identity_points, nearby_points):
    arch = Architecture(components=[component("authentication-service")])
    graph = graph_for(arch, {"authentication-service": hop})
    security = dimensions(score_risk(facts(), graph, arch))["security"]
    assert security.score == 8 + identity_points + nearby_points


@pytest.mark.parametrize("ambiguity,points", [("low", 10), ("medium", 30), ("high", 55)])
def test_ambiguity_weights(st115, ambiguity, points):
    requirement, graph, arch = st115
    requirement = requirement.model_copy(update={"ambiguity": ambiguity})
    delivery = dimensions(score_risk(requirement, graph, arch))["delivery"]
    assert factor_map(delivery)[f"{ambiguity} ambiguity"].points == points
    assert delivery.score == 5 + points + 10 + 12


@pytest.mark.parametrize("on_payment_path,score", [(True, 55), (False, 20)])
def test_performance_payment_business_rule(on_payment_path, score):
    arch = Architecture(components=[
        component("payment-service"), component("transaction-db", kind="database"),
        component("mobile-banking", kind="channel"),
    ])
    graph = graph_for(arch, {
        "mobile-banking": 0,
        "payment-service": 1 if on_payment_path else None,
        "transaction-db": 2 if on_payment_path else None,
    })
    performance = dimensions(score_risk(facts(change_type="business_rule_change"), graph, arch))["performance"]
    assert performance.score == score
    if on_payment_path:
        assert factor_map(performance)["transaction path"].points == 20
        assert factor_map(performance)["payment business rule"].node_ids == ["payment-service", "transaction-db"]


def test_architecture_metadata_is_authoritative_and_summary_noise_is_ignored(st115):
    requirement, graph, arch = st115
    expected = score_risk(requirement, graph, arch)
    for node in graph.nodes:
        node.criticality = 10
        node.data_classes = ["pii", "card"]
        node.owner_team = "misleading-team"
        node.type = "database"
    graph.downstream_systems += ["unknown-node", "reporting-db"]
    graph.deployment_groups += ["unknown-deployment", graph.deployment_groups[0]]
    graph.nodes.reverse()
    assert score_risk(requirement, graph, arch) == expected


def test_direct_database_does_not_count_as_direct_service():
    arch = Architecture(components=[component("reporting-db", kind="database", criticality=10)])
    graph = graph_for(arch, {"reporting-db": 0})
    scored = dimensions(score_risk(facts(), graph, arch))
    assert scored["technical"].score == 5
    assert scored["operational"].score == 7
    assert scored["delivery"].score == 15


def test_config_loader_returns_independent_copies_and_accepts_a_path(tmp_path):
    cfg = load_scoring_config()
    cfg["security"]["base"] = 999
    assert load_scoring_config()["security"]["base"] == 8
    path = tmp_path / "weights.yaml"
    path.write_text("security:\n  base: 12\n", encoding="utf-8")
    assert load_scoring_config(path) == {"security": {"base": 12}}
