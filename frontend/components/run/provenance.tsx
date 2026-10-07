"use client";

import { Bug } from "lucide-react";
import { useAppContext } from "@/components/shell/app-context";
import { InfoTip } from "@/components/ui/info-tip";
import { classifyProvider, explain, splitProvider } from "@/lib/explain";
import type { Run, SprintAnalysis, StoryAnalysis } from "@/lib/types";
import { attemptSummary, formatElapsed, shortStageLabel, STORY_STAGE_ORDER } from "./model";
import { SourceBadge } from "./parts";

function RunFacts({ run }: { run: Run | null }) {
  const { setDebugOpen } = useAppContext();
  if (!run) return null;
  const { calls, failed } = attemptSummary(run);
  const fixture = run.stages.every((stage) => stage.source === "fixture");
  return (
    <span className="flex flex-wrap items-center gap-x-3 gap-y-1 text-meta text-muted tabular-nums">
      <span>{fixture ? "Saved demo result, no model calls" : `Ran in ${formatElapsed(run.elapsed_ms)}`}</span>
      {!fixture && <span>{calls} model call{calls === 1 ? "" : "s"}{failed ? `, ${failed} fell through to the next provider` : ""}</span>}
      <button type="button" onClick={() => setDebugOpen(true)} className="inline-flex items-center gap-1 rounded text-model hover:underline"><Bug aria-hidden="true" className="size-3.5" />Debug details</button>
    </span>
  );
}

/** Which engine produced each stage of a story: shown with every result. */
export function StoryProvenance({ analysis, run }: { analysis: StoryAnalysis; run: Run | null }) {
  const fromRun = (stage: string) => run?.stages.find((item) => item.stage === stage && item.story_id === analysis.story.id);
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-line py-3">
      <span className="flex items-center gap-1.5 text-meta font-medium text-muted">How this was produced <InfoTip label="sources">{explain.sources}</InfoTip></span>
      <ul className="flex flex-wrap items-center gap-x-3 gap-y-2">
        {STORY_STAGE_ORDER.map((stage) => {
          const tracked = fromRun(stage);
          const label = analysis.providers_used[stage];
          const badge = tracked?.source ? tracked : label ? { source: classifyProvider(label), provider: label } : null;
          return (
            <li key={stage} className="flex items-center gap-1.5 text-meta">
              <span className="text-muted">{shortStageLabel[stage]}</span>
              {badge ? <SourceBadge stage={badge} /> : <span className="text-muted">–</span>}
            </li>
          );
        })}
      </ul>
      <RunFacts run={run} />
    </div>
  );
}

/** Models behind a sprint's stories, counted by stage. */
export function SprintProvenance({ analysis, run }: { analysis: SprintAnalysis; run: Run | null }) {
  const counts = new Map<string, number>();
  let fallbacks = 0;
  for (const story of analysis.stories) {
    for (const [stage, label] of Object.entries(story.providers_used)) {
      if (stage === "dependency" || stage === "scoring") continue;
      const kind = classifyProvider(label);
      if (kind === "llm") counts.set(label, (counts.get(label) ?? 0) + 1);
      else if (kind === "fallback") fallbacks += 1;
    }
  }
  const fixture = run?.stages.every((stage) => stage.source === "fixture") ?? false;
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-line py-3">
      <span className="flex items-center gap-1.5 text-meta font-medium text-muted">Models behind this sprint <InfoTip label="sources">{explain.sources} Dependency mapping and scoring are always plain code.</InfoTip></span>
      <ul className="flex flex-wrap items-center gap-x-3 gap-y-2">
        {[...counts].sort((a, b) => b[1] - a[1]).map(([label, stages]) => {
          const { provider, model } = splitProvider(label);
          return <li key={label} className="text-meta"><SourceBadge stage={{ source: "llm", provider: label }} /> <span className="text-muted">{model} · {stages} stage{stages === 1 ? "" : "s"}</span><span className="sr-only"> by {provider}</span></li>;
        })}
        {fallbacks > 0 && <li className="text-meta"><SourceBadge stage={{ source: "fallback", provider: "template-fallback" }} /> <span className="text-muted">{fallbacks} stage{fallbacks === 1 ? "" : "s"}</span></li>}
        {!counts.size && !fallbacks && !fixture && <li className="text-meta text-muted">Not reported</li>}
      </ul>
      <RunFacts run={run} />
    </div>
  );
}
