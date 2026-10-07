"use client";

import { useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import type { GraphNode, ImpactGraph, Severity } from "@/lib/types";
import { hopLabel, typeLabel } from "./node-icon";

export interface DependencyGraphProps {
  graph: ImpactGraph;
  highlight?: string[];
  selectedId?: string | null;
  onNodeSelect?: (id: string | null) => void;
}

const NODE_W = 228;
const NODE_H = 58;
const COL_GAP = 104;
const ROW_GAP = 22;
const PAD = 28;

const tone: Record<Severity, string> = {
  high: "border-impact-high/70",
  medium: "border-impact-med/70",
  low: "border-impact-low/70",
};
const fill: Record<Severity, string> = {
  high: "bg-impact-high/15",
  medium: "bg-impact-med/15",
  low: "bg-impact-low/15",
};

type Placed = { node: GraphNode; x: number; y: number };

/** Columns by distance from the change; each column ordered to keep links short. */
function layout(graph: ImpactGraph) {
  const affected = graph.nodes.filter((node) => node.hop !== null);
  const links = graph.edges.filter((edge) => edge.on_impact_path);
  const columns: GraphNode[][] = [];
  for (const node of affected) (columns[node.hop as number] ??= []).push(node);
  const filled = columns.map((column) => column ?? []);
  const order = new Map<string, number>();
  filled.forEach((column, index) => {
    if (index === 0) column.sort((a, b) => b.criticality - a.criticality || a.label.localeCompare(b.label));
    else {
      const centre = (node: GraphNode) => {
        const neighbours = links.flatMap((edge) => edge.source === node.id ? [edge.target] : edge.target === node.id ? [edge.source] : [])
          .map((id) => order.get(id)).filter((value): value is number => value !== undefined);
        return neighbours.length ? neighbours.reduce((sum, value) => sum + value, 0) / neighbours.length : Infinity;
      };
      column.sort((a, b) => centre(a) - centre(b) || a.label.localeCompare(b.label));
    }
    column.forEach((node, row) => order.set(node.id, row));
  });
  const tallest = Math.max(1, ...filled.map((column) => column.length));
  const height = tallest * NODE_H + (tallest - 1) * ROW_GAP + PAD * 2;
  const placed = new Map<string, Placed>();
  filled.forEach((column, index) => {
    const columnHeight = column.length * NODE_H + Math.max(0, column.length - 1) * ROW_GAP;
    const top = (height - columnHeight) / 2;
    column.forEach((node, row) => placed.set(node.id, {
      node, x: PAD + index * (NODE_W + COL_GAP), y: top + row * (NODE_H + ROW_GAP),
    }));
  });
  const width = PAD * 2 + filled.length * NODE_W + Math.max(0, filled.length - 1) * COL_GAP;
  const lines = links
    .map((edge) => [placed.get(edge.source), placed.get(edge.target)] as const)
    .filter((pair): pair is readonly [Placed, Placed] => Boolean(pair[0] && pair[1]))
    .map(([a, b]) => (a.x <= b.x ? [a, b] : [b, a]) as [Placed, Placed])
    .filter(([a, b]) => a.x !== b.x);
  return { placed: [...placed.values()], lines, width, height, columns: filled.length };
}

/** A plain map of what the change touches: changed on the left, each column one step further. */
export function DependencyGraph({ graph, highlight = [], selectedId = null, onNodeSelect }: DependencyGraphProps) {
  const [internal, setInternal] = useState<string | null>(null);
  const selection = onNodeSelect ? selectedId : internal;
  const select = (id: string | null) => (onNodeSelect ?? setInternal)(id);
  const { placed, lines, width, height, columns } = useMemo(() => layout(graph), [graph]);
  const lit = new Set(highlight);
  const dim = (id: string) => lit.size > 0 && !lit.has(id);

  if (!placed.length) {
    return <p className="rounded-xl border border-dashed border-line px-4 py-10 text-center text-body text-muted">No catalog components matched. Add more detail to the story.</p>;
  }
  return (
    <figure className="overflow-hidden rounded-xl border border-line bg-surface">
      <figcaption className="flex items-center justify-between border-b border-line px-5 py-3">
        <span className="text-body font-semibold">Impact footprint</span>
        <span className="text-dense text-muted tabular-nums">{placed.length} component{placed.length === 1 ? "" : "s"}{columns > 1 ? ` · ${columns - 1} step${columns > 2 ? "s" : ""} deep` : ""}</span>
      </figcaption>
      <div className="graph-grid overflow-x-auto">
        <div className="relative mx-auto" style={{ width, height }}>
          <svg className="pointer-events-none absolute inset-0" width={width} height={height} aria-hidden="true">
            {lines.map(([a, b]) => (
              <line key={`${a.node.id}-${b.node.id}`} x1={a.x + NODE_W} y1={a.y + NODE_H / 2} x2={b.x} y2={b.y + NODE_H / 2}
                stroke="var(--line-strong)" strokeWidth={dim(a.node.id) || dim(b.node.id) ? 1 : 2} strokeOpacity={dim(a.node.id) || dim(b.node.id) ? 0.35 : 0.9} />
            ))}
          </svg>
          <ul aria-label="Affected components">
          {placed.map(({ node, x, y }) => {
            const severity = node.severity ?? "low";
            const changed = node.hop === 0;
            return (
              <li key={node.id} className="absolute" style={{ left: x, top: y, width: NODE_W, height: NODE_H }}>
              <button type="button" onClick={() => select(selection === node.id ? null : node.id)}
                aria-pressed={selection === node.id}
                aria-label={`${node.label}, ${typeLabel[node.type]}, criticality ${node.criticality} of 10, ${hopLabel(node.hop).toLowerCase()}, ${severity} impact. Show details`}
                className={cn(
                  "flex size-full flex-col justify-center rounded-lg border px-3.5 text-left transition-opacity duration-150",
                  changed ? `border-2 ${fill[severity]} ${tone[severity]}` : `bg-canvas ${tone[severity]}`,
                  selection === node.id && "outline-2 outline-offset-2 outline-chalk",
                  dim(node.id) && "opacity-30",
                )}
                >
                <span className="truncate text-body font-semibold">{node.label}</span>
                <span className="truncate text-meta text-muted">{typeLabel[node.type]} · criticality {node.criticality}/10</span>
              </button>
              </li>
            );
          })}
          </ul>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-line px-5 py-2.5 text-dense text-muted">
        <span className="flex items-center gap-1.5"><i className="size-3 rounded-sm border-2 border-impact-high/70 bg-impact-high/15" aria-hidden="true" />Changed</span>
        <span className="flex items-center gap-1.5"><i className="size-2.5 rounded-full bg-impact-high" aria-hidden="true" />High impact</span>
        <span className="flex items-center gap-1.5"><i className="size-2.5 rounded-full bg-impact-med" aria-hidden="true" />Medium</span>
        <span className="flex items-center gap-1.5"><i className="size-2.5 rounded-full bg-impact-low" aria-hidden="true" />Low</span>
        <span className="ml-auto">Left to right: changed, then each step further away</span>
      </div>
    </figure>
  );
}
