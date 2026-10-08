import { InfoTip } from "@/components/ui/info-tip";
import { explain } from "@/lib/explain";
import { decisionClass, decisionLabel, formatNumber } from "@/lib/format";
import type { ReleaseAssessment } from "@/lib/types";
import { plainRule, shorten } from "./impact-summary";

function Steps({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <details open className="group border-t border-line py-3">
      <summary className="cursor-pointer list-none text-dense font-medium"><span aria-hidden="true" className="mr-2 inline-block text-muted transition-transform duration-150 group-open:rotate-90">›</span>{title}</summary>
      <ol className="mt-3 list-decimal space-y-1.5 pl-9 text-dense">{items.slice(0, 3).map((item, index) => <li key={index}>{item}</li>)}</ol>
    </details>
  );
}

/** Decision, why, and what to do first. Full plans stay folded away. */
export function ReleaseTab({ release }: { release: ReleaseAssessment }) {
  const reasons = release.triggered_rules.filter((rule) => !rule.startsWith("GO:")).slice(0, 3);
  const todo = release.conditions.slice(0, 3);
  return (
    <section aria-label="Release" className="space-y-5 py-5">
      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2">
        <h2 className={`flex items-center gap-2 text-title numeral ${decisionClass[release.decision]}`}>{decisionLabel[release.decision]}<InfoTip label="the release decision">{explain.decision}</InfoTip></h2>
        <p className="flex items-center gap-1 text-dense text-muted"><span className="text-text tabular-nums">{formatNumber(release.confidence)}%</span> confidence <InfoTip label="release confidence">{explain.confidence}</InfoTip></p>
        <p className="flex items-center gap-1 text-dense text-muted"><span className="text-text capitalize">{release.complexity}</span> complexity <InfoTip label="complexity">{explain.complexity}</InfoTip></p>
      </div>
      <div className="grid gap-6 md:grid-cols-2">
        <div>
          <h3 className="text-body font-medium">Why</h3>
          {reasons.length ? <ul className="mt-2 list-disc space-y-1 pl-5 text-dense">{reasons.map((rule, index) => <li key={index}>{plainRule(rule)}</li>)}</ul> : <p className="mt-2 text-dense">No release rule fired.</p>}
          {release.triggered_rules.length > reasons.length + 1 && <p className="mt-1 text-meta text-muted">+{release.triggered_rules.length - reasons.length} more rules</p>}
        </div>
        <div>
          <h3 className="text-body font-medium">Before release</h3>
          {todo.length ? <ul className="mt-2 list-disc space-y-1 pl-5 text-dense">{todo.map((item, index) => <li key={index}>{shorten(item, 120)}</li>)}</ul> : <p className="mt-2 text-dense">Nothing extra.</p>}
          {release.conditions.length > todo.length && <p className="mt-1 text-meta text-muted">+{release.conditions.length - todo.length} more</p>}
        </div>
      </div>
      <div>
        <Steps title="Rollback plan" items={release.rollback_plan} />
        <Steps title="Deployment steps" items={release.deployment_notes} />
      </div>
    </section>
  );
}
