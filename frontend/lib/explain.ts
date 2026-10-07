// Plain-language explanations shown in tooltips. Every formula here mirrors the
// backend code (scoring.py, release.py, compliance.py, testing.py, sprint.py);
// change both together.

import type { StageSource } from "./types";

export const explain = {
  decision: "Decided by fixed rules in code, never by the model. No go if any risk dimension is 85 or more, if the highest risk is 70+ while test coverage is under 70%, or if a high-risk compliance framework meets card data or an authentication change. Go with conditions if the highest risk is 60+, any framework is at medium or high risk, or the story conflicts with another in the sprint. Otherwise go.",
  confidence: "100 − 0.45 × highest risk − 30 × (1 − test coverage) − 5 for each applicable framework at medium or high risk − 8 for each sprint conflict, kept between 0 and 100.",
  highestRisk: "The highest of the six risk dimensions. Each is the sum of named factors (see the Risk tab), capped at 100: under 40 is low, 40–69 medium, 70+ high.",
  impacted: "Components the change reaches in the architecture map: the services it changes directly, plus their callers and the systems they call, up to 3 hops away.",
  coverage: "Share of impacted components covered by at least one selected or new test.",
  blastRadius: "Built in code from the architecture map. Centre: services the story changes directly. Rings: components 1, 2 and 3 hops away, following both callers and callees. Colour is severity: criticality × 10, reduced with distance (×1, ×0.7, ×0.45, ×0.25); 60+ is high, 35–59 medium.",
  riskProfile: "Six dimensions scored 0–100. The model only supplies yes/no facts about the story (for example, “touches card data”); every point is computed in code from those facts and the architecture map, with weights in scoring_config.yaml.",
  baseline: "Every dimension starts from a small baseline before factors are added.",
  dimensions: {
    security: "Customer data, card data, authentication and external API changes from the story, plus the identity path (authentication-service, api-gateway) within one hop and the size of the blast radius.",
    compliance: "Regulated data (PII, card, financial, audit) on directly changed components scores in full; the same data one hop away scores less. A database schema change adds more.",
    technical: "Database schema changes, how many services change directly, how deep the dependencies go, and the type of change.",
    operational: "Criticality of the most critical changed service, downstream systems reached and deployment groups touched.",
    performance: "Whether the change sits on the transaction path (transaction-db, payment-service) or a channel path (api-gateway, mobile, web), and payment business-rule changes.",
    delivery: "How ambiguous the story is, how many services change directly and how many owner teams must coordinate.",
  } as Record<string, string>,
  effort: "Durations of the selected catalog tests plus 1.5 hours for each new test.",
  automation: "Catalog tests that are already automated, plus new API and regression tests.",
  priority: "P1 if the test covers a high-severity component or a risk dimension at 70+. P2 if it covers a medium-severity component. Otherwise P3. Set by rules in code.",
  testSource: "Catalog: chosen from the 60 existing tests whose services are impacted (up to 15). Generated: new tests written by the model for gaps, or from templates when no model answers.",
  complianceScore: "Each applicable framework starts at 100 and loses fixed points for each condition met; the overall score is the lowest of them. Under 60 is high risk, 60–79 medium, 80+ low. The rules are a screening heuristic in code, not legal advice. The model only writes the findings and recommendations.",
  frameworks: {
    GDPR: "Applies when a component holding personal data (PII) is changed or one hop away, or the story touches customer data.",
    "PCI DSS": "Applies when a component holding card data is changed or one hop away, or the story touches card data.",
    SOX: "Applies when a financial or audit component is changed or one hop away, or the story touches financial data.",
    "Internal Governance": "Applies when a directly changed component has criticality 8 or more, or the authentication flow changes.",
  } as Record<string, string>,
  complexity: "From the larger of deployment groups touched and services changed directly: 1 is low, 2–3 medium, 4 or more high.",
  triggeredRules: "Every release rule is evaluated in order, and every rule that fired is listed, so no blocker is hidden behind the first one.",
  plans: "Written by the model, or from templates without one, using the deployment order computed in code. The decision is fixed before any text is written.",
  sources: "Which engine produced each stage: a live model (provider and model name), plain code, a cached result, a saved demo result, or the built-in fallback when no model answered.",
  sampleData: "The analysis server couldn't be reached, or mock mode is on, so the page is showing saved demo results.",
  conflicts: "Found in code for every pair of stories: both change the same component or deployment group (deployment collision), the same database (shared database or schema contention), or the same external API (shared API change). Risk: 40 + 4 × criticality, +20 if either story is no go, +10 if either changes authentication.",
  chain: "Each model call tries the providers in order. A provider is passed over after a timeout, a rate limit, an error, or an answer that is cut off or isn't valid JSON. If none answers, the stage uses built-in templates, so a run always finishes.",
  kpis: {
    stories: "Stories analysed together in this sprint.",
    applications_impacted: "Distinct non-database components impacted by any story.",
    dependencies_impacted: "Distinct components reached indirectly (one hop or more away) by any story.",
    conflicts: "Story pairs that change the same component, database, API or deployment group.",
    compliance_issues: "Applicable compliance frameworks at high risk, counted across all stories.",
    testing_effort_hours: "Total test effort across all stories.",
    health_score: "100 − 0.35 × average overall risk − 6 per high-risk conflict − 3 per other conflict − 10 per no-go story − 2 per compliance issue, kept between 0 and 100.",
    release_confidence: "Average release confidence across the stories.",
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
