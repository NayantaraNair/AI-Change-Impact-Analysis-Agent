import type { Conflict, Severity, SprintAnalysis, SprintKpis, StoryInput } from "@/lib/types";

export const kpiDefinitions = [
  { key: "stories", label: "Stories" },
  { key: "applications_impacted", label: "Apps impacted" },
  { key: "dependencies_impacted", label: "Dependencies" },
  { key: "conflicts", label: "Conflicts" },
  { key: "compliance_issues", label: "Compliance issues" },
  { key: "testing_effort_hours", label: "Test effort", unit: "h" },
  { key: "health_score", label: "Health score", positive: true },
  { key: "release_confidence", label: "Release confidence", positive: true },
] as const;

export function riskLevel(score: number): Severity {
  return score >= 70 ? "high" : score >= 40 ? "medium" : "low";
}

export function healthLevel(score: number): Severity {
  return score >= 70 ? "low" : score >= 40 ? "medium" : "high";
}

export const conflictLabels: Record<Conflict["kind"], string> = {
  deployment_collision: "Deployment collision", schema_contention: "Schema contention",
  parallel_modification: "Parallel modification", shared_api_change: "Shared API change",
  shared_database: "Shared database",
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function validateStory(value: unknown, index: number): StoryInput {
  const prefix = `Story ${index + 1}`;
  if (!isRecord(value)) throw new Error(`${prefix} must be an object with id, title and description.`);
  for (const field of ["id", "title", "description"] as const) {
    if (typeof value[field] !== "string" || !value[field].trim()) throw new Error(`${prefix} needs a non-empty ${field}.`);
  }
  const type = value.type ?? "story";
  if (type !== "story" && type !== "epic" && type !== "change_request") throw new Error(`${prefix} type must be story, epic or change_request.`);
  const criteria = value.acceptance_criteria ?? [];
  if (!Array.isArray(criteria) || !criteria.every((item) => typeof item === "string")) throw new Error(`${prefix} acceptance_criteria must be an array of strings.`);
  return {
    id: (value.id as string).trim(), title: (value.title as string).trim(), description: (value.description as string).trim(), type,
    acceptance_criteria: criteria.map((item: string) => item.trim()).filter(Boolean),
  };
}

export function parseStories(input: string): StoryInput[] {
  const text = input.trim();
  if (!text) throw new Error("Paste a JSON array or one story per line: ID | title | description.");
  let values: unknown[];
  if (text.startsWith("[") || text.startsWith("{")) {
    let parsed: unknown;
    try { parsed = JSON.parse(text); }
    catch { throw new Error("The JSON could not be read. Check commas and quotes, then try again."); }
    if (!Array.isArray(parsed)) throw new Error("Use a JSON array of stories, enclosed in square brackets.");
    values = parsed;
  } else {
    values = text.split(/\r?\n/).filter((line) => line.trim()).map((line, index) => {
      const [id, title, ...description] = line.split("|");
      if (!description.length) throw new Error(`Line ${index + 1} must use ID | title | description.`);
      return { id, title, description: description.join("|") };
    });
  }
  if (!values.length) throw new Error("Add at least one story before analyzing the sprint.");
  const stories = values.map(validateStory);
  const ids = new Set<string>();
  for (const story of stories) {
    if (ids.has(story.id)) throw new Error(`Story ID ${story.id} is repeated. Give each story a unique ID.`);
    ids.add(story.id);
  }
  return stories;
}

export function conflictHighlights(analysis: SprintAnalysis, conflict: Conflict): string[] {
  return [...new Set([
    conflict.shared_component,
    ...analysis.stories.filter(({ story }) => story.id === conflict.story_a || story.id === conflict.story_b)
      .flatMap(({ graph }) => graph.nodes.filter((node) => node.hop === 0).map((node) => node.id)),
  ])];
}

interface KpiHistory { latest: SprintKpis; previous: SprintKpis | null }
type StorageAccess = Pick<Storage, "getItem" | "setItem">;

function validKpis(value: unknown): value is SprintKpis {
  return isRecord(value) && kpiDefinitions.every(({ key }) => typeof value[key] === "number" && Number.isFinite(value[key]))
    && Array.isArray(value.high_risk_stories) && value.high_risk_stories.every((id) => typeof id === "string");
}

/** New analyses advance history; reloading the same saved KPIs preserves the baseline. */
export function rememberRun(analysis: SprintAnalysis, newRun: boolean, storage: StorageAccess): SprintKpis | null {
  const key = `change-impact:sprint:${analysis.sprint_id}:kpis:v1`;
  let stored: KpiHistory | null = null;
  try {
    const value: unknown = JSON.parse(storage.getItem(key) ?? "null");
    if (isRecord(value) && validKpis(value.latest)) stored = { latest: value.latest, previous: validKpis(value.previous) ? value.previous : null };
  } catch { /* Storage may be unavailable or contain old/corrupt data. */ }
  const changed = stored && kpiDefinitions.some(({ key }) => stored.latest[key] !== analysis.kpis[key]);
  const previous = stored ? (newRun || changed ? stored.latest : stored.previous) : null;
  try { storage.setItem(key, JSON.stringify({ latest: analysis.kpis, previous })); }
  catch { /* Analysis remains usable when browser storage is full or blocked. */ }
  return previous;
}
