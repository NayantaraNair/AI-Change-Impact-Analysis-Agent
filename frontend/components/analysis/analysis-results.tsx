"use client";

import { useState } from "react";
import { RotateCw } from "lucide-react";
import { DependencyGraph, NodeDetailsPanel } from "@/components/graph";
import { RunNote } from "@/components/run/provenance";
import { useAppContext } from "@/components/shell/app-context";
import { Button } from "@/components/ui/button";
import { InfoTip } from "@/components/ui/info-tip";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { explain } from "@/lib/explain";
import type { Component, Run, StoryAnalysis } from "@/lib/types";
import { ComplianceTab } from "./compliance-tab";
import { ImpactSummary } from "./impact-summary";
import { factorsForNode } from "./model";
import { ReleaseTab } from "./release-tab";
import { RiskTab } from "./risk-tab";
import { StatStrip } from "./stat-strip";
import { TestsTab } from "./tests-tab";

export function AnalysisResults({ analysis, components, run, onRerunLive }: { analysis: StoryAnalysis; components: Component[]; run: Run | null; onRerunLive: () => void }) {
  const { highlight, setHighlight } = useAppContext();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selectedNode = analysis.graph.nodes.find((node) => node.id === selectedId);
  const component = components.find((item) => item.id === selectedId);
  return (
    <section aria-label={`Analysis for ${analysis.story.id}`}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-body font-medium"><span className="text-muted">{analysis.story.id}</span> {analysis.story.title}</h2>
        <span className="flex items-center gap-1.5">
          <Button type="button" variant="outline" size="sm" onClick={onRerunLive}><RotateCw aria-hidden="true" />Re-run live</Button>
          <InfoTip label="re-run live">Runs again with live AI, skipping saved results. Takes 1–3 minutes.</InfoTip>
        </span>
      </div>
      <StatStrip analysis={analysis} />
      <RunNote analysis={analysis} run={run} />
      <ImpactSummary analysis={analysis} />
      <div className={`grid min-w-0 ${selectedNode ? "min-[1024px]:grid-cols-[minmax(0,1fr)_340px]" : "grid-cols-1"}`}>
        <section aria-label="Dependency graph" className="min-w-0 border-b border-line">
          <div className="flex min-h-14 flex-wrap items-center justify-between gap-3 py-3">
            <div className="flex flex-wrap items-baseline gap-3"><h2 className="flex items-center gap-1.5">Dependency graph <InfoTip label="the dependency graph">{explain.blastRadius}</InfoTip></h2><p className="text-meta text-muted">What this change touches, and how far it spreads.</p></div>
            {highlight.length > 0 && <Button type="button" variant="outline" size="sm" onClick={() => setHighlight([])}>Clear highlight</Button>}
          </div>
          <p className="sr-only" role="status" aria-live="polite">{highlight.length ? `Highlighted: ${highlight.join(", ")}` : "Showing all affected components"}</p>
          <DependencyGraph graph={analysis.graph} highlight={highlight} selectedId={selectedId} onNodeSelect={setSelectedId} />
        </section>
        {selectedNode && <aside aria-label="Selected component" className="min-w-0 border-b border-line py-4 min-[1024px]:col-start-2 min-[1024px]:row-start-1 min-[1024px]:row-span-2 min-[1024px]:border-b-0 min-[1024px]:border-l min-[1024px]:pl-4">
          <div className="sticky top-4">
            <NodeDetailsPanel node={selectedNode} component={component} factors={factorsForNode(analysis.risk, selectedNode.id)} onClose={() => setSelectedId(null)} />
          </div>
        </aside>}
        <Tabs defaultValue="risk" className="min-w-0 gap-0 min-[1024px]:col-start-1 min-[1024px]:row-start-2">
          <TabsList variant="line" aria-label="Details" className="h-12! w-full justify-start overflow-x-auto rounded-none border-b border-line p-0">
            {["Risk", "Tests", "Compliance", "Release"].map((tab) => <TabsTrigger key={tab} value={tab.toLowerCase()} className="flex-none px-4 py-3 text-dense after:bottom-0!">{tab}</TabsTrigger>)}
          </TabsList>
          <TabsContent value="risk" keepMounted><RiskTab risk={analysis.risk} /></TabsContent>
          <TabsContent value="tests"><TestsTab plan={analysis.tests} nodes={analysis.graph.nodes} /></TabsContent>
          <TabsContent value="compliance"><ComplianceTab report={analysis.compliance} nodes={analysis.graph.nodes} /></TabsContent>
          <TabsContent value="release"><ReleaseTab release={analysis.release} /></TabsContent>
        </Tabs>
      </div>
    </section>
  );
}
