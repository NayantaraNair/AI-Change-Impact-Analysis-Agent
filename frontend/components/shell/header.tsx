"use client";

import { Bug } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { InfoTip } from "@/components/ui/info-tip";
import { explain } from "@/lib/explain";
import { useAppContext } from "./app-context";

export function Header() {
  const { usingSampleData, run, setDebugOpen } = useAppContext();
  const running = run?.status === "running";
  return (
    <header className="flex min-h-12 flex-wrap items-center gap-3 border-b border-line bg-surface px-6 py-2">
      <span className="flex items-center gap-2.5">
        <svg aria-hidden="true" viewBox="0 0 24 24" className="size-6">
          <circle cx="12" cy="12" r="10.5" fill="none" stroke="var(--line-strong)" strokeWidth="1" />
          <circle cx="12" cy="12" r="6.5" fill="none" stroke="var(--impact-med)" strokeOpacity="0.7" strokeWidth="1.25" />
          <circle cx="12" cy="12" r="2.75" fill="var(--impact-high)" />
        </svg>
        <span className="text-body font-semibold [font-stretch:112%]">Change Impact Copilot</span>
      </span>
      <span role="status" aria-live="polite" className="flex items-center gap-1.5">
        {usingSampleData && <><Badge variant="outline" className="text-muted">Sample data</Badge><InfoTip label="sample data" side="bottom">{explain.sampleData}</InfoTip></>}
      </span>
      <Button type="button" variant="ghost" size="sm" className="ml-auto text-muted hover:text-text" onClick={() => setDebugOpen(true)}>
        {running && <span aria-hidden="true" className="size-1.5 rounded-full bg-model" />}
        <Bug aria-hidden="true" />Details{running ? " (running)" : ""}
      </Button>
    </header>
  );
}
