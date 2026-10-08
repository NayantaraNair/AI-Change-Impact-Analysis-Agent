import type { RiskReport, StoryInput, TestCase } from "@/lib/types";

export const STAGES = [
  { key: "requirement", label: "Reading story…" },
  { key: "dependency", label: "Mapping dependencies…" },
  { key: "scoring", label: "Scoring…" },
  { key: "testing", label: "Planning tests…" },
  { key: "compliance", label: "Checking compliance…" },
  { key: "release", label: "Deciding release…" },
] as const;

export const dimensionLabel: Record<string, string> = {
  delivery: "Delivery", technical: "Technical", security: "Security",
  operational: "Operational", compliance: "Compliance", performance: "Performance",
};

export interface StoryFormValue {
  id: string;
  title: string;
  description: string;
  type: StoryInput["type"];
  criteria: string;
}

export const emptyStory: StoryFormValue = {
  id: "", title: "", description: "", type: "story", criteria: "",
};

export function formFromStory(story: StoryInput): StoryFormValue {
  return { id: story.id, title: story.title, description: story.description, type: story.type, criteria: story.acceptance_criteria.join("\n") };
}

export function storyFromForm(form: StoryFormValue, generatedId: string): StoryInput {
  return {
    id: form.id.trim() || generatedId,
    title: form.title.trim(),
    description: form.description.trim(),
    type: form.type,
    acceptance_criteria: form.criteria.split(/\r?\n/).map((line) => line.trim()).filter(Boolean),
  };
}

export function factorsForNode(risk: RiskReport, id: string) {
  return risk.dimensions.flatMap((dimension) => dimension.factors
    .filter((factor) => factor.node_ids.includes(id))
    .map((factor) => ({ dimension: dimension.name, label: factor.label, points: factor.points })));
}

export function filterTests(tests: TestCase[], priorities: TestCase["priority"][], types: TestCase["type"][]) {
  return tests.filter((test) => (!priorities.length || priorities.includes(test.priority))
    && (!types.length || types.includes(test.type)));
}

export function sameNodes(a: string[], b: string[]) {
  return a.length === b.length && a.every((id) => b.includes(id));
}

/** Restore a preview only if it is still ours; a new Copilot selection wins. */
export function restoreHighlight(current: string[], preview: string[], previous: string[]) {
  return sameNodes(current, preview) ? previous : current;
}

/** Bar widths describe backend contributions on the fixed 0–100 scale. */
export function factorWidth(points: number) {
  return `${Math.max(0, Math.min(100, points))}%`;
}
