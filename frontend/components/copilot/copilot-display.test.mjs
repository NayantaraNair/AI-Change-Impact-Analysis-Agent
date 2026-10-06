import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

// The repo has no frontend test runner. Use Node's runner and the installed TS compiler.
async function loadTypeScript(relativePath) {
  const source = await readFile(new URL(relativePath, import.meta.url), "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
  });
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);
}

const { answerContent, contextLabel, MISSING_SAMPLE_ANSWER } = await loadTypeScript("./copilot-display.ts");
const api = await loadTypeScript("../../lib/api.ts");
const request = {
  session_id: "test-session", context_type: "story", context_id: "ST-107",
  message: "What is impacted?",
};

test("missing starter fixtures give the required actionable sample message", async (t) => {
  const paths = [];
  t.mock.method(globalThis, "fetch", async (path) => {
    paths.push(path);
    return new Response("{}", { status: String(path).startsWith("/fixtures/") ? 404 : 503 });
  });
  const response = await api.chat(request);
  assert.equal(answerContent(response), MISSING_SAMPLE_ANSWER);
  assert.deepEqual(response.cited_nodes, []);
  assert.ok(paths.includes("/fixtures/chat-ST-107-0.json"));
});

test("prepared sample answers retain their markdown and graph citations", async (t) => {
  const prepared = {
    answer: "- Impacted: **mobile-banking**.", cited_nodes: ["mobile-banking"],
    cited_factors: [], provider: "sample-fixture",
  };
  t.mock.method(globalThis, "fetch", async (path) => String(path).startsWith("/fixtures/")
    ? Response.json(prepared) : new Response("{}", { status: 503 }));
  const response = await api.chat(request);
  assert.equal(answerContent(response), prepared.answer);
  assert.deepEqual(response.cited_nodes, prepared.cited_nodes);
});

test("open questions in sample mode remain actionable", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response("{}", { status: 503 }));
  const response = await api.chat({ ...request, message: "Who owns the deployment?" });
  assert.equal(answerContent(response), MISSING_SAMPLE_ANSWER);
});

test("live copilot answers are preserved even when they discuss sample limitations", () => {
  const answer = "No prepared answer is available, but the analysis records a release blocker.";
  assert.equal(answerContent({ answer, provider: "mock:live", cited_nodes: [], cited_factors: [] }), answer);
});

test("context labels describe the current story or sprint, including during page changes", () => {
  const sprint = { sprint_id: "sprint-42", name: "Sprint 42: Q4 payments & cards" };
  assert.equal(contextLabel({ type: "story", id: "ST-107" }, sprint), "ST-107");
  assert.equal(contextLabel({ type: "sprint", id: "sprint-42" }, sprint), "Sprint 42");
  assert.equal(contextLabel({ type: "sprint", id: "sprint-43" }, sprint), "Sprint 43");
  assert.equal(contextLabel({ type: "sprint", id: "sprint-42" }, null), "Sprint 42");
});
