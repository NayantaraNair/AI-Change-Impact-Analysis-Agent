"""Validate the banking fixtures without loading configuration or calling an LLM.

Run from the repository root or with:
    cd backend && uv run --offline python ../scripts/validate_data.py

Edges point from a caller/writer to its dependency. Database replication points
from transaction-db to reporting-db. Authentication and audit are shared
dependencies; authentication-service does not authenticate itself. No cycles are
intentional in this dataset.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import networkx as nx

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.contracts import Architecture, CatalogTest, DemoSprint, StoryInput  # noqa: E402


EXPECTED_COMPONENTS = {
    "channel": {"mobile-banking", "web-banking", "atm", "branch-portal"},
    "core": {
        "customer-service", "account-service", "payment-service", "loan-service",
        "card-service", "crm",
    },
    "platform": {
        "authentication-service", "notification-service", "api-gateway", "document-service",
    },
    "database": {"customer-db", "transaction-db", "audit-db", "reporting-db"},
    "analytics": {"fraud-engine", "risk-engine", "reporting-service"},
}
TEST_TYPES = {"functional", "api", "integration", "regression", "security"}
STORY_IDS = {"ST-101", "ST-104", "ST-107", "ST-110", "ST-112", "ST-115"}
STORY_COMPONENTS = {
    "ST-101": {"payment-service", "account-service", "fraud-engine", "transaction-db"},
    "ST-104": {"customer-service", "crm", "customer-db", "notification-service"},
    "ST-107": {"card-service", "authentication-service", "mobile-banking", "api-gateway"},
    "ST-110": {"fraud-engine", "payment-service", "risk-engine"},
    "ST-112": {"authentication-service", "mobile-banking"},
    "ST-115": {"document-service", "reporting-service"},
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _unique(values: list[str], label: str) -> None:
    duplicates = sorted(value for value, count in Counter(values).items() if count > 1)
    _require(not duplicates, f"Duplicate {label}: {duplicates}")


def validate_architecture(architecture: Architecture) -> None:
    components = architecture.components
    _unique([component.id for component in components], "component IDs")
    by_id = {component.id: component for component in components}
    ids = set(by_id)
    expected_ids = set().union(*EXPECTED_COMPONENTS.values())
    _require(ids == expected_ids, f"Component IDs differ: {sorted(ids ^ expected_ids)}")
    api_ids: list[str] = []
    graph = nx.DiGraph()
    graph.add_nodes_from(ids)

    for component in components:
        cid = component.id
        _require(cid in EXPECTED_COMPONENTS[component.type], f"Wrong component type for {cid}")
        for field in ("name", "description", "owner_team", "owner_contact", "deployment_group"):
            _require(bool(getattr(component, field).strip()), f"{cid}: empty {field}")
        _require(2 <= len(component.apis) <= 5, f"{cid}: expected 2-5 APIs")
        _unique(component.upstream, f"{cid} upstream links")
        _unique(component.downstream, f"{cid} downstream links")
        _unique(component.data_classes, f"{cid} data classes")
        for direction in ("upstream", "downstream"):
            unknown = set(getattr(component, direction)) - ids
            _require(not unknown, f"{cid}: unknown {direction} IDs {sorted(unknown)}")
        for api in component.apis:
            _require(bool(api.id.strip()), f"{cid}: empty API ID")
            _require(bool(api.description.strip()), f"{api.id}: empty API description")
            _require(api.path.startswith("/"), f"{api.id}: REST path must start with /")
            if component.type == "channel" or cid == "api-gateway":
                _require(api.external, f"{api.id}: channel/gateway APIs must be external")
            api_ids.append(api.id)
        _unique([f"{api.method} {api.path}" for api in component.apis], f"{cid} API routes")
        for target in component.downstream:
            graph.add_edge(cid, target)

    _unique(api_ids, "API IDs")
    for component in components:
        expected_upstream = set(graph.predecessors(component.id))
        _require(
            set(component.upstream) == expected_upstream,
            f"{component.id}: upstream must be the exact inverse of downstream; "
            f"expected {sorted(expected_upstream)}",
        )
    _require(nx.is_directed_acyclic_graph(graph), "Downstream graph contains a cycle")

    for cid in EXPECTED_COMPONENTS["channel"]:
        _require("api-gateway" in by_id[cid].downstream, f"{cid}: missing gateway route")
    _require(
        EXPECTED_COMPONENTS["core"] <= set(by_id["api-gateway"].downstream),
        "api-gateway must route to all core services",
    )
    for component in components:
        if component.type == "database":
            continue
        if component.id != "authentication-service":
            _require("authentication-service" in component.downstream,
                     f"{component.id}: missing authentication dependency")
        _require("audit-db" in component.downstream, f"{component.id}: missing audit write")
    for cid in EXPECTED_COMPONENTS["core"]:
        business_databases = EXPECTED_COMPONENTS["database"] - {"audit-db"}
        _require(bool(set(by_id[cid].downstream) & business_databases),
                 f"{cid}: missing business database write")
    for source, target in (
        ("payment-service", "fraud-engine"),
        ("reporting-service", "reporting-db"),
        ("transaction-db", "reporting-db"),
    ):
        _require(target in by_id[source].downstream, f"Missing required edge {source} -> {target}")
    for cid, classes in {
        "customer-db": {"pii"}, "transaction-db": {"financial"},
        "card-service": {"card", "pii"}, "audit-db": {"audit"},
    }.items():
        _require(classes <= set(by_id[cid].data_classes), f"{cid}: missing required data classes")
    for cid in ("authentication-service", "payment-service", "api-gateway"):
        _require(by_id[cid].criticality >= 9, f"{cid}: criticality must be 9-10")
    for cid in ("atm", "branch-portal", "document-service"):
        _require(by_id[cid].criticality < 9, f"{cid}: criticality must be lower than 9")
    _require(6 <= len({c.deployment_group for c in components}) <= 8,
             "Expected 6-8 deployment groups")
    for cid, group in {
        "authentication-service": "identity", "api-gateway": "identity",
        "mobile-banking": "channels-mobile", "payment-service": "core-payments",
        "fraud-engine": "core-payments",
    }.items():
        _require(by_id[cid].deployment_group == group, f"{cid}: expected deployment group {group}")


def validate_test_catalog(tests: list[CatalogTest], architecture: Architecture) -> None:
    _require(55 <= len(tests) <= 65, "Expected about 60 catalog tests (55-65)")
    _unique([test.id for test in tests], "test IDs")
    ids = {component.id for component in architecture.components}
    api_owner = {api.id: component.id for component in architecture.components for api in component.apis}
    coverage: Counter[str] = Counter()
    for test in tests:
        _require(bool(test.id.strip()) and bool(test.title.strip()), "Test ID/title must not be empty")
        _require(bool(test.services), f"{test.id}: must cover at least one component")
        _unique(test.services, f"{test.id} service references")
        _unique(test.apis, f"{test.id} API references")
        _require(not (set(test.services) - ids), f"{test.id}: unknown service reference")
        _require(test.duration_min > 0, f"{test.id}: duration must be positive")
        for api_id in test.apis:
            _require(api_id in api_owner, f"{test.id}: unknown API reference {api_id}")
            _require(api_owner[api_id] in test.services,
                     f"{test.id}: API {api_id} belongs to a component outside services")
        if test.type == "api":
            _require(bool(test.apis), f"{test.id}: API tests must reference endpoints")
        coverage.update(test.services)
    missing = sorted(cid for cid in ids if coverage[cid] < 2)
    _require(not missing, f"Components need at least two tests: {missing}")
    _require({test.type for test in tests} == TEST_TYPES, "Catalog must cover all five test types")


def validate_demo_sprint(sprint: DemoSprint) -> None:
    _require(sprint.sprint_id == "sprint-42", "Expected sprint_id sprint-42")
    _require(sprint.name == "Sprint 42: Q4 payments & cards", "Unexpected demo sprint name")
    _unique([story.id for story in sprint.stories], "story IDs")
    _require({story.id for story in sprint.stories} == STORY_IDS, "Expected the six demo story IDs")
    for story in sprint.stories:
        StoryInput.model_validate(story.model_dump(), strict=True)
        _require(bool(story.title.strip()), f"{story.id}: title must not be empty")
        words = len(story.description.split())
        _require(60 <= words <= 120, f"{story.id}: description needs 60-120 words, got {words}")
        _require(3 <= len(story.acceptance_criteria) <= 5,
                 f"{story.id}: expected 3-5 acceptance criteria")
        _require(all(criterion.strip() for criterion in story.acceptance_criteria),
                 f"{story.id}: empty acceptance criterion")
        _unique(story.acceptance_criteria, f"{story.id} acceptance criteria")
        # Contracts do not contain structured service references on stories. Check
        # any explicit component IDs embedded in prose, without guessing from nouns.
        known = set().union(*EXPECTED_COMPONENTS.values())
        prose = " ".join([story.description, *story.acceptance_criteria])
        references = set(re.findall(r"\b[a-z]+(?:-[a-z]+)*-(?:service|db|engine|gateway|banking|portal)\b", prose))
        _require(references <= known, f"{story.id}: unknown component IDs {sorted(references - known)}")
        normalized = prose.lower().replace("-", " ")
        missing = sorted(
            cid for cid in STORY_COMPONENTS[story.id]
            if not re.search(r"\b" + re.escape(cid.replace("-", " ")) + r"\b", normalized)
        )
        _require(not missing, f"{story.id}: missing intended component wording {missing}")


@dataclass(frozen=True)
class ValidationSummary:
    components: int
    edges: int
    deployment_groups: int
    tests: int
    stories: int


def validate_data(data_dir: Path = REPO_ROOT / "data") -> ValidationSummary:
    architecture = Architecture.model_validate(
        json.loads((data_dir / "architecture.json").read_text(encoding="utf-8")), strict=True,
    )
    catalog_data = json.loads((data_dir / "test_catalog.json").read_text(encoding="utf-8"))
    _require(isinstance(catalog_data, list), "test_catalog.json must be a JSON array")
    tests = [CatalogTest.model_validate(test, strict=True) for test in catalog_data]
    sprint = DemoSprint.model_validate(
        json.loads((data_dir / "demo_sprint.json").read_text(encoding="utf-8")), strict=True,
    )
    validate_architecture(architecture)
    validate_test_catalog(tests, architecture)
    validate_demo_sprint(sprint)
    return ValidationSummary(
        components=len(architecture.components),
        edges=sum(len(c.downstream) for c in architecture.components),
        deployment_groups=len({c.deployment_group for c in architecture.components}),
        tests=len(tests), stories=len(sprint.stories),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=REPO_ROOT / "data")
    args = parser.parse_args()
    try:
        summary = validate_data(args.data_dir)
    except (OSError, ValueError) as exc:
        print(f"Data validation failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"Data valid: {summary.components} components, {summary.edges} DAG edges, "
        f"{summary.deployment_groups} deployment groups, {summary.tests} tests, "
        f"{summary.stories} stories."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
