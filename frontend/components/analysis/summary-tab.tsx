import { formatDate, formatDuration } from "@/lib/format";
import type { StoryAnalysis } from "@/lib/types";
import { STAGES } from "./model";
import { NodeLinks } from "./node-links";
import { InfoTip } from "@/components/ui/info-tip";
import { explain } from "@/lib/explain";

const stageLabel: Record<string, string> = { requirement: "Requirement", dependency: "Dependencies", scoring: "Scoring", testing: "Tests", compliance: "Compliance", release: "Release" };

export function SummaryTab({ analysis }: { analysis: StoryAnalysis }) {
  const { requirement, providers_used } = analysis;
  return (
    <section aria-label="Analysis summary" className="space-y-6 py-5">
      <div className="grid gap-6 md:grid-cols-2">
        <div className="space-y-2"><h2>Business summary</h2><p className="text-body">{requirement.business_summary}</p><p className="text-dense text-muted">Domain: {requirement.business_domain}</p></div>
        <div className="space-y-2"><h2>Technical summary</h2><p className="text-body">{requirement.technical_summary}</p><p className="text-dense text-muted">Engineering scope: {requirement.engineering_scope}</p></div>
      </div>
      <div className="space-y-2"><h3>Affected capabilities</h3><ul className="flex flex-wrap gap-2">{requirement.affected_capabilities.map((item) => <li key={item} className="rounded border border-line px-2 py-1 text-dense">{item}</li>)}</ul>{!requirement.affected_capabilities.length && <p className="text-dense text-muted">No capabilities identified.</p>}</div>
      <div className="space-y-2"><h3>Directly changed services</h3><NodeLinks ids={requirement.affected_services} nodes={analysis.graph.nodes} /></div>
      <div className="border-t border-line pt-4">
        <h3 className="flex items-center gap-1.5 text-body font-medium">Analysis sources <InfoTip label="analysis sources">{explain.sources}</InfoTip></h3>
        <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-2 text-meta text-muted">
          {STAGES.map(({ key }) => <div key={key} className="flex gap-2"><dt>{stageLabel[key]}</dt><dd>{providers_used[key] ?? "Not reported"}</dd></div>)}
        </dl>
        <p className="mt-3 text-meta text-muted">{analysis.story.id} · {formatDate(analysis.created_at)} · {formatDuration(analysis.duration_ms)}</p>
      </div>
    </section>
  );
}
