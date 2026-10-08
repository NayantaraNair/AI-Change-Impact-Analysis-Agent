"use client";

import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import { ArrowRight, Boxes, Database, FileCode, GitBranch, Network, TestTube2 } from "lucide-react";
import { RunProgress } from "@/components/run/run-progress";
import { useAppContext } from "@/components/shell/app-context";
import { Button } from "@/components/ui/button";
import { InfoTip } from "@/components/ui/info-tip";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { getDemoCodebase, runCodebase } from "@/lib/api";
import { classifyProvider, splitProvider } from "@/lib/explain";
import type { CodebaseAnalysis, CodebaseRequest, Run, TestCategory } from "@/lib/types";
import { cn } from "@/lib/utils";
import { CodeTree } from "./code-tree";

const categoryTone: Record<TestCategory, string> = {
  functional: "border-chalk/40 text-text",
  api: "border-model/50 text-model",
  unit: "border-line-strong text-muted",
  integration: "border-impact-med/50 text-impact-med",
  security: "border-impact-high/50 text-impact-high",
  regression: "border-impact-low/50 text-impact-low",
};

function Chips({ items, empty, mono = false }: { items: string[]; empty: string; mono?: boolean }) {
  if (!items.length) return <p className="text-dense text-muted">{empty}</p>;
  return <ul className="flex flex-wrap gap-1.5">{items.map((item) => <li key={item} className={cn("rounded-md border border-line bg-canvas px-2 py-0.5 text-dense", mono && "tabular-nums")}>{item}</li>)}</ul>;
}

function Field({ label, icon: Icon, children }: { label: string; icon: typeof Boxes; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <p className="flex items-center gap-1.5 text-meta font-medium text-muted"><Icon aria-hidden="true" className="size-3.5" />{label}</p>
      {children}
    </div>
  );
}

/** Story -> services -> files -> classes, APIs, tables -> tests, with counts. */
function FlowStrip({ analysis }: { analysis: CodebaseAnalysis }) {
  const classes = analysis.services.reduce((sum, item) => sum + item.classes.length, 0);
  const apis = analysis.services.reduce((sum, item) => sum + item.apis.length, 0);
  const tables = new Set(analysis.services.flatMap((item) => item.tables)).size;
  const steps = [
    { label: "User story", value: analysis.story.id, by: "map_services" },
    { label: "Services", value: String(analysis.services.length), by: "map_services" },
    { label: "Files", value: String(analysis.files.length), by: "map_files" },
    { label: "Classes · APIs · DBs", value: `${classes} · ${apis} · ${tables}`, by: "map_classes" },
    { label: "Developer tests", value: String(analysis.tests.length), by: "plan_tests" },
  ];
  return (
    <ol className="flex flex-wrap items-stretch gap-2" aria-label="AI flow">
      {steps.map((step, index) => {
        const label = analysis.providers_used[step.by];
        const ai = label && classifyProvider(label) === "llm";
        return (
          <li key={step.label} className="flex items-center gap-2">
            <div className="rounded-lg border border-line bg-surface px-4 py-2.5">
              <p className="text-meta text-muted">{step.label}</p>
              <p className="text-section numeral">{step.value}</p>
              {index > 0 && <p className={cn("text-[11px]", ai ? "text-model" : "text-muted")}>{ai ? `AI · ${splitProvider(label).provider}` : "Rules"}</p>}
            </div>
            {index < steps.length - 1 && <ArrowRight aria-hidden="true" className="size-4 text-muted" />}
          </li>
        );
      })}
    </ol>
  );
}

