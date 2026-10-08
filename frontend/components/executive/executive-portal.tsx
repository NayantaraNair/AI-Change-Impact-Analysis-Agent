"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { DependencyGraph } from "@/components/graph";
import { RunProgress } from "@/components/run/run-progress";
import { useAppContext } from "@/components/shell/app-context";
import { parseStories } from "@/components/sprint/model";
import { getSavedSprint } from "@/components/sprint/data";
import { Button } from "@/components/ui/button";
import { InfoTip } from "@/components/ui/info-tip";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { getDemoPortfolio, runSprint, runStory } from "@/lib/api";
import { affectedCustomers, businessImpact, levelChip, levelWord, riskLevel } from "@/lib/business";
import type { DemoSprint, Run, SprintAnalysis, StoryAnalysis, StoryInput } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ChangeTable, ConflictEngine, Decision, ImpactHeatmap, PortfolioKpis, tips } from "./portfolio-views";
import { ReasoningTimeline } from "./reasoning-timeline";

type Mode = "backlog" | "feature";
type Result = { kind: "sprint"; sprint: SprintAnalysis } | { kind: "feature"; story: StoryAnalysis };

const PORTFOLIO_ID = "portfolio-q4";

function Section({ title, tip, children, action }: { title: string; tip?: string; children: ReactNode; action?: ReactNode }) {
  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-1.5">{title}{tip && <InfoTip label={title.toLowerCase()}>{tip}</InfoTip>}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

export function ExecutivePortal() {
  const { setRun, setCurrentAnalysis, setCurrentContext, setHighlight } = useAppContext();
  const [mode, setMode] = useState<Mode>("backlog");
  const [backlog, setBacklog] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [examples, setExamples] = useState<DemoSprint | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [progress, setProgress] = useState<Run | null>(null);
  const [busy, setBusy] = useState<string | null>("Loading the portfolio…");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const token = useRef(0);

  const show = useCallback((next: Result) => {
    setResult(next);
    const stories = next.kind === "sprint" ? next.sprint.stories : [next.story];
    const pick = [...stories].sort((a, b) => b.risk.overall - a.risk.overall)[0];
    setSelectedId(pick?.story.id ?? null);
    setHighlight([]);
    if (next.kind === "sprint") {
      setCurrentAnalysis(next.sprint);
      setCurrentContext({ type: "sprint", id: next.sprint.sprint_id });
    } else {
      setCurrentAnalysis(next.story);
      setCurrentContext({ type: "story", id: next.story.story.id });
    }
  }, [setCurrentAnalysis, setCurrentContext, setHighlight]);

  useEffect(() => {
    const controller = new AbortController();
    const mine = ++token.current;
    void getDemoPortfolio().then((demo) => { if (!controller.signal.aborted) setExamples(demo); }).catch(() => {});
    void getSavedSprint(controller.signal, PORTFOLIO_ID).then((sprint) => {
      if (!controller.signal.aborted && token.current === mine && sprint) show({ kind: "sprint", sprint });
    }).catch(() => { /* An empty portfolio is a valid start. */ })
      .finally(() => { if (!controller.signal.aborted && token.current === mine) setBusy(null); });
    return () => controller.abort();
  }, [show]);

  async function analyse(work: (onProgress: (run: Run) => void) => Promise<Result & { run: Run | null }>, label: string) {
    const mine = ++token.current;
    setError(null);
    setProgress(null);
    setRun(null);
    setRunning(true);
    setBusy(label);
    try {
      const outcome = await work((update) => { if (token.current === mine) { setProgress(update); setRun(update); } });
      if (token.current !== mine) return;
      setRun(outcome.run);
      setProgress(outcome.run);
      show(outcome.kind === "sprint" ? { kind: "sprint", sprint: outcome.sprint } : { kind: "feature", story: outcome.story });
    } catch (reason) {
      if (token.current === mine) setError(reason instanceof Error ? reason.message : "Couldn't analyse that. Check the server and try again.");
    } finally {
      if (token.current === mine) { setBusy(null); setRunning(false); }
    }
  }

  function analyseBacklog(stories: StoryInput[] | null, name = "Your backlog") {
    const request = stories ? { sprint_id: `portfolio-${crypto.randomUUID().slice(0, 8)}`, name, stories } : { sprint_id: PORTFOLIO_ID };
    void analyse(async (onProgress) => {
      const { result: sprint, run } = await runSprint(request, { onProgress });
      return { kind: "sprint", sprint, run };
    }, `Analysing ${stories?.length ?? examples?.stories.length ?? 5} changes`);
  }

  function submitBacklog(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try { analyseBacklog(parseStories(backlog)); } catch (reason) { setError(reason instanceof Error ? reason.message : "Check the backlog and try again."); }
  }

  function submitFeature(event: FormEvent<HTMLFormElement>, story?: StoryInput) {
    event?.preventDefault();
    const feature: StoryInput = story ?? {
      id: `FT-${crypto.randomUUID().slice(0, 6).toUpperCase()}`, title: title.trim(), description: description.trim(),
      type: "epic", acceptance_criteria: [],
    };
    void analyse(async (onProgress) => {
      const { result: analysis, run } = await runStory(feature, { onProgress });
      return { kind: "feature", story: analysis, run };
    }, `Analysing ${feature.title}`);
  }

  const analyses = result ? (result.kind === "sprint" ? result.sprint.stories : [result.story]) : [];
  const selected = analyses.find((analysis) => analysis.story.id === selectedId) ?? analyses[0];
  const featureExamples = examples?.stories.filter((story) => story.id.startsWith("EX-")) ?? [];

  return (
    <div className="mx-auto max-w-[1400px] space-y-8">
      <header>
        <h1>Portfolio view</h1>
        <p className="mt-1 text-body text-muted">What every change will touch, how risky it is and whether it is ready, before it is planned.</p>
      </header>

      <div className="rounded-xl border border-line bg-surface">
        <div role="tablist" aria-label="Input" className="flex border-b border-line">
          {([["backlog", "Sprint backlog"], ["feature", "New major feature"]] as const).map(([id, label]) => (
            <button key={id} type="button" role="tab" aria-selected={mode === id} onClick={() => setMode(id)}
              className={cn("px-5 py-3 text-dense font-medium transition-colors duration-150", mode === id ? "border-b-2 border-chalk text-text" : "text-muted hover:text-text")}>{label}</button>
          ))}
        </div>
        {mode === "backlog" ? (
          <form onSubmit={submitBacklog} className="space-y-3 p-5" aria-label="Sprint backlog">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-dense text-muted">Paste the stories planned for the sprint: JSON, CSV, or one per line as ID | title | description.</p>
              <div className="flex gap-2">
                <Button type="button" variant="outline" size="sm" disabled={Boolean(busy)} onClick={() => analyseBacklog(null)}>Example portfolio</Button>
              </div>
            </div>
            <Textarea value={backlog} onChange={(event) => setBacklog(event.target.value)} rows={4} disabled={Boolean(busy)} aria-label="Backlog stories"
              placeholder={"EX-201 | OTP login | Add a one-time passcode step to customer login\nEX-202 | Password reset | Let customers reset a forgotten password"} />
            <Button type="submit" disabled={Boolean(busy) || !backlog.trim()}>Analyse backlog</Button>
          </form>
        ) : (
          <form onSubmit={(event) => submitFeature(event)} className="space-y-3 p-5" aria-label="New major feature">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-dense text-muted">Describe the feature in business terms. ImpactIQ maps it to the systems it will touch.</p>
              {featureExamples.length > 0 && <div className="flex flex-wrap gap-2">
                {featureExamples.map((story) => (
                  <Button key={story.id} type="button" variant="outline" size="sm" disabled={Boolean(busy)}
                    onClick={(event) => { setTitle(story.title); setDescription(story.description); submitFeature(event as unknown as FormEvent<HTMLFormElement>, story); }}>
                    {story.title.split(" for ")[0]}
                  </Button>
                ))}
              </div>}
            </div>
            <Input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Feature name, e.g. OTP MFA login" disabled={Boolean(busy)} aria-label="Feature name" />
            <Textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={3} disabled={Boolean(busy)} aria-label="Feature description"
              placeholder="What changes for customers and the bank, and which channels or systems are involved." />
            <Button type="submit" disabled={Boolean(busy) || !title.trim() || !description.trim()}>Analyse feature</Button>
          </form>
        )}
      </div>

      {error && <p role="alert" className="rounded-xl border border-impact-high/40 bg-surface p-4 text-body">{error}</p>}
      {busy && (running ? <RunProgress run={progress} title={busy} hide={["testing"]} /> : <p role="status" className="text-body text-muted">{busy}</p>)}

      {result && analyses.length > 0 && (
        <div className="space-y-8" aria-busy={Boolean(busy)}>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <p className="text-section font-semibold">{result.kind === "sprint" ? result.sprint.name : result.story.story.title}</p>
            <p className="text-meta text-muted">{result.kind === "sprint" ? `${analyses.length} changes` : "Single feature"}</p>
          </div>
          <PortfolioKpis analyses={analyses} />

          {result.kind === "feature" && selected && <FeatureSummary analysis={selected} />}
          {result.kind === "sprint" && (
            <Section title="Changes">
              <ChangeTable analyses={analyses} selectedId={selected?.story.id ?? null} onSelect={setSelectedId} />
            </Section>
          )}

          <Section title="Impact heatmap" tip={tips.heatmap}>
            <ImpactHeatmap analyses={analyses} selectedId={selected?.story.id ?? null} onSelect={setSelectedId} />
          </Section>

          {result.kind === "sprint" && (
            <Section title="Conflict engine" tip={tips.conflict}>
              <ConflictEngine sprint={result.sprint} />
            </Section>
          )}

          {selected && (
            <div className="space-y-8">
              <Section title={`Dependency graph · ${selected.story.id}`}>
                <DependencyGraph graph={selected.graph} />
              </Section>
              <Section title="AI reasoning timeline">
                <div className="rounded-xl border border-line bg-surface p-5"><ReasoningTimeline analysis={selected} run={progress} /></div>
              </Section>
            </div>
          )}
        </div>
      )}
      {!result && !busy && <p className="rounded-xl border border-dashed border-line p-10 text-center text-body text-muted">Analyse a sprint backlog or a new feature, or open the example portfolio.</p>}
    </div>
  );
}

/** The single-feature brief: the five answers an executive asks first. */
function FeatureSummary({ analysis }: { analysis: StoryAnalysis }) {
  const systems = analysis.graph.nodes.filter((node) => node.hop !== null).sort((a, b) => (a.hop ?? 9) - (b.hop ?? 9));
  const rows: [string, ReactNode, string?][] = [
    ["Business impact", <Chip key="b" level={businessImpact(analysis)} />, tips.business],
    ["Affected customers", <Chip key="c" level={affectedCustomers(analysis)} />, tips.customers],
    ["Affected systems", <span key="s">{systems.slice(0, 6).map((node) => node.label).join(", ")}{systems.length > 6 ? ` +${systems.length - 6} more` : ""}</span>],
    ["Risk", <span key="r" className="flex items-center gap-2"><Chip level={riskLevel(analysis.risk.overall)} /><span className="text-dense text-muted tabular-nums">{analysis.risk.overall}/100</span></span>],
    ["Release readiness", <span key="rr" className="flex items-center gap-3"><span className="text-section numeral">{analysis.release.confidence}%</span><Decision decision={analysis.release.decision} /></span>, tips.readiness],
  ];
  return (
    <section aria-label="Feature summary" className="rounded-xl border border-line bg-surface">
      <dl className="divide-y divide-line">
        {rows.map(([label, value, tip]) => (
          <div key={label} className="grid grid-cols-[12rem_minmax(0,1fr)] items-center gap-4 px-5 py-3">
            <dt className="flex items-center gap-1 text-dense text-muted">{label}{tip && <InfoTip label={label.toLowerCase()}>{tip}</InfoTip>}</dt>
            <dd className="text-body">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function Chip({ level }: { level: "low" | "medium" | "high" }) {
  return <span className={cn("inline-flex rounded-full border px-2.5 py-0.5 text-dense font-medium", levelChip[level])}>{levelWord[level]}</span>;
}
