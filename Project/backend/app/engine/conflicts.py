"""Deterministic cross-story conflicts over directly changed components."""

from __future__ import annotations

from itertools import combinations

from app.contracts import Architecture, Component, Conflict, StoryAnalysis


def _recommendation(kind: str, a: str, b: str, component: str) -> str:
    templates = {
        "deployment_collision": (
            "Sequence the releases of {a} and {b}: deploy {b} first behind a feature flag "
            "where available and run the shared regression suite for {component} before {a}."
        ),
        "parallel_modification": (
            "Coordinate {a} and {b} changes to {component}; agree on one compatible implementation "
            "and run combined regression tests before merging and releasing."
        ),
        "schema_contention": (
            "Sequence the {a} and {b} migrations on {component}; agree on a backward-compatible "
            "schema, rehearse rollback and run combined migration and data-integrity tests."
        ),
        "shared_database": (
            "Coordinate {a} and {b} writes to {component}; validate transaction isolation, "
            "concurrent access and data integrity in the shared database regression suite."
        ),
        "shared_api_change": (
            "Align the {a} and {b} external API changes on {component}; agree on a versioned "
            "compatible contract and run consumer contract tests before either release."
        ),
    }
    return templates[kind].format(a=a, b=b, component=component)


def detect_conflicts(analyses: list[StoryAnalysis], arch: Architecture) -> list[Conflict]:
    """Emit one conflict per story pair and kind, on the most telling component.

    A component both stories change directly outranks one that only shares a
    deployment group; ties go to the more critical component.

    Indirect database overlap matters only for two schema changes within one hop.
    Architecture metadata determines types, deployment membership and APIs.
    """
    components = {component.id: component for component in arch.components}
    conflicts: dict[tuple[str, str, str], tuple[tuple[int, int, str], Conflict]] = {}
    for first, second in combinations(sorted(analyses, key=lambda a: a.story.id), 2):
        a, b = first.story.id, second.story.id
        if a == b:
            continue
        direct_a = {n.id for n in first.graph.nodes if n.hop == 0 and n.id in components}
        direct_b = {n.id for n in second.graph.nodes if n.hop == 0 and n.id in components}
        shared_direct = direct_a & direct_b

        def add(kind: str, component: Component) -> None:
            score = 40 + component.criticality * 4
            if first.release.decision == "NO_GO" or second.release.decision == "NO_GO":
                score += 20
            if first.requirement.changes_auth_flow or second.requirement.changes_auth_flow:
                score += 10
            score = max(0, min(100, score))
            rank = (0 if component.id in shared_direct else 1, -component.criticality, component.id)
            current = conflicts.get((a, b, kind))
            if current is not None and current[0] <= rank:
                return
            conflicts[(a, b, kind)] = rank, Conflict(
                id=f"C-{a}-{b}-{component.id}", story_a=a, story_b=b,
                shared_component=component.id, kind=kind,
                risk_score=score, risk="high" if score >= 70 else "medium" if score >= 40 else "low",
                recommendation=_recommendation(kind, a, b, component.id),
            )

        for node_id in sorted(shared_direct):
            component = components[node_id]
            add("deployment_collision" if component.deployment_group else "parallel_modification", component)
            if (
                first.requirement.changes_external_api_contract
                and second.requirement.changes_external_api_contract
                and any(api.external for api in component.apis)
            ):
                add("shared_api_change", component)

        groups_a = {components[n].deployment_group for n in direct_a} - {""}
        groups_b = {components[n].deployment_group for n in direct_b} - {""}
        for group in sorted(groups_a & groups_b):
            members = [components[n] for n in direct_a | direct_b if components[n].deployment_group == group]
            # Break criticality ties by ID; add() deduplicates exact collisions.
            representative = min(members, key=lambda c: (-c.criticality, c.id))
            add("deployment_collision", representative)

        databases = {n for n in shared_direct if components[n].type == "database"}
        both_schema = first.requirement.changes_db_schema and second.requirement.changes_db_schema
        if both_schema:
            nearby_a = {n.id for n in first.graph.nodes if n.hop is not None and 0 <= n.hop <= 1}
            nearby_b = {n.id for n in second.graph.nodes if n.hop is not None and 0 <= n.hop <= 1}
            databases.update(
                n for n in nearby_a & nearby_b if n in components and components[n].type == "database"
            )
        for node_id in sorted(databases):
            add("schema_contention" if both_schema else "shared_database", components[node_id])

    return [conflicts[key][1] for key in sorted(conflicts)]
