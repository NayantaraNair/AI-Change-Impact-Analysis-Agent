import { analyzeSprint, ApiError, setUsingSampleData } from "@/lib/api";
import type { SprintAnalysis } from "@/lib/types";

export const DEMO_SPRINT_ID = "sprint-42";

/** A missing saved report is an empty state, rather than a new analysis request. */
export async function getSavedSprint(signal?: AbortSignal): Promise<SprintAnalysis | null> {
  if (process.env.NEXT_PUBLIC_MOCK === "1") return analyzeSprint({ sprint_id: DEMO_SPRINT_ID });
  const base = (process.env.NEXT_PUBLIC_API_URL || "/api").replace(/\/$/, "");
  let response: Response;
  try {
    response = await fetch(`${base}/sprint/${DEMO_SPRINT_ID}`, {
      cache: "no-store",
      signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(15_000)]) : AbortSignal.timeout(15_000),
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new Error("Couldn't reach the analysis server. Start the backend on :8000 or set NEXT_PUBLIC_MOCK=1, then try again.");
  }
  if (response.status === 404 || response.status === 204) return null;
  if (!response.ok) throw new ApiError(response.status, `Couldn't load the saved sprint (${response.status}). Check the backend and try again.`);
  const analysis = await response.json() as SprintAnalysis;
  setUsingSampleData(false);
  return analysis;
}
