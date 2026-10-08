"use client";

import { useSyncExternalStore } from "react";

export type Workspace = "executive" | "engineering";

export const APP_NAME = "ImpactIQ";
export const TAGLINE = "Every Change Before It Happens";

export const workspaces: Record<Workspace, { label: string; view: string; home: string }> = {
  executive: { label: "Executive workspace", view: "Portfolio view", home: "/executive" },
  engineering: { label: "Engineering workspace", view: "Technical analysis", home: "/story" },
};

const WORKSPACE_KEY = "impactiq-workspace";
const NAME_KEY = "impactiq-name";
const listeners = new Set<() => void>();

function read(key: string): string | null {
  try { return window.localStorage.getItem(key); } catch { return null; }
}

export function enterWorkspace(workspace: Workspace, name: string) {
  try {
    window.localStorage.setItem(WORKSPACE_KEY, workspace);
    if (name.trim()) window.localStorage.setItem(NAME_KEY, name.trim().slice(0, 60));
    else window.localStorage.removeItem(NAME_KEY);
  } catch { /* Storage blocked: the choice still applies to this page view. */ }
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

const snapshot = () => `${read(WORKSPACE_KEY) ?? ""}|${read(NAME_KEY) ?? ""}`;

/** The chosen workspace and name; null on the server and before a choice. */
export function useWorkspace(): { workspace: Workspace | null; name: string } {
  const value = useSyncExternalStore(subscribe, snapshot, () => "|");
  const [workspace, name] = value.split("|");
  return { workspace: workspace === "executive" || workspace === "engineering" ? workspace : null, name };
}
