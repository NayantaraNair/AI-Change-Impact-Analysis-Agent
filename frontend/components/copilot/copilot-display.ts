import type { AnalysisContext } from "@/components/shell/app-context";
import type { ChatResponse, SprintAnalysis, StoryAnalysis } from "@/lib/types";

export const MISSING_SAMPLE_ANSWER = "Sample data has no answer for that question. Start the backend to ask it.";

export function answerContent(response: ChatResponse): string {
  // Normalize the shared API's missing-fixture and open-question sample responses.
  if (response.provider === "sample-fixture" && (
    response.answer.startsWith("No prepared answer is available") ||
    response.answer.startsWith("Sample mode has prepared answers")
  )) return MISSING_SAMPLE_ANSWER;
  return response.answer;
}

export function contextLabel(context: AnalysisContext, analysis: StoryAnalysis | SprintAnalysis | null) {
  if (context.type === "story") return context.id;
  if (analysis && "sprint_id" in analysis && analysis.sprint_id === context.id) {
    return analysis.name.split(":")[0];
  }
  return context.id.replace(/^sprint[-_\s]*/i, "Sprint ");
}
