"use client";

import { Badge } from "@/components/ui/badge";
import { useAppContext } from "./app-context";

export function Header() {
  const { usingSampleData } = useAppContext();
  return (
    <header className="flex min-h-12 flex-wrap items-center gap-3 border-b border-line bg-surface px-6 py-2">
      <span className="text-body font-semibold">Change Impact Copilot</span>
      <span role="status" aria-live="polite">
        {usingSampleData && <Badge variant="outline" className="text-muted">Sample data</Badge>}
      </span>
    </header>
  );
}
