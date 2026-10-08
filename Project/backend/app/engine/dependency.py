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


def _severity(criticality: int, hop: int, scale: float = 1.0) -> Severity:
    # Explicitly requested deeper traversals retain the weakest decay.
    score = criticality * 10 * _DECAY[min(hop, 3)] * scale
    if score >= 60:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


NODE_SPACING = 190.0  # arc length per node on a ring
RING_GAP = 170.0


def _positions(
    components: list[Component], hops: dict[ServiceId, int]
) -> dict[ServiceId, tuple[float, float]]:
    rings: dict[int | None, list[Component]] = defaultdict(list)
    for component in components:
        rings[hops.get(component.id)].append(component)

    # Rings grow with their population so ~170 px-wide nodes never overlap, and
    # each ring sits at least RING_GAP outside the previous one.
    positions = {}
    radius = 0.0
    for hop in sorted(rings, key=lambda h: 99 if h is None else h):
        ring = sorted(rings[hop], key=lambda component: (component.type, component.id))
        if hop == 0 and len(ring) == 1:
            positions[ring[0].id] = (0.0, 0.0)
            continue
        floor = 110.0 if hop == 0 else radius + RING_GAP
        radius = max(floor, len(ring) * NODE_SPACING / (2 * pi))
        offset = pi / len(ring) if hop and hop % 2 else 0.0
        for index, component in enumerate(ring):
            angle = 2 * pi * index / len(ring) + offset
            positions[component.id] = (
                round(radius * cos(angle), 1),
                round(radius * sin(angle), 1),
            )
    return positions


def build_impact_graph(
    affected: list[ServiceId], arch: Architecture, max_hops: int = 3,
    include_callers: bool = True, blocked: frozenset[ServiceId] = frozenset(),
    severity_scale: float = 1.0,
) -> ImpactGraph:
    """Follow callees and callers, keeping minimum distance from any change.

    Downstream declarations are the source of truth for directed edges; their
    reverse direction supplies callers during traversal. Every catalog component
    and downstream edge is included, even when outside the impact radius.
    ``include_callers`` limits spread to callees when the change keeps its
    contract; ``blocked`` components are never reached (shared platform
    services a contained change does not touch). ``severity_scale`` lowers
    impact for smaller changes: a limit tweak hits a critical service less hard.
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

    start = sorted(set(affected) & components.keys())
    hops = {component_id: 0 for component_id in start}
    # Walk each direction separately: dependents of what we change, and callers
    # of what we change. Mixing directions would hop through shared sinks such as
    # audit-db and mark the whole estate as impacted.
    directions = (graph.successors, graph.predecessors) if include_callers else (graph.successors,)
    for neighbours in directions:
        seen = {component_id: 0 for component_id in start}
        pending = deque(start)
        while pending:
            source = pending.popleft()
            if seen[source] >= max_hops:
                continue
            for target in sorted(neighbours(source)):
                # Dangling references have no component metadata and cannot be impacted.
                if target not in components or target in seen or target in blocked:
                    continue
                seen[target] = seen[source] + 1
                pending.append(target)
        for component_id, hop in seen.items():
            hops[component_id] = min(hop, hops.get(component_id, hop))

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
                severity=_severity(component.criticality, hop, severity_scale) if hop is not None else None,
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
