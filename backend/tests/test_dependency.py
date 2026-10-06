"""Dependency engine tests use inline catalogs and never call an LLM."""

from math import hypot

import pytest

from app.contracts import ApiEndpoint, Architecture, Component, ComponentType
from app.engine.dependency import build_impact_graph


def component(
    component_id: str,
    *,
    downstream: list[str] | None = None,
    kind: ComponentType = "core",
    criticality: int = 10,
    group: str = "shared",
    api: str | None = None,
) -> Component:
    return Component(
        id=component_id,
        name=component_id.title(),
        type=kind,
        description="Test component",
        owner_team="Test team",
        owner_contact="test@bank.example",
        criticality=criticality,
        data_classes=["financial"],
        downstream=downstream or [],
        deployment_group=group,
        sla_tier="tier1",
        apis=[ApiEndpoint(id=component_id, method="POST", path=api, description="Test API")]
        if api else [],
    )


def node_map(result):
    return {node.id: node for node in result.nodes}


def test_single_change_includes_callers_callees_and_metadata():
    arch = Architecture(components=[
        component("channel", kind="channel", downstream=["payments"], api="/channel", group="channels"),
        component("payments", downstream=["ledger"], api="/payments", group="payments"),
        component("ledger", kind="database", criticality=5, group="payments"),
        component("unrelated", kind="analytics", group="analytics"),
    ])

    result = build_impact_graph(["payments"], arch)
    nodes = node_map(result)

    assert {key: node.hop for key, node in nodes.items()} == {
        "channel": 1, "payments": 0, "ledger": 1, "unrelated": None,
    }
    assert nodes["payments"].severity == "high"
    assert nodes["channel"].severity == "high"
    assert nodes["ledger"].severity == "medium"
    assert nodes["unrelated"].severity is None
    assert nodes["payments"].label == "Payments"
    assert nodes["payments"].owner_team == "Test team"
    assert nodes["payments"].data_classes == ["financial"]
    assert result.impacted_services == ["channel", "ledger", "payments"]
    assert result.impacted_databases == ["ledger"]
    assert result.impacted_apis == ["POST /channel", "POST /payments"]
    assert result.downstream_systems == ["channel", "ledger"]
    assert result.deployment_groups == ["channels", "payments"]
    assert [(edge.id, edge.on_impact_path) for edge in result.edges] == [
        ("channel->payments", True), ("payments->ledger", True),
    ]
    assert all(not edge.conflict for edge in result.edges)


def test_multi_hop_chain_stops_at_limit_but_keeps_all_edges():
    arch = Architecture(components=[
        component(str(index), downstream=[str(index + 1)] if index < 4 else [], api=f"/{index}")
        for index in range(5)
    ])
    result = build_impact_graph(["0"], arch)
    nodes = node_map(result)

    assert [nodes[str(index)].hop for index in range(5)] == [0, 1, 2, 3, None]
    assert [nodes[str(index)].severity for index in range(5)] == ["high", "high", "medium", "low", None]
    assert result.impacted_apis == ["POST /0", "POST /1"]
    assert [edge.id for edge in result.edges] == ["0->1", "1->2", "2->3", "3->4"]
    assert [edge.on_impact_path for edge in result.edges] == [True, True, True, False]


def test_leaf_change_propagates_upstream_without_upstream_declarations():
    arch = Architecture(components=[
        component("caller", downstream=["leaf"]),
        component("leaf", kind="database"),
    ])
    result = build_impact_graph(["leaf"], arch)
    assert {key: node.hop for key, node in node_map(result).items()} == {"caller": 1, "leaf": 0}
    assert result.edges[0].on_impact_path is True


def test_shared_sink_does_not_impact_another_caller():
    arch = Architecture(components=[
        component("A", downstream=["S"]),
        component("B", downstream=["S"]),
        component("S", kind="database"),
    ])
    result = build_impact_graph(["A"], arch)
    assert {key: node.hop for key, node in node_map(result).items()} == {
        "A": 0, "B": None, "S": 1,
    }
    assert result.impacted_services == ["A", "S"]
    assert node_map(result)["B"].severity is None
    assert {edge.id: edge.on_impact_path for edge in result.edges} == {
        "A->S": True, "B->S": False,
    }


def test_isolated_leaf_only_impacts_itself():
    arch = Architecture(components=[component("leaf"), component("unrelated")])
    result = build_impact_graph(["leaf"], arch)
    assert result.impacted_services == ["leaf"]
    assert result.downstream_systems == []
    assert result.edges == []


