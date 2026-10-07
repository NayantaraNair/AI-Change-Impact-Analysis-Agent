import type { LlmAttempt, Run, StageProgress } from "@/lib/types";

export const STORY_STAGE_ORDER = ["requirement", "dependency", "scoring", "testing", "compliance", "release"] as const;
export const SPRINT_STAGE_ORDER = ["conflicts", "recheck", "summary"] as const;

export const shortStageLabel: Record<string, string> = {
  requirement: "Read", dependency: "Map", scoring: "Score", testing: "Tests",
  compliance: "Compliance", release: "Release", conflicts: "Conflicts",
  recheck: "Re-check", summary: "Summary", answer: "Answer",
};

/** What each stage does, for tooltips on the progress view. */
export const stageExplain: Record<string, string> = {
  requirement: "A model reads the story and extracts facts only: which catalog services change, the change type and yes/no flags such as “touches card data”. No scores.",
  dependency: "Code walks the architecture map from the changed services to find everything they reach, up to 3 hops.",
  scoring: "Code adds up named risk factors in six dimensions from the facts and the graph.",
  testing: "Code picks existing tests for impacted components; a model drafts new tests for the gaps.",
  compliance: "Code decides which frameworks apply and scores them; a model writes the findings.",
  release: "Code applies the release rules; a model writes the rollback plan and deployment notes.",
  conflicts: "Code compares every pair of stories for shared components, databases, APIs and deployment groups.",
  recheck: "Release rules are re-applied to stories that conflict with another, without new model calls.",
  summary: "A model writes the sprint summary from the computed numbers.",
  answer: "The copilot answers from the current analysis.",
};

export function formatElapsed(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || !Number.isFinite(ms)) return "–";
  const seconds = Math.max(0, Math.round(ms / 1000));
  if (seconds < 60) return `${seconds} s`;
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

export function findStage(run: Run, stage: string, storyId: string | null): StageProgress | undefined {
  return run.stages.find((item) => item.stage === stage && item.story_id === storyId);
}

export function attemptsFor(run: Run, stage: string, storyId: string | null): LlmAttempt[] {
  return run.attempts.filter((attempt) => attempt.stage === stage && attempt.story_id === storyId);
}

export function activeAttempts(run: Run): LlmAttempt[] {
  return run.attempts.filter((attempt) => attempt.outcome === "running");
}

export function stageCounts(run: Run) {
  const total = run.stages.length;
  const done = run.stages.filter((item) => item.status === "done").length;
  return { done, total };
}

export function attemptSummary(run: Run) {
  const calls = run.attempts.filter((attempt) => attempt.outcome !== "skipped" && attempt.outcome !== "running");
  const failed = calls.filter((attempt) => attempt.outcome !== "ok");
  return { calls: calls.length, failed: failed.length, ok: calls.length - failed.length };
}

/** Distinct models that wrote at least one stage, with how many stages each wrote. */
export function modelsUsed(run: Run): Array<{ label: string; stages: number }> {
  const counts = new Map<string, number>();
  for (const stage of run.stages) {
    if (stage.source === "llm" && stage.provider) counts.set(stage.provider, (counts.get(stage.provider) ?? 0) + 1);
  }
  return [...counts].map(([label, stages]) => ({ label, stages })).sort((a, b) => b.stages - a.stages);
}
