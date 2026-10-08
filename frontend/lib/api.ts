import type { ChatRequest, ChatResponse, DebugInfo, DemoSprint, Run, RunStarted, SprintAnalysis, SprintRequest, StoryAnalysis, StoryInput } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "/api";
const MOCK = process.env.NEXT_PUBLIC_MOCK === "1";
let usingSampleData = MOCK;
const sampleListeners = new Set<() => void>();

export const getUsingSampleData = () => usingSampleData;
export function setUsingSampleData(value: boolean) {
  if (usingSampleData === value) return;
  usingSampleData = value;
  sampleListeners.forEach((listener) => listener());
}
export function subscribeToSampleData(listener: () => void) {
  sampleListeners.add(listener);
  return () => { sampleListeners.delete(listener); };
}

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

// Only transport failures and 5xx responses use samples. Do not hide bad input.
async function request<T>(path: string, init: RequestInit, decode: (response: Response) => Promise<T>, fallback: () => Promise<T>, timeoutMs = 15_000, sampleOn404 = false): Promise<T> {
  if (MOCK) return sample(fallback);
  let response: Response;
  try {
    response = await fetch(`${BASE.replace(/\/$/, "")}${path}`, {
      ...init,
      signal: AbortSignal.timeout(timeoutMs),
      cache: "no-store",
    });
  } catch {
    return sample(fallback);
  }
  if (response.status >= 500 || (sampleOn404 && response.status === 404)) return sample(fallback);
  if (!response.ok) {
    throw new ApiError(response.status, `The analysis server returned ${response.status}. Check your request and try again.`);
  }
  const data = await decode(response);
  setUsingSampleData(false);
  return data;
}

async function sample<T>(load: () => Promise<T>): Promise<T> {
  const data = await load();
  setUsingSampleData(true);
  return data;
}

async function fixture<T>(filename: string): Promise<T> {
  const response = await fetch(`/fixtures/${filename}`, { cache: "no-store" });
  if (!response.ok) throw new ApiError(response.status, `Sample data could not be loaded (${filename}). Start the backend or restore the fixtures and try again.`);
  return response.json() as Promise<T>;
}

async function storyFixture(id: string): Promise<StoryAnalysis> {
  try {
    return await fixture<StoryAnalysis>(`story-${encodeURIComponent(id)}.json`);
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 404) throw error;
    // demo-sprint is the fixture index, so T15 can replace the sample stories.
    const demo = await fixture<DemoSprint>("demo-sprint.json");
    const firstId = demo.stories[0]?.id;
    if (!firstId || firstId === id) throw error;
    return fixture<StoryAnalysis>(`story-${encodeURIComponent(firstId)}.json`);
  }
}

// A live sprint runs many LLM calls, each allowed up to 180 s per provider.
const LLM_TIMEOUT_MS = 900_000;

const post = (body: unknown): RequestInit => ({
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
});
const json = <T>(response: Response) => response.json() as Promise<T>;

export function analyzeStory(story: StoryInput, options: { refresh?: boolean } = {}): Promise<StoryAnalysis> {
  return request(`/analyze${options.refresh ? "?refresh=true" : ""}`, post(story), json<StoryAnalysis>, () => storyFixture(story.id), LLM_TIMEOUT_MS);
}

export function analyzeSprint(req: SprintRequest = {}): Promise<SprintAnalysis> {
  return request("/analyze-sprint", post(req), json<SprintAnalysis>, () => fixture<SprintAnalysis>("sprint.json"), LLM_TIMEOUT_MS);
}

export function getDemoSprint(): Promise<DemoSprint> {
  return request("/demo-sprint", {}, json<DemoSprint>, () => fixture<DemoSprint>("demo-sprint.json"));
}

export function getDemoPortfolio(): Promise<DemoSprint> {
  return request("/demo-portfolio", {}, json<DemoSprint>, () => fixture<DemoSprint>("demo-portfolio.json"));
}

export const COPILOT_STARTER_QUESTIONS = [
  "What is impacted?",
  "Why is risk high?",
  "What should be tested?",
  "Which stories are risky?",
  "Why is release confidence low?",
] as const;

export function chat(req: ChatRequest, options: { starterIndex?: number } = {}): Promise<ChatResponse> {
  return request("/chat", post(req), json<ChatResponse>, async () => {
    const index = options.starterIndex ?? COPILOT_STARTER_QUESTIONS.findIndex((question) => question.toLowerCase() === req.message.trim().toLowerCase());
    if (index < 0 || index > 4 || !Number.isInteger(index)) {
      return {
        answer: "Sample mode has prepared answers for the starter questions. Select a starter question, or start the backend to ask about your own analysis.",
        cited_nodes: [], cited_factors: [], provider: "sample-fixture",
      };
    }
    try {
      return await fixture<ChatResponse>(`chat-${encodeURIComponent(req.context_id)}-${index}.json`);
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 404) throw error;
      return {
        answer: "No prepared answer is available for this sample context. Load the demo sprint or start the backend and try again.",
        cited_nodes: [], cited_factors: [], provider: "sample-fixture",
      };
    }
  }, LLM_TIMEOUT_MS);
}

