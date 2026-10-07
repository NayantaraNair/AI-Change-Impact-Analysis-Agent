"""Change size decides how far impact spreads, so small changes stay small."""

import pytest

from app.architecture import get_architecture, get_test_catalog, load_demo_sprint
from app.contracts import RequirementFacts
from app.engine.dependency import build_impact_graph
from app.engine.scope import change_size, plan_scope
from app.engine.scoring import load_scoring_config, score_risk
from app.agents.testing import plan_tests


def facts(**overrides) -> RequirementFacts:
    values = dict(
        business_summary="s", technical_summary="t", business_domain="Payments",
        affected_capabilities=[], affected_services=["payment-service"],
        change_type="business_rule_change", touches_customer_data=False,
        touches_card_data=False, touches_financial_data=True, changes_auth_flow=False,
        changes_external_api_contract=False, changes_db_schema=False, ambiguity="low",
        engineering_scope="Raise the daily limit", source="test",
    )
    values.update(overrides)
    return RequirementFacts(**values)


def scoped_graph(requirement):
    arch = get_architecture()
    scope = plan_scope(requirement, arch, load_scoring_config())
    return scope, build_impact_graph(
        requirement.affected_services, arch, max_hops=scope.max_hops,
        include_callers=scope.include_callers, blocked=scope.blocked,
        severity_scale=scope.severity_scale,
    )


@pytest.mark.parametrize(("overrides", "size"), [
    ({}, "small"),
    ({"affected_services": ["payment-service", "account-service"]}, "small"),
    ({"affected_services": ["payment-service", "account-service", "transaction-db"]}, "small"),
    ({"changes_db_schema": True}, "medium"),
    ({"change_type": "new_feature"}, "medium"),
    ({"affected_services": ["payment-service", "account-service", "fraud-engine"]}, "medium"),
    ({"affected_services": ["payment-service", "account-service", "fraud-engine", "card-service"]}, "large"),
    ({"changes_auth_flow": True, "changes_external_api_contract": True}, "large"),
])
def test_change_size(overrides, size):
    assert change_size(facts(**overrides), get_architecture())[0] == size


def test_payment_limit_change_stays_small_and_practical():
    requirement = facts()
    scope, graph = scoped_graph(requirement)
    impacted = set(graph.impacted_services)
    assert scope.size == "small" and scope.max_hops == 1 and not scope.include_callers
    # Callees it really depends on, but not callers or shared login/audit/gateway.
    assert impacted == {"payment-service", "account-service", "fraud-engine", "notification-service", "transaction-db"}
    risk = score_risk(requirement, graph, get_architecture())
    assert risk.change_size == "small"
    assert max(dimension.score for dimension in risk.dimensions) < 60
    assert all(
        any(factor.label == "small, contained change" for factor in dimension.factors)
        for dimension in risk.dimensions
    )


async def test_small_change_runs_few_tests():
    requirement = facts()
    _, graph = scoped_graph(requirement)
    risk = score_risk(requirement, graph, get_architecture())
    plan, _ = await plan_tests(requirement, graph, risk, get_test_catalog())
    assert sum(test.source == "catalog" for test in plan.tests) <= 5
    assert sum(test.source == "generated" for test in plan.tests) <= 3


def test_shared_platform_counts_only_when_touched():
    _, contained = scoped_graph(facts())
    assert not {"authentication-service", "api-gateway", "audit-db"} & set(contained.impacted_services)
    _, login = scoped_graph(facts(changes_auth_flow=True))
    assert "authentication-service" in login.impacted_services
    _, schema = scoped_graph(facts(changes_db_schema=True))
    assert "audit-db" in schema.impacted_services


def test_callers_count_when_the_contract_changes():
    _, contained = scoped_graph(facts())
    _, api = scoped_graph(facts(changes_external_api_contract=True))
    assert "api-gateway" not in contained.impacted_services
    assert "api-gateway" in api.impacted_services


def test_footer_text_story_is_small_and_go():
    footer = next(story for story in load_demo_sprint().stories if story.id == "ST-115")
    requirement = facts(affected_services=["document-service"], change_type="enhancement",
                        touches_financial_data=False, engineering_scope=footer.title)
    scope, graph = scoped_graph(requirement)
    assert scope.size == "small"
    assert len(graph.impacted_services) <= 3


def test_small_change_compliance_counts_only_changed_data_and_earns_credit():
    from app.agents.compliance import SMALL_CHANGE_CREDIT, _assess_rules

    requirement = facts(touches_financial_data=False)
    _, graph = scoped_graph(requirement)
    frameworks = {item.framework: item for item in _assess_rules(requirement, graph, get_architecture())}
    # fraud-engine (card data) is one step away: not enough for PCI on a small change.
    assert not frameworks["PCI DSS"].applicable
    governance = frameworks["Internal Governance"]
    assert governance.applicable and governance.risk_level == "low"
    assert f"small, contained change (+{SMALL_CHANGE_CREDIT})" in governance.findings[1].text


def test_small_change_softens_impact_on_neighbours():
    _, graph = scoped_graph(facts())
    high = [node.id for node in graph.nodes if node.hop is not None and node.severity == "high"]
    assert high == ["payment-service"]
