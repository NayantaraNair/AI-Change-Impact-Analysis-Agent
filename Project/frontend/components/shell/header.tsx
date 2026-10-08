"use client";

import { Bug } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { InfoTip } from "@/components/ui/info-tip";
import { explain } from "@/lib/explain";
import Link from "next/link";
import { APP_NAME, TAGLINE, useWorkspace, workspaces } from "@/lib/workspace";
import { useAppContext } from "./app-context";
import { BrandMark } from "./brand";
import { ThemeToggle } from "./theme-toggle";

export function Header() {
  const { usingSampleData, run, setDebugOpen } = useAppContext();
  const running = run?.status === "running";
  const { workspace, name } = useWorkspace();
  return (
    <header className="flex min-h-12 flex-wrap items-center gap-3 border-b border-line bg-surface px-6 py-2">
      <Link href="/" className="flex items-center gap-2.5 rounded-md" title={`${APP_NAME}: ${TAGLINE}`}>
        <BrandMark />
        <span className="text-body font-semibold [font-stretch:112%]">{APP_NAME}</span>
        <span className="hidden text-meta text-muted md:inline">{TAGLINE}</span>
      </Link>
      {workspace && <span className="flex items-center gap-2 border-l border-line pl-3 text-dense">
        <span className="font-medium">{workspaces[workspace].view}</span>
        {name && <span className="text-muted">· {name}</span>}
        <Link href="/" className="link-ui text-meta">Switch workspace</Link>
      </span>}
      <span role="status" aria-live="polite" className="flex items-center gap-1.5">
        {usingSampleData && <><Badge variant="outline" className="text-muted">Sample data</Badge><InfoTip label="sample data" side="bottom">{explain.sampleData}</InfoTip></>}
      </span>
      <span className="ml-auto flex items-center gap-1">
      <ThemeToggle />
      <Button type="button" variant="ghost" size="sm" className="text-muted hover:text-text" onClick={() => setDebugOpen(true)}>
        {running && <span aria-hidden="true" className="size-1.5 rounded-full bg-model" />}
        <Bug aria-hidden="true" />Details{running ? " (running)" : ""}
      </Button>
      </span>
    </header>
  );
}
