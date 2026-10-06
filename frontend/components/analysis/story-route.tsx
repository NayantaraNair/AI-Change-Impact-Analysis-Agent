"use client";

import { useSearchParams } from "next/navigation";
import { StoryAnalysisPage } from "./story-analysis-page";

export function StoryRoute() {
  const reportId = useSearchParams().get("id")?.trim() || null;
  return <StoryAnalysisPage key={reportId ?? "new-story"} reportId={reportId} />;
}
