"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { BarChart3, Wrench } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { APP_NAME, enterWorkspace, TAGLINE, useWorkspace, workspaces, type Workspace } from "@/lib/workspace";
import { BrandMark } from "./brand";
import { ThemeToggle } from "./theme-toggle";

const options: { id: Workspace; icon: typeof BarChart3; who: string; points: string[] }[] = [
  {
    id: "executive", icon: BarChart3, who: "For product, release and delivery leads",
    points: ["Sprint backlogs and major features in business terms", "Business impact, customers reached and release readiness", "Clashes between stories, with what to do"],
  },
  {
    id: "engineering", icon: Wrench, who: "For tech leads, engineers and testers",
    points: ["Dependency graph and risk by area", "Top tests to run and compliance checks", "Release rules, rollback and deployment steps"],
  },
];

export function WorkspaceChooser() {
  const router = useRouter();
  const saved = useWorkspace();
  const [choice, setChoice] = useState<Workspace | null>(null);
  const [name, setName] = useState<string | null>(null);
  const selected = choice ?? saved.workspace ?? "executive";
  const shownName = name ?? saved.name;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    enterWorkspace(selected, shownName);
    router.push(workspaces[selected].home);
  }

  return (
    <div className="flex min-h-dvh flex-col bg-canvas">
      <div className="flex justify-end p-4"><ThemeToggle /></div>
      <main id="main-content" className="flex flex-1 items-center justify-center px-6 pb-16">
        <form onSubmit={submit} className="w-full max-w-3xl space-y-8" aria-labelledby="sign-in-title">
          <header className="space-y-3 text-center">
            <BrandMark className="mx-auto size-12" />
            <h1 id="sign-in-title" className="text-[2.5rem] leading-tight font-semibold [font-stretch:112%]">{APP_NAME}</h1>
            <p className="text-section text-muted">{TAGLINE}</p>
          </header>
          <fieldset className="space-y-3">
            <legend className="mb-3 text-body font-medium">Choose your workspace</legend>
            <div className="grid gap-4 md:grid-cols-2">
              {options.map(({ id, icon: Icon, who, points }) => {
                const active = selected === id;
                return (
                  <label key={id} className={cn(
                    "relative flex cursor-pointer flex-col gap-3 rounded-xl border bg-surface p-5 transition-colors duration-150 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-chalk",
                    active ? "border-chalk" : "border-line hover:border-line-strong",
                  )}>
                    <input type="radio" name="workspace" value={id} checked={active} onChange={() => setChoice(id)} className="sr-only" />
                    <span className="flex items-center gap-3">
                      <span className={cn("flex size-10 items-center justify-center rounded-lg border", active ? "border-chalk text-text" : "border-line text-muted")}><Icon aria-hidden="true" className="size-5" /></span>
                      <span>
                        <span className="block text-section font-semibold">{workspaces[id].label}</span>
                        <span className="block text-dense text-muted">{workspaces[id].view}</span>
                      </span>
                    </span>
                    <span className="text-dense text-muted">{who}</span>
                    <ul className="space-y-1 text-dense">
                      {points.map((point) => <li key={point} className="flex gap-2"><span aria-hidden="true" className="text-muted">·</span>{point}</li>)}
                    </ul>
                  </label>
                );
              })}
            </div>
          </fieldset>
          <div className="mx-auto flex max-w-md flex-col gap-3 sm:flex-row sm:items-end">
            <label className="flex-1 space-y-1 text-dense font-medium">
              <span>Your name <span className="font-normal text-muted">(optional)</span></span>
              <Input value={shownName} onChange={(event) => setName(event.target.value)} placeholder="e.g. Priya, Release Manager" maxLength={60} autoComplete="name" />
            </label>
            <Button type="submit" size="lg">Enter {selected === "executive" ? "portfolio view" : "technical analysis"}</Button>
          </div>
          <p className="text-center text-meta text-muted">Demo workspace. No account needed; your choice is remembered in this browser.</p>
        </form>
      </main>
    </div>
  );
}
