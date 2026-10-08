"use client";

import { Activity, Loader2 } from "lucide-react";
import { Explained, InfoTip } from "@/components/ui/info-tip";
import { explain, providerName } from "@/lib/explain";
import { cn } from "@/lib/utils";
import type { Run } from "@/lib/types";
import {
  activeAttempts, attemptsFor, findStage, formatElapsed, shortStageLabel, SPRINT_STAGE_ORDER,
  stageExplain, STORY_STAGE_ORDER,
} from "./model";
import { SourceBadge, StageIcon } from "./parts";

/** Live, step-by-step view of a run, so a slow model never leaves a blank wait. */
/** `hide` drops stages a page does not show (the executive view hides test planning). */
export function RunProgress({ run, title, hide = [] }: { run: Run | null; title: string; hide?: string[] }) {
  if (!run) {
    return (
      <section aria-label="Analysis progress" className="rounded-lg border border-line bg-surface p-5">
        <p role="status" className="flex items-center gap-2 text-body text-muted"><Loader2 aria-hidden="true" className="size-4 animate-spin text-model" />{title}: starting…</p>
      </section>
    );
  }
  const visible = run.stages.filter((stage) => !hide.includes(stage.stage));
  const total = visible.length;
  const done = visible.filter((stage) => stage.status === "done").length;
  const active = activeAttempts(run).filter((attempt) => !hide.includes(attempt.stage ?? ""));
  const running = visible.filter((stage) => stage.status === "running");
  return (
    <section aria-label="Analysis progress" aria-busy={run.status === "running"} className="space-y-5 rounded-lg border border-line bg-surface p-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="flex items-center gap-2"><Activity aria-hidden="true" className="size-4 text-model" />{title}</h2>
          <p className="mt-1 text-dense text-muted tabular-nums">
            {formatElapsed(run.elapsed_ms)} · {done} of {total} steps done
          </p>
        </div>
      </header>
      <div className="h-1 w-full overflow-hidden rounded-full bg-line" role="progressbar" aria-label="Steps done" aria-valuemin={0} aria-valuemax={total} aria-valuenow={done}>
        <div className="h-full rounded-full bg-model transition-[width] duration-500" style={{ width: `${total ? (done / total) * 100 : 0}%` }} />
      </div>
      <NowPanel run={run} active={active} running={running.map((stage) => stage.label + (stage.story_id && run.kind === "sprint" ? ` (${stage.story_id})` : ""))} />
      {run.kind === "sprint" ? <SprintMatrix run={run} hide={hide} /> : <StoryTimeline run={run} hide={hide} />}
    </section>
  );
}

function NowPanel({ run, active, running }: { run: Run; active: ReturnType<typeof activeAttempts>; running: string[] }) {
  return (
    <div role="status" aria-live="polite" className="rounded-md border border-line bg-canvas/60 px-4 py-3">
      <p className="flex items-center gap-1.5 text-meta font-medium text-muted">Now <InfoTip label="AI providers">{explain.chain}</InfoTip></p>
      {active.length ? (
        <ul className="mt-2 space-y-2">
          {active.slice(0, 4).map((attempt) => {
            const share = Math.min(100, (attempt.elapsed_ms / (attempt.timeout_s * 1000)) * 100);
            return (
              <li key={attempt.id} className="space-y-1">
                <p className="text-dense">
                  <span className="font-medium">{shortStageLabel[attempt.stage ?? ""] ?? attempt.stage}{run.kind === "sprint" && attempt.story_id ? ` · ${attempt.story_id}` : ""}</span>
                  <span className="text-muted">: waiting on AI, </span>{providerName(attempt.provider)} <span className="text-muted">{attempt.model}</span>
                  <span className="float-right tabular-nums text-muted">{formatElapsed(attempt.elapsed_ms)} / {attempt.timeout_s} s</span>
                </p>
                <div className="h-0.5 w-full rounded-full bg-line"><div className={cn("h-full rounded-full", share > 75 ? "bg-warn" : "bg-model")} style={{ width: `${share}%` }} /></div>
              </li>
            );
          })}
          {active.length > 4 && <li className="text-meta text-muted">+{active.length - 4} more calls in flight</li>}
        </ul>
      ) : (
        <p className="mt-1 text-dense">{running.length ? `${running.slice(0, 3).join(", ")}${running.length > 3 ? ` and ${running.length - 3} more` : ""}` : run.status === "running" ? "Queued for a free AI slot…" : "Finished"}</p>
      )}
    </div>
  );
}

