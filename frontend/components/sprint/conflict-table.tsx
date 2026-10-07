"use client";

import { Badge } from "@/components/ui/badge";
import { formatNumber, severityClass } from "@/lib/format";
import type { Conflict, SprintAnalysis } from "@/lib/types";
import { conflictLabels } from "./model";

export function ConflictTable({ analysis, selectedId, onSelect }: { analysis: SprintAnalysis; selectedId: string | null; onSelect: (conflict: Conflict) => void }) {
  const labels = new Map(analysis.conflict_graph.nodes.map((node) => [node.id, node.label]));
  return (
    <div className="overflow-x-auto rounded-md border border-line">
      <table className="w-full min-w-[850px] text-left text-dense">
        <caption className="sr-only">Sprint conflicts. Select a shared component to highlight both stories&apos; direct changes in the graph.</caption>
        <thead className="bg-surface text-muted"><tr>{["Story A", "Story B", "Shared component", "Kind", "Risk", "Recommendation"].map((label) => <th key={label} scope="col" className="px-3 py-2 font-medium">{label}</th>)}</tr></thead>
        <tbody>{analysis.conflicts.map((conflict) => (
          <tr key={conflict.id} className={`cursor-pointer border-t border-line align-top hover:bg-surface-raised focus-within:bg-surface-raised ${selectedId === conflict.id ? "bg-surface-raised" : ""}`} onClick={(event) => {
            if (!(event.target as HTMLElement).closest("button")) onSelect(conflict);
          }}>
            <td className="px-3 py-3 whitespace-nowrap">{conflict.story_a}</td>
            <td className="px-3 py-3 whitespace-nowrap">{conflict.story_b}</td>
            <td className="px-3 py-3"><button type="button" className="text-left link-ui" aria-pressed={selectedId === conflict.id} aria-label={`Highlight ${labels.get(conflict.shared_component) ?? conflict.shared_component} for ${conflict.story_a} and ${conflict.story_b}`} onClick={() => onSelect(conflict)}>{labels.get(conflict.shared_component) ?? conflict.shared_component}</button></td>
            <td className="px-3 py-3">{conflictLabels[conflict.kind]}</td>
            <td className="px-3 py-3 whitespace-nowrap"><Badge variant="outline" className={`rounded border-current/40 capitalize ${severityClass[conflict.risk]}`}>{conflict.risk}</Badge><span className={`ml-2 font-semibold tabular-nums ${severityClass[conflict.risk]}`}>{formatNumber(conflict.risk_score)}</span></td>
            <td className="w-[35%] px-3 py-3">{conflict.recommendation}</td>
          </tr>
        ))}
        {!analysis.conflicts.length && <tr><td colSpan={6} className="px-3 py-6 text-muted">No shared-component conflicts were detected in this sprint.</td></tr>}</tbody>
      </table>
    </div>
  );
}
