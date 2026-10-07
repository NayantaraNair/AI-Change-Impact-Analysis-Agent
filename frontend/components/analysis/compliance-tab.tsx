"use client";

import { InfoTip } from "@/components/ui/info-tip";
import { explain } from "@/lib/explain";
import { formatNumber, severityClass } from "@/lib/format";
import type { ComplianceReport, GraphNode } from "@/lib/types";
import { NodeLinks } from "./node-links";

export function ComplianceTab({ report, nodes }: { report: ComplianceReport; nodes: GraphNode[] }) {
  const applicable = report.frameworks.filter((framework) => framework.applicable);
  const notNeeded = report.frameworks.filter((framework) => !framework.applicable).map((framework) => framework.framework);
  return (
    <section aria-label="Compliance" className="space-y-4 py-5">
      <div className="flex flex-wrap items-baseline gap-4">
        <h2 className="flex items-center gap-1.5">Compliance <InfoTip label="compliance scoring">{explain.complianceScore}</InfoTip></h2>
        <p><span className="text-title numeral">{formatNumber(report.overall_score)}</span><span className="ml-2 text-meta text-muted">/ 100, higher is safer</span></p>
      </div>
      {applicable.length ? (
        <div className="divide-y divide-line border-y border-line">
          {applicable.map((framework) => (
            <details key={framework.framework} className="group">
              <summary className="grid cursor-pointer list-none grid-cols-[minmax(0,1fr)_90px_80px] items-center gap-4 py-3 text-dense">
                <span className="font-medium"><span aria-hidden="true" className="mr-2 inline-block text-muted transition-transform duration-150 group-open:rotate-90">›</span>{framework.framework}</span>
                <span className={framework.risk_level ? severityClass[framework.risk_level] : "text-muted"}>{framework.risk_level ? `${framework.risk_level[0].toUpperCase()}${framework.risk_level.slice(1)} risk` : "–"}</span>
                <span className="text-right tabular-nums text-muted">{framework.score ?? "–"} / 100</span>
              </summary>
              <div className="space-y-3 pb-4 pl-5 text-dense">
                <p className="text-muted">Applies because {framework.reason.charAt(0).toLowerCase() + framework.reason.slice(1)}</p>
                {framework.findings.length > 0 && <ul className="space-y-2">{framework.findings.slice(0, 3).map((finding, index) => <li key={index} className="space-y-1"><p>{finding.text}</p>{finding.node_ids.length > 0 && <NodeLinks ids={finding.node_ids} nodes={nodes} />}</li>)}</ul>}
                {framework.recommendations.length > 0 && <p><span className="text-muted">Do: </span>{framework.recommendations.slice(0, 2).join(" ")}</p>}
              </div>
            </details>
          ))}
        </div>
      ) : <p className="text-body">No compliance review needed.</p>}
      {notNeeded.length > 0 && <p className="text-meta text-muted">Not needed: {notNeeded.join(", ")}</p>}
    </section>
  );
}
