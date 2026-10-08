"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, FolderGit2 } from "lucide-react";
import { useWorkspace } from "@/lib/workspace";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

const destinations = {
  executive: [{ href: "/executive", label: "Portfolio view", icon: BarChart3 }],
  engineering: [{ href: "/engineering", label: "Codebase impact", icon: FolderGit2 }],
};

export function NavRail() {
  const pathname = usePathname();
  const { workspace } = useWorkspace();
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
    </nav>
  );
}
