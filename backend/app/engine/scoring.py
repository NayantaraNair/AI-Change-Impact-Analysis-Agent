"""Deterministic risk scoring with traceable factors and YAML-tunable weights."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from app.contracts import (
    Architecture,
    ImpactGraph,
    RequirementFacts,
    RiskDimension,
    RiskDimensionName,
    RiskFactor,
    RiskReport,
    Severity,
)

DIMENSION_ORDER: tuple[RiskDimensionName, ...] = (
    "security",
    "compliance",
    "technical",
    "operational",
    "performance",
    "delivery",
)
SCORING_CONFIG_PATH = Path(__file__).resolve().parents[1] / "scoring_config.yaml"


def load_scoring_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load a fresh config so callers can tune weights without shared mutation."""
    with Path(path or SCORING_CONFIG_PATH).open(encoding="utf-8") as stream:
        cfg = yaml.safe_load(stream)
    if not isinstance(cfg, dict):
        raise ValueError("Scoring configuration must be a mapping")
    return cfg


def _level(score: int) -> Severity:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _dimension(name: RiskDimensionName, factors: list[RiskFactor]) -> RiskDimension:
    score = max(0, min(100, sum(factor.points for factor in factors)))
    level = _level(score)
    contributors = [
        factor for factor in factors if factor.label != "baseline" and factor.points
    ]
    top = sorted(contributors, key=lambda factor: -factor.points)[:3] or factors[:1]
    reasons = []
    for factor in top:
        location = f" on {', '.join(factor.node_ids)}" if factor.node_ids else ""
        reasons.append(f"{factor.label} ({factor.points:+d}){location}")
    explanation = f"{name.capitalize()} risk is {level} ({score}) because "
    explanation += " and ".join(reasons) + "."
    return RiskDimension(
        name=name,
        score=score,
        level=level,
        factors=factors,
        explanation=explanation,
    )


