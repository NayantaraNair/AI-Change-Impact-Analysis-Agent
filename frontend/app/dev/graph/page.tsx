"use client";

import { useEffect, useState } from "react";
import { Network, RotateCcw } from "lucide-react";
import { BlastRadiusGraph, NodeDetailsPanel } from "@/components/graph";
import type { Component, StoryAnalysis } from "@/lib/types";
import previewComponents from "@/components/graph/preview-components.json";

type FixtureState = { status: "loading" } | { status: "error" } | { status: "ready"; analysis: StoryAnalysis };

function GraphPreview({ analysis }: { analysis: StoryAnalysis }) {
  const [selectedId, setSelectedId] = useState<string | null>(() => analysis.graph.nodes.find((node) => node.hop === 0)?.id ?? null);
  const [factorId, setFactorId] = useState<string | null>(null);
  const node = analysis.graph.nodes.find((item) => item.id === selectedId);
  const component = (previewComponents as Component[]).find((item) => item.id === selectedId);
  const allFactors = analysis.risk.dimensions.flatMap((dimension) => dimension.factors.map((factor, index) => ({ ...factor, dimension: dimension.name, id: `${dimension.name}-${index}` })));
  const activeFactor = allFactors.find((factor) => factor.id === factorId);
  const factors = node ? allFactors.filter((factor) => factor.node_ids.includes(node.id)) : [];
  const impacted = analysis.graph.nodes.filter((item) => item.hop !== null).length;
  const highest = analysis.risk.dimensions.find((dimension) => dimension.name === analysis.risk.highest);

  return (
    <div className="mx-auto max-w-[1600px]">
      <header className="mb-6 flex items-start justify-between gap-6">
        <div><h1>Blast radius</h1><p className="mt-1 text-muted">{analysis.story.id} · {analysis.story.title}</p></div>
        <span className="flex items-center gap-2 rounded border border-line px-3 py-1.5 text-meta text-muted"><Network size={14} aria-hidden="true" />Fixture preview</span>
      </header>
      <div className="mb-6 flex flex-wrap gap-y-4 border-y border-line py-4" aria-label="Analysis statistics">
        <div className="min-w-[150px] border-r border-line pr-8"><p className="text-hero font-semibold leading-none">{impacted}</p><p className="mt-2 text-dense text-muted">Impacted components</p></div>
        <div className="min-w-[150px] border-r border-line px-8"><p className="text-hero font-semibold leading-none">{analysis.graph.nodes.length - impacted}</p><p className="mt-2 text-dense text-muted">Unimpacted</p></div>
        <div className="min-w-[150px] border-r border-line px-8"><p className="text-hero font-semibold leading-none">{analysis.graph.deployment_groups.length}</p><p className="mt-2 text-dense text-muted">Deployment groups</p></div>
        {highest && <div className="px-8"><p className="text-hero font-semibold leading-none" style={{ color: highest.level === "medium" ? "var(--impact-med)" : `var(--impact-${highest.level})` }}>{highest.score}</p><p className="mt-2 text-dense text-muted">Highest risk · {highest.name}</p></div>}
      </div>
      <div className={`grid items-start gap-4 ${node ? "min-[1024px]:grid-cols-[minmax(0,1fr)_360px]" : "grid-cols-1"}`}>
        <BlastRadiusGraph graph={analysis.graph} height={680} selectedId={selectedId} highlight={activeFactor?.node_ids} onNodeSelect={setSelectedId} />
        {node && <NodeDetailsPanel node={node} component={component} factors={factors} onClose={() => setSelectedId(null)} />}
      </div>
      <section className="mt-6 border-t border-line pt-4" aria-label="Factor highlighting preview">
        <div className="mb-3 flex items-center gap-4"><h2>Risk factors</h2><span className="text-meta text-muted">Select a factor to highlight its components</span>{activeFactor && <button type="button" className="ml-auto flex items-center gap-1.5 text-dense text-azure" onClick={() => setFactorId(null)}><RotateCcw size={14} aria-hidden="true" />Clear highlight</button>}</div>
        <div className="flex flex-wrap gap-2">{allFactors.map((factor) => <button key={factor.id} type="button" aria-pressed={factor.id === factorId} onClick={() => setFactorId((current) => current === factor.id ? null : factor.id)} className={`rounded border px-3 py-2 text-dense ${factor.id === factorId ? "border-azure bg-surface-raised text-text" : "border-line bg-surface text-muted hover:text-text"}`}><span className="mr-2 text-text">{factor.points >= 0 ? "+" : ""}{factor.points}</span>{factor.label}</button>)}</div>
      </section>
    </div>
  );
}

export default function GraphPreviewPage() {
  const [state, setState] = useState<FixtureState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const response = await fetch("/fixtures/story-ST-107.json", { signal: controller.signal });
        if (!response.ok) throw new Error("Fixture request failed");
        const analysis: StoryAnalysis = await response.json();
        if (!Array.isArray(analysis.graph?.nodes) || !Array.isArray(analysis.graph?.edges) || !Array.isArray(analysis.risk?.dimensions)) throw new Error("Invalid graph fixture");
        if (!controller.signal.aborted) setState({ status: "ready", analysis });
      } catch {
        if (!controller.signal.aborted) setState({ status: "error" });
      }
    }
    void load();
    return () => controller.abort();
  }, [attempt]);

  if (state.status === "loading") return <p role="status" className="py-12 text-muted">Loading blast radius fixture…</p>;
  if (state.status === "error") return <div role="alert" className="border border-line bg-surface p-6"><h1>Graph fixture unavailable</h1><p className="mt-2 text-muted">Couldn’t load the graph fixture. Restore public/fixtures/story-ST-107.json and try again.</p><button type="button" className="mt-4 rounded border border-azure px-3 py-2 text-azure" onClick={() => { setState({ status: "loading" }); setAttempt((value) => value + 1); }}>Try again</button></div>;
  return <GraphPreview analysis={state.analysis} />;
}
