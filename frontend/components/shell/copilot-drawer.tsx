"use client";

import type { FunctionComponent, ReactNode } from "react";
import { CopilotPanel } from "@/components/copilot/copilot-panel";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { useAppContext } from "./app-context";

// Accept the shell's original placeholder slot while supplying the actual panel here.
export const CopilotDrawer: FunctionComponent<{ children?: ReactNode }> = () => {
  const { copilotOpen, setCopilotOpen } = useAppContext();
  return (
    <Sheet open={copilotOpen} onOpenChange={setCopilotOpen} triggerId="copilot-toggle">
      <SheetContent id="copilot-drawer" side="right" className="max-w-[calc(100vw-56px)] gap-0 bg-surface data-[side=right]:w-[400px] data-[side=right]:sm:max-w-[400px]">
        <SheetTitle className="sr-only">Copilot</SheetTitle>
        <SheetDescription className="sr-only">Ask about the current analysis.</SheetDescription>
        <CopilotPanel />
      </SheetContent>
    </Sheet>
  );
};