// ---------------------------------------------------------------- runs with live progress

const POLL_MS = 1_000;
const MAX_POLL_FAILURES = 10;

export interface TrackedResult<T> { result: T; run: Run | null }

function apiUrl(path: string) {
  return `${BASE.replace(/\/$/, "")}${path}`;
}

const pause = (ms: number, signal?: AbortSignal) => new Promise<void>((resolve, reject) => {
  const timer = setTimeout(resolve, ms);
  signal?.addEventListener("abort", () => { clearTimeout(timer); reject(signal.reason); }, { once: true });
});

/**
 * Start a background run and poll it until it finishes, reporting each update.
 * Returns null when the server is unreachable or predates runs, so callers can
 * use the one-shot endpoint (which has its own sample-data fallback).
 */
async function trackRun(path: string, body: unknown, onProgress: (run: Run) => void, signal?: AbortSignal): Promise<Run | null> {
  if (MOCK) return null;
  let started: Response;
  try {
    started = await fetch(apiUrl(path), { ...post(body), signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(15_000)]) : AbortSignal.timeout(15_000), cache: "no-store" });
  } catch (error) {
    if (signal?.aborted) throw error;
    return null;
  }
  if (started.status === 404 || started.status === 405 || started.status >= 500) return null;
  if (!started.ok) {
    const detail = await started.json().then((value: { detail?: unknown }) => (typeof value.detail === "string" ? value.detail : null)).catch(() => null);
    throw new ApiError(started.status, detail ?? `The analysis server returned ${started.status}. Check your request and try again.`);
  }
  const { run_id: runId } = await started.json() as RunStarted;
  let failures = 0;
  for (;;) {
    let response: Response;
    try {
      response = await fetch(apiUrl(`/runs/${encodeURIComponent(runId)}`), { cache: "no-store", signal });
    } catch (error) {
      if (signal?.aborted) throw error;
      if (++failures >= MAX_POLL_FAILURES) throw new ApiError(503, "Lost contact with the analysis server while the run was in progress. Check that the backend is running and try again.");
      await pause(POLL_MS, signal);
      continue;
    }
    if (response.status === 404) throw new ApiError(410, "The analysis server restarted and this run was lost. Start the analysis again.");
    if (!response.ok) {
      if (++failures >= MAX_POLL_FAILURES) throw new ApiError(response.status, `The analysis server returned ${response.status} while reporting progress.`);
      await pause(POLL_MS, signal);
      continue;
    }
    failures = 0;
    const run = await response.json() as Run;
    onProgress(run);
    if (run.status === "failed") throw new ApiError(500, run.error ?? "The analysis failed. Check the backend logs.");
    if (run.status === "succeeded") {
      setUsingSampleData(false);
      return run;
    }
    await pause(POLL_MS, signal);
  }
}

export async function runStory(story: StoryInput, options: { refresh?: boolean; signal?: AbortSignal; onProgress?: (run: Run) => void } = {}): Promise<TrackedResult<StoryAnalysis>> {
  const query = options.refresh ? "?refresh=true" : "";
  const run = await trackRun(`/runs/story${query}`, story, options.onProgress ?? (() => {}), options.signal);
  if (run?.story_result) return { result: run.story_result, run };
  return { result: await analyzeStory(story, options), run: null };
}

export async function runSprint(req: SprintRequest = {}, options: { refresh?: boolean; signal?: AbortSignal; onProgress?: (run: Run) => void } = {}): Promise<TrackedResult<SprintAnalysis>> {
  const query = options.refresh ? "?refresh=true" : "";
  const run = await trackRun(`/runs/sprint${query}`, req, options.onProgress ?? (() => {}), options.signal);
  if (run?.sprint_result) return { result: run.sprint_result, run };
  return { result: await analyzeSprint(req), run: null };
}

export async function getRun(runId: string): Promise<Run> {
  const response = await fetch(apiUrl(`/runs/${encodeURIComponent(runId)}`), { cache: "no-store", signal: AbortSignal.timeout(15_000) });
  if (!response.ok) throw new ApiError(response.status, response.status === 404 ? "This run is no longer available. Runs are kept in memory until the backend restarts." : `The analysis server returned ${response.status}.`);
  return response.json() as Promise<Run>;
}

export async function getRecentRuns(): Promise<Run[]> {
  const response = await fetch(apiUrl("/runs"), { cache: "no-store", signal: AbortSignal.timeout(15_000) });
  if (!response.ok) throw new ApiError(response.status, `The analysis server returned ${response.status}.`);
  return response.json() as Promise<Run[]>;
}

export async function getDebugInfo(): Promise<DebugInfo> {
  const response = await fetch(apiUrl("/debug"), { cache: "no-store", signal: AbortSignal.timeout(15_000) });
  if (!response.ok) throw new ApiError(response.status, `The analysis server returned ${response.status}.`);
  return response.json() as Promise<DebugInfo>;
}

/** Latest saved analysis for a story; falls back to sample data when the server has none. */
export function getReport(storyId: string): Promise<StoryAnalysis> {
  return request(`/report/${encodeURIComponent(storyId)}`, {}, json<StoryAnalysis>, () => storyFixture(storyId), 15_000, true);
}
