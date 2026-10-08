import type { Architecture, Component } from "@/lib/types";

export async function fetchArchitecture(signal?: AbortSignal): Promise<Component[]> {
  if (process.env.NEXT_PUBLIC_MOCK === "1") return [];
  const base = (process.env.NEXT_PUBLIC_API_URL || "/api").replace(/\/$/, "");
  try {
    const response = await fetch(`${base}/architecture`, {
      cache: "no-store",
      signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(10_000)]) : AbortSignal.timeout(10_000),
    });
    if (!response.ok) return [];
    const data = await response.json() as Architecture;
    return Array.isArray(data.components) ? data.components : [];
  } catch {
    // The graph itself still supplies owner, criticality, data classes and factors.
    return [];
  }
}
