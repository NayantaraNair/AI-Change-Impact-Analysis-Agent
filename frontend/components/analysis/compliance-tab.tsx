"use client";

import { formatNumber, severityClass } from "@/lib/format";
import type { ComplianceReport, GraphNode } from "@/lib/types";
import { NodeLinks } from "./node-links";

export function ComplianceTab({ report, nodes }: { report: ComplianceReport; nodes: GraphNode[] }) {
  return (
    <section aria-label="Compliance assessments" className="space-y-4 py-5">
      <div className="flex flex-wrap items-baseline gap-4">
        <h2>Compliance check</h2>
        <p><span className="text-title font-semibold tabular-nums">{formatNumber(report.overall_score)}</span><span className="ml-2 text-meta text-muted">/ 100 · higher means more compliant</span></p>
      </div>
      <p className="text-body text-muted">{report.summary}</p>
      <div className="divide-y divide-line border-y border-line">
        {report.frameworks.map((framework) => (
          <details key={framework.framework} className="group">
            <summary className="grid cursor-pointer list-none grid-cols-[minmax(0,1fr)_120px_100px_70px] items-center gap-4 py-4 text-dense focus-visible:rounded-md">
              <span className="font-medium text-azure"><span aria-hidden="true" className="mr-2 inline-block transition-transform duration-150 group-open:rotate-90">›</span>{framework.framework}</span>
              <span className="text-muted">{framework.applicable ? "Applicable" : "Not applicable"}</span>
              <span className={framework.risk_level ? severityClass[framework.risk_level] : "text-muted"}>{framework.risk_level ? `${framework.risk_level[0].toUpperCase()}${framework.risk_level.slice(1)} risk` : "No risk score"}</span>
              <span className={`text-right font-semibold tabular-nums ${framework.risk_level ? severityClass[framework.risk_level] : "text-muted"}`}>{framework.score === null ? "–" : `${formatNumber(framework.score)} / 100`}</span>
            </summary>
            <div className="space-y-4 pb-5 pl-5 text-body">
              <p className="text-muted">{framework.reason}</p>
              <div>
                <h3 className="mb-2 text-body font-medium">Findings</h3>
                {framework.findings.length ? <ul className="space-y-3">{framework.findings.map((finding, index) => <li key={index} className="space-y-1"><p>{finding.text}</p>{finding.node_ids.length > 0 && <NodeLinks ids={finding.node_ids} nodes={nodes} />}</li>)}</ul> : <p className="text-dense text-muted">No findings reported.</p>}
              </div>
              <div>
                <h3 className="mb-2 text-body font-medium">Recommendations</h3>
                {framework.recommendations.length ? <ul className="list-disc space-y-1 pl-5">{framework.recommendations.map((item, index) => <li key={index}>{item}</li>)}</ul> : <p className="text-dense text-muted">No recommendations reported.</p>}
              </div>
            </div>
          </details>
        ))}
      </div>
    </section>
  );
}
