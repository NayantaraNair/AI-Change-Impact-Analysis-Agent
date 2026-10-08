import type { ReactNode } from "react";
import { InfoTip } from "@/components/ui/info-tip";
import { explain } from "@/lib/explain";
import { formatHours, formatPercent } from "@/lib/format";
import type { StoryAnalysis } from "@/lib/types";
import { dimensionLabel } from "./model";

/** Release rules read as plain sentences: "NO_GO: security risk is 100 (>= 85)" -> "Security risk is 100 (limit 85)". */
export function plainRule(rule: string): string {
  const text = rule.replace(/^(NO_GO|GO_WITH_CONDITIONS|GO):\s*/, "").replace(/\(>=\s*(\d+)\)/, "(limit $1)").replace(/\(<\s*(\d+)%\)/, "(needs $1%)");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function shorten(text: string, max = 110): string {
  return text.length <= max ? text : `${text.slice(0, max - 1).replace(/[\s,;:]+\S*$/, "")}…`;
}

function list(items: string[], max = 4): string {
  if (items.length <= max) return items.join(", ");
  return `${items.slice(0, max).join(", ")} +${items.length - max} more`;
}

function Line({ label, children }: { label: string; children: ReactNode }) {
  return (
    <li className="grid grid-cols-[7.5rem_minmax(0,1fr)] gap-x-4 py-2">
      <span className="text-dense text-muted">{label}</span>
      <span className="text-body">{children}</span>
    </li>
  );
}

/** The whole analysis in seven short lines, for planning a sprint. */
export function ImpactSummary({ analysis }: { analysis: StoryAnalysis }) {
  const { graph, risk, tests, compliance, release } = analysis;
  const changed = graph.nodes.filter((node) => node.hop === 0).map((node) => node.label);
  const affected = graph.nodes.filter((node) => node.hop !== null);
  const highImpact = affected.filter((node) => node.severity === "high").length;
  const teams = [...new Set(graph.nodes.filter((node) => node.hop !== null && node.hop <= 1).map((node) => node.owner_team))].sort();
  const ranked = [...risk.dimensions].sort((a, b) => b.score - a.score);
  const high = ranked.filter((dimension) => dimension.score >= 70);
  const mainRisks = (high.length ? high : ranked.slice(0, 1)).slice(0, 3);
  const frameworks = compliance.frameworks.filter((item) => item.applicable && item.risk_level !== "low");
  const p1 = tests.tests.filter((test) => test.priority === "P1").length;
  const blockers = release.triggered_rules.filter((rule) => rule.startsWith("NO_GO"));

  return (
    <section aria-labelledby="impact-summary-heading" className="py-4">
      <h2 id="impact-summary-heading" className="flex items-center gap-1.5">Impact summary <InfoTip label="the impact summary">{explain.summary}</InfoTip></h2>
      <ul className="mt-2 divide-y divide-line border-y border-line">
        <Line label="Changes">{list(changed) || "No catalog services matched. Add more detail to the story."}</Line>
        <Line label="Affects">{affected.length} components{highImpact ? `, ${highImpact} at high impact` : ""} ({risk.change_size} change)</Line>
        <Line label="Teams">{list(teams, 5) || "None"}</Line>
        <Line label="Main risks">
          {mainRisks.map((dimension, index) => (
            <span key={dimension.name}>{index > 0 && ", "}{dimensionLabel[dimension.name]} <span className={dimension.level === "high" ? "text-impact-high" : dimension.level === "medium" ? "text-impact-med" : "text-impact-low"}>{dimension.score}</span></span>
          ))}
        </Line>
        <Line label="Compliance">{frameworks.length ? list(frameworks.map((item) => `${item.framework} (${item.risk_level})`)) : "No review needed"}</Line>
        <Line label="Tests">{Math.min(5, tests.tests.length)} key tests of {tests.tests.length} ({p1} must-run) · {formatHours(tests.effort_hours)} · {formatPercent(tests.coverage_estimate)} coverage</Line>
        <Line label="Release">
          {release.decision === "NO_GO" ? `Blocked. ${shorten(plainRule(blockers[0] ?? "Blocking rule fired"))}`
            : release.decision === "GO_WITH_CONDITIONS" ? `Go once: ${shorten(release.conditions[0] ?? "conditions are met")}`
            : "Ready to release."}
        </Line>
      </ul>
    </section>
  );
}
