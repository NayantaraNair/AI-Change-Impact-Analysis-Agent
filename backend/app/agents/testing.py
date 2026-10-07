"""Select existing tests and draft gap tests; compute all plan metrics in Python."""

from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app import llm
from app.architecture import get_component
from app.engine.scoring import load_scoring_config
from app.contracts import (
    CatalogTest,
    GraphNode,
    ImpactGraph,
    RequirementFacts,
    RiskDimension,
    RiskReport,
    TestCase,
    TestPlan,
)

_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, None: 3}
_TYPE_DIMENSIONS = {
    "security": {"security"},
    "api": {"technical"},
    "integration": {"technical", "operational"},
    "regression": {"delivery", "operational"},
    "functional": {"delivery"},
}
_DIMENSION_TEMPLATES = {
    "security": ("security", "rejects unauthorised access", "Access is denied without exposing protected data."),
    "compliance": ("functional", "preserves required audit evidence", "Required audit evidence is complete and traceable."),
    "technical": ("integration", "maintains its dependency contracts", "Dependent systems accept the documented request and response contracts."),
    "operational": ("integration", "recovers after a dependency failure", "Recovery preserves data and restores the documented service behavior."),
    "performance": ("api", "meets its documented latency target under load", "Latency and throughput meet the documented service targets."),
    "delivery": ("regression", "satisfies the acceptance criteria after deployment", "The changed behavior and existing acceptance scenarios pass."),
}


class _GeneratedTest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1)
    type: Literal["functional", "api", "integration", "regression", "security"]
    covers: list[str]
    steps: list[str] = Field(min_length=1)
    expected: str = Field(min_length=1)


