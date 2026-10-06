import { MarkerType, Position, type Edge, type Node } from "@xyflow/react";
import type { ComponentType, GraphEdge, GraphNode, ImpactGraph, Severity } from "@/lib/types";

export type ImpactNodeData = {
  node: GraphNode;
  onSelect?: (id: string | null) => void;
};
export type ImpactFlowNode = Node<ImpactNodeData, ComponentType>;
export type ImpactEdgeData = {
  onImpactPath: boolean;
  conflict: boolean;
  animate: boolean;
};
export type ImpactFlowEdge = Edge<ImpactEdgeData, "impact">;

export const severityColor = (severity: Severity | null) =>
  severity === "medium" ? "var(--impact-med)" : severity ? `var(--impact-${severity})` : "var(--line)";

export function searchNodes(nodes: GraphNode[], query: string): GraphNode[] {
  const term = query.trim().toLocaleLowerCase();
  if (!term) return [];
  return nodes
    .filter((node) => `${node.label} ${node.id}`.toLocaleLowerCase().includes(term))
    .sort((a, b) => {
      const exactA = a.label.toLocaleLowerCase() === term || a.id.toLocaleLowerCase() === term;
      const exactB = b.label.toLocaleLowerCase() === term || b.id.toLocaleLowerCase() === term;
      return Number(exactB) - Number(exactA) || a.label.localeCompare(b.label);
    });
}

function connectionSides(source: GraphNode, target: GraphNode) {
  const dx = target.x - source.x;
  const dy = target.y - source.y;
  if (Math.abs(dx) >= Math.abs(dy)) {
    return dx >= 0 ? [Position.Right, Position.Left] : [Position.Left, Position.Right];
  }
  return dy >= 0 ? [Position.Bottom, Position.Top] : [Position.Top, Position.Bottom];
}

export function toFlowElements(
  graph: ImpactGraph,
  options: {
    highlight?: string[];
    selectedId?: string | null;
    showUnimpacted: boolean;
    animate: boolean;
    onSelect?: (id: string | null) => void;
    conflictEdges?: GraphEdge[];
  },
): { nodes: ImpactFlowNode[]; edges: ImpactFlowEdge[] } {
  const highlighted = new Set(options.highlight);
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const hidden = new Set(graph.nodes.filter((node) => node.hop === null && !options.showUnimpacted).map((node) => node.id));
  const nodes: ImpactFlowNode[] = graph.nodes.map((node) => ({
    id: node.id,
    type: node.type,
    position: { x: node.x, y: node.y },
    data: { node, onSelect: options.onSelect },
    selected: node.id === options.selectedId,
    hidden: hidden.has(node.id),
    draggable: false,
    connectable: false,
    focusable: false,
    style: {
      opacity: highlighted.size && !highlighted.has(node.id) ? 0.2 : node.hop === null ? 0.35 : 1,
    },
  }));
  // Additional conflict edges replace an edge with the same id, rather than duplicating it.
  const merged = new Map(graph.edges.map((edge) => [edge.id, edge]));
  options.conflictEdges?.forEach((edge) => merged.set(edge.id, { ...edge, conflict: true }));
  const edges: ImpactFlowEdge[] = [];
  for (const edge of merged.values()) {
    const source = byId.get(edge.source);
    const target = byId.get(edge.target);
    // A partial graph can omit endpoints; do not ask React Flow to render a broken edge.
    if (!source || !target) continue;
    const [sourceSide, targetSide] = connectionSides(source, target);
    const color = edge.conflict ? "var(--impact-high)" : edge.on_impact_path ? severityColor(target.severity) : "var(--line)";
    edges.push({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      sourceHandle: `source-${sourceSide}`,
      targetHandle: `target-${targetSide}`,
      type: "impact",
      hidden: hidden.has(source.id) || hidden.has(target.id),
      selectable: false,
      focusable: false,
      data: { onImpactPath: edge.on_impact_path, conflict: edge.conflict, animate: options.animate && !edge.conflict },
      style: {
        stroke: color,
        strokeWidth: edge.conflict ? 2 : edge.on_impact_path ? 1.8 : 1,
        opacity: highlighted.size && !(highlighted.has(source.id) && highlighted.has(target.id)) ? 0.2 : 1,
      },
      markerEnd: { type: MarkerType.ArrowClosed, color, width: 12, height: 12 },
    });
  }
  return { nodes, edges };
}
