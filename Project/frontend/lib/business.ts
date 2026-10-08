// Business view of an analysis, computed by rules from the engineering result.
// Every value here is derived from data already in StoryAnalysis, so the
// executive portal never shows a number the engineering view cannot explain.

import type { Severity, SprintAnalysis, StoryAnalysis } from "./types";

export type Level = "low" | "medium" | "high";

const CHANNELS = new Set(["mobile-banking", "web-banking", "atm", "branch-portal"]);
const SIZE_SCALE = { small: 0.6, medium: 0.85, large: 1 } as const;

export const levelWord: Record<Level, string> = { low: "Low", medium: "Medium", high: "High" };

export function riskLevel(score: number): Level {
  return score >= 70 ? "high" : score >= 40 ? "medium" : "low";
}

/** How much the business depends on what changes: criticality of changed services, scaled by change size. */
export function businessImpact(analysis: StoryAnalysis): Level {
  const changed = analysis.graph.nodes.filter((node) => node.hop === 0);
  const criticality = Math.max(0, ...changed.map((node) => node.criticality));
  const score = criticality * 10 * SIZE_SCALE[analysis.risk.change_size];
  return score >= 70 ? "high" : score >= 45 ? "medium" : "low";
}

/** Customers reached: a changed customer-facing channel is high; customer data or a channel one step away is medium. */
export function affectedCustomers(analysis: StoryAnalysis): Level {
  const nodes = analysis.graph.nodes.filter((node) => node.hop !== null);
  if (nodes.some((node) => node.hop === 0 && CHANNELS.has(node.id))) return "high";
  if (analysis.requirement.touches_customer_data || nodes.some((node) => CHANNELS.has(node.id))) return "medium";
  return "low";
}

export function affectedSystems(analysis: StoryAnalysis): string[] {
  return analysis.graph.nodes
    .filter((node) => node.hop !== null)
    .sort((a, b) => (a.hop ?? 9) - (b.hop ?? 9) || b.criticality - a.criticality)
    .map((node) => node.label);
}

export function complianceImpact(analysis: StoryAnalysis): string[] {
  return analysis.compliance.frameworks
    .filter((framework) => framework.applicable && framework.risk_level && framework.risk_level !== "low")
    .map((framework) => framework.framework);
}

export interface Portfolio {
  stories: number;
  systems: number;
  riskScore: number;
  riskLevel: Level;
  compliance: string[];
  confidence: number;
}

export function portfolioKpis(analyses: StoryAnalysis[]): Portfolio {
  const systems = new Set(analyses.flatMap((analysis) => analysis.graph.nodes.filter((node) => node.hop !== null).map((node) => node.id)));
  const riskScore = analyses.length ? Math.round(analyses.reduce((sum, analysis) => sum + analysis.risk.overall, 0) / analyses.length) : 0;
  const confidence = analyses.length ? Math.round(analyses.reduce((sum, analysis) => sum + analysis.release.confidence, 0) / analyses.length) : 0;
  return {
    stories: analyses.length,
    systems: systems.size,
    riskScore,
    riskLevel: riskLevel(riskScore),
    compliance: [...new Set(analyses.flatMap(complianceImpact))],
    confidence,
  };
}

/** Rows are changes, columns are the systems they touch most; cells are impact severity. */
export function heatmap(analyses: StoryAnalysis[], maxColumns = 10) {
  const reach = new Map<string, { label: string; count: number; weight: number }>();
  for (const analysis of analyses) {
    for (const node of analysis.graph.nodes) {
      if (node.hop === null) continue;
      const entry = reach.get(node.id) ?? { label: node.label, count: 0, weight: 0 };
      entry.count += 1;
      entry.weight += node.severity === "high" ? 3 : node.severity === "medium" ? 2 : 1;
      reach.set(node.id, entry);
    }
  }
  const columns = [...reach].sort((a, b) => b[1].count - a[1].count || b[1].weight - a[1].weight || a[1].label.localeCompare(b[1].label))
    .slice(0, maxColumns).map(([id, entry]) => ({ id, label: entry.label }));
  const rows = analyses.map((analysis) => {
    const byId = new Map(analysis.graph.nodes.map((node) => [node.id, node]));
    return {
      id: analysis.story.id,
      title: analysis.story.title,
      cells: columns.map((column) => {
        const node = byId.get(column.id);
        return node && node.hop !== null ? { severity: node.severity as Severity | null, changed: node.hop === 0 } : null;
      }),
    };
  });
  return { columns, rows };
}

