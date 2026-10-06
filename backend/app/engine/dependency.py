"""Deterministic dependency traversal, impact severity, and graph layout."""

from __future__ import annotations

from collections import defaultdict, deque
from math import cos, pi, sin

import networkx as nx

from app.contracts import (
    Architecture,
    Component,
    GraphEdge,
    GraphNode,
    ImpactGraph,
    ServiceId,
    Severity,
)

_DECAY = {0: 1.0, 1: 0.7, 2: 0.45, 3: 0.25}


def _severity(criticality: int, hop: int) -> Severity:
    # Explicitly requested deeper traversals retain the weakest decay.
    score = criticality * 10 * _DECAY[min(hop, 3)]
    if score >= 60:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


def _positions(
    components: list[Component], hops: dict[ServiceId, int]
) -> dict[ServiceId, tuple[float, float]]:
    rings: dict[int | None, list[Component]] = defaultdict(list)
    for component in components:
        rings[hops.get(component.id)].append(component)

    positions = {}
    for hop, ring in rings.items():
        ring.sort(key=lambda component: (component.type, component.id))
        if hop == 0 and len(ring) == 1:
            positions[ring[0].id] = (0.0, 0.0)
            continue
        radius = 70 if hop == 0 else 140 + (4 if hop is None else hop) * 170
        for index, component in enumerate(ring):
            angle = 2 * pi * index / len(ring)
            positions[component.id] = (
                round(radius * cos(angle), 1),
                round(radius * sin(angle), 1),
            )
    return positions


def build_impact_graph(
    affected: list[ServiceId], arch: Architecture, max_hops: int = 3
) -> ImpactGraph:
    """Follow callees and callers, keeping minimum distance from any change.

    Downstream declarations are the source of truth for directed edges; their
    reverse direction supplies callers during traversal. Every catalog component
    and downstream edge is included, even when outside the impact radius.
    """
    if max_hops < 0:
        raise ValueError("max_hops must be non-negative")

    components = {component.id: component for component in arch.components}
    graph = nx.DiGraph()
    graph.add_nodes_from(components)
    graph.add_edges_from(
        (component.id, target)
        for component in arch.components
        for target in component.downstream
    )

    hops = {component_id: 0 for component_id in sorted(set(affected) & components.keys())}
    pending = deque(hops)
    while pending:
        source = pending.popleft()
        if hops[source] >= max_hops:
            continue
        neighbors = set(graph.successors(source)) | set(graph.predecessors(source))
        for target in sorted(neighbors):
            # Dangling references have no component metadata and cannot be impacted.
            if target not in components or target in hops:
                continue
            hops[target] = hops[source] + 1
            pending.append(target)

    positions = _positions(list(components.values()), hops)
    nodes = []
    for component_id, component in sorted(components.items()):
        hop = hops.get(component_id)
        x, y = positions[component_id]
        nodes.append(
            GraphNode(
                id=component_id,
                label=component.name,
                type=component.type,
                hop=hop,
                severity=_severity(component.criticality, hop) if hop is not None else None,
                x=x,
                y=y,
                criticality=component.criticality,
                owner_team=component.owner_team,
                data_classes=component.data_classes,
            )
        )

    edges = [
        GraphEdge(
            id=f"{source}->{target}",
            source=source,
            target=target,
            on_impact_path=(
                source in hops and target in hops and abs(hops[source] - hops[target]) == 1
            ),
        )
        for source, target in sorted(graph.edges())
    ]
    impacted = sorted(hops)
    return ImpactGraph(
        nodes=nodes,
        edges=edges,
        impacted_services=impacted,
        impacted_databases=[
            component_id for component_id in impacted if components[component_id].type == "database"
        ],
        impacted_apis=sorted(
            {
                f"{api.method} {api.path}"
                for component_id in impacted
                if hops[component_id] <= 1
                for api in components[component_id].apis
            }
        ),
        downstream_systems=[component_id for component_id in impacted if hops[component_id] >= 1],
        deployment_groups=sorted({components[component_id].deployment_group for component_id in impacted}),
    )
