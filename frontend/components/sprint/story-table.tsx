"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { dimensionLabel } from "@/components/analysis/model";
import { decisionClass, decisionLabel, formatNumber, severityClass } from "@/lib/format";
import type { StoryAnalysis } from "@/lib/types";

export function StoryTable({ stories }: { stories: StoryAnalysis[] }) {
  const router = useRouter();
  return (
    <section aria-labelledby="sprint-stories-heading" className="min-w-0">
      <h2 id="sprint-stories-heading" className="mb-3">Stories</h2>
      <div className="overflow-x-auto border border-line rounded-md">
        <table className="w-full min-w-[560px] text-left text-dense">
          <thead className="bg-surface text-muted"><tr>{["ID", "Title", "Highest risk", "Decision", "Impacted"].map((label) => <th key={label} scope="col" className="px-3 py-2 font-medium">{label}</th>)}</tr></thead>
          <tbody>{stories.map((analysis) => {
            const { story, risk, graph, release } = analysis;
            const highest = risk.dimensions.find((dimension) => dimension.name === risk.highest)
              ?? risk.dimensions.reduce<(typeof risk.dimensions)[number] | undefined>((max, dimension) => !max || dimension.score > max.score ? dimension : max, undefined);
            const href = `/story?id=${encodeURIComponent(story.id)}`;
            return (
              <tr key={story.id} className="cursor-pointer border-t border-line hover:bg-surface-raised focus-within:bg-surface-raised" onClick={(event) => {
                if (!(event.target as HTMLElement).closest("a")) router.push(href);
              }}>
                <td className="whitespace-nowrap px-3 py-3 text-muted">{story.id}</td>
                <td className="px-3 py-3"><Link className="text-azure hover:underline" href={href}>{story.title}</Link></td>
                <td className="px-3 py-3">{highest ? <><span className={`font-semibold tabular-nums ${severityClass[highest.level]}`}>{formatNumber(highest.score)}</span><span className="ml-2 text-meta text-muted">{dimensionLabel[highest.name]}</span></> : <span className="text-muted">Not reported</span>}</td>
                <td className="px-3 py-3"><Badge variant="outline" className={`rounded border-current/40 ${decisionClass[release.decision]}`}>{decisionLabel[release.decision]}</Badge></td>
                <td className="px-3 py-3 tabular-nums">{graph.nodes.filter((node) => node.hop !== null).length}</td>
              </tr>
            );
          })}
          {!stories.length && <tr><td colSpan={5} className="px-3 py-6 text-muted">No stories in this analysis. Paste stories and analyze the sprint again.</td></tr>}</tbody>
        </table>
      </div>
    </section>
  );
}
