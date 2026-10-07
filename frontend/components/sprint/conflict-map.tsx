import Link from "next/link";
import { cn } from "@/lib/utils";
import type { Conflict, SprintAnalysis } from "@/lib/types";

// Plain words for each kind of clash, and the one thing to do about it.
export const clashLabel: Record<Conflict["kind"], string> = {
  deployment_collision: "Same release group",
  parallel_modification: "Both change it",
  schema_contention: "Both change its schema",
  shared_database: "Both write to it",
  shared_api_change: "Both change its API",
};

export function clashAction(conflict: Conflict): string {
  switch (conflict.kind) {
    case "deployment_collision": return `Release ${conflict.story_b} first, then ${conflict.story_a}.`;
    case "parallel_modification": return "Agree one design, then test both together.";
    case "schema_contention": return "Plan one schema change, then release in turn.";
    case "shared_database": return "Test both together before release.";
    case "shared_api_change": return "Agree one API version first.";
  }
}

const tone = {
  high: "border-impact-high/60 text-impact-high",
  medium: "border-impact-med/60 text-impact-med",
  low: "border-impact-low/60 text-impact-low",
};

function StoryChip({ id, title }: { id: string; title?: string }) {
  return (
    <Link href={`/story?id=${encodeURIComponent(id)}`} title={title} className="min-w-0 rounded-lg border border-line bg-surface px-3 py-2 text-dense transition-colors duration-150 hover:border-line-strong">
      <span className="block font-semibold">{id}</span>
      {title && <span className="block truncate text-meta text-muted">{title}</span>}
    </Link>
  );
}

/** Each clash as one line: story ─ shared component ─ story, with what to do. */
export function ConflictMap({ analysis }: { analysis: SprintAnalysis }) {
  const labels = new Map(analysis.conflict_graph.nodes.map((node) => [node.id, node.label]));
  const titles = new Map(analysis.stories.map(({ story }) => [story.id, story.title]));
  if (!analysis.conflicts.length) return <p className="py-4 text-body">No clashes. These stories can be worked on in parallel.</p>;
  return (
    <ul className="space-y-3">
      {analysis.conflicts.map((conflict) => (
        <li key={conflict.id} className="rounded-xl border border-line px-4 py-3">
          <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1.1fr)_auto_minmax(0,1fr)] items-center">
            <StoryChip id={conflict.story_a} title={titles.get(conflict.story_a)} />
            <span aria-hidden="true" className="h-px w-6 bg-line-strong sm:w-10" />
            <div className={cn("rounded-lg border-2 bg-canvas px-3 py-2 text-center", tone[conflict.risk])}>
              <span className="block text-dense font-semibold text-text">{labels.get(conflict.shared_component) ?? conflict.shared_component}</span>
              <span className="block text-meta">{clashLabel[conflict.kind]} · {conflict.risk} risk</span>
            </div>
            <span aria-hidden="true" className="h-px w-6 bg-line-strong sm:w-10" />
            <StoryChip id={conflict.story_b} title={titles.get(conflict.story_b)} />
          </div>
          <p className="mt-2 text-dense"><span className="text-muted">Do: </span>{clashAction(conflict)}</p>
        </li>
      ))}
    </ul>
  );
}
