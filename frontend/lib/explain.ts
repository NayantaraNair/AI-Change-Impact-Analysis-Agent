// Plain-language explanations shown in tooltips. Every formula here mirrors the
// backend code (scoring.py, release.py, compliance.py, testing.py, sprint.py);
// change both together.

import type { StageSource } from "./types";

export const explain = {
  summary: "Built from the analysis, not written by AI. Each line is a count or a rule result.",
  decision: "Set by fixed rules, never by AI. No go: any risk 85+, or risk 70+ with test coverage under 70%, or high compliance risk on card data or login changes. Go with conditions: risk 60+, any compliance risk, or a sprint conflict.",
  confidence: "Starts at 100. Drops with the highest risk, missing test coverage, compliance risks and sprint conflicts.",
  highestRisk: "The worst of the six risk areas, 0 to 100. Under 40 low, 40–69 medium, 70+ high.",
  impacted: "Everything the change reaches, up to 3 steps away in the architecture map.",
  coverage: "Share of affected components with at least one test.",
  blastRadius: "Centre: what the story changes. Each ring: one step further away. Colour: how hard it is hit (high, medium, low). Built from the architecture map by code.",
  riskProfile: "Each area adds up named causes from the story and the graph. AI only says yes or no to facts like “touches card data”. Rules do the maths.",
  baseline: "Every area starts from a small base score.",
  dimensions: {
    security: "Customer data, card data, login changes and public API changes.",
    compliance: "Regulated data (personal, card, financial, audit) the change touches.",
    technical: "Database changes, how many services change, and how deep the dependencies go.",
    operational: "How critical the changed services are and how much depends on them.",
    performance: "Changes on the payment or app traffic paths.",
    delivery: "How vague the story is and how many teams must coordinate.",
  } as Record<string, string>,
  effort: "Existing test durations plus 1.5 hours per new test.",
  automation: "Tests that are or can be automated.",
  priority: "P1 must run: covers a high-impact component or a high risk. P2: medium impact. P3: the rest.",
  testSource: "Catalog: existing tests. Generated: new tests for gaps.",
  complianceScore: "Each framework starts at 100 and loses points per issue. Under 60 is high risk. A screening aid, not legal advice.",
  frameworks: {
    GDPR: "Personal data is changed or nearby, or the story touches customer data.",
    "PCI DSS": "Card data is changed or nearby, or the story touches card data.",
    SOX: "Financial or audit data is changed or nearby.",
    "Internal Governance": "A critical service changes, or the login flow changes.",
  } as Record<string, string>,
  complexity: "How many release groups and services are involved: 1 low, 2–3 medium, 4+ high.",
  triggeredRules: "Every rule that fired, so no blocker is hidden.",
  plans: "Written by AI (or templates) after the decision is fixed.",
  sources: "Which AI or rule produced each step.",
  sampleData: "Can't reach the server, so this shows saved demo results.",
  conflicts: "Two stories clash when they change the same service, database, API or release group. Risk rises with how critical it is and whether either story is blocked.",
  chain: "Tries each AI provider in order. Skips one that times out, errors or returns bad output. If none answers, rules and templates finish the job.",
  kpis: {
    stories: "Stories in this backlog.",
    applications_impacted: "Services affected by any story.",
    dependencies_impacted: "Components reached indirectly.",
    conflicts: "Story pairs that change the same thing.",
    compliance_issues: "High compliance risks across all stories.",
    testing_effort_hours: "Total test effort.",
    health_score: "100 minus points for risk, conflicts, blocked stories and compliance issues.",
    release_confidence: "Average release confidence.",
    high_risk: "Stories that are blocked or score 70+ overall.",
  } as Record<string, string>,
} as const;

export const sourceLabel: Record<string, string> = {
  llm: "Live model",
  deterministic: "Code",
  cache: "Cached",
  fixture: "Saved result",
  fallback: "Fallback",
};

export const sourceExplain: Record<string, string> = {
  llm: "Written by a live model.",
  deterministic: "Computed in code, with no model involved.",
  cache: "Reused from an earlier run with identical input.",
  fixture: "The saved demo result, built earlier with live models.",
  fallback: "No model answered, so built-in rules and templates were used.",
};

export const outcomeLabel: Record<string, string> = {
  running: "Waiting",
  ok: "Answered",
  timeout: "Timed out",
  rate_limited: "Rate limited",
  http_error: "Error",
  connection_error: "No connection",
  truncated: "Cut off",
  invalid_json: "Invalid JSON",
  schema_mismatch: "Wrong shape",
  empty: "Empty",
  skipped: "Skipped",
};

/** "tokenharbor:deepseek-v4.1-flash:free" -> { provider: "Token Harbor", model: "deepseek-v4.1-flash:free" } */
export function splitProvider(label: string | null | undefined): { provider: string; model: string } {
  if (!label) return { provider: "Unknown", model: "" };
  const [name, ...rest] = label.split(":");
  const provider = providerName(name);
  return { provider, model: rest.join(":") };
}

export function providerName(name: string): string {
  return ({ tokenharbor: "Token Harbor", openrouter: "OpenRouter" } as Record<string, string>)[name] ?? name;
}

/** Collapse provider labels used by stages into a classification for display. */
export function classifyProvider(label: string): StageSource {
  if (label === "deterministic" || label === "reused") return "deterministic";
  if (label === "fixture") return "fixture";
  if (label.endsWith("fallback") || label === "template" || label === "none") return "fallback";
  return "llm";
}
