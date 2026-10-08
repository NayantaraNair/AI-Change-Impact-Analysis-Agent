"""Test planning uses real dependency/scoring engines and mocked or disabled LLMs."""

import json

import pytest

from app import llm
from app.agents.testing import plan_tests
from app.architecture import get_architecture
from app.contracts import CatalogTest, RequirementFacts
from app.engine.dependency import build_impact_graph
from app.engine.scoring import score_risk


@pytest.fixture
def st107():
    arch = get_architecture()
    facts = RequirementFacts(
        business_summary="Require step-up authentication for mobile card payments",
        technical_summary="Change the authentication and payment API contract",
        business_domain="cards and payments",
        affected_capabilities=["card payments", "authentication"],
        affected_services=["mobile-banking", "payment-service"],
        change_type="integration_change",
        touches_customer_data=True, touches_card_data=True,
        touches_financial_data=True, changes_auth_flow=True,
        changes_external_api_contract=True, changes_db_schema=False,
        ambiguity="low", engineering_scope="Mobile authentication and payment APIs",
        source="test-fixture",
    )
    graph = build_impact_graph(facts.affected_services, arch)
    return facts, graph, score_risk(facts, graph, arch)


def catalog_test(test_id, services, *, kind="functional", automated=False, duration=30, title=None):
    return CatalogTest(
        id=test_id, title=title or f"Scenario {test_id}", type=kind,
        services=services, automated=automated, duration_min=duration,
    )


def with_scores(risk, **scores):
    return risk.model_copy(update={"dimensions": [
        dimension.model_copy(update={
            "score": scores.get(dimension.name, 0),
            "level": "high" if scores.get(dimension.name, 0) >= 70 else "low",
        }) for dimension in risk.dimensions
    ]})


def with_severities(graph, levels):
    return graph.model_copy(update={"nodes": [
        node.model_copy(update={"hop": 0 if node.id in levels else None,
                                "severity": levels.get(node.id)})
        for node in graph.nodes
    ]})


@pytest.mark.asyncio
async def test_st107_fallback_has_p1_security_valid_coverage_and_metrics(st107):
    facts, graph, risk = st107
    catalog = [catalog_test("CAT-1", ["mobile-banking", "unknown-id"], automated=True)]
    assert next(d.score for d in risk.dimensions if d.name == "security") >= 70

    plan, provider = await plan_tests(facts, graph, risk, catalog)

    assert provider == "template-fallback"
    assert any(test.type == "security" and test.priority == "P1" for test in plan.tests)
    impacted = {node.id for node in graph.nodes if node.hop is not None}
    covered = {node_id for test in plan.tests for node_id in test.covers}
    assert covered <= impacted
    assert all(test.covers for test in plan.tests)
    assert 0 <= plan.coverage_estimate <= 1
    assert plan.coverage_estimate == len(covered) / len(impacted)
    generated = [test for test in plan.tests if test.source == "generated"]
    assert 0 < len(generated) <= 8
    assert plan.effort_hours == 0.5 + 1.5 * len(generated)
    assert plan.automation_candidates == sum(test.automation_candidate for test in plan.tests)
    for test in generated:
        assert test.automation_candidate == (test.type in {"api", "regression"})
    assert (plan, provider) == await plan_tests(facts, graph, risk, catalog)


@pytest.mark.asyncio
async def test_catalog_selection_order_limit_and_catalog_fields(st107):
    facts, graph, risk = st107
    ids = sorted(node.id for node in graph.nodes)[:4]
    high, medium, low, unaffected = ids
    graph = with_severities(graph, {high: "high", medium: "medium", low: "low"})
    catalog = [
        catalog_test(f"H-{index:02}", [high], kind="functional" if index % 2 else "api",
                     automated=bool(index % 2), duration=index + 1)
        for index in range(12)
    ] + [catalog_test(f"M-{index}", [medium]) for index in range(4)] + [
        catalog_test("L-1", [low]),
        catalog_test("NO-1", [unaffected]),
        catalog_test("NO-2", ["unknown-id"]),
    ]
    risk = with_scores(risk)
    plan, _ = await plan_tests(facts, graph, risk, catalog[::-1])
    selected = [test for test in plan.tests if test.source == "catalog"]
    expected = sorted(catalog[:12], key=lambda test: (test.type, test.id))
    expected += sorted(catalog[12:16], key=lambda test: test.id)[:3]
    assert [test.id for test in selected] == [test.id for test in expected]
    assert len(selected) == 15
    for test, original in zip(selected, expected):
        assert test.title == original.title
        assert test.type == original.type
        assert test.covers == original.services
        assert test.automation_candidate == original.automated
        assert len(test.steps) == 3
        assert all(original.title in step for step in test.steps)
        assert test.expected.endswith(".")
    assert plan.effort_hours == sum(test.duration_min for test in expected) / 60 + 1.5
    reversed_graph = graph.model_copy(update={"nodes": graph.nodes[::-1]})
    assert (plan, "template-fallback") == await plan_tests(facts, reversed_graph, risk, catalog)