function ImpactPanel({ analysis, selected, onSelect }: { analysis: CodebaseAnalysis; selected: string | null; onSelect: (path: string) => void }) {
  const file = selected ? analysis.repo.files.find((item) => item.path === selected) : undefined;
  const impacted = selected ? analysis.files.find((item) => item.path === selected) : undefined;
  return (
    <div className="space-y-4">
      {selected && (
        <section className="rounded-xl border border-chalk/30 bg-surface p-4" aria-label="Selected file">
          <p className="text-meta text-muted">Selected file</p>
          <p className="truncate font-semibold" title={selected}>{selected}</p>
          {impacted ? <p className="mt-1 text-dense"><span className="text-impact-high">Changes: </span>{impacted.reason}</p> : <p className="mt-1 text-dense text-muted">Not changed by this story.</p>}
          {file && <div className="mt-3 grid gap-3 sm:grid-cols-3">
            <Field label="Classes" icon={Boxes}><Chips items={file.classes.slice(0, 10)} empty="None found" /></Field>
            <Field label="APIs" icon={Network}><Chips items={file.apis} empty="None" /></Field>
            <Field label="Tables" icon={Database}><Chips items={file.tables} empty="None" /></Field>
          </div>}
        </section>
      )}
      {analysis.services.map((service) => (
        <section key={service.service} className="rounded-xl border border-line bg-surface p-4" aria-label={service.service}>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h3 className="text-section font-semibold">{service.service}</h3>
            <span className="text-meta text-muted">{service.files.length} file{service.files.length === 1 ? "" : "s"}</span>
          </div>
          <p className="mt-1 text-dense text-muted">{service.reason}</p>
          <div className="mt-4 space-y-3">
            <Field label="Affected classes" icon={Boxes}><Chips items={service.classes} empty="No classes found in the changed files" /></Field>
            <Field label="Affected APIs" icon={Network}><Chips items={service.apis} empty="No API routes in the changed files" mono /></Field>
            <Field label="Databases" icon={Database}><Chips items={service.tables} empty="No tables touched" /></Field>
            <Field label="Files" icon={FileCode}>
              <ul className="space-y-1">
                {service.files.map((path) => (
                  <li key={path}><button type="button" onClick={() => onSelect(path)} className={cn("w-full truncate text-left text-dense link-ui", selected === path && "font-semibold")} title={path}>{path}</button></li>
                ))}
              </ul>
            </Field>
          </div>
        </section>
      ))}
      {!analysis.services.length && <p className="rounded-xl border border-dashed border-line p-6 text-center text-body text-muted">No service in this repository matched the story. Add more detail, or check the URL points at the right folder.</p>}
    </div>
  );
}

function TestPlan({ analysis }: { analysis: CodebaseAnalysis }) {
  return (
    <ol className="divide-y divide-line rounded-xl border border-line bg-surface">
      {analysis.tests.map((test, index) => (
        <li key={test.id} className="grid gap-x-4 gap-y-1 px-5 py-3 md:grid-cols-[2rem_7.5rem_minmax(0,1fr)]">
          <span className="text-dense tabular-nums text-muted">{index + 1}</span>
          <span><span className={cn("inline-flex rounded-full border px-2 py-0.5 text-meta font-medium capitalize", categoryTone[test.category])}>{test.category === "api" ? "API" : test.category}</span></span>
          <div className="min-w-0">
            <p className="font-medium">{test.title}</p>
            <p className="text-meta text-muted">Target: <span className="text-text">{test.target}</span></p>
            <details className="group mt-1">
              <summary className="cursor-pointer list-none text-meta link-ui w-fit">Steps and expected result</summary>
              <ol className="mt-2 list-decimal space-y-1 pl-5 text-dense text-muted">{test.steps.map((step, i) => <li key={i}>{step}</li>)}</ol>
              <p className="mt-1 text-dense"><span className="text-muted">Expected: </span>{test.expected}</p>
            </details>
          </div>
        </li>
      ))}
    </ol>
  );
}