function StoryTimeline({ run, hide }: { run: Run; hide: string[] }) {
  const storyId = run.story_ids[0] ?? null;
  return (
    <ol className="divide-y divide-line border-y border-line">
      {run.stages.filter((item) => item.story_id === storyId && !hide.includes(item.stage)).map((item) => item.stage).map((name, index) => {
        const stage = findStage(run, name, storyId);
        if (!stage) return null;
        const attempts = attemptsFor(run, name, storyId);
        return (
          <li key={name} className="grid grid-cols-[auto_minmax(0,1fr)_auto] gap-x-3 gap-y-1 py-3" aria-current={stage.status === "running" ? "step" : undefined}>
            <StageIcon stage={stage} className="mt-0.5" />
            <div className="min-w-0">
              <p className="flex flex-wrap items-center gap-2 text-dense">
                <span className={cn("font-medium", stage.status === "pending" && "text-muted")}>{index + 1}. {stage.label}</span>
                <InfoTip label={stage.label}>{stageExplain[name]}</InfoTip>
                <SourceBadge stage={stage} />
              </p>
              {stage.message && <p className="mt-0.5 text-meta text-muted">{stage.message}</p>}
              {attempts.some((attempt) => attempt.outcome !== "ok" && attempt.outcome !== "running" && attempt.outcome !== "skipped") && <p className="mt-0.5 text-meta text-warn">Switched AI provider {attempts.filter((attempt) => attempt.outcome !== "ok" && attempt.outcome !== "running" && attempt.outcome !== "skipped").length}× ({attempts.filter((attempt) => attempt.outcome !== "ok" && attempt.outcome !== "running" && attempt.outcome !== "skipped").map((attempt) => attempt.detail.split(";")[0].toLowerCase()).join(", ")})</p>}
            </div>
            <span className="text-meta tabular-nums text-muted">{stage.status === "pending" ? "" : formatElapsed(stage.elapsed_ms)}</span>
          </li>
        );
      })}
    </ol>
  );
}

function SprintMatrix({ run, hide }: { run: Run; hide: string[] }) {
  const columns = STORY_STAGE_ORDER.filter((name) => !hide.includes(name));
  return (
    <div className="space-y-4">
      <div className="overflow-x-auto rounded-md border border-line">
        <table className="w-full min-w-[640px] text-left text-dense">
          <thead className="bg-canvas/60 text-meta text-muted">
            <tr>
              <th scope="col" className="px-3 py-2 font-medium">Story</th>
              {columns.map((name) => (
                <th key={name} scope="col" className="px-2 py-2 font-medium">
                  <span className="inline-flex items-center gap-1">{shortStageLabel[name]}<InfoTip label={shortStageLabel[name]}>{stageExplain[name]}</InfoTip></span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {run.story_ids.map((storyId) => (
              <tr key={storyId} className="border-t border-line">
                <th scope="row" className="px-3 py-2 font-medium whitespace-nowrap">{storyId}</th>
                {columns.map((name) => {
                  const stage = findStage(run, name, storyId);
                  if (!stage) return <td key={name} />;
                  const attempts = attemptsFor(run, name, storyId).filter((a) => a.outcome !== "skipped");
                  const tip = [
                    `${stage.label}: ${stage.status}`,
                    stage.message,
                    stage.provider && stage.source === "llm" ? `Written by ${stage.provider}` : stage.source === "fallback" ? "No model answered; used the built-in fallback" : "",
                    attempts.length ? `${attempts.length} model call${attempts.length > 1 ? "s" : ""}: ${attempts.map((a) => `${providerName(a.provider)} ${a.outcome}`).join(", ")}` : "",
                  ].filter(Boolean).join(" · ");
                  return (
                    <td key={name} className="px-2 py-2">
                      <Explained tip={tip}>
                        <span tabIndex={0} className="inline-flex items-center gap-1.5 rounded px-1 tabular-nums" aria-label={tip}>
                          <StageIcon stage={stage} />
                          <span className="text-meta text-muted">{stage.status === "pending" ? "" : formatElapsed(stage.elapsed_ms)}</span>
                        </span>
                      </Explained>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ol className="flex flex-wrap gap-x-6 gap-y-2 text-dense">
        {SPRINT_STAGE_ORDER.map((name) => {
          const stage = findStage(run, name, null);
          if (!stage) return null;
          return (
            <li key={name} className="flex items-center gap-2">
              <StageIcon stage={stage} />
              <Explained tip={[stageExplain[name], stage.message].filter(Boolean).join(" ")}>
                <span tabIndex={0} className={cn(stage.status === "pending" && "text-muted")}>{stage.label}</span>
              </Explained>
              <SourceBadge stage={stage} />
            </li>
          );
        })}
      </ol>
    </div>
  );
}