@pytest.mark.asyncio
async def test_node_severity_priorities(st107):
    facts, graph, risk = st107
    ids = sorted(node.id for node in graph.nodes)[:3]
    graph = with_severities(graph, dict(zip(ids, ["high", "medium", "low"])))
    plan, _ = await plan_tests(
        facts, graph, with_scores(risk),
        [catalog_test(f"CAT-{index}", [node_id]) for index, node_id in enumerate(ids)],
    )
    assert {test.id: test.priority for test in plan.tests} == {
        "CAT-0": "P1", "CAT-1": "P2", "CAT-2": "P3",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("dimension", ["security", "compliance", "technical", "operational", "performance", "delivery"])
@pytest.mark.parametrize("score,priority", [(69, "P3"), (70, "P1")])
async def test_dimension_priority_threshold_is_independent_of_node_severity(st107, dimension, score, priority):
    facts, graph, risk = st107
    graph = with_severities(graph, {"mobile-banking": "low"})
    kind = "security" if dimension == "security" else "functional"
    plan, _ = await plan_tests(
        facts, graph, with_scores(risk, **{dimension: score}),
        [catalog_test("DIM-1", ["mobile-banking"], kind=kind,
                      title=f"Verify {dimension} controls")],
    )
    assert plan.tests[0].priority == priority
    if score == 70:
        assert any(test.source == "generated" and dimension in test.title for test in plan.tests)


@pytest.mark.asyncio
async def test_llm_prompt_filtering_new_tests_and_computed_fields(st107, monkeypatch):
    facts, graph, risk = st107
    ids = sorted(node.id for node in graph.nodes)[:4]
    first, second, third, unaffected = ids
    graph = with_severities(graph, {first: "low", second: "medium", third: "low"})
    risk = with_scores(risk, security=70)
    seen = {}

    def draft(title, kind, covers):
        return dict(title=title, type=kind, covers=covers,
                    steps=["Prepare fixtures", "Send request", "Check result"],
                    expected="The expected response is returned.")

    async def complete(system, user, schema, tier, max_tokens):
        seen.update(system=system, prompt=json.loads(user), tier=tier)
        return schema.model_validate({"tests": [
            draft("New API behavior", "api", [first, first, "unknown-id", unaffected]),
            draft("Unknown only", "functional", ["unknown-id"]),
            draft("New regression scenario", "regression", [second]),
            draft("New access checks", "security", [third]),
            draft("  existing SCENARIO  ", "api", [third]),
            draft("New API behavior", "api", [second]),
            draft("Unaffected only", "api", [unaffected]),
            draft("Empty coverage", "functional", []),
        ]}), "mock:strong"

    monkeypatch.setattr(llm, "complete_structured", complete)
    catalog = [catalog_test("CAT-1", [first], title="Existing scenario", duration=45)]
    plan, provider = await plan_tests(facts, graph, risk, catalog)
    assert provider == "mock:strong"
    assert seen["tier"] == "strong"
    prompt = seen["prompt"]
    assert prompt["facts"] == facts.model_dump()
    assert set(prompt["uncovered_nodes"]) == {second, third}
    assert {node["id"] for node in prompt["impacted_nodes"]} == {first, second, third}
    assert prompt["high_risk_dimensions"] == ["security"]
    assert prompt["risk_dimensions"][0]["top_factors"]
    assert prompt["existing_tests"][0]["title"] == "Existing scenario"
    generated = plan.tests[1:]
    assert [test.id for test in generated] == ["GEN-1", "GEN-2", "GEN-3"]
    assert [test.covers for test in generated] == [[first], [second], [third]]
    assert [test.priority for test in generated] == ["P3", "P2", "P1"]
    assert [test.automation_candidate for test in generated] == [True, True, False]
    assert plan.coverage_estimate == 1
    assert plan.effort_hours == 0.75 + 3 * 1.5
    assert plan.automation_candidates == 2


@pytest.mark.asyncio
async def test_fallback_caps_generated_tests_and_reports_partial_coverage(st107, monkeypatch):
    facts, graph, risk = st107
    prototype = graph.nodes[0]
    graph = graph.model_copy(update={"nodes": [
        prototype.model_copy(update={"id": f"node-{index:02}", "label": f"Node {index}",
                                     "hop": 0, "severity": "low"})
        for index in range(12)
    ]})

    async def unavailable(*args, **kwargs):
        raise llm.NoLLM("Disabled for testing")

    monkeypatch.setattr(llm, "complete_structured", unavailable)
    plan, provider = await plan_tests(facts, graph, with_scores(risk), [])
    assert provider == "template-fallback"
    assert len(plan.tests) == 8
    assert plan.coverage_estimate == 8 / 12
    assert plan.effort_hours == 12
    assert all("rejects unauthorised access" in test.title for test in plan.tests)


@pytest.mark.asyncio
async def test_no_gap_skips_llm_and_empty_graph_is_zero(st107, monkeypatch):
    facts, graph, risk = st107

    async def unexpected(*args, **kwargs):
        pytest.fail("No drafting call is needed when there are no gaps")

    monkeypatch.setattr(llm, "complete_structured", unexpected)
    risk = with_scores(risk)
    graph = with_severities(graph, {"mobile-banking": "low"})
    plan, _ = await plan_tests(facts, graph, risk, [catalog_test("CAT-1", ["mobile-banking"])])
    assert plan.coverage_estimate == 1
    assert len(plan.tests) == 1
    empty = with_severities(graph, {})
    plan, provider = await plan_tests(facts, empty, risk, [])
    assert provider == "deterministic"
    assert plan.tests == []
    assert plan.coverage_estimate == plan.effort_hours == plan.automation_candidates == 0
