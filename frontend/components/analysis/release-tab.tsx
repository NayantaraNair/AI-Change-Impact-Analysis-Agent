import { decisionClass, decisionLabel, formatNumber } from "@/lib/format";
import type { ReleaseAssessment } from "@/lib/types";
import { InfoTip } from "@/components/ui/info-tip";
import { explain } from "@/lib/explain";

function ReleaseList({ title, items, ordered = false, empty, tip }: { title: string; items: string[]; ordered?: boolean; empty: string; tip?: string }) {
  const List = ordered ? "ol" : "ul";
  return (
    <section className="space-y-2">
      <h3 className="flex items-center gap-1.5">{title}{tip && <InfoTip label={title.toLowerCase()}>{tip}</InfoTip>}</h3>
      {items.length ? <List className={`${ordered ? "list-decimal" : "list-disc"} space-y-2 pl-5 text-body`}>{items.map((item, index) => <li key={index}>{item}</li>)}</List> : <p className="text-body text-muted">{empty}</p>}
    </section>
  );
}

export function ReleaseTab({ release }: { release: ReleaseAssessment }) {
  return (
    <section aria-label="Release assessment" className="space-y-6 py-5">
      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2">
        <h2 className={`flex items-center gap-2 text-hero font-semibold ${decisionClass[release.decision]}`}>{decisionLabel[release.decision]}<InfoTip label="the release decision">{explain.decision}</InfoTip></h2>
        <p><span className="text-title font-semibold tabular-nums">{formatNumber(release.confidence)}%</span><span className="ml-2 text-meta text-muted">release confidence</span> <InfoTip label="release confidence">{explain.confidence}</InfoTip></p>
        <p className="flex items-center gap-1 text-dense text-muted">Deployment complexity: {release.complexity} <InfoTip label="complexity">{explain.complexity}</InfoTip></p>
      </div>
      <div className="grid gap-6 md:grid-cols-2">
        <ReleaseList title="Triggered rules" items={release.triggered_rules} empty="No release rules were triggered." tip={explain.triggeredRules} />
        <ReleaseList title="Conditions" items={release.conditions} empty="No release conditions were returned." />
      </div>
      <div className="grid gap-6 border-t border-line pt-6 md:grid-cols-2">
        <ReleaseList title="Rollback plan" tip={explain.plans} items={release.rollback_plan} ordered empty="No rollback plan was returned. Confirm a plan with the service owner before release." />
        <ReleaseList title="Deployment notes" items={release.deployment_notes} ordered empty="No deployment notes were returned." />
      </div>
    </section>
  );
}
