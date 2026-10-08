"use client";

import type { ReactElement, ReactNode } from "react";
import { Info } from "lucide-react";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

/** A small "how is this worked out?" affordance: hover or focus to read. */
export function InfoTip({ label, children, className, side = "top" }: {
  label: string;
  children: ReactNode;
  className?: string;
  side?: "top" | "bottom" | "left" | "right";
}) {
  return (
    <Tooltip>
      <TooltipTrigger
        render={<button type="button" aria-label={`About ${label}`} className={cn("inline-flex size-4 shrink-0 cursor-help items-center justify-center rounded-full align-middle text-muted transition-colors duration-150 hover:text-text focus-visible:text-text", className)} />}
      >
        <Info aria-hidden="true" className="size-3.5" />
      </TooltipTrigger>
      <TooltipContent side={side} className="max-w-sm text-left text-meta leading-relaxed">{children}</TooltipContent>
    </Tooltip>
  );
}

/** Wrap any element so hovering it explains it, without adding an icon. */
export function Explained({ tip, children, side = "top" }: { tip: ReactNode; children: ReactElement; side?: "top" | "bottom" | "left" | "right" }) {
  return (
    <Tooltip>
      <TooltipTrigger render={children} />
      <TooltipContent side={side} className="max-w-sm text-left text-meta leading-relaxed">{tip}</TooltipContent>
    </Tooltip>
  );
}
