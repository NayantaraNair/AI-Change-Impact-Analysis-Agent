"use client";

import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { StoryAnalysis } from "@/lib/types";
import { riskLevel } from "./model";

const colors = { low: "var(--impact-low)", medium: "var(--impact-med)", high: "var(--impact-high)" };

export function RiskByStoryChart({ stories }: { stories: StoryAnalysis[] }) {
  const data = stories.map(({ story, risk }) => ({ id: story.id, title: story.title, risk: risk.overall }));
  return (
    <section aria-labelledby="sprint-risk-heading" className="min-w-0">
      <h2 id="sprint-risk-heading">Risk by story</h2>
      <p className="mt-1 text-meta text-muted">Overall risk on a 0–100 scale</p>
      {data.length ? <div className="mt-3 w-full min-w-0" style={{ height: Math.max(260, data.length * 40 + 50) }}>
        <ResponsiveContainer width="100%" height="100%" minWidth={0}>
          <BarChart data={data} layout="vertical" margin={{ top: 8, right: 16, bottom: 8, left: 0 }} accessibilityLayer>
            <CartesianGrid stroke="var(--line)" horizontal={false} />
            <XAxis type="number" domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tick={{ fill: "var(--muted)", fontSize: 12 }} axisLine={false} tickLine={false} />
            <YAxis type="category" dataKey="id" width={78} tick={{ fill: "var(--text)", fontSize: 12 }} axisLine={false} tickLine={false} />
            <Tooltip cursor={{ fill: "var(--surface-raised)" }} contentStyle={{ background: "var(--surface-raised)", border: "1px solid var(--line)", borderRadius: 6, color: "var(--text)", fontSize: 13 }} itemStyle={{ color: "var(--text)" }} labelFormatter={(_, items) => items[0]?.payload?.title ?? "Story risk"} formatter={(value) => [`${value} / 100`, "Overall risk"]} />
            <Bar dataKey="risk" maxBarSize={22} isAnimationActive={false}>{data.map((story) => <Cell key={story.id} fill={colors[riskLevel(story.risk)]} />)}</Bar>
          </BarChart>
        </ResponsiveContainer>
      </div> : <p className="py-6 text-dense text-muted">No story risk scores to display.</p>}
      <div className="mt-2 flex flex-wrap gap-4 text-meta text-muted" aria-label="Risk legend">
        {(["low", "medium", "high"] as const).map((level) => <span key={level} className="flex items-center gap-1.5"><i className="size-2.5 rounded-sm" style={{ background: colors[level] }} aria-hidden="true" />{level === "low" ? "Low <40" : level === "medium" ? "Medium 40–69" : "High ≥70"}</span>)}
      </div>
      <ul className="sr-only" aria-label="Story risk scores">{data.map((story) => <li key={story.id}>{story.id}: {story.title}, overall risk {story.risk} out of 100, {riskLevel(story.risk)}</li>)}</ul>
    </section>
  );
}
