import type { ReleaseDecision, Severity } from "./types";

const numbers = new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 });
const percentages = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 0 });

export function formatNumber(value: number): string {
  return Number.isFinite(value) ? numbers.format(value) : "–";
}

/** Coverage values in the shared contract are fractions from zero to one. */
export function formatPercent(fraction: number): string {
  return Number.isFinite(fraction) ? percentages.format(fraction) : "–";
}

export function formatScore(score: number): string {
  return Number.isFinite(score) ? `${Math.round(score)}%` : "–";
}

export function formatDuration(milliseconds: number): string {
  return `${formatNumber(milliseconds / 1_000)} s`;
}

export function formatHours(hours: number): string {
  return `${formatNumber(hours)} h`;
}

export function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "–";
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeZone: "UTC" }).format(date);
}

export const severityClass: Record<Severity, string> = {
  low: "text-impact-low", medium: "text-impact-med", high: "text-impact-high",
};

export const decisionLabel: Record<ReleaseDecision, string> = {
  GO: "Go", GO_WITH_CONDITIONS: "Go with conditions", NO_GO: "No go",
};

export const decisionClass: Record<ReleaseDecision, string> = {
  GO: severityClass.low, GO_WITH_CONDITIONS: severityClass.medium, NO_GO: severityClass.high,
};
