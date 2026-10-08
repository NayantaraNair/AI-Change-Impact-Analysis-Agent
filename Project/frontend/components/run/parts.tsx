"use client";

import { AlertTriangle, Check, Circle, Loader2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Explained } from "@/components/ui/info-tip";
import { outcomeLabel, providerName, sourceExplain, sourceLabel, splitProvider } from "@/lib/explain";
import type { LlmAttempt, StageProgress } from "@/lib/types";
import { formatElapsed } from "./model";

const sourceTone: Record<string, string> = {
  llm: "border-model/40 text-model",
  deterministic: "border-line text-muted",
  cache: "border-line text-muted",
  fixture: "border-line text-muted",
  fallback: "border-warn/50 text-warn",
};

export function SourceBadge({ stage, className }: { stage: Pick<StageProgress, "source" | "provider">; className?: string }) {
  if (!stage.source) return null;
  const { provider, model } = splitProvider(stage.provider);
  const text = stage.source === "llm" ? provider : sourceLabel[stage.source];
  const tip = stage.source === "llm" ? `${sourceExplain.llm} ${provider} · ${model}` : sourceExplain[stage.source];
  return (
    <Explained tip={tip}>
      <span tabIndex={0} className={cn("inline-flex h-5 shrink-0 items-center rounded-full border px-2 text-meta font-medium whitespace-nowrap", sourceTone[stage.source], className)}>{text}</span>
    </Explained>
  );
}

export function StageIcon({ stage, className }: { stage: Pick<StageProgress, "status" | "source">; className?: string }) {
  const base = cn("size-4 shrink-0", className);
  if (stage.status === "running") return <Loader2 aria-hidden="true" className={cn(base, "animate-spin text-model")} />;
  if (stage.status === "failed") return <X aria-hidden="true" className={cn(base, "text-impact-high")} />;
  if (stage.status === "done") {
    return stage.source === "fallback"
      ? <AlertTriangle aria-hidden="true" className={cn(base, "text-warn")} />
      : <Check aria-hidden="true" className={cn(base, "text-text")} />;
  }
  return <Circle aria-hidden="true" className={cn(base, "text-line")} />;
}

const outcomeTone: Record<string, string> = {
  running: "text-model", ok: "text-text", skipped: "text-muted",
};

export function AttemptLine({ attempt, showWhere = false }: { attempt: LlmAttempt; showWhere?: boolean }) {
  const tone = outcomeTone[attempt.outcome] ?? "text-warn";
  const tokens = attempt.completion_tokens !== null
    ? `${attempt.completion_tokens.toLocaleString()} out${attempt.reasoning_tokens ? ` (${attempt.reasoning_tokens.toLocaleString()} thinking)` : ""} / ${attempt.max_tokens.toLocaleString()} cap`
    : `cap ${attempt.max_tokens.toLocaleString()} tokens`;
  return (
    <li className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-baseline gap-x-3 text-meta">
      <span className={cn("font-medium whitespace-nowrap", tone)}>{outcomeLabel[attempt.outcome]}</span>
      <span className="min-w-0 text-muted">
        <span className="text-text">{providerName(attempt.provider)}</span> · {attempt.model}
        {showWhere && attempt.stage && <> · {attempt.story_id ? `${attempt.story_id} ` : ""}{attempt.stage}</>}
        <span className="block truncate">{attempt.detail} · {tokens}</span>
      </span>
      <span className="tabular-nums text-muted">{attempt.outcome === "running" ? `${formatElapsed(attempt.elapsed_ms)} of ${attempt.timeout_s} s` : formatElapsed(attempt.elapsed_ms)}</span>
    </li>
  );
}
