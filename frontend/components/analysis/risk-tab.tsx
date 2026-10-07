"use client";

import { useState } from "react";
import { useAppContext } from "@/components/shell/app-context";
import { InfoTip } from "@/components/ui/info-tip";
import { explain } from "@/lib/explain";
import { cn } from "@/lib/utils";
import type { RiskDimension, RiskReport, Severity } from "@/lib/types";
import { dimensionLabel } from "./model";

const barColor: Record<Severity, string> = { low: "bg-impact-low", medium: "bg-impact-med", high: "bg-impact-high" };
const textColor: Record<Severity, string> = { low: "text-impact-low", medium: "text-impact-med", high: "text-impact-high" };
const levelWord: Record<Severity, string> = { low: "Low", medium: "Medium", high: "High" };

/** Scoring labels shown in plain words. */
const factorLabel = (label: string) => label === "blast radius size" ? "dependency reach" : label;

/** The two biggest causes, in plain words: "card data, auth flow change". */
function causes(dimension: RiskDimension) {
  const top = dimension.factors.filter((factor) => factor.label !== "baseline" && factor.points > 0)
    .sort((a, b) => b.points - a.points).slice(0, 2);
  return { text: top.map((factor) => factorLabel(factor.label)).join(", "), nodes: [...new Set(top.flatMap((factor) => factor.node_ids))] };
}

export function RiskTab({ risk }: { risk: RiskReport }) {
  const { setHighlight } = useAppContext();
  const [pinned, setPinned] = useState<string | null>(null);
  const rows = [...risk.dimensions].sort((a, b) => b.score - a.score);

  function toggle(dimension: RiskDimension, nodes: string[]) {
    const clear = pinned === dimension.name;
    setPinned(clear ? null : dimension.name);
    setHighlight(clear ? [] : nodes);
  }

  return (
    <section aria-label="Risk" className="space-y-4 py-5">
      <div>
        <h2 className="flex items-center gap-1.5">Risk by area <InfoTip label="risk scores">{explain.riskProfile}</InfoTip></h2>
        <p className="mt-1 text-dense text-muted">0 to 100. Higher is riskier. Click a row to see its causes in the graph.</p>
      </div>
      <ul className="divide-y divide-line border-y border-line">
        {rows.map((dimension) => {
          const why = causes(dimension);
          const active = pinned === dimension.name;
          return (
            <li key={dimension.name} className={cn("grid grid-cols-[8.5rem_minmax(0,1fr)] items-center gap-x-4 px-2 transition-colors duration-150", active && "bg-surface-raised")}>
              <span className="flex items-center gap-1.5 text-body font-medium">
                {dimensionLabel[dimension.name]}
                <InfoTip label={`${dimensionLabel[dimension.name]} risk`}>{explain.dimensions[dimension.name]}</InfoTip>
              </span>
              <button type="button" aria-pressed={active} aria-label={`${dimensionLabel[dimension.name]} risk ${dimension.score}, ${levelWord[dimension.level]}. ${why.text ? `Causes: ${why.text}. ` : ""}Show causes in the graph`} onClick={() => toggle(dimension, why.nodes)}
                className="grid min-w-0 grid-cols-[minmax(0,1fr)_3.5rem_4.5rem] items-center gap-x-4 py-3 text-left">
                <span className="min-w-0">
                  <span className="block h-2 w-full overflow-hidden rounded-full bg-line" aria-hidden="true">
                    <span className={cn("block h-full rounded-full", barColor[dimension.level])} style={{ width: `${dimension.score}%` }} />
                  </span>
                  <span className="mt-1.5 block truncate text-meta text-muted">{why.text ? `Why: ${why.text}` : "No specific causes"}</span>
                </span>
                <span className={cn("text-right text-section numeral", textColor[dimension.level])}>{dimension.score}</span>
                <span className={cn("text-dense font-medium", textColor[dimension.level])}>{levelWord[dimension.level]}</span>
              </button>
            </li>
          );
        })}
      </ul>
      <p className="text-meta text-muted">Low under 40 · Medium 40–69 · High 70 and over</p>
    </section>
  );
}
