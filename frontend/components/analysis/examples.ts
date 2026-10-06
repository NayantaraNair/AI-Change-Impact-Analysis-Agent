import demo from "./demo-stories.json";
import type { StoryInput } from "@/lib/types";

/** Older sample fixtures contain two stories; keep the six repository demos available. */
export function demoExamples(stories: StoryInput[]): StoryInput[] {
  if (stories.length >= 6) return stories;
  const canonical = demo.stories as StoryInput[];
  return canonical.map((story) => stories.find((sample) => sample.id === story.id) ?? story);
}
