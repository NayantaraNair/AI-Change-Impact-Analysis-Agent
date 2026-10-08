"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, Bug, FileSearch, FolderGit2, GitMerge } from "lucide-react";
import { useWorkspace } from "@/lib/workspace";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useAppContext } from "./app-context";

const destinations = {
  executive: [{ href: "/executive", label: "Portfolio view", icon: BarChart3 }],
  engineering: [
    { href: "/engineering", label: "Codebase impact", icon: FolderGit2 },
    { href: "/story", label: "Story or epic", icon: FileSearch },
    { href: "/sprint", label: "Sprint backlog", icon: GitMerge },
  ],
};

export function NavRail() {
  const pathname = usePathname();
  const { workspace } = useWorkspace();
  const { debugOpen, setDebugOpen, run } = useAppContext();
  return (
    <nav aria-label="Main navigation" className="fixed inset-y-0 left-0 z-30 flex w-14 flex-col items-center gap-2 border-r border-line bg-surface py-3">
      {destinations[workspace ?? (pathname.startsWith("/executive") ? "executive" : "engineering")].map(({ href, label, icon: Icon }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Tooltip key={href}>
            <TooltipTrigger render={<Link href={href} aria-label={label} aria-current={active ? "page" : undefined} className={cn("flex size-10 items-center justify-center rounded-md text-muted hover:bg-surface-raised hover:text-chalk", active && "bg-surface-raised text-chalk")} />}>
              <Icon size={20} aria-hidden="true" />
            </TooltipTrigger>
            <TooltipContent side="right">{label}</TooltipContent>
          </Tooltip>
        );
      })}
      <div className="mt-auto flex flex-col items-center gap-2">
        <Tooltip>
          <TooltipTrigger render={<Button id="debug-toggle" variant="ghost" size="icon-lg" aria-label={debugOpen ? "Close debug pane" : "Open debug pane"} aria-expanded={debugOpen} onClick={() => setDebugOpen((open) => !open)} className={cn("relative text-muted hover:text-chalk", debugOpen && "bg-surface-raised text-chalk")} />}>
            <Bug size={20} aria-hidden="true" />
            {run?.status === "running" && <span aria-hidden="true" className="absolute top-1.5 right-1.5 size-1.5 rounded-full bg-model" />}
          </TooltipTrigger>
          <TooltipContent side="right">Details: steps, AI calls, setup</TooltipContent>
        </Tooltip>
      </div>
    </nav>
  );
}