export function CodebasePortal() {
  const { setRun } = useAppContext();
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [details, setDetails] = useState("");
  const [demo, setDemo] = useState<CodebaseRequest | null>(null);
  const [analysis, setAnalysis] = useState<CodebaseAnalysis | null>(null);
  const [progress, setProgress] = useState<Run | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const token = useRef(0);

  useEffect(() => { void getDemoCodebase().then(setDemo); }, []);

  async function analyse(request: CodebaseRequest) {
    const mine = ++token.current;
    setBusy(true);
    setError(null);
    setProgress(null);
    setRun(null);
    try {
      const { result, run } = await runCodebase(request, { onProgress: (update) => { if (token.current === mine) { setProgress(update); setRun(update); } } });
      if (token.current !== mine) return;
      setRun(run);
      setAnalysis(result);
      setSelected(result.files[0]?.path ?? null);
    } catch (reason) {
      if (token.current === mine) setError(reason instanceof Error ? reason.message : "Couldn't analyse that repository.");
    } finally {
      if (token.current === mine) setBusy(false);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const lines = details.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    const criteria = lines.filter((line) => /^[-*•]/.test(line)).map((line) => line.replace(/^[-*•]\s*/, ""));
    void analyse({
      repo_url: url.trim(),
      story: { id: `US-${crypto.randomUUID().slice(0, 6).toUpperCase()}`, title: title.trim(), description: lines.filter((line) => !/^[-*•]/.test(line)).join(" ") || title.trim(), type: "story", acceptance_criteria: criteria },
    });
  }

  function useDemo() {
    if (!demo) return;
    setUrl(demo.repo_url);
    setTitle(demo.story.title);
    setDetails([demo.story.description, ...demo.story.acceptance_criteria.map((item) => `- ${item}`)].join("\n"));
    void analyse(demo);
  }

  const impacted = useMemo(() => new Set(analysis?.files.map((file) => file.path) ?? []), [analysis]);
  const indexed = useMemo(() => new Set(analysis?.repo.files.map((file) => file.path) ?? []), [analysis]);

  return (
    <div className="mx-auto max-w-[1500px] space-y-8">
      <header>
        <h1>Codebase impact</h1>
        <p className="mt-1 text-body text-muted">Point at a repository and a user story. See the services, files, classes, APIs and tables it will change, and the tests to write.</p>
      </header>

      <form onSubmit={submit} className="space-y-4 rounded-xl border border-line bg-surface p-5" aria-label="Repository and story">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-dense font-medium">Inputs</span>
          {demo && <Button type="button" variant="outline" size="sm" disabled={busy} onClick={useDemo}>Example: OTP login on the demo bank</Button>}
        </div>
        <label className="block space-y-1 text-dense font-medium">
          <span className="flex items-center gap-1.5"><GitBranch aria-hidden="true" className="size-4" />Git repository URL <InfoTip label="supported URLs">Public GitHub repositories. Add /tree/branch/folder to analyse one folder, for example a services directory. The code is read, never run.</InfoTip></span>
          <Input value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://github.com/owner/repo or …/tree/main/services" disabled={busy} inputMode="url" />
        </label>
        <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
          <label className="block space-y-1 text-dense font-medium">
            <span>User story</span>
            <Input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="e.g. OTP multi-factor login" disabled={busy} />
          </label>
          <label className="block space-y-1 text-dense font-medium">
            <span>Details <span className="font-normal text-muted">(acceptance criteria as “- ” lines, optional)</span></span>
            <Textarea value={details} onChange={(event) => setDetails(event.target.value)} rows={3} disabled={busy} placeholder="What changes and why. Start lines with - for acceptance criteria." />
          </label>
        </div>
        <Button type="submit" disabled={busy || !url.trim() || !title.trim()}>{busy ? "Analysing…" : "Analyse codebase"}</Button>
      </form>

      {error && <p role="alert" className="rounded-xl border border-impact-high/40 bg-surface p-4 text-body">{error}</p>}
      {busy && <RunProgress run={progress} title={`Mapping ${title || "the story"} onto the code`} />}

      {analysis && (
        <div className="space-y-8" aria-busy={busy}>
          <div className="space-y-3">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2>AI flow</h2>
              <p className="text-meta text-muted">{analysis.repo.repo_url}</p>
            </div>
            <FlowStrip analysis={analysis} />
            <p className="text-body">{analysis.summary}</p>
          </div>

          <section aria-label="Split view" className="grid gap-4 lg:grid-cols-[minmax(280px,1fr)_minmax(0,1.6fr)]">
            <div className="h-[640px] overflow-hidden rounded-xl border border-line bg-surface lg:sticky lg:top-4">
              <CodeTree key={analysis.created_at} paths={analysis.repo.tree} impacted={impacted} indexed={indexed} selected={selected} onSelect={setSelected} />
            </div>
            <div>
              <h2 className="mb-3 flex items-center gap-1.5">Architecture impact <InfoTip label="architecture impact">Services the story changes, with the classes, API routes and database tables found in their changed files. Classes come from the AI&apos;s choice, checked against the code; routes and tables are read straight from the files.</InfoTip></h2>
              <ImpactPanel analysis={analysis} selected={selected} onSelect={setSelected} />
            </div>
          </section>

          <section className="space-y-3">
            <h2 className="flex items-center gap-1.5"><TestTube2 aria-hidden="true" className="size-5" />Developer test plan <InfoTip label="developer tests">Between 5 and 7 tests, grouped by category, each aimed at a named class, API, table or service.</InfoTip></h2>
            <TestPlan analysis={analysis} />
          </section>
        </div>
      )}
      {!analysis && !busy && <p className="rounded-xl border border-dashed border-line p-10 text-center text-body text-muted">Enter a repository URL and a user story, or try the example.</p>}
    </div>
  );
}
