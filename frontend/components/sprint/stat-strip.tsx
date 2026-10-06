import { formatNumber, severityClass } from "@/lib/format";
import type { SprintKpis } from "@/lib/types";
import { healthLevel, kpiDefinitions } from "./model";

export function SprintStatStrip({ kpis, previous }: { kpis: SprintKpis; previous: SprintKpis | null }) {
  return (
    <dl aria-label="Sprint statistics" className="flex items-center overflow-x-auto border-y border-line py-5 [&>div]:shrink-0 [&>div]:px-4 [&>div]:first:pl-0 [&>div]:not-first:border-l [&>div]:border-line">
      {kpiDefinitions.map((stat) => {
        const value = kpis[stat.key];
        const delta = previous ? Math.round((value - previous[stat.key]) * 10) / 10 : null;
        const positive = "positive" in stat;
        const unit = "unit" in stat ? stat.unit : "";
        return (
          <div key={stat.key}>
            <div className="flex items-baseline gap-2">
              <dt className="order-2 text-meta text-muted">{stat.label}</dt>
              <dd className={`text-hero font-semibold leading-tight tabular-nums ${positive ? severityClass[healthLevel(value)] : "text-text"}`}>
                {formatNumber(value)}{unit && <span className="ml-1 text-body font-normal text-muted">{unit}</span>}
              </dd>
            </div>
            {delta !== null && <p className="mt-1 text-meta text-muted tabular-nums" aria-label={`${stat.label}: ${delta > 0 ? "increased by" : delta < 0 ? "decreased by" : "unchanged,"} ${formatNumber(Math.abs(delta))}${unit ? ` ${unit}` : positive ? " points" : ""} versus previous run`}>
              {delta > 0 ? "+" : delta < 0 ? "−" : ""}{formatNumber(Math.abs(delta))}{unit ? ` ${unit}` : positive ? " pts" : ""} vs previous run
            </p>}
          </div>
        );
      })}
    </dl>
  );
}
