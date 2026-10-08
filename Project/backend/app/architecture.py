"""Loads data/architecture.json and data/test_catalog.json into typed objects."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app import config
from app.contracts import ApiEndpoint, Architecture, CatalogTest, Component, DemoSprint

_STUB = Architecture(
    components=[
        Component(
            id="mobile-banking", name="Mobile Banking", type="channel",
            description="Customer mobile app", owner_team="Digital Channels",
            owner_contact="channels@bank.example", criticality=8,
            apis=[ApiEndpoint(id="mobile-login", method="POST", path="/mobile/login",
                              description="Login", external=True)],
            downstream=["payment-service"], deployment_group="channels-mobile", sla_tier="tier1",
        ),
        Component(
            id="payment-service", name="Payment Service", type="core",
            description="Executes payments", owner_team="Payments Platform",
            owner_contact="payments@bank.example", criticality=10, data_classes=["financial"],
            apis=[ApiEndpoint(id="payments-create", method="POST", path="/payments",
                              description="Create payment")],
            upstream=["mobile-banking"], downstream=["transaction-db", "audit-db"],
            deployment_group="core-payments", sla_tier="tier1",
        ),
        Component(
            id="transaction-db", name="Transaction DB", type="database",
            description="Ledger of transactions", owner_team="Core Banking",
            owner_contact="core@bank.example", criticality=9, data_classes=["financial"],
            upstream=["payment-service"], deployment_group="core-payments", sla_tier="tier1",
        ),
        Component(
            id="audit-db", name="Audit DB", type="database", description="Audit trail",
            owner_team="Core Banking", owner_contact="core@bank.example", criticality=7,
            data_classes=["audit"], upstream=["payment-service"],
            deployment_group="data-platform", sla_tier="tier2",
        ),
    ]
)


def load_architecture(path: Path | None = None) -> Architecture:
    path = path or config.ARCHITECTURE_PATH
    if not path.exists():
        return _STUB
    return Architecture.model_validate(json.loads(path.read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def get_architecture() -> Architecture:
    return load_architecture()


def get_component(component_id: str, arch: Architecture | None = None) -> Component | None:
    arch = arch or get_architecture()
    return next((c for c in arch.components if c.id == component_id), None)


def all_ids(arch: Architecture | None = None) -> list[str]:
    arch = arch or get_architecture()
    return [c.id for c in arch.components]


def catalog_string(arch: Architecture | None = None) -> str:
    """Short component catalog for LLM prompts: `id: name — description`."""
    arch = arch or get_architecture()
    return "\n".join(f"{c.id}: {c.name} — {c.description}" for c in arch.components)


@lru_cache(maxsize=1)
def get_test_catalog() -> list[CatalogTest]:
    path = config.TEST_CATALOG_PATH
    if not path.exists():
        return []
    return [CatalogTest.model_validate(t) for t in json.loads(path.read_text(encoding="utf-8"))]


def load_demo_sprint() -> DemoSprint:
    return DemoSprint.model_validate(
        json.loads(config.DEMO_SPRINT_PATH.read_text(encoding="utf-8"))
    )


def load_demo_portfolio() -> DemoSprint:
    """The executive demo: major features and stories that clash on identity."""
    return DemoSprint.model_validate(
        json.loads(config.DEMO_PORTFOLIO_PATH.read_text(encoding="utf-8"))
    )


def demo_backlogs() -> list[DemoSprint]:
    backlogs = [load_demo_sprint()]
    if config.DEMO_PORTFOLIO_PATH.exists():
        backlogs.append(load_demo_portfolio())
    return backlogs
