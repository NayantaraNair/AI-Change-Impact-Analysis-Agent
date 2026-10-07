"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { BACKLOG_HANDOFF_KEY, readAttachment } from "@/lib/attach";
import { Button } from "@/components/ui/button";
import { useAppContext } from "@/components/shell/app-context";
import { ApiError, getDemoSprint, getReport, runStory, type TrackedResult } from "@/lib/api";
import type { Component, Run, StoryAnalysis, StoryInput } from "@/lib/types";
import { RunProgress } from "@/components/run/run-progress";
import { fetchArchitecture } from "./architecture";
import { demoExamples } from "./examples";
import { emptyStory, formFromStory, storyFromForm } from "./model";
import { AnalysisResults } from "./analysis-results";
import { StoryForm } from "./story-form";

type RequestKind = "story" | "report";
type Task = (onProgress: (run: Run) => void) => Promise<TrackedResult<StoryAnalysis>>;
const connectionError = "Can't reach the analysis server. Start the backend and try again.";

export function StoryAnalysisPage({ reportId }: { reportId: string | null }) {
  const { setCurrentAnalysis, setCurrentContext, setHighlight, setRun } = useAppContext();
  const [form, setForm] = useState(emptyStory);
  const [examples, setExamples] = useState<StoryInput[]>([]);
  const [examplesLoading, setExamplesLoading] = useState(true);
  const [examplesError, setExamplesError] = useState(false);
  const [components, setComponents] = useState<Component[]>([]);
  const [analysis, setAnalysis] = useState<StoryAnalysis | null>(null);
  const [progress, setProgress] = useState<Run | null>(null);
  const [pending, setPending] = useState<StoryInput | null>(null);
  const [loading, setLoading] = useState<RequestKind | null>(reportId ? "report" : null);
  const [error, setError] = useState<string | null>(null);
  const [sampleMismatch, setSampleMismatch] = useState(false);
  const [attachError, setAttachError] = useState<string | null>(null);
  const router = useRouter();
  const active = useRef(true);
  const sequence = useRef(0);
  const lastRequest = useRef<{ task: Task; kind: RequestKind; story?: StoryInput } | null>(null);

  const loadExamples = useCallback(async () => {
    setExamplesLoading(true);
    setExamplesError(false);
    try {
      const demo = await getDemoSprint();
      if (active.current) setExamples(demoExamples(demo.stories));
    } catch {
      if (active.current) setExamplesError(true);
    } finally {
      if (active.current) setExamplesLoading(false);
    }
  }, []);

  const run = useCallback(async (task: Task, kind: RequestKind, story?: StoryInput) => {
    const request = ++sequence.current;
    lastRequest.current = { task, kind, story };
    setLoading(kind);
    setPending(story ?? null);
    setProgress(null);
    setRun(null);
    setError(null);
    setAnalysis(null);
    setSampleMismatch(false);
    setHighlight([]);
    setCurrentAnalysis(null);
    setCurrentContext(null);
    try {
      const { result, run: finished } = await task((update) => {
        if (!active.current || request !== sequence.current) return;
        setProgress(update);
        setRun(update);
      });
      if (!active.current || request !== sequence.current) return;
      setRun(finished);
      setAnalysis(result);
      setCurrentAnalysis(result);
      setCurrentContext({ type: "story", id: result.story.id });
      if (kind === "report") setForm(formFromStory(result.story));
      setSampleMismatch(story ? JSON.stringify(result.story) !== JSON.stringify(story) : Boolean(reportId && result.story.id !== reportId));
    } catch (cause) {
      if (!active.current || request !== sequence.current) return;
      setError(cause instanceof ApiError && cause.status >= 400 && cause.status < 500
        ? `Couldn't load the analysis. ${cause.message}` : connectionError);
    } finally {
      if (active.current && request === sequence.current) setLoading(null);
    }
  }, [reportId, setCurrentAnalysis, setCurrentContext, setHighlight, setRun]);

  useEffect(() => {
    active.current = true;
    const controller = new AbortController();
    // Start external work after mount; obsolete responses cannot update a new route.
    void Promise.resolve().then(() => {
      if (!active.current || controller.signal.aborted) return;
      setHighlight([]);
      setCurrentAnalysis(null);
      setCurrentContext(null);
      void loadExamples();
      void fetchArchitecture(controller.signal).then((items) => {
        if (active.current && !controller.signal.aborted) setComponents(items);
      });
      if (reportId) void run(async () => ({ result: await getReport(reportId), run: null }), "report");
    });
    return () => {
      active.current = false;
      sequence.current += 1;
      controller.abort();
      setHighlight([]);
      setCurrentAnalysis(null);
      setCurrentContext(null);
    };
  }, [loadExamples, reportId, run, setCurrentAnalysis, setCurrentContext, setHighlight]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (loading || !form.title.trim() || !form.description.trim()) return;
    const story = storyFromForm(form, `ST-${crypto.randomUUID()}`);
    setForm(formFromStory(story));
    void run((onProgress) => runStory(story, { onProgress }), "story", story);
  }

  function rerunLive(story: StoryInput) {
    if (loading) return;
    void run((onProgress) => runStory(story, { refresh: true, onProgress }), "story", story);
  }

  async function attach(file: File) {
    setAttachError(null);
    try {
      const stories = await readAttachment(file);
      if (stories.length === 1) {
        setForm(formFromStory(stories[0]));
        return;
      }
      // A backlog belongs on the sprint page, which analyses stories together.
      try { window.sessionStorage.setItem(BACKLOG_HANDOFF_KEY, JSON.stringify(stories)); } catch { /* storage blocked */ }
      router.push("/sprint");
    } catch (reason) {
      setAttachError(reason instanceof Error ? reason.message : "Couldn't read that file.");
    }
  }

  function retry() {
    const request = lastRequest.current;
    if (request) void run(request.task, request.kind, request.story);
  }

  return (
    <div className="min-w-0">
      <StoryForm value={form} onChange={setForm} onSubmit={submit} examples={examples}
        onExample={(story) => { setForm(formFromStory(story)); setError(null); }}
        examplesLoading={examplesLoading} examplesError={examplesError} onRetryExamples={() => void loadExamples()} busy={Boolean(loading)} onAttach={(file) => void attach(file)} attachError={attachError} />
      {error && <div role="alert" className="mb-4 flex flex-wrap items-center gap-3 rounded-md border border-impact-high/40 bg-surface p-4"><p className="flex-1 text-body">{error}</p><Button type="button" variant="outline" onClick={retry}>Try again</Button></div>}
      {loading === "report" ? <p role="status" className="border-y border-line py-4 text-muted">Loading saved analysis…</p> : loading ? <RunProgress run={progress} title={`Analyzing ${pending?.id ?? "story"}`} /> : analysis ? (
        <>
          {sampleMismatch && <p role="status" className="mb-4 border-l-2 border-chalk bg-surface px-4 py-3 text-dense text-muted">Showing the available sample report for {analysis.story.id}: {analysis.story.title}. Start the backend to analyze the requested story.</p>}
          <AnalysisResults key={`${analysis.story.id}-${analysis.created_at}`} analysis={analysis} components={components} run={progress?.story_result?.story.id === analysis.story.id ? progress : null} onRerunLive={() => rerunLive(analysis.story)} />
        </>
      ) : !error && <div className="flex min-h-[380px] items-center justify-center border-y border-line bg-surface/40"><p className="text-body text-muted">Attach or paste a story, then select Analyze.</p></div>}
    </div>
  );
}