class _GeneratedTests(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tests: list[_GeneratedTest] = Field(max_length=8)


def _dimensions_for(test: _GeneratedTest | CatalogTest) -> set[str]:
    # The shared contract has no dimension field. Test types supply their usual
    # dimensions; explicit dimension names in prose cover compliance/performance.
    dimensions = set(_TYPE_DIMENSIONS[test.type])
    prose = test.title
    if isinstance(test, _GeneratedTest):
        prose += " " + " ".join(test.steps) + " " + test.expected
    for name in _DIMENSION_TEMPLATES:
        if re.search(rf"\b{name}\b", prose, re.IGNORECASE):
            dimensions.add(name)
    return dimensions


def _priority(
    test: _GeneratedTest | CatalogTest, covers: list[str],
    nodes: dict[str, GraphNode], high_dimensions: set[str],
) -> Literal["P1", "P2", "P3"]:
    if any(nodes[node_id].severity == "high" for node_id in covers):
        return "P1"
    if _dimensions_for(test) & high_dimensions:
        return "P1"
    if any(nodes[node_id].severity == "medium" for node_id in covers):
        return "P2"
    return "P3"


def _target(node: GraphNode) -> str:
    component = get_component(node.id)
    if component and component.apis:
        api = component.apis[0]
        return f"{api.method} {api.path}"
    return node.label


def _fallback_tests(
    uncovered: list[str], nodes: dict[str, GraphNode], high: list[RiskDimension],
    facts: RequirementFacts,
) -> list[_GeneratedTest]:
    tests = []
    remaining = set(uncovered)
    for dimension in high:
        covers = sorted({
            node_id for factor in dimension.factors for node_id in factor.node_ids
            if node_id in nodes
        })
        if not covers:
            covers = [next((node_id for node_id in nodes if node_id in remaining), next(iter(nodes)))]
        kind, action, expected = _DIMENSION_TEMPLATES[dimension.name]
        targets = ", ".join(_target(nodes[node_id]) for node_id in covers)
        tests.append(_GeneratedTest(
            title=f"Verify {dimension.name}: {targets} {action}", type=kind, covers=covers,
            steps=[f"Prepare {dimension.name} fixtures for {targets}.",
                   f"Exercise the change and verify it {action}.",
                   "Compare the observed result with the documented requirements."],
            expected=expected,
        ))
        remaining.difference_update(covers)
    for node_id in uncovered:
        if node_id not in remaining or len(tests) >= 8:
            continue
        node = nodes[node_id]
        target = _target(node)
        if facts.changes_auth_flow:
            kind, action, expected = _DIMENSION_TEMPLATES["security"]
        elif node.type == "database":
            kind, action, expected = (
                "integration", "persists valid changes and rejects invalid writes",
                "Valid data is persisted, and rejected writes leave existing data intact.",
            )
        else:
            kind, action, expected = (
                "regression", "preserves the required banking behavior",
                "The changed behavior meets acceptance criteria without breaking existing behavior.",
            )
        tests.append(_GeneratedTest(
            title=f"Verify {target} {action}", type=kind, covers=[node_id],
            steps=[f"Prepare valid and invalid fixtures for {target}.",
                   f"Exercise {target} with both fixture sets.",
                   "Check responses and persisted state against acceptance criteria."],
            expected=expected,
        ))
    return tests[:8]


async def plan_tests(
    facts: RequirementFacts, graph: ImpactGraph, risk: RiskReport,
    catalog: list[CatalogTest],
) -> tuple[TestPlan, str]:
    """Return catalog tests plus new, impacted-only tests, capped by change size
    (small 5 + 3, medium 8 + 5, large 15 + 8; see scoring_config.yaml).

    Catalog order is highest covered severity, alphabetical type, then ID.
    A graph node is impacted when its hop is nonnegative, including databases.
    """
    nodes = {
        node.id: node for node in sorted(
            graph.nodes, key=lambda node: (_SEVERITY_ORDER[node.severity], node.id)
        ) if node.hop is not None and node.hop >= 0
    }
    caps = load_scoring_config().get("tests", {})
    catalog_cap = int(caps.get("catalog", {}).get(risk.change_size, 15))
    generated_cap = int(caps.get("generated", {}).get(risk.change_size, 8))
    high = sorted(
        (dimension for dimension in risk.dimensions if dimension.score >= 70),
        key=lambda dimension: (-dimension.score, dimension.name),
    )
    high_dimensions = {dimension.name for dimension in high}
    selected = sorted(
        (test for test in catalog if set(test.services) & nodes.keys()),
        key=lambda test: (
            min(_SEVERITY_ORDER[nodes[node_id].severity]
                for node_id in test.services if node_id in nodes),
            test.type, test.id,
        ),
    )[:catalog_cap]
    tests = []
    for test in selected:
        covers = sorted(set(test.services) & nodes.keys())
        tests.append(TestCase(
            id=test.id, title=test.title, type=test.type,
            priority=_priority(test, covers, nodes, high_dimensions), covers=covers,
            steps=[f"Prepare fixtures for {test.title}.",
                   f"Execute the scenario: {test.title}.",
                   f"Check the documented outcome for {test.title}."],
            expected=f"{test.title} meets its documented acceptance criteria.",
            source="catalog", automation_candidate=test.automated,
        ))
    covered = {node_id for test in tests for node_id in test.covers}
    uncovered = [node_id for node_id in nodes if node_id not in covered]
    # Full coverage and no high risk leave nothing for a model to write.
    provider = "template-fallback" if nodes and (uncovered or high) else "deterministic"
    generated = []
    if nodes and (uncovered or high):
        prompt = {
            "facts": facts.model_dump(),
            "impacted_nodes": [node.model_dump() for node in nodes.values()],
            "impacted_apis": graph.impacted_apis,
            "uncovered_nodes": uncovered,
            "high_risk_dimensions": [dimension.name for dimension in high],
            "risk_dimensions": [{
                "name": dimension.name, "score": dimension.score,
                "top_factors": [factor.model_dump() for factor in sorted(
                    dimension.factors, key=lambda factor: (-factor.points, factor.label)
                )[:3]],
            } for dimension in risk.dimensions],
            "existing_tests": [{"title": test.title, "type": test.type,
                                "covers": test.services} for test in catalog],
        }
        try:
            result, provider = await llm.complete_structured(
                system=(
                    f"Draft at most {generated_cap} NEW banking test cases for uncovered impacted nodes "
                    "and risk dimensions scoring at least 70. Do not repeat existing tests. "
                    "Use only impacted node IDs in covers. Include explicit risk dimension "
                    "names in titles for dimension tests, and use security type for security "
                    "tests. Write concrete steps and expected outcomes from the supplied facts. "
                    "Do not compute scores, priorities, effort or coverage."
                ),
                user=json.dumps(prompt), schema=_GeneratedTests,
                tier="strong", max_tokens=llm.MAX_TOKENS["testing"],
            )
            generated = _GeneratedTests.model_validate(result.model_dump()).tests
        except llm.NoLLM:
            generated = _fallback_tests(uncovered, nodes, high, facts)[:generated_cap]

    titles = {" ".join(test.title.casefold().split()) for test in catalog}
    used_ids = {test.id for test in tests}
    generated_count = 0
    next_id = 1
    for test in generated[:generated_cap]:
        covers = sorted(set(test.covers) & nodes.keys())
        title_key = " ".join(test.title.casefold().split())
        if not covers or title_key in titles:
            continue
        titles.add(title_key)
        while f"GEN-{next_id}" in used_ids:
            next_id += 1
        test_id = f"GEN-{next_id}"
        used_ids.add(test_id)
        next_id += 1
        tests.append(TestCase(
            id=test_id, title=test.title, type=test.type,
            priority=_priority(test, covers, nodes, high_dimensions), covers=covers,
            steps=test.steps, expected=test.expected, source="generated",
            automation_candidate=test.type in {"api", "regression"},
        ))
        generated_count += 1
    covered = {node_id for test in tests for node_id in test.covers}
    coverage = len(covered) / len(nodes) if nodes else 0.0
    effort = sum(test.duration_min for test in selected) / 60 + 1.5 * generated_count
    return TestPlan(
        tests=tests, coverage_estimate=coverage, effort_hours=effort,
        automation_candidates=sum(test.automation_candidate for test in tests),
        summary=(f"Selected {len(selected)} catalog tests and {generated_count} new tests, "
                 f"covering {len(covered)} of {len(nodes)} impacted nodes "
                 f"({coverage:.0%}); estimated effort is {effort:.1f} hours."),
    ), provider
