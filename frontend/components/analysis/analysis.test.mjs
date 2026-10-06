import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

const folder = dirname(fileURLToPath(import.meta.url));
const frontend = resolve(folder, "../..");
const cache = new Map();

// Use the installed TypeScript compiler: no additional test runner or packages.
function load(file, overrides = {}, isolated = false) {
  const filename = resolve(folder, file);
  if (!isolated && cache.has(filename)) return cache.get(filename);
  const localRequire = createRequire(filename);
  const compiled = ts.transpileModule(readFileSync(filename, "utf8"), {
    fileName: filename,
    compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true },
  }).outputText;
  const loadedModule = { exports: {} };
  const sandbox = {
    module: loadedModule, exports: loadedModule.exports, process: { env: {} }, AbortSignal, fetch: globalThis.fetch,
    require(id) {
      if (id.startsWith("@/") || id.startsWith(".")) {
        const path = id.startsWith("@/") ? resolve(frontend, id.slice(2)) : resolve(dirname(filename), id);
        for (const extension of [".ts", ".tsx"]) if (existsSync(path + extension)) return load(path + extension);
      }
      return localRequire(id);
    },
    ...overrides,
  };
  runInNewContext(compiled, sandbox, { filename });
  if (!isolated) cache.set(filename, loadedModule.exports);
  return loadedModule.exports;
}

const model = load("model.ts");
const report = JSON.parse(readFileSync(resolve(frontend, "public/fixtures/story-ST-107.json"), "utf8"));
const plain = (value) => JSON.parse(JSON.stringify(value));

test("story form preserves input type and splits Windows acceptance criteria without empty lines", () => {
  const result = model.storyFromForm({ id: "  CR-9  ", title: "  Change limit  ", description: "  Details  ", type: "change_request", criteria: " First criterion \r\n\r\n Second criterion \r\n" }, "generated");
  assert.deepEqual(plain(result), { id: "CR-9", title: "Change limit", description: "Details", type: "change_request", acceptance_criteria: ["First criterion", "Second criterion"] });
  assert.equal(model.storyFromForm({ ...model.emptyStory, title: "New", description: "Change" }, "ST-new").id, "ST-new");
  assert.deepEqual(plain(model.storyFromForm(model.formFromStory(report.story), "unused")), report.story);
});

test("test filters combine priority and type while an empty filter means all", () => {
  const tests = [
    { id: "a", priority: "P1", type: "security" },
    { id: "b", priority: "P2", type: "integration" },
    { id: "c", priority: "P3", type: "security" },
  ];
  assert.equal(model.filterTests(tests, [], []).length, 3);
  assert.deepEqual(plain(model.filterTests(tests, ["P1", "P2"], ["security"])).map((t) => t.id), ["a"]);
  assert.equal(model.filterTests(tests, ["P2"], ["regression"]).length, 0);
});

test("node details include only cited factors with their original points and dimensions", () => {
  const factors = plain(model.factorsForNode(report.risk, "customer-db"));
  assert.deepEqual(factors.map((f) => f.dimension), ["technical", "security", "compliance", "performance"]);
  assert.equal(factors.find((f) => f.dimension === "security").points, 25);
  assert.deepEqual(plain(model.factorsForNode(report.risk, "analytics")), []);
});

test("leaving a factor restores the previous pin but preserves a newer Copilot highlight", () => {
  assert.deepEqual(plain(model.restoreHighlight(["card", "auth"], ["auth", "card"], ["payment"])), ["payment"]);
  assert.deepEqual(plain(model.restoreHighlight(["copilot-node"], ["card"], ["payment"])), ["copilot-node"]);
  assert.equal(model.factorWidth(25), "25%");
  assert.equal(model.factorWidth(130), "100%");
});

test("incomplete sample fixtures still offer all six canonical demo IDs, retaining API stories", () => {
  const { demoExamples } = load("examples.ts");
  const examples = plain(demoExamples([report.story]));
  assert.deepEqual(examples.map((story) => story.id), ["ST-101", "ST-104", "ST-107", "ST-110", "ST-112", "ST-115"]);
  assert.deepEqual(examples.find((story) => story.id === "ST-107"), report.story);
  assert.equal(demoExamples(examples), examples);
});

test("architecture uses the API base and returns component metadata", async () => {
  let requested;
  const components = [{ id: "card-service", owner_team: "Cards" }];
  const { fetchArchitecture } = load("architecture.ts", {
    process: { env: { NEXT_PUBLIC_API_URL: "http://localhost:8000/" } },
    fetch: async (url) => { requested = url; return { ok: true, json: async () => ({ components }) }; },
  }, true);
  assert.deepEqual(plain(await fetchArchitecture()), components);
  assert.equal(requested, "http://localhost:8000/architecture");
});

test("architecture failure, invalid data and mock mode do not prevent report rendering", async () => {
  for (const fetch of [async () => { throw new Error("offline"); }, async () => ({ ok: false }), async () => ({ ok: true, json: async () => ({}) })]) {
    const { fetchArchitecture } = load("architecture.ts", { fetch }, true);
    assert.deepEqual(plain(await fetchArchitecture()), []);
  }
  const { fetchArchitecture } = load("architecture.ts", {
    process: { env: { NEXT_PUBLIC_MOCK: "1" } }, fetch: () => assert.fail("mock mode must not fetch"),
  }, true);
  assert.deepEqual(plain(await fetchArchitecture()), []);
});

test("stat strip renders backend decisions and fractional coverage correctly", () => {
  const { StatStrip } = load("stat-strip.tsx");
  const html = renderToStaticMarkup(React.createElement(StatStrip, { analysis: report }));
  assert.match(html, /Go with conditions/);
  assert.match(html, /100%/);
  assert.match(html, /Technical/);
  assert.match(html, /text-impact-low/);
  assert.match(html, /Impacted services/);
});

test("risk bars are labelled buttons with raw contributions and an accessible six-dimension chart", () => {
  const { RiskTab } = load("risk-tab.tsx");
  const { AppProvider } = load("../shell/app-context.tsx");
  const html = renderToStaticMarkup(React.createElement(AppProvider, null, React.createElement(RiskTab, { risk: report.risk })));
  assert.match(html, /width:25%/);
  assert.match(html, /Security: \+25 Customer data/);
  assert.match(html, /role="img"/);
  assert.match(html, /Performance 10 out of 100/);
  assert.match(html, /aria-pressed="false"/);
  const baselineRisk = { ...report.risk, dimensions: [{ ...report.risk.dimensions[0], factors: [
    { label: "Baseline", points: 10, node_ids: [] },
    { label: "High ambiguity", points: 20, node_ids: [] },
  ] }] };
  const baselineHtml = renderToStaticMarkup(React.createElement(AppProvider, null, React.createElement(RiskTab, { risk: baselineRisk })));
  assert.match(baselineHtml, /bg-line text-text/);
  assert.match(baselineHtml, /bg-impact-low text-canvas/);
  assert.match(baselineHtml, /no cited nodes/);
});

test("pipeline stage names follow requirement, dependency, scoring, testing, compliance, release", () => {
  assert.deepEqual(plain(model.STAGES).map((stage) => stage.key), ["requirement", "dependency", "scoring", "testing", "compliance", "release"]);
});
