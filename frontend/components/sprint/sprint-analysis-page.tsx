"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { BlastRadiusGraph, NodeDetailsPanel } from "@/components/graph";
import { factorsForNode } from "@/components/analysis/model";
import { useAppContext } from "@/components/shell/app-context";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { analyzeSprint, getDemoSprint } from "@/lib/api";
import type { Conflict, SprintAnalysis, SprintKpis, SprintRequest } from "@/lib/types";
import { ConflictTable } from "./conflict-table";
import { DEMO_SPRINT_ID, getSavedSprint } from "./data";
import { conflictHighlights, parseStories, rememberRun } from "./model";
import { RiskByStoryChart } from "./risk-chart";
import { SprintStatStrip } from "./stat-strip";
import { StoryTable } from "./story-table";

export function SprintAnalysisPage() {
  const { highlight, setHighlight, setCurrentContext, setCurrentAnalysis } = useAppContext();
  const [analysis, setAnalysis] = useState<SprintAnalysis | null>(null);
  const [previous, setPrevious] = useState<SprintKpis | null>(null);
  const [loading, setLoading] = useState<string | null>("Loading saved sprint…");
  const [error, setError] = useState<string | null>(null);
  const [inputError, setInputError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [demoCount, setDemoCount] = useState(6);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedConflictId, setSelectedConflictId] = useState<string | null>(null);
  const lastRequest = useRef<SprintRequest | null>(null);
  const operation = useRef(0);

  const accept = useCallback((result: SprintAnalysis, newRun: boolean) => {
    let baseline: SprintKpis | null = null;
    try { baseline = rememberRun(result, newRun, window.localStorage); }
    catch { /* Access to localStorage itself can be blocked by browser policy. */ }
    setPrevious(baseline);
    setAnalysis(result);
    setSelectedNodeId(null);
    setSelectedConflictId(null);
    setHighlight([]);
    setCurrentContext({ type: "sprint", id: result.sprint_id });
    setCurrentAnalysis(result);
  }, [setCurrentAnalysis, setCurrentContext, setHighlight]);

  useEffect(() => {
    const controller = new AbortController();
    const operations = operation;
    const token = ++operations.current;
    setCurrentContext(null);
    setCurrentAnalysis(null);
    setHighlight([]);
    void getDemoSprint().then((demo) => {
      if (!controller.signal.aborted && demo.stories.length) setDemoCount(demo.stories.length);
    }).catch(() => { /* The demo can still run with the backend's default stories. */ });
    void getSavedSprint(controller.signal).then((result) => {
      if (!controller.signal.aborted && operation.current === token && result) accept(result, false);
    }).catch((reason: unknown) => {
      if (!controller.signal.aborted && operation.current === token) setError(reason instanceof Error ? reason.message : "Couldn't load the sprint. Check the backend and try again.");
    }).finally(() => {
      if (!controller.signal.aborted && operation.current === token) setLoading(null);
    });
    return () => { controller.abort(); operations.current++; };
  }, [accept, setCurrentAnalysis, setCurrentContext, setHighlight]);

  async function run(request: SprintRequest) {
    const token = ++operation.current;
    lastRequest.current = request;
    setError(null);
    setInputError(null);
    setLoading(`Analyzing ${request.stories?.length ?? demoCount} stories in parallel…`);
    try {
      const result = await analyzeSprint(request);
      if (operation.current === token) accept(result, true);
    } catch (reason) {
      if (operation.current === token) setError(reason instanceof Error ? reason.message : "Couldn't analyze the sprint. Check the backend and try again.");
    } finally {
      if (operation.current === token) setLoading(null);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const stories = parseStories(input);
      void run({ sprint_id: "sprint-custom", name: "Pasted stories", stories });
    } catch (reason) {
      setInputError(reason instanceof Error ? reason.message : "Check the stories and try again.");
    }
  }

  async function retry() {
    if (lastRequest.current) return run(lastRequest.current);
    const token = ++operation.current;
    setError(null);
    setLoading("Loading saved sprint…");
    try {
      const result = await getSavedSprint();
      if (operation.current === token && result) accept(result, false);
    } catch (reason) {
      if (operation.current === token) setError(reason instanceof Error ? reason.message : "Couldn't load the sprint. Check the backend and try again.");
    } finally {
      if (operation.current === token) setLoading(null);
    }
  }

  function selectConflict(conflict: Conflict) {
    if (!analysis) return;
    setSelectedConflictId(conflict.id);
    setSelectedNodeId(conflict.shared_component);
    setHighlight(conflictHighlights(analysis, conflict));
  }

  const selectedNode = analysis?.conflict_graph.nodes.find((node) => node.id === selectedNodeId);
  const selectedFactors = analysis && selectedNode ? analysis.stories.flatMap((story) => factorsForNode(story.risk, selectedNode.id).map((factor) => ({ ...factor, label: `${story.story.id}: ${factor.label}` }))) : [];

  return (
    <div className="min-w-0 space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div><h1>Sprint analysis</h1>{analysis && <p className="mt-1 text-dense text-muted">{analysis.name} · {analysis.sprint_id}</p>}</div>
        <Button type="button" disabled={Boolean(loading)} onClick={() => void run({ sprint_id: DEMO_SPRINT_ID })}>Analyze demo sprint</Button>
      </header>
      <details className="rounded-md border border-line bg-surface px-4 py-3">
        <summary className="w-fit cursor-pointer text-dense font-medium text-azure">Paste stories</summary>
        <form onSubmit={submit} className="mt-3 space-y-3" aria-label="Custom sprint input">
          <label htmlFor="sprint-stories" className="block text-dense">Stories</label>
          <p id="sprint-input-help" className="text-meta text-muted">Paste a JSON array with id, title, description, type and acceptance_criteria, or one story per line: ID | title | description. Type defaults to story; acceptance criteria default to an empty list.</p>
          <Textarea id="sprint-stories" value={input} onChange={(event) => { setInput(event.target.value); setInputError(null); }} rows={6} disabled={Boolean(loading)} placeholder="ST-201 | Update transfer limits | Apply the new daily limit to mobile transfers" aria-describedby={`sprint-input-help${inputError ? " sprint-input-error" : ""}`} aria-invalid={Boolean(inputError)} className="min-h-36 resize-y" />
          {inputError && <p id="sprint-input-error" role="alert" className="text-dense text-impact-high">{inputError}</p>}
          <Button type="submit" disabled={Boolean(loading) || !input.trim()}>Analyze sprint</Button>
        </form>
      </details>
      {error && <div role="alert" className="flex flex-wrap items-center gap-3 rounded-md border border-impact-high/40 bg-surface p-4"><p className="flex-1 text-body">{error}</p><Button type="button" variant="outline" disabled={Boolean(loading)} onClick={() => void retry()}>Try again</Button></div>}
      {loading && <p role="status" aria-live="polite" className="border-y border-line py-6 text-body text-muted">{loading}</p>}
      {analysis ? <section aria-label="Sprint results" aria-busy={Boolean(loading)} className="space-y-5">
        <SprintStatStrip kpis={analysis.kpis} previous={previous} />
        <p className="text-body text-muted">{analysis.summary}</p>
        <div className="grid min-w-0 gap-6 border-b border-line pb-5 min-[1024px]:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          <StoryTable stories={analysis.stories} />
          <RiskByStoryChart stories={analysis.stories} />
        </div>
        <section aria-labelledby="sprint-conflicts-heading" className="space-y-3">
          <h2 id="sprint-conflicts-heading">Conflicts</h2>
          <p className="text-meta text-muted">Select a conflict to highlight its shared component and both stories&apos; direct changes.</p>
          <ConflictTable analysis={analysis} selectedId={selectedConflictId} onSelect={selectConflict} />
        </section>
        <section aria-labelledby="sprint-graph-heading">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div><h2 id="sprint-graph-heading">Conflict graph</h2><p className="mt-1 text-meta text-muted">Dashed high-risk edges mark conflicts. Select a component for details.</p></div>
            {highlight.length > 0 && <Button type="button" variant="outline" onClick={() => { setHighlight([]); setSelectedConflictId(null); }}>Clear highlight ({highlight.length})</Button>}
          </div>
          <p role="status" className="sr-only">{highlight.length ? `Highlighted components: ${highlight.join(", ")}` : "Showing all graph components"}</p>
          <div className={`grid min-w-0 gap-4 ${selectedNode ? "min-[1024px]:grid-cols-[minmax(0,1fr)_360px]" : "grid-cols-1"}`}>
            <BlastRadiusGraph graph={analysis.conflict_graph} highlight={highlight} selectedId={selectedNodeId} onNodeSelect={setSelectedNodeId} height={460} />
            {selectedNode && <NodeDetailsPanel node={selectedNode} factors={selectedFactors} onClose={() => setSelectedNodeId(null)} />}
          </div>
        </section>
      </section> : !loading && <div className="flex min-h-[300px] items-center justify-center border-y border-line bg-surface/40 px-4 text-center"><p className="text-body text-muted">Select Analyze demo sprint or paste stories and select Analyze sprint to see shared impacts and conflicts.</p></div>}
    </div>
  );
}
