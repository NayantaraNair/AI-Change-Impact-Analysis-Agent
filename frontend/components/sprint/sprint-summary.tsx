import Link from "next/link";
import type { ReactNode } from "react";
import { dimensionLabel } from "@/components/analysis/model";
import { formatHours } from "@/lib/format";
import type { SprintAnalysis } from "@/lib/types";

function Line({ label, children }: { label: string; children: ReactNode }) {
  return (
    <li className="grid grid-cols-[7.5rem_minmax(0,1fr)] gap-x-4 py-2">
      <span className="text-dense text-muted">{label}</span>
      <span className="text-body">{children}</span>
    </li>
  );
}

function Ids({ ids }: { ids: string[] }) {
  if (!ids.length) return <span className="text-muted">None</span>;
  return <>{ids.map((id, index) => <span key={id}>{index > 0 && ", "}<Link className="link-ui" href={`/story?id=${encodeURIComponent(id)}`}>{id}</Link></span>)}</>;
}

/** The backlog in five short lines: what can start, what clashes, what to watch. */
export function SprintSummary({ analysis }: { analysis: SprintAnalysis }) {
  const by = (decision: string) => analysis.stories.filter((story) => story.release.decision === decision).map((story) => story.story.id);
  const riskiest = [...analysis.stories].sort((a, b) => b.risk.overall - a.risk.overall)[0];
  const highest = riskiest?.risk.dimensions.find((dimension) => dimension.name === riskiest.risk.highest);
  const order = analysis.conflicts.filter((conflict) => conflict.kind === "deployment_collision")
    .map((conflict) => `${conflict.story_b} before ${conflict.story_a}`);
  return (
    <section aria-labelledby="sprint-summary-heading" className="py-2">
      <h2 id="sprint-summary-heading">Summary</h2>
      <ul className="mt-2 divide-y divide-line border-y border-line">
        <Line label="Ready"><Ids ids={by("GO")} /></Line>
        <Line label="With conditions"><Ids ids={by("GO_WITH_CONDITIONS")} /></Line>
        <Line label="Blocked"><Ids ids={by("NO_GO")} /></Line>
        <Line label="Clashes">{analysis.conflicts.length ? `${analysis.conflicts.length}. Release ${order.length ? order.join("; ") : "the clashing stories one at a time"}.` : "None"}</Line>
        <Line label="Riskiest">{riskiest ? <><Link className="link-ui" href={`/story?id=${encodeURIComponent(riskiest.story.id)}`}>{riskiest.story.id}</Link>{highest ? `, ${dimensionLabel[highest.name]} ${highest.score}` : ""}</> : "None"}</Line>
        <Line label="Test effort">{formatHours(analysis.kpis.testing_effort_hours)} across {analysis.stories.length} stories</Line>
      </ul>
    </section>
  );
}
