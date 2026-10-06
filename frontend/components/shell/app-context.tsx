"use client";

import { createContext, useContext, useState, useSyncExternalStore, type Dispatch, type ReactNode, type SetStateAction } from "react";
import { getUsingSampleData, setUsingSampleData, subscribeToSampleData } from "@/lib/api";
import type { StoryAnalysis, SprintAnalysis } from "@/lib/types";

export type AnalysisContext = { type: "story" | "sprint"; id: string };

interface AppContextValue {
  copilotOpen: boolean;
  setCopilotOpen: Dispatch<SetStateAction<boolean>>;
  toggleCopilot: () => void;
  highlight: string[];
  setHighlight: Dispatch<SetStateAction<string[]>>;
  currentContext: AnalysisContext | null;
  setCurrentContext: Dispatch<SetStateAction<AnalysisContext | null>>;
  currentAnalysis: StoryAnalysis | SprintAnalysis | null;
  setCurrentAnalysis: Dispatch<SetStateAction<StoryAnalysis | SprintAnalysis | null>>;
  usingSampleData: boolean;
  setUsingSampleData: (value: boolean) => void;
}

const AppContext = createContext<AppContextValue | null>(null);
const getServerSampleData = () => process.env.NEXT_PUBLIC_MOCK === "1";

export function AppProvider({ children }: { children: ReactNode }) {
  const [copilotOpen, setCopilotOpen] = useState(false);
  const [highlight, setHighlight] = useState<string[]>([]);
  const [currentContext, setCurrentContext] = useState<AnalysisContext | null>(null);
  const [currentAnalysis, setCurrentAnalysis] = useState<StoryAnalysis | SprintAnalysis | null>(null);
  const usingSampleData = useSyncExternalStore(subscribeToSampleData, getUsingSampleData, getServerSampleData);

  return (
    <AppContext.Provider value={{
      copilotOpen, setCopilotOpen, toggleCopilot: () => setCopilotOpen((open) => !open),
      highlight, setHighlight, currentContext, setCurrentContext,
      currentAnalysis, setCurrentAnalysis, usingSampleData, setUsingSampleData,
    }}>
      {children}
    </AppContext.Provider>
  );
}

export function useAppContext() {
  const context = useContext(AppContext);
  if (!context) throw new Error("useAppContext must be used within AppProvider");
  return context;
}
