"use client";

import { useEffect, useRef, useState } from "react";
import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer } from "recharts";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useAppContext } from "@/components/shell/app-context";
import { formatNumber, severityClass } from "@/lib/format";
import type { RiskFactor, RiskReport, Severity } from "@/lib/types";
import { dimensionLabel, factorWidth, restoreHighlight, sameNodes } from "./model";
import { InfoTip } from "@/components/ui/info-tip";
import { explain } from "@/lib/explain";

const factorColor: Record<Severity, string> = {
  low: "bg-impact-low", medium: "bg-impact-med", high: "bg-impact-high",
};

export function RiskTab({ risk }: { risk: RiskReport }) {
  const { highlight, setHighlight } = useAppContext();
  const [pinned, setPinned] = useState<string | null>(null);
  const hovered = useRef<string | null>(null);
  const focused = useRef<string | null>(null);
  const preview = useRef<{ nodes: string[]; previous: string[] } | null>(null);

  useEffect(() => () => {
    const value = preview.current;
    if (value) setHighlight((current) => restoreHighlight(current, value.nodes, value.previous));
  }, [setHighlight]);

  function show(key: string, factor: RiskFactor, source: "mouse" | "focus") {
    if (source === "mouse") hovered.current = key;
    else focused.current = key;
    preview.current = { nodes: factor.node_ids, previous: preview.current?.previous ?? highlight };
    setHighlight(factor.node_ids);
  }

  function restore(key: string, source: "mouse" | "focus") {
    if (source === "mouse") hovered.current = null;
    else focused.current = null;
    if (hovered.current === key || focused.current === key) return;
    const value = preview.current;
    preview.current = null;
    if (value) setHighlight((current) => restoreHighlight(current, value.nodes, value.previous));
  }

  function toggle(key: string, factor: RiskFactor) {
    const clear = pinned === key && sameNodes(highlight, factor.node_ids);
    const nodes = clear ? [] : factor.node_ids;
    setPinned(clear ? null : key);
    setHighlight(nodes);
    // Leaving the segment after a click keeps the new pinned selection.
    if (preview.current) preview.current = { nodes, previous: nodes };
  }

  const chartData = risk.dimensions.map((dimension) => ({ label: dimensionLabel[dimension.name], score: dimension.score }));
  return (
    <section aria-label="Risk breakdown" className="grid gap-6 py-5 min-[1280px]:grid-cols-[300px_minmax(0,1fr)]">
      <div>
        <h2 className="flex items-center gap-1.5">Risk profile <InfoTip label="risk scoring">{explain.riskProfile}</InfoTip></h2>
        <p className="mt-1 text-meta text-muted">Six dimensions on a 0–100 scale</p>
        <div className="h-[280px] w-full min-w-0" role="img" aria-label={risk.dimensions.map((d) => `${dimensionLabel[d.name]} ${d.score} out of 100`).join(", ")}>
          <ResponsiveContainer width="100%" height="100%" minWidth={0}>
            <RadarChart data={chartData} outerRadius="68%">
              <PolarGrid stroke="var(--line)" />
              <PolarAngleAxis dataKey="label" tick={{ fill: "var(--muted)", fontSize: 12 }} />
              <PolarRadiusAxis domain={[0, 100]} ticks={[25, 50, 75, 100]} tick={false} axisLine={false} />
              <Radar dataKey="score" stroke="var(--azure)" strokeWidth={2} fill="var(--azure)" fillOpacity={0.12} isAnimationActive={false} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="min-w-0 space-y-5">
        <div>
          <h2>What drives the risk</h2>
          <p className="mt-1 text-dense text-muted">Hover or focus a factor to preview its nodes in the graph. Click to pin; click again to clear.</p>
          <p role="status" className="mt-2 text-meta text-muted">{highlight.length ? `Graph highlight: ${highlight.join(", ")}` : "Graph shows all nodes."}</p>
        </div>
        {risk.dimensions.map((dimension) => (
          <div key={dimension.name} className="space-y-2">
            <div className="flex items-baseline gap-2">
              <h3 className="flex items-center gap-1.5 text-body font-medium">{dimensionLabel[dimension.name]}<InfoTip label={`${dimensionLabel[dimension.name]} risk`}>{explain.dimensions[dimension.name]}</InfoTip></h3>
              <span className={`text-title font-semibold tabular-nums ${severityClass[dimension.level]}`}>{formatNumber(dimension.score)}</span>
              <span className="text-meta text-muted">/ 100 · {dimension.level} risk</span>
            </div>
            <div className="flex min-h-8 w-full overflow-x-auto rounded-md bg-surface-raised" aria-label={`${dimensionLabel[dimension.name]} factor contributions`}>
              {dimension.factors.filter((factor) => factor.points > 0).map((factor, index) => {
                const key = `${dimension.name}-${index}`;
                const baseline = /\bbaseline\b/i.test(factor.label);
                const noNodes = factor.node_ids.length === 0;
                const selected = pinned === key && sameNodes(highlight, factor.node_ids);
                const label = `+${factor.points} ${factor.label}`;
                return (
                  <Tooltip key={key}>
                    <TooltipTrigger render={
                      <button type="button" aria-label={`${dimensionLabel[dimension.name]}: ${label}${noNodes ? "; no cited nodes" : ""}`} aria-pressed={selected}
                        onMouseEnter={() => show(key, factor, "mouse")} onMouseLeave={() => restore(key, "mouse")} onFocus={() => show(key, factor, "focus")} onBlur={() => restore(key, "focus")}
                        onClick={() => toggle(key, factor)} style={{ width: factorWidth(factor.points) }}
                        className={`relative min-w-0 shrink-0 border-r border-canvas/40 px-2 py-1.5 text-left text-meta font-medium transition-opacity duration-150 hover:opacity-85 focus-visible:z-10 focus-visible:-outline-offset-2 ${baseline ? "bg-line text-text" : `${factorColor[dimension.level]} text-canvas`} ${selected ? "ring-2 ring-azure ring-inset" : ""}`} />
                    }><span className="block truncate">{label}</span></TooltipTrigger>
                    <TooltipContent className="max-w-sm">{label} · {baseline ? explain.baseline : noNodes ? "No cited nodes" : `Caused by ${factor.node_ids.join(", ")}`}</TooltipContent>
                  </Tooltip>
                );
              })}
              {dimension.factors.every((factor) => factor.points <= 0) && <span className="px-2 py-1.5 text-meta text-muted">No contributing factors</span>}
            </div>
            <p className="text-dense text-muted">{dimension.explanation}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
