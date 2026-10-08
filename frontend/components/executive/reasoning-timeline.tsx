import { Bot, Calculator } from "lucide-react";
import { formatElapsed } from "@/components/run/model";
import { classifyProvider, splitProvider } from "@/lib/explain";
import type { Run, StoryAnalysis } from "@/lib/types";
import { cn } from "@/lib/utils";

type Step = { stage: string; title: string; detail: string; by: "ai" | "rules" };

function steps(analysis: StoryAnalysis): Step[] {
  const { requirement, graph, risk, tests, compliance, release } = analysis;
  const changed = graph.nodes.filter((node) => node.hop === 0).map((node) => node.label);
  const flags = [
    requirement.touches_customer_data && "customer data",
    requirement.touches_card_data && "card data",
    requirement.touches_financial_data && "financial data",
    requirement.changes_auth_flow && "login flow",
    requirement.changes_external_api_contract && "public API",
    requirement.changes_db_schema && "database schema",
  ].filter(Boolean);
  const highest = risk.dimensions.find((dimension) => dimension.name === risk.highest);
  const frameworks = compliance.frameworks.filter((framework) => framework.applicable);
  const p1 = tests.tests.filter((test) => test.priority === "P1").length;
  const reason = release.triggered_rules.find((rule) => !rule.startsWith("GO:"))?.replace(/^\w+:\s*/, "");
  return [
    { stage: "requirement", by: "ai", title: "Read the change",
      detail: `A ${requirement.change_type.replace(/_/g, " ")} to ${changed.join(", ") || "no catalog system"}${flags.length ? `; touches ${flags.join(", ")}` : ""}.` },
    { stage: "dependency", by: "rules", title: "Mapped what it reaches",
      detail: `${risk.change_size[0].toUpperCase()}${risk.change_size.slice(1)} change: ${graph.impacted_services.length} systems affected.` },
    { stage: "scoring", by: "rules", title: "Scored the risk",
      detail: `Overall ${risk.overall}/100; highest is ${highest?.name ?? risk.highest} at ${highest?.score ?? "–"}.` },
    { stage: "testing", by: "ai", title: "Planned the tests",
      detail: `${tests.tests.length} tests, ${p1} must-run, ${Math.round(tests.coverage_estimate * 100)}% of affected systems covered.` },
    { stage: "compliance", by: "ai", title: "Checked compliance",
      detail: frameworks.length ? frameworks.map((framework) => `${framework.framework} ${framework.risk_level}`).join(", ") + "." : "No framework applies." },
    { stage: "release", by: "rules", title: "Decided readiness",
      detail: `${release.decision.replace(/_/g, " ")} at ${release.confidence}% confidence${reason ? `: ${reason}` : ""}.` },
  ];
}

/** How the AI and the rules reached this result, step by step. */
export function ReasoningTimeline({ analysis, run }: { analysis: StoryAnalysis; run: Run | null }) {
  return (
    <ol className="relative space-y-4 border-l border-line pl-6">
      {steps(analysis).map((step) => {
        const label = analysis.providers_used[step.stage];
        const ai = label ? classifyProvider(label) === "llm" : step.by === "ai";
        const tracked = run?.stages.find((item) => item.stage === step.stage && item.story_id === analysis.story.id);
        const Icon = ai ? Bot : Calculator;
        return (
          <li key={step.stage} className="relative">
            <span className={cn("absolute top-0.5 -left-[2.05rem] flex size-6 items-center justify-center rounded-full border bg-surface", ai ? "border-model/50 text-model" : "border-line text-muted")}>
              <Icon aria-hidden="true" className="size-3.5" />
            </span>
            <p className="flex flex-wrap items-baseline gap-x-2 text-dense">
              <span className="font-medium">{step.title}</span>
              <span className={cn("text-meta", ai ? "text-model" : "text-muted")}>{ai ? `AI · ${splitProvider(label).provider}` : "Rules"}</span>
              {tracked?.elapsed_ms ? <span className="text-meta text-muted tabular-nums">{formatElapsed(tracked.elapsed_ms)}</span> : null}
            </p>
            <p className="mt-0.5 text-dense text-muted">{step.detail}</p>
          </li>
        );
      })}
    </ol>
  );
}
