import type { StoryInput } from "./types";

// Read an attached story, epic or backlog into stories. Accepts:
// - JSON: one story object, or an array of them (id, title, description, type, acceptance_criteria)
// - CSV with a header row: id, title, description, type, acceptance_criteria (criteria split on ";")
// - Text or Markdown: one story per file (first line is the title; lines under an
//   "Acceptance criteria" heading become criteria), or one story per line as "ID | title | description"

export const ATTACH_ACCEPT = ".json,.csv,.txt,.md,.markdown";
export const BACKLOG_HANDOFF_KEY = "cip-backlog-handoff";

const TYPES = new Set(["story", "epic", "change_request"]);

function fail(message: string): never {
  throw new Error(message);
}

function toStory(value: unknown, index: number): StoryInput {
  if (typeof value !== "object" || value === null || Array.isArray(value)) fail(`Item ${index + 1} isn't a story object.`);
  const record = value as Record<string, unknown>;
  const title = String(record.title ?? record.summary ?? record.name ?? "").trim();
  const description = String(record.description ?? record.details ?? "").trim();
  if (!title) fail(`Story ${index + 1} has no title.`);
  if (!description) fail(`Story ${index + 1} has no description.`);
  const rawType = String(record.type ?? record.issue_type ?? "story").trim().toLowerCase().replace(/\s+/g, "_");
  const rawCriteria = record.acceptance_criteria ?? record.criteria ?? [];
  const criteria = Array.isArray(rawCriteria) ? rawCriteria.map(String) : String(rawCriteria).split(/;|\n/);
  return {
    id: String(record.id ?? record.key ?? `ST-${index + 1}`).trim() || `ST-${index + 1}`,
    title,
    description,
    type: (TYPES.has(rawType) ? rawType : "story") as StoryInput["type"],
    acceptance_criteria: criteria.map((item) => item.trim()).filter(Boolean),
  };
}

function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    if (quoted) {
      if (char === '"' && text[i + 1] === '"') { cell += '"'; i++; }
      else if (char === '"') quoted = false;
      else cell += char;
    } else if (char === '"') quoted = true;
    else if (char === ",") { row.push(cell); cell = ""; }
    else if (char === "\n" || char === "\r") {
      if (char === "\r" && text[i + 1] === "\n") i++;
      row.push(cell); cell = "";
      if (row.some((value) => value.trim())) rows.push(row);
      row = [];
    } else cell += char;
  }
  row.push(cell);
  if (row.some((value) => value.trim())) rows.push(row);
  return rows;
}

function fromCsv(text: string): StoryInput[] {
  const [header, ...rows] = parseCsv(text);
  if (!header || !rows.length) fail("The CSV needs a header row and at least one story.");
  const keys = header.map((name) => name.trim().toLowerCase().replace(/\s+/g, "_"));
  if (!keys.includes("title")) fail("The CSV needs a title column.");
  return rows.map((row, index) => toStory(Object.fromEntries(keys.map((key, column) => [key, row[column] ?? ""])), index));
}

function fromText(text: string, fileName: string): StoryInput[] {
  const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  if (!lines.length) fail("The file is empty.");
  if (lines.every((line) => line.split("|").length >= 3)) {
    return lines.map((line, index) => {
      const [id, title, ...rest] = line.split("|");
      return toStory({ id, title, description: rest.join("|") }, index);
    });
  }
  const title = lines[0].replace(/^#+\s*/, "").replace(/^title:\s*/i, "");
  const description: string[] = [];
  const criteria: string[] = [];
  let inCriteria = false;
  for (const line of lines.slice(1)) {
    if (/^#*\s*acceptance criteria\s*:?$/i.test(line)) { inCriteria = true; continue; }
    if (/^#+\s/.test(line)) { inCriteria = false; continue; }
    const text = line.replace(/^([-*•]|\d+[.)])\s*/, "").replace(/^description:\s*/i, "");
    (inCriteria ? criteria : description).push(text);
  }
  const id = fileName.replace(/\.[^.]+$/, "").replace(/[^A-Za-z0-9_.-]+/g, "-").slice(0, 40) || "ST-1";
  return [toStory({ id, title, description: description.join(" ") || title, acceptance_criteria: criteria }, 0)];
}

export async function readAttachment(file: File): Promise<StoryInput[]> {
  if (file.size > 1_000_000) fail("That file is over 1 MB. Attach a smaller export.");
  const text = (await file.text()).replace(/^﻿/, "");
  const name = file.name.toLowerCase();
  let stories: StoryInput[];
  if (name.endsWith(".json")) {
    let parsed: unknown;
    try { parsed = JSON.parse(text); } catch { fail("The JSON couldn't be read. Check commas and quotes."); }
    const items = Array.isArray(parsed) ? parsed : (parsed as { stories?: unknown[] })?.stories ?? [parsed];
    stories = items.map(toStory);
  } else if (name.endsWith(".csv")) {
    stories = fromCsv(text);
  } else {
    stories = fromText(text, file.name);
  }
  if (!stories.length) fail("No stories found in that file.");
  const ids = new Set<string>();
  return stories.map((story, index) => {
    const id = ids.has(story.id) ? `${story.id}-${index + 1}` : story.id;
    ids.add(id);
    return { ...story, id };
  });
}
