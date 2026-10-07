"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { formatHours, formatNumber, formatPercent } from "@/lib/format";
import type { GraphNode, TestCase, TestPlan } from "@/lib/types";
import { filterTests } from "./model";
import { NodeLinks } from "./node-links";
import { InfoTip } from "@/components/ui/info-tip";
import { explain } from "@/lib/explain";

const priorities: TestCase["priority"][] = ["P1", "P2", "P3"];
const types: TestCase["type"][] = ["functional", "api", "integration", "regression", "security"];
const priorityStyle = { P1: "text-impact-high border-impact-high/40", P2: "text-impact-med border-impact-med/40", P3: "text-impact-low border-impact-low/40" };
const typeLabel = (type: string) => type === "api" ? "API" : type[0].toUpperCase() + type.slice(1);

export function TestsTab({ plan, nodes }: { plan: TestPlan; nodes: GraphNode[] }) {
  const [selectedPriorities, setPriorities] = useState<TestCase["priority"][]>([]);
  const [selectedTypes, setTypes] = useState<TestCase["type"][]>([]);
  const tests = filterTests(plan.tests, selectedPriorities, selectedTypes);
  function toggle<T>(items: T[], item: T): T[] {
    return items.includes(item) ? items.filter((value) => value !== item) : [...items, item];
  }
  const chipClass = "rounded-md border border-line px-2 py-1 text-dense text-azure transition-colors duration-150 hover:bg-surface-raised aria-pressed:border-azure aria-pressed:bg-azure/10";

  return (
    <section aria-label="Test plan" className="space-y-4 py-5">
      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2">
        <h2>Test plan</h2>
        <p className="flex items-baseline gap-1"><span className="font-semibold tabular-nums">{formatPercent(plan.coverage_estimate)}</span> <span className="text-meta text-muted">coverage estimate</span><InfoTip label="coverage">{explain.coverage}</InfoTip></p>
        <p className="flex items-baseline gap-1"><span className="font-semibold tabular-nums">{formatHours(plan.effort_hours)}</span> <span className="text-meta text-muted">effort</span><InfoTip label="effort">{explain.effort}</InfoTip></p>
        <p className="flex items-baseline gap-1"><span className="font-semibold tabular-nums">{formatNumber(plan.automation_candidates)}</span> <span className="text-meta text-muted">automation candidates</span><InfoTip label="automation candidates">{explain.automation}</InfoTip></p>
      </div>
      <p className="text-body text-muted">{plan.summary}</p>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
        <div role="group" aria-label="Filter by priority" className="flex items-center gap-1.5">
          <span className="mr-1 text-meta text-muted">Priority</span>
          {priorities.map((priority) => <button key={priority} type="button" aria-pressed={selectedPriorities.includes(priority)} className={chipClass} onClick={() => setPriorities(toggle(selectedPriorities, priority))}>{priority}</button>)}
        </div>
        <div role="group" aria-label="Filter by test type" className="flex flex-wrap items-center gap-1.5">
          <span className="mr-1 text-meta text-muted">Type</span>
          {types.map((type) => <button key={type} type="button" aria-pressed={selectedTypes.includes(type)} className={chipClass} onClick={() => setTypes(toggle(selectedTypes, type))}>{typeLabel(type)}</button>)}
        </div>
        {(selectedPriorities.length > 0 || selectedTypes.length > 0) && <Button variant="ghost" onClick={() => { setPriorities([]); setTypes([]); }}>Clear filters</Button>}
      </div>
      <p role="status" className="text-meta text-muted">{tests.length} of {plan.tests.length} tests · Select a title to see steps and expected results.</p>
      <div className="overflow-x-auto rounded-md border border-line">
        <table className="w-full min-w-[760px] text-left text-dense">
          <thead className="bg-surface text-muted"><tr>{["Priority", "Title", "Type", "Covers", "Source", "Automation"].map((label) => <th key={label} scope="col" className="px-3 py-2 font-medium"><span className="inline-flex items-center gap-1">{label}{label === "Priority" && <InfoTip label="priority">{explain.priority}</InfoTip>}{label === "Source" && <InfoTip label="test source">{explain.testSource}</InfoTip>}{label === "Automation" && <InfoTip label="automation">{explain.automation}</InfoTip>}</span></th>)}</tr></thead>
          <tbody>
            {tests.map((test) => (
              <tr key={test.id} className="border-t border-line align-top">
                <td className="px-3 py-3"><span className={`rounded border px-1.5 py-0.5 text-meta font-medium ${priorityStyle[test.priority]}`}>{test.priority}</span></td>
                <td className="w-[35%] px-3 py-3">
                  <details className="group">
                    <summary className="cursor-pointer text-azure">{test.title}<span className="ml-2 text-meta text-muted">{test.id}</span></summary>
                    <div className="mt-3 space-y-2">
                      <ol className="list-decimal space-y-1 pl-5 text-muted">{test.steps.map((step, index) => <li key={index}>{step}</li>)}</ol>
                      <p><span className="font-medium">Expected: </span>{test.expected}</p>
                    </div>
                  </details>
                </td>
                <td className="px-3 py-3">{typeLabel(test.type)}</td>
                <td className="px-3 py-3"><NodeLinks ids={test.covers} nodes={nodes} /></td>
                <td className="px-3 py-3">{typeLabel(test.source)}</td>
                <td className="px-3 py-3">{test.automation_candidate ? "Candidate" : "Manual"}</td>
              </tr>
            ))}
            {!tests.length && <tr><td colSpan={6} className="px-3 py-6 text-muted">{plan.tests.length ? "No tests match these filters. Clear filters to see the full plan." : "No tests were returned. Refine the story and analyze it again."}</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );
}
