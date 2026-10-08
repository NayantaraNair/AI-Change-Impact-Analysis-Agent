"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Check, Copy, RefreshCw } from "lucide-react";
import { useAppContext } from "@/components/shell/app-context";
import { AttemptLine, SourceBadge, StageIcon } from "@/components/run/parts";
import { attemptSummary, formatElapsed, modelsUsed } from "@/components/run/model";
import { Button } from "@/components/ui/button";
import { InfoTip } from "@/components/ui/info-tip";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getDebugInfo, getRecentRuns, getRun } from "@/lib/api";
import { explain, outcomeLabel, providerName, splitProvider } from "@/lib/explain";
import type { DebugInfo, Run } from "@/lib/types";
import { cn } from "@/lib/utils";

const statusTone: Record<Run["status"], string> = {
  running: "text-model", succeeded: "text-text", failed: "text-impact-high",
};

/** Everything behind the current page: the run, every model call, the log and the setup. */
export function DebugPanel() {
  const { debugOpen, setDebugOpen, run: pageRun, currentAnalysis, usingSampleData } = useAppContext();
  const [info, setInfo] = useState<DebugInfo | null>(null);
  const [history, setHistory] = useState<Run[]>([]);
  const [picked, setPicked] = useState<Run | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [debugInfo, runs] = await Promise.all([getDebugInfo(), getRecentRuns()]);
      setInfo(debugInfo);
      setHistory(runs);
      setError(null);
    } catch {
      setError("Couldn't reach the analysis server for debug details. The page may be showing sample data.");
    }
  }, []);

  useEffect(() => {
    if (!debugOpen) return;
    void Promise.resolve().then(refresh);
    const timer = window.setInterval(() => void refresh(), 3_000);
    return () => window.clearInterval(timer);
  }, [debugOpen, refresh]);

  // The page's live run wins; otherwise show what the user picked from history.
  const run = picked && picked.id !== pageRun?.id ? picked : pageRun;

  async function pick(id: string) {
    try { setPicked(await getRun(id)); } catch (reason) { setError(reason instanceof Error ? reason.message : "Couldn't load that run."); }
  }

  return (
    <Sheet open={debugOpen} onOpenChange={setDebugOpen}>
      <SheetContent id="debug-drawer" side="right" className="max-w-[calc(100vw-56px)] gap-0 overflow-hidden bg-surface data-[side=right]:w-[680px] data-[side=right]:sm:max-w-[680px]">
        <div className="border-b border-line px-5 pt-5 pb-3 pr-12">
          <SheetTitle className="text-section font-semibold">Debug</SheetTitle>
          <SheetDescription className="mt-1 text-meta text-muted">How the current analysis ran: steps, every model call and fallback, the log and the server setup.</SheetDescription>
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-meta text-muted">
            <span>Data: <span className="text-text">{usingSampleData ? "Sample data (server unreachable or mock mode)" : "Live server"}</span></span>
            {run && <span>Run <span className="text-text">{run.id}</span> · <span className={statusTone[run.status]}>{run.status}</span> · {formatElapsed(run.elapsed_ms)}</span>}
            <Button type="button" variant="ghost" size="xs" onClick={() => void refresh()}><RefreshCw aria-hidden="true" />Refresh</Button>
          </div>
          {error && <p role="alert" className="mt-2 text-meta text-warn">{error}</p>}
        </div>
        <Tabs defaultValue="run" className="min-h-0 flex-1 gap-0">
          <TabsList variant="line" aria-label="Debug sections" className="h-11! w-full justify-start overflow-x-auto rounded-none border-b border-line px-3">
            {[["run", "Run"], ["calls", "Model calls"], ["log", "Log"], ["setup", "Setup"], ["history", "History"], ["raw", "Raw JSON"]].map(([value, label]) => (
              <TabsTrigger key={value} value={value} className="flex-none px-3 text-dense after:bottom-0!">{label}</TabsTrigger>
            ))}
          </TabsList>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
            <TabsContent value="run"><RunTab run={run} /></TabsContent>
            <TabsContent value="calls"><CallsTab run={run} /></TabsContent>
            <TabsContent value="log"><LogTab run={run} /></TabsContent>
            <TabsContent value="setup"><SetupTab info={info} /></TabsContent>
            <TabsContent value="history"><HistoryTab runs={history} current={run?.id ?? null} onPick={(id) => void pick(id)} /></TabsContent>
            <TabsContent value="raw"><RawTab value={run?.status === "running" ? run : currentAnalysis ?? run} /></TabsContent>
          </div>
        </Tabs>
      </SheetContent>
    </Sheet>
  );
}

function Empty({ children }: { children: ReactNode }) {
  return <p className="py-6 text-dense text-muted">{children}</p>;
}

