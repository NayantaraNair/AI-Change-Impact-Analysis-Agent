"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bot, FileSearch, GitMerge } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useAppContext } from "./app-context";

const destinations = [
  { href: "/story", label: "Story analysis", icon: FileSearch },
  { href: "/sprint", label: "Sprint", icon: GitMerge },
];

export function NavRail() {
  const pathname = usePathname();
  const { copilotOpen, toggleCopilot } = useAppContext();
  return (
    <nav aria-label="Main navigation" className="fixed inset-y-0 left-0 z-30 flex w-14 flex-col items-center gap-2 border-r border-line bg-surface py-3">
      {destinations.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Tooltip key={href}>
            <TooltipTrigger render={<Link href={href} aria-label={label} aria-current={active ? "page" : undefined} className={cn("flex size-10 items-center justify-center rounded-md text-muted hover:bg-surface-raised hover:text-azure", active && "bg-surface-raised text-azure")} />}>
              <Icon size={20} aria-hidden="true" />
            </TooltipTrigger>
            <TooltipContent side="right">{label}</TooltipContent>
          </Tooltip>
        );
      })}
      <div className="mt-auto">
        <Tooltip>
          <TooltipTrigger render={<Button id="copilot-toggle" variant="ghost" size="icon-lg" aria-label={copilotOpen ? "Close copilot" : "Open copilot"} aria-expanded={copilotOpen} aria-controls={copilotOpen ? "copilot-drawer" : undefined} onClick={toggleCopilot} className={cn("text-muted hover:text-azure", copilotOpen && "bg-surface-raised text-azure")} />}>
            <Bot size={20} aria-hidden="true" />
          </TooltipTrigger>
          <TooltipContent side="right">Copilot</TooltipContent>
        </Tooltip>
      </div>
    </nav>
  );
}
