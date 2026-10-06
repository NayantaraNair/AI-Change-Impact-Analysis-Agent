"use client";

import type { FormEvent } from "react";
import { ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import type { StoryInput } from "@/lib/types";
import type { StoryFormValue } from "./model";

interface Props {
  value: StoryFormValue;
  onChange: (value: StoryFormValue) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  examples: StoryInput[];
  onExample: (story: StoryInput) => void;
  examplesLoading: boolean;
  examplesError: boolean;
  onRetryExamples: () => void;
  busy: boolean;
}

export function StoryForm({ value, onChange, onSubmit, examples, onExample, examplesLoading, examplesError, onRetryExamples, busy }: Props) {
  function update(key: keyof StoryFormValue, next: string) {
    onChange({ ...value, [key]: next });
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4" aria-label="Story input">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1>Story analysis</h1>
        <DropdownMenu>
          <DropdownMenuTrigger render={<Button type="button" variant="outline" disabled={busy || examplesLoading} />}>
            {examplesLoading ? "Loading examples…" : "Load example"}<ChevronDown aria-hidden="true" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-[420px] max-w-[90vw]">
            {examples.map((story) => (
              <DropdownMenuItem key={story.id} onClick={() => onExample(story)} className="items-start gap-3 px-3 py-2">
                <span className="shrink-0 text-meta text-muted">{story.id}</span>
                <span className="text-dense">{story.title}</span>
              </DropdownMenuItem>
            ))}
            {examplesError && <DropdownMenuItem onClick={onRetryExamples}>Retry loading examples</DropdownMenuItem>}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      {examplesError && <p role="status" className="text-dense text-muted">Couldn&apos;t load examples. Start the backend or restore the demo fixture, then select Retry loading examples.</p>}
      <fieldset disabled={busy} className="grid min-w-0 gap-3 disabled:opacity-60">
        <div className="grid gap-3 sm:grid-cols-[140px_minmax(0,1fr)_150px]">
          <label className="space-y-1 text-dense font-medium">
            <span>Story ID <span className="text-meta font-normal text-muted">(optional)</span></span>
            <Input value={value.id} onChange={(event) => update("id", event.target.value)} placeholder="ST-107" maxLength={100} />
          </label>
          <label className="space-y-1 text-dense font-medium">
            <span>Title</span>
            <Input value={value.title} onChange={(event) => update("title", event.target.value)} placeholder="Describe the change in a sentence" required maxLength={500} />
          </label>
          <label className="space-y-1 text-dense font-medium">
            <span>Type</span>
            <select value={value.type} onChange={(event) => update("type", event.target.value)} className="h-8 w-full rounded-md border border-line bg-surface px-2 text-dense">
              <option value="story">Story</option><option value="epic">Epic</option><option value="change_request">Change request</option>
            </select>
          </label>
        </div>
        <div className="grid gap-3 md:grid-cols-[3fr_2fr]">
          <label className="space-y-1 text-dense font-medium">
            <span>Description</span>
            <Textarea value={value.description} onChange={(event) => update("description", event.target.value)} placeholder="What changes, which services are involved, and why?" required rows={4} className="h-28 resize-y" />
          </label>
          <label className="space-y-1 text-dense font-medium">
            <span>Acceptance criteria <span className="text-meta font-normal text-muted">(one per line)</span></span>
            <Textarea value={value.criteria} onChange={(event) => update("criteria", event.target.value)} placeholder="Describe the expected behavior" rows={4} className="h-28 resize-y" />
          </label>
        </div>
      </fieldset>
      <div className="flex items-center gap-4 pb-4">
        <Button type="submit" disabled={busy || !value.title.trim() || !value.description.trim()}>
          {busy ? "Preparing analysis…" : "Analyze story"}
        </Button>
        <p className="text-meta text-muted">Facts extracted by AI. Scores and release decisions computed by code.</p>
      </div>
    </form>
  );
}
