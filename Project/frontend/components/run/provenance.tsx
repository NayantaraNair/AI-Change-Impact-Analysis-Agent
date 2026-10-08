"use client";

import { useAppContext } from "@/components/shell/app-context";
import { classifyProvider, splitProvider } from "@/lib/explain";
import type { Run, SprintAnalysis, StoryAnalysis } from "@/lib/types";
import { formatElapsed } from "./model";

/** One quiet line: which AI read the story, that rules scored it, and a way into the details. */
export function RunNote({ analysis, run }: { analysis: StoryAnalysis | SprintAnalysis; run: Run | null }) {
  const { setDebugOpen } = useAppContext();
  const stories = "stories" in analysis ? analysis.stories : [analysis];
  const models = new Map<string, number>();
  let fallbacks = 0;
  for (const story of stories) {
    for (const [stage, label] of Object.entries(story.providers_used)) {
      if (stage === "dependency" || stage === "scoring") continue;
      const kind = classifyProvider(label);
      if (kind === "llm") models.set(label, (models.get(label) ?? 0) + 1);
      else if (kind === "fallback") fallbacks += 1;
    }
  }
  const main = [...models].sort((a, b) => b[1] - a[1])[0]?.[0];
  const ai = main ? `${splitProvider(main).provider} (${splitProvider(main).model})${models.size > 1 ? ` +${models.size - 1} more` : ""}` : "built-in rules (no AI key)";
  const saved = run?.stages.every((stage) => stage.source === "fixture");
  return (
    <p className="flex flex-wrap items-center gap-x-2 border-b border-line py-2 text-meta text-muted">
      <span>Read by <span className="text-model">{ai}</span>. Scored by rules.{fallbacks ? ` ${fallbacks} step${fallbacks === 1 ? "" : "s"} used the fallback.` : ""}</span>
      {run && <span>{saved ? "Saved demo result." : `Took ${formatElapsed(run.elapsed_ms)}.`}</span>}
      <button type="button" onClick={() => setDebugOpen(true)} className="link-ui">Details</button>
    </p>
  );
}
