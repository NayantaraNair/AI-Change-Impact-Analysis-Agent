"use client";

import { ArrowLeftRight } from "lucide-react";
import { InfoTip } from "@/components/ui/info-tip";
import {
  affectedCustomers, affectedSystems, businessImpact, conflictPairs, heatmap, levelChip, levelTone,
  levelWord, portfolioKpis, riskLevel, type Level,
} from "@/lib/business";
import type { SprintAnalysis, StoryAnalysis } from "@/lib/types";
import { cn } from "@/lib/utils";

export const tips = {
  stories: "Changes analysed in this view.",
  systems: "Distinct systems any of these changes reaches.",
  risk: "Average overall risk, 0 to 100. Under 40 low, 40–69 medium, 70+ high.",
  compliance: "Regulations at medium or high risk across these changes.",
  confidence: "Average release confidence: how ready these changes are to ship.",
  business: "How much the business relies on what changes: the most critical changed system, scaled down for small changes.",
  customers: "High: a customer app or channel itself changes. Medium: customer data or a channel is affected. Low: back-office only.",
  readiness: "Release confidence from the release rules: risk, test coverage, compliance and clashes.",
  heatmap: "Each row is a change; each column a system it reaches. Darker means harder hit; an outlined cell means that change edits the system itself.",
  conflict: "70% weight on how much of what the two changes edit is the same, 30% on how much of what they reach overlaps. 80%+ means plan them together.",
};

function Chip({ level }: { level: Level }) {
  return <span className={cn("inline-flex rounded-full border px-2 py-0.5 text-meta font-medium", levelChip[level])}>{levelWord[level]}</span>;
}

export function PortfolioKpis({ analyses }: { analyses: StoryAnalysis[] }) {
  const kpis = portfolioKpis(analyses);
  const items = [
    { label: "Stories analysed", value: String(kpis.stories), tip: tips.stories },
    { label: "Impacted systems", value: String(kpis.systems), tip: tips.systems },
    { label: "Risk score", value: String(kpis.riskScore), tip: tips.risk, tone: levelTone[kpis.riskLevel], detail: levelWord[kpis.riskLevel] },
    { label: "Compliance impact", value: kpis.compliance.length ? String(kpis.compliance.length) : "None", tip: tips.compliance, detail: kpis.compliance.join(", ") || "No review needed", tone: kpis.compliance.length ? "text-impact-med" : "" },
    { label: "Release confidence", value: `${kpis.confidence}%`, tip: tips.confidence, tone: kpis.confidence >= 70 ? "text-impact-low" : kpis.confidence >= 45 ? "text-impact-med" : "text-impact-high" },
  ];
  return (
    <div className="rounded-xl border border-line bg-surface py-5">
      <dl aria-label="Portfolio KPIs" className="readouts gap-y-5">
        {items.map((item) => (
          <div key={item.label}>
            <dt className="flex items-center gap-1 text-dense text-muted">{item.label}<InfoTip label={item.label.toLowerCase()} side="bottom">{item.tip}</InfoTip></dt>
            <dd className={cn("mt-1 text-hero numeral", item.tone)}>{item.value}</dd>
            {item.detail && <dd className="mt-1 truncate text-meta text-muted" title={item.detail}>{item.detail}</dd>}
          </div>
        ))}
      </dl>
    </div>
  );
}

