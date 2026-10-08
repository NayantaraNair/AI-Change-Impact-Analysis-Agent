"""How far a change reaches, decided in code from the extracted facts.

A one-line limit change and a new cross-channel feature must not get the same
blast radius. Code (not the LLM) classifies the change as small, medium or
large, then picks how many steps impact spreads, whether it spreads to callers,
and which shared platform services count.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from app.contracts import Architecture, RequirementFacts

ChangeSize = Literal["small", "medium", "large"]
_CONTAINED_TYPES = {"enhancement", "bug_fix", "config_change", "business_rule_change"}


@dataclass(frozen=True)
class Scope:
    size: ChangeSize
    max_hops: int
    include_callers: bool
    blocked: frozenset[str]
    severity_scale: float
    reason: str


def change_size(facts: RequirementFacts, arch: Architecture) -> tuple[ChangeSize, str]:
    """Small: a contained rule, limit, text or config change in one or two services.

    Large: four or more services change, or both the login flow and a public
    API change. Everything else is medium.
    """
    components = {component.id: component for component in arch.components}
    services = [
        service for service in dict.fromkeys(facts.affected_services)
        if service in components and components[service].type != "database"
    ]
    contract = facts.changes_db_schema or facts.changes_auth_flow or facts.changes_external_api_contract
    if (facts.changes_auth_flow and facts.changes_external_api_contract) or len(services) >= 4:
        return "large", f"{len(services)} services change" + (
            " and both the login flow and a public API change"
            if facts.changes_auth_flow and facts.changes_external_api_contract else ""
        )
    if len(services) <= 2 and not contract and facts.change_type in _CONTAINED_TYPES:
        return "small", "a contained change in one or two services, with no API, schema or login change"
    return "medium", f"{len(services)} service{'' if len(services) == 1 else 's'} change" + (
        ", including an API, schema or login change" if contract else ""
    )


def plan_scope(facts: RequirementFacts, arch: Architecture, cfg: Mapping[str, Any]) -> Scope:
    size, reason = change_size(facts, arch)
    scope = cfg["scope"]
    blocked = set(scope["shared_platform"]) - set(facts.affected_services)
    # Shared platform services matter only when the change touches what they do.
    if facts.changes_auth_flow:
        blocked -= set(scope["auth_platform"])
    if facts.changes_external_api_contract:
        blocked -= set(scope["api_platform"])
    if facts.changes_db_schema:
        blocked -= set(scope["schema_platform"])
    # Callers are affected only when the contract they rely on changes.
    include_callers = facts.changes_external_api_contract or facts.changes_db_schema or size == "large"
    return Scope(
        size=size, max_hops=int(scope["max_hops"][size]), include_callers=include_callers,
        blocked=frozenset(blocked), reason=reason,
        severity_scale=float(scope["severity_scale"][size]),
    )
