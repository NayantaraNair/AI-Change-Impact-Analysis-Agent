"use client";

import type { ReactNode } from "react";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useAppContext } from "./app-context";

export function CopilotDrawer({ children }: { children: ReactNode }) {
  const { copilotOpen, setCopilotOpen } = useAppContext();
  return (
    <Sheet open={copilotOpen} onOpenChange={setCopilotOpen} triggerId="copilot-toggle">
      <SheetContent id="copilot-drawer" side="right" className="w-[400px] max-w-[calc(100vw-56px)] bg-surface sm:max-w-[400px]">
        <SheetHeader className="border-b border-line pr-12">
          <SheetTitle>Copilot</SheetTitle>
          <SheetDescription>Ask about the current analysis.</SheetDescription>
        </SheetHeader>
        <div className="flex min-h-0 flex-1 flex-col px-4 pb-4">{children}</div>
      </SheetContent>
    </Sheet>
  );
}