export interface ConflictPair {
  a: StoryAnalysis;
  b: StoryAnalysis;
  score: number;
  shared: string[];
  sharedChanged: string[];
  recommendation: string;
  why: string;
}

/**
 * Conflict % for a pair of stories: 70% weight on how much of what they change
 * is the same (shared changed systems over the smaller change), 30% on how much
 * of what they reach overlaps. Two stories that change the same services score
 * near 100%; stories that only touch the same neighbours score low.
 */
export function conflictPairs(sprint: SprintAnalysis, minimum = 25): ConflictPair[] {
  const pairs: ConflictPair[] = [];
  const stories = sprint.stories;
  for (let i = 0; i < stories.length; i++) {
    for (let j = i + 1; j < stories.length; j++) {
      const a = stories[i];
      const b = stories[j];
      const changedA = new Set(a.graph.nodes.filter((node) => node.hop === 0).map((node) => node.id));
      const changedB = new Set(b.graph.nodes.filter((node) => node.hop === 0).map((node) => node.id));
      const reachA = new Set(a.graph.nodes.filter((node) => node.hop !== null).map((node) => node.id));
      const reachB = new Set(b.graph.nodes.filter((node) => node.hop !== null).map((node) => node.id));
      const sharedChangedIds = [...changedA].filter((id) => changedB.has(id));
      const sharedReach = [...reachA].filter((id) => reachB.has(id));
      const unionReach = new Set([...reachA, ...reachB]).size;
      const smaller = Math.max(1, Math.min(changedA.size, changedB.size));
      const directOverlap = sharedChangedIds.length / smaller;
      const reachOverlap = unionReach ? sharedReach.length / unionReach : 0;
      const engine = sprint.conflicts.filter((conflict) =>
        (conflict.story_a === a.story.id && conflict.story_b === b.story.id) || (conflict.story_a === b.story.id && conflict.story_b === a.story.id));
      // A release-group clash the engine found keeps the pair visible even with little overlap.
      let score = Math.round(100 * (0.7 * directOverlap + 0.3 * reachOverlap));
      if (engine.length) score = Math.max(score, 40);
      if (score < minimum) continue;
      const labels = new Map([...a.graph.nodes, ...b.graph.nodes].map((node) => [node.id, node.label]));
      const sharedChanged = sharedChangedIds.map((id) => labels.get(id) ?? id);
      const engineShared = engine.map((conflict) => labels.get(conflict.shared_component) ?? conflict.shared_component);
      const shared = [...new Set([...sharedChanged, ...engineShared])];
      const first = engine.find((conflict) => conflict.kind === "deployment_collision");
      const recommendation = score >= 80
        ? "Merge sprint planning: plan, build and test these together as one change."
        : first
          ? `Sequence releases: ship ${first.story_b} first, then ${first.story_a}.`
          : score >= 50
            ? "Coordinate: one owner, one shared test cycle."
            : "Low overlap: run a shared regression on the common systems.";
      const why = `${sharedChangedIds.length} of ${smaller} changed system${smaller === 1 ? "" : "s"} shared, ${sharedReach.length} of ${unionReach} reached systems overlap.`;
      pairs.push({ a, b, score, shared: shared.length ? shared : sharedReach.slice(0, 3).map((id) => labels.get(id) ?? id), sharedChanged, recommendation, why });
    }
  }
  return pairs.sort((x, y) => y.score - x.score);
}

export const levelTone: Record<Level, string> = {
  low: "text-impact-low",
  medium: "text-impact-med",
  high: "text-impact-high",
};

export const levelChip: Record<Level, string> = {
  low: "border-impact-low/50 bg-impact-low/10 text-impact-low",
  medium: "border-impact-med/50 bg-impact-med/10 text-impact-med",
  high: "border-impact-high/50 bg-impact-high/10 text-impact-high",
};