def score_risk(
    facts: RequirementFacts,
    graph: ImpactGraph,
    arch: Architecture,
    cfg: Mapping[str, Any] | None = None,
) -> RiskReport:
    """Score facts and graph hops, using architecture metadata as the authority.

    A node is impacted when its hop is nonnegative. Summary lists are deduplicated
    and matched to those nodes so unrelated systems cannot add risk points.
    Factor points retain their original values even when a dimension is clamped.
    """
    if cfg is None:
        cfg = load_scoring_config()
    components = {component.id: component for component in arch.components}
    hops = {
        node.id: node.hop
        for node in graph.nodes
        if node.hop is not None and node.hop >= 0 and node.id in components
    }
    impacted = sorted(hops)
    direct = [node_id for node_id in impacted if hops[node_id] == 0]
    direct_services = [
        node_id for node_id in direct if components[node_id].type != "database"
    ]
    anchors = (
        direct or impacted or sorted(set(facts.affected_services) & components.keys())
    )
    # Regulated data counts when it is changed directly or one hop away.
    data_nodes = {
        data_class: [
            node_id for node_id in impacted
            if hops[node_id] <= 1 and data_class in components[node_id].data_classes
        ]
        for data_class in ("pii", "card", "financial", "audit")
    }
    databases = [
        node_id for node_id in impacted if components[node_id].type == "database"
    ]
    factors = {
        name: [RiskFactor(label="baseline", points=cfg[name]["base"], node_ids=[])]
        for name in DIMENSION_ORDER
    }

    def add(
        name: RiskDimensionName, label: str, points: int, node_ids: list[str]
    ) -> None:
        if points:
            factors[name].append(
                RiskFactor(label=label, points=points, node_ids=sorted(set(node_ids)))
            )

    security = cfg["security"]
    for enabled, key, label, node_ids in (
        (
            facts.touches_customer_data, "customer_data", "customer data",
            data_nodes["pii"] or anchors,
        ),
        (
            facts.touches_card_data, "card_data", "card data",
            data_nodes["card"] or anchors,
        ),
        (facts.changes_auth_flow, "auth_flow_change", "auth flow change", anchors),
        (
            facts.changes_external_api_contract, "external_api_contract",
            "external API contract", anchors,
        ),
    ):
        if enabled:
            add("security", label, security[key], node_ids)
    identity = [
        node_id for node_id in impacted
        if node_id in security["identity_nodes"] and hops[node_id] <= 1
    ]
    if identity:
        add(
            "security", "critical identity path",
            security["critical_identity_path"], identity,
        )
    nearby = [node_id for node_id in impacted if hops[node_id] <= 2]
    add(
        "security", "blast radius size",
        min(len(nearby) * security["nearby_node"], security["nearby_node_cap"]),
        nearby,
    )

    compliance = cfg["compliance"]
    # Regulated data changed directly scores in full; data one hop away scores
    # at the reduced "nearby" weight.
    for data_class, nodes in data_nodes.items():
        direct_nodes = [node_id for node_id in nodes if hops[node_id] == 0]
        if direct_nodes:
            add(
                "compliance", f"{data_class} data",
                compliance[data_class], direct_nodes,
            )
        elif nodes:
            add(
                "compliance", f"nearby {data_class} data",
                compliance["nearby"][data_class], nodes,
            )
    if facts.changes_db_schema:
        add(
            "compliance", "database schema change",
            compliance["db_schema_change"], databases or anchors,
        )

    technical = cfg["technical"]
    if facts.changes_db_schema:
        add(
            "technical", "database schema change",
            technical["db_schema_change"], databases or anchors,
        )
    add(
        "technical", "direct services",
        min(
            len(direct_services) * technical["direct_service"],
            technical["direct_service_cap"],
        ),
        direct_services,
    )
    max_hop = max(hops.values(), default=0)
    deepest = [node_id for node_id in impacted if hops[node_id] == max_hop]
    add("technical", "dependency depth", max_hop * technical["hop_depth"], deepest)
    add(
        "technical", facts.change_type.replace("_", " "),
        technical["change_types"].get(facts.change_type, 0), anchors,
    )

    operational = cfg["operational"]
    max_criticality = max(
        (components[node_id].criticality for node_id in direct_services), default=0
    )
    critical = [
        node_id for node_id in direct_services
        if components[node_id].criticality == max_criticality
    ]
    add(
        "operational", "service criticality",
        max_criticality * operational["criticality"], critical,
    )
    downstream = sorted(set(graph.downstream_systems) & hops.keys())
    add(
        "operational", "downstream systems",
        min(
            len(downstream) * operational["downstream_system"],
            operational["downstream_system_cap"],
        ),
        downstream,
    )
    deployment_nodes = [
        node_id for node_id in impacted
        if components[node_id].deployment_group in graph.deployment_groups
    ]
    groups = {components[node_id].deployment_group for node_id in deployment_nodes}
    add(
        "operational", "deployment groups",
        min(
            len(groups) * operational["deployment_group"],
            operational["deployment_group_cap"],
        ),
        deployment_nodes,
    )

    performance = cfg["performance"]
    transaction_nodes = [
        node_id for node_id in impacted if node_id in performance["transaction_nodes"]
    ]
    channel_nodes = [
        node_id for node_id in impacted if node_id in performance["channel_nodes"]
    ]
    if transaction_nodes:
        add(
            "performance", "transaction path",
            performance["transaction_path"], transaction_nodes,
        )
    if channel_nodes:
        add("performance", "channel path", performance["channel_path"], channel_nodes)
    if facts.change_type == "business_rule_change" and transaction_nodes:
        add(
            "performance", "payment business rule",
            performance["payment_business_rule"], transaction_nodes,
        )

    delivery = cfg["delivery"]
    add(
        "delivery", f"{facts.ambiguity} ambiguity",
        delivery["ambiguity"][facts.ambiguity], anchors,
    )
    add(
        "delivery", "direct services",
        len(direct_services) * delivery["direct_service"], direct_services,
    )
    owners = {components[node_id].owner_team for node_id in impacted}
    add(
        "delivery", "owner coordination",
        max(0, len(owners) - 1) * delivery["additional_owner_team"], impacted,
    )

    dimensions = [_dimension(name, factors[name]) for name in DIMENSION_ORDER]
    top_three = sorted((dimension.score for dimension in dimensions), reverse=True)[:3]
    return RiskReport(
        dimensions=dimensions,
        overall=round(sum(top_three) / len(top_three)),
        highest=max(dimensions, key=lambda dimension: dimension.score).name,
    )
