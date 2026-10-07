import { InfoTip } from "@/components/ui/info-tip";
import { explain } from "@/lib/explain";
import { formatHours, formatNumber, severityClass } from "@/lib/format";
import type { SprintKpis } from "@/lib/types";
import { healthLevel } from "./model";

export function SprintStatStrip({ kpis }: { kpis: SprintKpis }) {
  const stats = [
    { key: "stories", label: "Stories", value: formatNumber(kpis.stories) },
    { key: "conflicts", label: "Clashes", value: formatNumber(kpis.conflicts), tone: kpis.conflicts ? "text-impact-med" : "" },
    { key: "high_risk", label: "High-risk stories", value: formatNumber(kpis.high_risk_stories.length), tone: kpis.high_risk_stories.length ? "text-impact-high" : "" },
    { key: "testing_effort_hours", label: "Test effort", value: formatHours(kpis.testing_effort_hours) },
    { key: "health_score", label: "Health", value: `${formatNumber(kpis.health_score)}/100`, tone: severityClass[healthLevel(kpis.health_score)] },
  ];
  return (
    <div className="border-y border-line py-5">
      <dl aria-label="Sprint numbers" className="readouts -mx-5 gap-y-5">
        {stats.map((stat) => (
          <div key={stat.key} className="flex items-baseline gap-2.5">
            <dt className="order-2 flex items-center gap-1 text-meta text-muted">{stat.label}<InfoTip label={stat.label.toLowerCase()} side="bottom">{explain.kpis[stat.key]}</InfoTip></dt>
            <dd className={`text-hero numeral ${stat.tone ?? ""}`}>{stat.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
