import type { ReactNode } from "react";
import { InfoTip } from "@/components/ui/info-tip";
import type { StoryAnalysis } from "@/lib/types";
import { explain } from "@/lib/explain";
import { decisionClass, decisionLabel, formatNumber, formatPercent, severityClass } from "@/lib/format";
import { dimensionLabel } from "./model";

function Stat({ label, tip, detail, children, className = "" }: { label: string; tip: string; detail?: string; children: ReactNode; className?: string }) {
  return (
    <div className={`flex items-baseline gap-2.5 ${className}`}>
      <dt className="order-2 flex items-start gap-1 text-meta text-muted">
        <span>{label}{detail && <span className="block">{detail}</span>}</span>
        <InfoTip label={label.toLowerCase()} side="bottom">{tip}</InfoTip>
      </dt>
      {children}
    </div>
  );
}

export function StatStrip({ analysis }: { analysis: StoryAnalysis }) {
  const { release, risk, graph, tests } = analysis;
  const highest = risk.dimensions.find((dimension) => dimension.name === risk.highest);
  return (
    <div className="border-y border-line py-5">
    <dl aria-label="Analysis statistics" className="readouts -mx-5">
      <Stat label="Decision" tip={explain.decision} className="max-w-full">
        <dd className={`text-hero numeral ${decisionClass[release.decision]}`}>{decisionLabel[release.decision]}</dd>
      </Stat>
      <Stat label="Confidence" tip={explain.confidence}>
        <dd className="text-hero numeral">{formatNumber(release.confidence)}%</dd>
      </Stat>
      <Stat label="Highest risk" detail={dimensionLabel[risk.highest] ?? risk.highest} tip={explain.highestRisk}>
        <dd className={`text-hero numeral ${highest ? severityClass[highest.level] : "text-muted"}`}>{highest ? formatNumber(highest.score) : "–"}</dd>
      </Stat>
      <Stat label="Impacted services" tip={explain.impacted}>
        <dd className="text-hero numeral">{formatNumber(graph.impacted_services.length)}</dd>
      </Stat>
      <Stat label="Coverage" tip={explain.coverage}>
        <dd className="text-hero numeral">{formatPercent(tests.coverage_estimate)}</dd>
      </Stat>
    </dl>
    </div>
  );
}
