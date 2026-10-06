import type { StoryAnalysis } from "@/lib/types";
import { decisionClass, decisionLabel, formatNumber, formatPercent, severityClass } from "@/lib/format";
import { dimensionLabel } from "./model";

export function StatStrip({ analysis }: { analysis: StoryAnalysis }) {
  const { release, risk, graph, tests } = analysis;
  const highest = risk.dimensions.find((dimension) => dimension.name === risk.highest);
  return (
    <dl aria-label="Analysis statistics" className="flex items-center overflow-x-auto border-y border-line py-5 [&>div]:flex [&>div]:items-baseline [&>div]:gap-2 [&>div]:shrink-0 [&>div]:px-3 [&>div]:first:pl-0 [&>div]:not-first:border-l [&>div]:border-line">
      <div className="max-w-full">
        <dt className="order-2 text-meta text-muted">Decision</dt>
        <dd className={`text-hero leading-tight font-semibold tabular-nums ${decisionClass[release.decision]}`}>{decisionLabel[release.decision]}</dd>
      </div>
      <div>
        <dt className="order-2 text-meta text-muted">Confidence</dt>
        <dd className="text-hero leading-tight font-semibold tabular-nums">{formatNumber(release.confidence)}%</dd>
      </div>
      <div>
        <dt className="order-2 text-meta text-muted">Highest risk<span className="block">{dimensionLabel[risk.highest] ?? risk.highest}</span></dt>
        <dd className={`text-hero leading-tight font-semibold tabular-nums ${highest ? severityClass[highest.level] : "text-muted"}`}>{highest ? formatNumber(highest.score) : "–"}</dd>
      </div>
      <div>
        <dt className="order-2 text-meta text-muted">Impacted services</dt>
        <dd className="text-hero leading-tight font-semibold tabular-nums">{formatNumber(graph.impacted_services.length)}</dd>
      </div>
      <div>
        <dt className="order-2 text-meta text-muted">Coverage</dt>
        <dd className="text-hero leading-tight font-semibold tabular-nums">{formatPercent(tests.coverage_estimate)}</dd>
      </div>
    </dl>
  );
}
