"use client";

import { useAppContext } from "@/components/shell/app-context";
import type { GraphNode } from "@/lib/types";

export function NodeLinks({ ids, nodes }: { ids: string[]; nodes: GraphNode[] }) {
  const { highlight, setHighlight } = useAppContext();
  if (!ids.length) return <span className="text-meta text-muted">None</span>;
  return (
    <span className="flex flex-wrap gap-1">
      {ids.map((id) => (
        <button key={id} type="button" onClick={() => setHighlight(highlight.length === 1 && highlight[0] === id ? [] : [id])}
          aria-pressed={highlight.length === 1 && highlight[0] === id}
          title={`Highlight ${id} in the graph`}
          className="rounded border border-line px-1.5 py-0.5 text-meta text-azure transition-colors duration-150 hover:bg-surface-raised aria-pressed:border-azure">
          {nodes.find((node) => node.id === id)?.label ?? id}
        </button>
      ))}
    </span>
  );
}
