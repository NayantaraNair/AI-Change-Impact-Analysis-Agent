"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Paperclip, RotateCw } from "lucide-react";
import { RunNote } from "@/components/run/provenance";
import { RunProgress } from "@/components/run/run-progress";
import { useAppContext } from "@/components/shell/app-context";
import { Button } from "@/components/ui/button";
import { InfoTip } from "@/components/ui/info-tip";
import { Textarea } from "@/components/ui/textarea";
import { getDemoSprint, runSprint } from "@/lib/api";
import { ATTACH_ACCEPT, BACKLOG_HANDOFF_KEY, readAttachment } from "@/lib/attach";
import { explain } from "@/lib/explain";
import type { Run, SprintAnalysis, SprintRequest, StoryInput } from "@/lib/types";
import { ConflictMap } from "./conflict-map";
import { DEMO_SPRINT_ID, getSavedSprint } from "./data";
import { parseStories } from "./model";
import { RiskByStoryChart } from "./risk-chart";
import { SprintStatStrip } from "./stat-strip";
import { SprintSummary } from "./sprint-summary";
import { StoryTable } from "./story-table";

function takeHandoff(): StoryInput[] | null {
  try {
    const raw = window.sessionStorage.getItem(BACKLOG_HANDOFF_KEY);
    if (!raw) return null;
    window.sessionStorage.removeItem(BACKLOG_HANDOFF_KEY);
    const stories = JSON.parse(raw) as StoryInput[];
    return Array.isArray(stories) && stories.length ? stories : null;
  } catch {
    return null;
  }
}