export function ChangeTable({ analyses, selectedId, onSelect }: { analyses: StoryAnalysis[]; selectedId: string | null; onSelect: (id: string) => void }) {
  const head = "px-4 py-2.5 text-left text-meta font-medium text-muted";
  return (
    <div className="overflow-x-auto rounded-xl border border-line bg-surface">
      <table className="w-full min-w-[860px] text-dense">
        <thead className="border-b border-line">
          <tr>
            <th scope="col" className={head}>Change</th>
            <th scope="col" className={head}><span className="inline-flex items-center gap-1">Business impact<InfoTip label="business impact">{tips.business}</InfoTip></span></th>
            <th scope="col" className={head}><span className="inline-flex items-center gap-1">Affected customers<InfoTip label="affected customers">{tips.customers}</InfoTip></span></th>
            <th scope="col" className={head}>Affected systems</th>
            <th scope="col" className={head}>Risk</th>
            <th scope="col" className={head}><span className="inline-flex items-center gap-1">Release readiness<InfoTip label="release readiness">{tips.readiness}</InfoTip></span></th>
          </tr>
        </thead>
        <tbody>
          {analyses.map((analysis) => {
            const systems = affectedSystems(analysis);
            const risk = riskLevel(analysis.risk.overall);
            const readiness = analysis.release.confidence;
            const active = selectedId === analysis.story.id;
            return (
              <tr key={analysis.story.id} className={cn("border-t border-line align-top first:border-t-0", active && "bg-surface-raised")}>
                <td className="px-4 py-3">
                  <button type="button" onClick={() => onSelect(analysis.story.id)} aria-pressed={active} className="text-left">
                    <span className="block font-semibold link-ui no-underline hover:underline">{analysis.story.title}</span>
                    <span className="text-meta text-muted">{analysis.story.id} · {analysis.story.type === "epic" ? "Feature" : "Story"} · {analysis.risk.change_size} change</span>
                  </button>
                </td>
                <td className="px-4 py-3"><Chip level={businessImpact(analysis)} /></td>
                <td className="px-4 py-3"><Chip level={affectedCustomers(analysis)} /></td>
                <td className="px-4 py-3 text-muted"><span className="text-text">{systems.slice(0, 3).join(", ")}</span>{systems.length > 3 ? ` +${systems.length - 3}` : ""}</td>
                <td className="px-4 py-3"><Chip level={risk} /> <span className="ml-1 text-meta text-muted tabular-nums">{analysis.risk.overall}</span></td>
                <td className="px-4 py-3">
                  <span className={cn("font-semibold tabular-nums", readiness >= 70 ? "text-impact-low" : readiness >= 45 ? "text-impact-med" : "text-impact-high")}>{readiness}%</span>
                  <span className="mt-1.5 block h-1.5 w-28 overflow-hidden rounded-full bg-line" aria-hidden="true"><span className={cn("block h-full rounded-full", readiness >= 70 ? "bg-impact-low" : readiness >= 45 ? "bg-impact-med" : "bg-impact-high")} style={{ width: `${readiness}%` }} /></span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const cellTone = { high: "bg-impact-high", medium: "bg-impact-med", low: "bg-impact-low" } as const;

export function ImpactHeatmap({ analyses, selectedId, onSelect }: { analyses: StoryAnalysis[]; selectedId: string | null; onSelect: (id: string) => void }) {
  const { columns, rows } = heatmap(analyses);
  if (!columns.length) return null;
  return (
    <div className="overflow-x-auto rounded-xl border border-line bg-surface p-4">
      <table className="w-full border-separate border-spacing-1 text-meta">
        <thead>
          <tr>
            <th scope="col" className="w-56 text-left font-medium text-muted">Change</th>
            {columns.map((column) => (
              <th key={column.id} scope="col" className="h-24 align-bottom font-medium text-muted">
                <span className="mx-auto block w-4 whitespace-nowrap [writing-mode:vertical-rl] rotate-180 text-left">{column.label}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <th scope="row" className="max-w-56 pr-2 text-left font-normal">
                <button type="button" onClick={() => onSelect(row.id)} className={cn("block w-full truncate text-left", selectedId === row.id ? "font-semibold text-text" : "text-muted hover:text-text")} title={row.title}>{row.title}</button>
              </th>
              {row.cells.map((cell, index) => (
                <td key={columns[index].id} className="p-0">
                  <span
                    title={cell ? `${row.title} → ${columns[index].label}: ${cell.severity ?? "low"} impact${cell.changed ? " (changed)" : ""}` : `${row.title} does not reach ${columns[index].label}`}
                    className={cn(
                      "block h-8 min-w-8 rounded",
                      cell ? cn(cellTone[cell.severity ?? "low"], cell.changed ? "opacity-100 ring-2 ring-chalk ring-inset" : cell.severity === "high" ? "opacity-80" : "opacity-55") : "bg-line/40",
                    )}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-meta text-muted">
        <span className="flex items-center gap-1.5"><i className="size-3 rounded-sm bg-impact-high" aria-hidden="true" />High</span>
        <span className="flex items-center gap-1.5"><i className="size-3 rounded-sm bg-impact-med opacity-55" aria-hidden="true" />Medium</span>
        <span className="flex items-center gap-1.5"><i className="size-3 rounded-sm bg-impact-low opacity-55" aria-hidden="true" />Low</span>
        <span className="flex items-center gap-1.5"><i className="size-3 rounded-sm ring-2 ring-chalk ring-inset" aria-hidden="true" />Changed by this story</span>
      </p>
    </div>
  );
}

export function ConflictEngine({ sprint }: { sprint: SprintAnalysis }) {
  const pairs = conflictPairs(sprint);
  if (!pairs.length) return <p className="rounded-xl border border-line bg-surface p-5 text-body">No clashes. These changes can be planned independently.</p>;
  return (
    <ul className="grid gap-4 lg:grid-cols-2">
      {pairs.slice(0, 6).map((pair) => {
        const level: Level = pair.score >= 80 ? "high" : pair.score >= 50 ? "medium" : "low";
        return (
          <li key={`${pair.a.story.id}-${pair.b.story.id}`} className="flex flex-col gap-4 rounded-xl border border-line bg-surface p-5">
            <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-start gap-3">
              <div className="min-w-0"><p className="text-meta text-muted">Story A · {pair.a.story.id}</p><p className="font-semibold">{pair.a.story.title}</p></div>
              <ArrowLeftRight aria-hidden="true" className="mt-4 size-4 text-muted" />
              <div className="min-w-0"><p className="text-meta text-muted">Story B · {pair.b.story.id}</p><p className="font-semibold">{pair.b.story.title}</p></div>
            </div>
            <div className="flex items-baseline gap-3">
              <span className={cn("text-hero numeral", levelTone[level])}>{pair.score}%</span>
              <span className="flex items-center gap-1 text-dense text-muted">conflict<InfoTip label="conflict score">{tips.conflict} {pair.why}</InfoTip></span>
            </div>
            <div>
              <p className="text-meta text-muted">Shared systems</p>
              <ul className="mt-1 flex flex-wrap gap-1.5">{pair.shared.map((system) => <li key={system} className="rounded-full border border-line px-2.5 py-0.5 text-dense">{system}</li>)}</ul>
            </div>
            <p className="border-t border-line pt-3 text-dense"><span className="text-muted">Recommendation: </span><span className="font-medium">{pair.recommendation}</span></p>
          </li>
        );
      })}
    </ul>
  );
}