function RunTab({ run }: { run: Run | null }) {
  if (!run) return <Empty>No run yet on this page. Analyze a story or sprint, or pick an earlier run from History.</Empty>;
  const { calls, failed } = attemptSummary(run);
  const inFlight = run.attempts.filter((attempt) => attempt.outcome === "running").length;
  const models = modelsUsed(run);
  const groups = [...new Set(run.stages.map((stage) => stage.story_id))];
  return (
    <div className="space-y-5">
      <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-dense sm:grid-cols-4">
        <div><dt className="text-meta text-muted">Kind</dt><dd className="capitalize">{run.kind}</dd></div>
        <div><dt className="text-meta text-muted">Elapsed</dt><dd className="tabular-nums">{formatElapsed(run.elapsed_ms)}</dd></div>
        <div><dt className="text-meta text-muted">Model calls</dt><dd className="tabular-nums">{calls}{inFlight ? ` + ${inFlight} in flight` : ""}</dd></div>
        <div><dt className="text-meta text-muted">Fell through</dt><dd className={cn("tabular-nums", failed && "text-warn")}>{failed}</dd></div>
      </dl>
      <p className="text-dense"><span className="text-muted">Title: </span>{run.title}</p>
      {run.error && <p role="alert" className="rounded-md border border-impact-high/40 px-3 py-2 text-dense text-impact-high">{run.error}</p>}
      {models.length > 0 && (
        <div>
          <h3 className="text-meta font-medium text-muted">Models that wrote output</h3>
          <ul className="mt-2 space-y-1 text-dense">{models.map(({ label, stages }) => { const { provider, model } = splitProvider(label); return <li key={label}>{provider} <span className="text-muted">· {model} · {stages} stage{stages === 1 ? "" : "s"}</span></li>; })}</ul>
        </div>
      )}
      {groups.map((group) => (
        <div key={group ?? "sprint"}>
          <h3 className="mb-1 text-meta font-medium text-muted">{group ?? "Sprint-wide steps"}</h3>
          <ul className="divide-y divide-line border-y border-line">
            {run.stages.filter((stage) => stage.story_id === group).map((stage) => (
              <li key={stage.stage} className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-x-3 py-2 text-dense">
                <StageIcon stage={stage} className="mt-0.5" />
                <div className="min-w-0">
                  <p className="flex flex-wrap items-center gap-2"><span>{stage.label}</span><SourceBadge stage={stage} /></p>
                  {stage.message && <p className="text-meta text-muted">{stage.message}</p>}
                  {stage.provider && stage.source === "llm" && <p className="text-meta text-muted">Model: {stage.provider}</p>}
                </div>
                <span className="text-meta tabular-nums text-muted">{stage.status === "pending" ? "pending" : formatElapsed(stage.elapsed_ms)}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function CallsTab({ run }: { run: Run | null }) {
  if (!run) return <Empty>No run selected.</Empty>;
  if (!run.attempts.length) return <Empty>{run.stages.every((stage) => stage.source === "fixture") ? "This run served the saved demo result, so no model was called." : "No model calls in this run. Without API keys every stage uses code and built-in templates."}</Empty>;
  const byOutcome = new Map<string, number>();
  for (const attempt of run.attempts) byOutcome.set(attempt.outcome, (byOutcome.get(attempt.outcome) ?? 0) + 1);
  return (
    <div className="space-y-4">
      <p className="flex items-center gap-1.5 text-meta text-muted">Calls in order. A failed call passes the work to the next provider. <InfoTip label="fallback chain">{explain.chain}</InfoTip></p>
      <ul className="flex flex-wrap gap-2 text-meta">{[...byOutcome].map(([outcome, total]) => <li key={outcome} className="rounded-full border border-line px-2 py-0.5">{outcomeLabel[outcome]} <span className="tabular-nums text-muted">{total}</span></li>)}</ul>
      <ol className="space-y-3">
        {run.attempts.map((attempt) => (
          <li key={attempt.id} className="rounded-md border border-line px-3 py-2">
            <p className="mb-1 text-meta text-muted">#{attempt.id} · {attempt.story_id ?? "sprint"} · {attempt.stage ?? "call"} · {attempt.tier} tier · started {new Date(attempt.started_at).toLocaleTimeString()}{attempt.prompt_tokens !== null ? ` · ${attempt.prompt_tokens.toLocaleString()} prompt tokens` : ""}</p>
            <ul><AttemptLine attempt={attempt} /></ul>
          </li>
        ))}
      </ol>
    </div>
  );
}

function LogTab({ run }: { run: Run | null }) {
  if (!run) return <Empty>No run selected.</Empty>;
  if (!run.log.length) return <Empty>Nothing logged yet.</Empty>;
  return (
    <ol className="space-y-1.5 text-meta">
      {run.log.map((entry, index) => (
        <li key={index} className={cn("grid grid-cols-[auto_auto_minmax(0,1fr)] gap-x-3", entry.level === "warning" ? "text-warn" : entry.level === "error" ? "text-impact-high" : "text-text")}>
          <span className="tabular-nums text-muted">{new Date(entry.at).toLocaleTimeString()}</span>
          <span className="w-14 text-muted">{entry.level}</span>
          <span className="min-w-0">{entry.story_id ? <span className="text-muted">{entry.story_id} · </span> : null}{entry.message}</span>
        </li>
      ))}
    </ol>
  );
}

function SetupTab({ info }: { info: DebugInfo | null }) {
  if (!info) return <Empty>Loading the server setup…</Empty>;
  return (
    <div className="space-y-6 text-dense">
      <section>
        <h3 className="flex items-center gap-1.5 text-body font-medium">Model chain <InfoTip label="fallback chain">{explain.chain}</InfoTip></h3>
        <p className="mt-1 text-meta text-muted">{info.llm_disabled ? "Models are disabled (LLM_DISABLED=1): every stage uses code and templates." : "Tried in this order for every call. API keys are never shown."}</p>
        <ol className="mt-3 divide-y divide-line border-y border-line">
          {info.providers.map((provider) => (
            <li key={`${provider.name}-${provider.model}`} className="grid grid-cols-[1.5rem_minmax(0,1fr)_auto] items-baseline gap-x-3 py-2">
              <span className="tabular-nums text-muted">{provider.order}</span>
              <span className="min-w-0"><span className="font-medium">{providerName(provider.name)}</span> <span className="text-muted">· {provider.model} · {provider.host}{provider.tool_calling_only ? " · JSON via tool calling" : ""}</span></span>
              <span className={cn("text-meta", !provider.configured ? "text-muted" : provider.cooling_down_s ? "text-warn" : "text-text")}>{!provider.configured ? "No key" : provider.cooling_down_s ? `Cooling down ${provider.cooling_down_s} s` : "Ready"}</span>
            </li>
          ))}
          <li className="grid grid-cols-[1.5rem_minmax(0,1fr)] gap-x-3 py-2"><span className="tabular-nums text-muted">{info.providers.length + 1}</span><span className="text-muted">Built-in fallback: keyword matching and templates</span></li>
        </ol>
        <p className="mt-2 text-meta text-muted">Strong-tier calls (tests and release plans) use {info.strong_tier_model} on Token Harbor.</p>
      </section>
      <section>
        <h3 className="text-body font-medium">Limits</h3>
        <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-3">
          <div><dt className="text-meta text-muted">Per-call timeout</dt><dd className="tabular-nums">{info.timeout_s} s</dd></div>
          <div><dt className="text-meta text-muted">Calls at once</dt><dd className="tabular-nums">{info.max_concurrent_calls}</dd></div>
          <div><dt className="text-meta text-muted">Stage cache</dt><dd>{info.cache_enabled ? "On (identical input reuses results)" : "Off"}</dd></div>
        </dl>
        <h4 className="mt-4 text-meta font-medium text-muted">Output token caps by stage</h4>
        <ul className="mt-1 grid grid-cols-2 gap-x-6 gap-y-1 sm:grid-cols-3">{Object.entries(info.max_tokens).map(([stage, tokens]) => <li key={stage} className="flex justify-between gap-3"><span className="capitalize text-muted">{stage}</span><span className="tabular-nums">{tokens.toLocaleString()}</span></li>)}</ul>
      </section>
      <section>
        <h3 className="text-body font-medium">Saved demo results</h3>
        <p className="mt-1 text-meta text-muted">Unchanged demo stories and the demo sprint load these instantly, with no model calls. Edit any field to run live.</p>
        <p className="mt-2 text-meta">{info.fixtures_available.filter((name) => !name.startsWith("chat-")).join(", ") || "None"}</p>
      </section>
    </div>
  );
}

function HistoryTab({ runs, current, onPick }: { runs: Run[]; current: string | null; onPick: (id: string) => void }) {
  if (!runs.length) return <Empty>No runs since the backend started.</Empty>;
  return (
    <ul className="divide-y divide-line border-y border-line">
      {runs.map((run) => {
        const { calls, failed } = attemptSummary(run);
        return (
          <li key={run.id}>
            <button type="button" onClick={() => onPick(run.id)} aria-current={run.id === current ? "true" : undefined} className="grid w-full grid-cols-[minmax(0,1fr)_auto] gap-x-3 px-1 py-2 text-left text-dense hover:bg-surface-raised aria-[current=true]:bg-surface-raised">
              <span className="min-w-0"><span className="block truncate">{run.title}</span><span className="text-meta text-muted capitalize">{run.kind} · {new Date(run.started_at).toLocaleTimeString()} · {calls} calls{failed ? `, ${failed} fell through` : ""}</span></span>
              <span className={cn("text-meta", statusTone[run.status])}>{run.status} · {formatElapsed(run.elapsed_ms)}</span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function RawTab({ value }: { value: unknown }) {
  const [copied, setCopied] = useState(false);
  if (!value) return <Empty>Nothing to show yet.</Empty>;
  const text = JSON.stringify(value, null, 2);
  async function copy() {
    try { await navigator.clipboard.writeText(text); setCopied(true); window.setTimeout(() => setCopied(false), 1500); } catch { /* Clipboard can be blocked; the text is still selectable. */ }
  }
  return (
    <div className="space-y-2">
      <Button type="button" variant="outline" size="sm" onClick={() => void copy()}>{copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}{copied ? "Copied" : "Copy JSON"}</Button>
      <pre className="max-h-[60vh] overflow-auto rounded-md border border-line bg-canvas p-3 text-meta leading-relaxed">{text}</pre>
    </div>
  );
}
