"use client";

import type { ReactNode } from "react";
import { DebugPanel } from "@/components/debug/debug-panel";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AppProvider } from "./app-context";
import { CopilotDrawer } from "./copilot-drawer";
import { Header } from "./header";
import { NavRail } from "./nav-rail";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <AppProvider>
      <TooltipProvider delay={200}>
        <a href="#main-content" className="fixed top-2 left-16 z-[60] rounded-md bg-surface px-3 py-2 text-chalk sr-only focus:not-sr-only">Skip to content</a>
        <NavRail />
        <div className="ml-14 flex min-h-dvh min-w-0 flex-col">
          <Header />
          <main id="main-content" tabIndex={-1} className="min-w-0 flex-1 p-6">{children}</main>
        </div>
        <CopilotDrawer />
        <DebugPanel />
      </TooltipProvider>
    </AppProvider>
  );
}