def test_cycle_terminates_and_same_hop_edges_are_not_impact_paths():
    arch = Architecture(components=[
        component("a", downstream=["b", "a"]),
        component("b", downstream=["c"]),
        component("c", downstream=["a"]),
    ])
    result = build_impact_graph(["a"], arch)
    assert {key: node.hop for key, node in node_map(result).items()} == {"a": 0, "b": 1, "c": 1}
    assert {edge.id: edge.on_impact_path for edge in result.edges} == {
        "a->a": False, "a->b": True, "b->c": False, "c->a": True,
    }


def test_multiple_changes_keep_minimum_distance_and_deduplicate():
    arch = Architecture(components=[
        component(str(index), downstream=[str(index + 1)] if index < 4 else [])
        for index in range(5)
    ])
    result = build_impact_graph(["0", "4", "4", "unknown"], arch)
    assert [node_map(result)[str(index)].hop for index in range(5)] == [0, 1, 2, 1, 0]
    assert len(result.impacted_services) == 5
    assert result.deployment_groups == ["shared"]


def test_positions_are_deterministic_and_grouped_by_type():
    components = [
        component("root", downstream=["core-b", "channel", "core-a", "db"]),
        component("core-b"), component("channel", kind="channel"),
        component("core-a"), component("db", kind="database"),
        component("outside", kind="analytics"),
    ]
    arch = Architecture(components=components)
    result = build_impact_graph(["root"], arch)
    reordered = Architecture(components=[item.model_copy(update={"downstream": list(reversed(item.downstream))})
                                         for item in reversed(components)])
    assert result == build_impact_graph(["root", "root"], reordered)
    nodes = node_map(result)
    assert (nodes["root"].x, nodes["root"].y) == (0.0, 0.0)
    assert [(nodes[key].x, nodes[key].y) for key in ["channel", "core-a", "core-b", "db"]] == [
        (310.0, 0.0), (0.0, 310.0), (-310.0, 0.0), (0.0, -310.0),
    ]
    assert (nodes["outside"].x, nodes["outside"].y) == (820.0, 0.0)


def test_multiple_changed_nodes_use_a_small_ring():
    arch = Architecture(components=[component("b"), component("a"), component("c")])
    result = build_impact_graph(["b", "a", "c"], arch)
    assert result == build_impact_graph(["c", "a", "b"], arch)
    for node in result.nodes:
        assert hypot(node.x, node.y) == pytest.approx(70, abs=0.1)
        assert node.x == round(node.x, 1)
        assert node.y == round(node.y, 1)
    assert len({(node.x, node.y) for node in result.nodes}) == 3


@pytest.mark.parametrize("affected", [[], ["unknown"]])
def test_no_known_changes_leave_every_component_unimpacted(affected):
    arch = Architecture(components=[component("a", downstream=["b"]), component("b")])
    result = build_impact_graph(affected, arch)
    assert all(node.hop is None and node.severity is None for node in result.nodes)
    assert not result.edges[0].on_impact_path
    assert result.impacted_services == result.impacted_databases == result.impacted_apis == []
    assert result.downstream_systems == result.deployment_groups == []


def test_empty_architecture():
    result = build_impact_graph(["unknown"], Architecture(components=[]))
    assert result.nodes == result.edges == result.impacted_services == []


@pytest.mark.parametrize("criticality,expected", [(3, "low"), (4, "medium"), (5, "medium"), (6, "high")])
def test_direct_severity_thresholds(criticality, expected):
    arch = Architecture(components=[component("a", criticality=criticality)])
    assert build_impact_graph(["a"], arch).nodes[0].severity == expected


@pytest.mark.parametrize("criticality,expected", [(4, "low"), (5, "medium"), (8, "medium"), (9, "high")])
def test_first_hop_severity_thresholds(criticality, expected):
    arch = Architecture(components=[component("a", downstream=["b"]), component("b", criticality=criticality)])
    assert node_map(build_impact_graph(["a"], arch))["b"].severity == expected


def test_zero_hop_limit_keeps_only_direct_changes():
    arch = Architecture(components=[component("a", downstream=["b"]), component("b")])
    result = build_impact_graph(["a"], arch, max_hops=0)
    assert result.impacted_services == ["a"]
    assert node_map(result)["b"].hop is None
    assert result.edges[0].on_impact_path is False


def test_negative_hop_limit_is_rejected():
    with pytest.raises(ValueError, match="max_hops"):
        build_impact_graph([], Architecture(components=[]), max_hops=-1)