export function SprintAnalysisPage() {
  const { setHighlight, setCurrentContext, setCurrentAnalysis, setRun } = useAppContext();
  const [analysis, setAnalysis] = useState<SprintAnalysis | null>(null);
  const [progress, setProgress] = useState<Run | null>(null);
  const [running, setRunning] = useState(false);
  const [loading, setLoading] = useState<string | null>("Loading the last backlog…");
  const [error, setError] = useState<string | null>(null);
  const [inputError, setInputError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const demoCount = useRef(6);
  const lastRequest = useRef<SprintRequest | null>(null);
  const operation = useRef(0);
  const fileInput = useRef<HTMLInputElement>(null);

  const accept = useCallback((result: SprintAnalysis) => {
    setAnalysis(result);
    setHighlight([]);
    setCurrentContext({ type: "sprint", id: result.sprint_id });
    setCurrentAnalysis(result);
  }, [setCurrentAnalysis, setCurrentContext, setHighlight]);

  const run = useCallback(async (request: SprintRequest, refresh = false) => {
    const token = ++operation.current;
    lastRequest.current = request;
    setError(null);
    setInputError(null);
    setProgress(null);
    setRun(null);
    setRunning(true);
    setLoading(`Analyzing ${request.stories?.length ?? demoCount.current} stories`);
    try {
      const { result, run: finished } = await runSprint(request, {
        refresh,
        onProgress: (update) => {
          if (operation.current !== token) return;
          setProgress(update);
          setRun(update);
        },
      });
      if (operation.current !== token) return;
      setRun(finished);
      setProgress(finished);
      accept(result);
    } catch (reason) {
      if (operation.current === token) setError(reason instanceof Error ? reason.message : "Couldn't analyze the backlog. Check the backend and try again.");
    } finally {
      if (operation.current === token) { setLoading(null); setRunning(false); }
    }
  }, [accept, setRun]);

  useEffect(() => {
    const controller = new AbortController();
    const operations = operation;
    const token = ++operations.current;
    setCurrentContext(null);
    setCurrentAnalysis(null);
    setHighlight([]);
    void getDemoSprint().then((demo) => {
      if (!controller.signal.aborted && demo.stories.length) demoCount.current = demo.stories.length;
    }).catch(() => { /* The demo still runs with the backend's default stories. */ });
    const handoff = takeHandoff();
    if (handoff) {
      // A backlog attached on the story page: show it and analyse it straight away.
      void Promise.resolve().then(() => {
        setInput(JSON.stringify(handoff, null, 2));
        void run({ sprint_id: "sprint-attached", name: "Attached backlog", stories: handoff });
      });
      return () => controller.abort();
    }
    void getSavedSprint(controller.signal).then((result) => {
      if (!controller.signal.aborted && operation.current === token && result) accept(result);
    }).catch((reason: unknown) => {
      if (!controller.signal.aborted && operation.current === token) setError(reason instanceof Error ? reason.message : "Couldn't load the backlog. Check the backend and try again.");
    }).finally(() => {
      if (!controller.signal.aborted && operation.current === token) setLoading(null);
    });
    return () => { controller.abort(); operations.current++; };
  }, [accept, run, setCurrentAnalysis, setCurrentContext, setHighlight]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      void run({ sprint_id: "sprint-custom", name: "Your backlog", stories: parseStories(input) });
    } catch (reason) {
      setInputError(reason instanceof Error ? reason.message : "Check the stories and try again.");
    }
  }

  async function attach(file: File) {
    setInputError(null);
    try {
      const stories = await readAttachment(file);
      setInput(JSON.stringify(stories, null, 2));
    } catch (reason) {
      setInputError(reason instanceof Error ? reason.message : "Couldn't read that file.");
    }
  }

  return (
    <div className="min-w-0 space-y-5">
      <header>
        <h1>Sprint backlog</h1>
        <p className="mt-1 text-dense text-muted">Attach or paste a backlog. See risks and clashes before you assign work.</p>
      </header>
      <form onSubmit={submit} aria-label="Backlog input" className="space-y-3 rounded-xl border border-line bg-surface p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <label htmlFor="sprint-stories" className="text-dense font-medium">Stories</label>
          <div className="flex flex-wrap gap-2">
            <input ref={fileInput} type="file" accept={ATTACH_ACCEPT} className="sr-only" tabIndex={-1} aria-hidden="true"
              onChange={(event) => { const file = event.target.files?.[0]; if (file) void attach(file); event.target.value = ""; }} />
            <Button type="button" variant="outline" size="sm" disabled={Boolean(loading)} onClick={() => fileInput.current?.click()}><Paperclip aria-hidden="true" />Attach file</Button>
            <Button type="button" variant="outline" size="sm" disabled={Boolean(loading)} onClick={() => void run({ sprint_id: DEMO_SPRINT_ID })}>Demo backlog</Button>
          </div>
        </div>
        <Textarea id="sprint-stories" value={input} onChange={(event) => { setInput(event.target.value); setInputError(null); }} rows={5} disabled={Boolean(loading)}
          placeholder={"ST-201 | Raise transfer limits | Apply the new daily limit to mobile transfers\nST-202 | Add biometric login | Let customers log in with fingerprint"}
          aria-describedby={`sprint-input-help${inputError ? " sprint-input-error" : ""}`} aria-invalid={Boolean(inputError)} className="min-h-28 resize-y" />
        <p id="sprint-input-help" className="text-meta text-muted">JSON, CSV, or one story per line: ID | title | description.</p>
        {inputError && <p id="sprint-input-error" role="alert" className="text-dense text-impact-high">{inputError}</p>}
        <Button type="submit" disabled={Boolean(loading) || !input.trim()}>Analyze backlog</Button>
      </form>
      {error && <div role="alert" className="flex flex-wrap items-center gap-3 rounded-md border border-impact-high/40 bg-surface p-4"><p className="flex-1 text-body">{error}</p><Button type="button" variant="outline" disabled={Boolean(loading)} onClick={() => void run(lastRequest.current ?? { sprint_id: DEMO_SPRINT_ID })}>Try again</Button></div>}
      {loading && (running ? <RunProgress run={progress} title={loading} /> : <p role="status" aria-live="polite" className="py-4 text-body text-muted">{loading}</p>)}
      {analysis ? <section aria-label="Backlog results" aria-busy={Boolean(loading)} className="space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-body font-medium"><span className="text-muted">{analysis.sprint_id}</span> {analysis.name}</h2>
          <span className="flex items-center gap-1.5">
            <Button type="button" variant="outline" size="sm" disabled={Boolean(loading)} onClick={() => void run(lastRequest.current ?? { sprint_id: DEMO_SPRINT_ID }, true)}><RotateCw aria-hidden="true" />Re-run live</Button>
            <InfoTip label="re-run live">Runs every story again with live AI, skipping saved results. Takes a few minutes.</InfoTip>
          </span>
        </div>
        <SprintStatStrip kpis={analysis.kpis} />
        <RunNote analysis={analysis} run={progress?.sprint_result ? progress : null} />
        <SprintSummary analysis={analysis} />
        <section aria-labelledby="sprint-conflicts-heading" className="space-y-3">
          <h2 id="sprint-conflicts-heading" className="flex items-center gap-1.5">Clashes <InfoTip label="clashes">{explain.conflicts}</InfoTip></h2>
          <ConflictMap analysis={analysis} />
        </section>
        <div className="grid min-w-0 gap-6 border-t border-line pt-5 min-[1024px]:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          <StoryTable stories={analysis.stories} />
          <RiskByStoryChart stories={analysis.stories} />
        </div>
      </section> : !loading && <div className="flex min-h-[200px] items-center justify-center rounded-xl border border-dashed border-line px-4 text-center"><p className="text-body text-muted">Attach or paste a backlog, or try the demo backlog.</p></div>}
    </div>
  );
}
