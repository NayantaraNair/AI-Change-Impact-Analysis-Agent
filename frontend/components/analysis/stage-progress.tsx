"use client";

import { useEffect, useState } from "react";
import { Check, Circle, CircleDot } from "lucide-react";
import { STAGES } from "./model";

export function StageProgress({ report = false }: { report?: boolean }) {
  const [stage, setStage] = useState(0);
  useEffect(() => {
    if (report) return;
    const timer = window.setInterval(() => setStage((value) => Math.min(value + 1, STAGES.length - 1)), 700);
    return () => window.clearInterval(timer);
  }, [report]);

  if (report) return <p role="status" className="border-y border-line py-4 text-muted">Loading saved analysis…</p>;
  return (
    <section aria-label="Analysis progress" className="border-y border-line bg-surface px-4 py-4">
      <p className="mb-3 text-dense text-muted">Analyzing story. Progress is estimated while the server prepares your report.</p>
      <ol className="flex flex-wrap gap-x-6 gap-y-3 text-dense">
        {STAGES.map(({ key, label }, index) => {
          const Icon = index < stage ? Check : index === stage ? CircleDot : Circle;
          return (
            <li key={key} aria-current={index === stage ? "step" : undefined} className={`flex items-center gap-2 ${index === stage ? "text-text" : "text-muted"}`}>
              <Icon aria-hidden="true" className={`size-4 ${index === stage ? "text-azure" : ""}`} />
              {label}
            </li>
          );
        })}
      </ol>
      <p className="sr-only" role="status" aria-live="polite">{STAGES[stage].label}</p>
    </section>
  );
}
