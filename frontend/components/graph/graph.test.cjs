/* eslint-disable @typescript-eslint/no-require-imports -- Dependency-free Node tests use CommonJS to transpile the TS/TSX modules in memory. */
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const ts = require("typescript");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const { ReactFlowProvider } = require("@xyflow/react");

// Use the installed TypeScript compiler and Node test runner; no test packages required.
const cache = new Map();
function loadSource(relativePath) {
  const filename = path.resolve(__dirname, relativePath);
  if (cache.has(filename)) return cache.get(filename);
  const output = ts.transpileModule(readFileSync(filename, "utf8"), {
    fileName: filename,
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020, esModuleInterop: true },
  }).outputText;
  const loaded = { exports: {} };
  cache.set(filename, loaded.exports);
  const localRequire = (id) => {
    if (id.endsWith(".css")) return new Proxy({}, { get: (_, key) => key === "__esModule" ? false : String(key) });
    if (id.startsWith(".")) {
      const base = path.resolve(path.dirname(filename), id);
      for (const extension of [".ts", ".tsx"]) {
        try { return loadSource(path.relative(__dirname, `${base}${extension}`)); }
        catch (error) { if (error.code !== "ENOENT") throw error; }
      }
    }
    return require(id);
  };
  new Function("require", "module", "exports", output)(localRequire, loaded, loaded.exports);
  return loaded.exports;
}

const { toFlowElements, searchNodes } = loadSource("graph-model.ts");
const { NodeDetailsPanel } = loadSource("node-details-panel.tsx");
const { impactNodeTypes } = loadSource("impact-nodes.tsx");
const fixture = JSON.parse(readFileSync(path.resolve(__dirname, "../../public/fixtures/story-ST-107.json"), "utf8"));
const defaults = { showUnimpacted: true, animate: true };
const cloneGraph = () => structuredClone(fixture.graph);

test("fixture conversion preserves every supplied position and does not mutate the analysis", () => {
  const graph = cloneGraph();
  const original = structuredClone(graph);
  const result = toFlowElements(graph, { ...defaults, selectedId: graph.nodes[0].id });
  assert.equal(result.nodes.length, graph.nodes.length);
  graph.nodes.forEach((node, index) => {
    assert.deepEqual(result.nodes[index].position, { x: node.x, y: node.y });
    assert.equal(result.nodes[index].type, node.type);
  });
  assert.equal(result.nodes[0].selected, true);
  assert.deepEqual(graph, original);
});

test("unimpacted visibility removes incident edges and keeps impacted nodes even without severity", () => {
  const graph = cloneGraph();
  graph.nodes[0].severity = null;
  const visible = toFlowElements(graph, defaults);
  const hidden = toFlowElements(graph, { ...defaults, showUnimpacted: false });
  for (const node of graph.nodes) {
    assert.equal(hidden.nodes.find((item) => item.id === node.id).hidden, node.hop === null);
    assert.equal(visible.nodes.find((item) => item.id === node.id).style.opacity, node.hop === null ? 0.35 : 1);
  }
  for (const edge of graph.edges) {
    const hasUnimpactedEndpoint = graph.nodes.some((node) => node.hop === null && [edge.source, edge.target].includes(node.id));
    assert.equal(hidden.edges.find((item) => item.id === edge.id).hidden, hasUnimpactedEndpoint);
  }
});

test("factor highlighting requires both endpoints to retain an edge's opacity", () => {
  const graph = cloneGraph();
  const edge = graph.edges.find((item) => graph.nodes.find((node) => node.id === item.source).hop !== null && graph.nodes.find((node) => node.id === item.target).hop !== null);
  const one = toFlowElements(graph, { ...defaults, highlight: [edge.source] });
  assert.equal(one.nodes.find((node) => node.id === edge.source).style.opacity, 1);
  assert.equal(one.nodes.find((node) => node.id === edge.target).style.opacity, 0.2);
  assert.equal(one.edges.find((item) => item.id === edge.id).style.opacity, 0.2);
  const both = toFlowElements(graph, { ...defaults, highlight: [edge.source, edge.target] });
  assert.equal(both.edges.find((item) => item.id === edge.id).style.opacity, 1);
  assert.equal(toFlowElements(graph, { ...defaults, highlight: [] }).edges.every((item) => item.style.opacity === 1), true);
});

test("impact paths use the target severity while ordinary edges use line colour", () => {
  const graph = cloneGraph();
  const pathEdge = graph.edges.find((edge) => edge.on_impact_path && !edge.conflict);
  graph.nodes.find((node) => node.id === pathEdge.target).severity = "high";
  const result = toFlowElements(graph, defaults);
  assert.equal(result.edges.find((edge) => edge.id === pathEdge.id).style.stroke, "var(--impact-high)");
  for (const edge of graph.edges.filter((item) => !item.on_impact_path && !item.conflict)) {
    assert.equal(result.edges.find((item) => item.id === edge.id).style.stroke, "var(--line)");
  }
});

test("conflicts override an impact path without duplicates or animation", () => {
  const graph = cloneGraph();
  const edge = graph.edges[0];
  const result = toFlowElements(graph, { ...defaults, conflictEdges: [edge] });
  const conflict = result.edges.find((item) => item.id === edge.id);
  assert.equal(result.edges.length, graph.edges.length);
  assert.equal(conflict.style.stroke, "var(--impact-high)");
  assert.equal(conflict.data.conflict, true);
  assert.equal(conflict.data.animate, false);
  graph.edges[0].conflict = true;
  assert.equal(toFlowElements(graph, defaults).edges[0].data.animate, false);
});

test("animation can end without changing severity or edge geometry", () => {
  const graph = cloneGraph();
  const result = toFlowElements(graph, { ...defaults, animate: false });
  assert.equal(result.edges.every((edge) => edge.data.animate === false), true);
  assert.deepEqual(result.edges.map((edge) => edge.style), toFlowElements(graph, defaults).edges.map((edge) => edge.style));
});

test("partial graphs skip missing endpoints and attach valid edges to facing handles", () => {
  const graph = cloneGraph();
  graph.edges.push({ id: "missing", source: graph.nodes[0].id, target: "not-in-this-graph", on_impact_path: true, conflict: false });
  const result = toFlowElements(graph, defaults);
  assert.equal(result.edges.some((edge) => edge.id === "missing"), false);
  for (const edge of result.edges) {
    const source = graph.nodes.find((node) => node.id === edge.source);
    const target = graph.nodes.find((node) => node.id === edge.target);
    const dx = target.x - source.x;
    const dy = target.y - source.y;
    const horizontal = Math.abs(dx) >= Math.abs(dy);
    assert.equal(edge.sourceHandle, `source-${horizontal ? dx >= 0 ? "right" : "left" : dy >= 0 ? "bottom" : "top"}`);
    assert.equal(edge.targetHandle, `target-${horizontal ? dx >= 0 ? "left" : "right" : dy >= 0 ? "top" : "bottom"}`);
  }
});

test("search filters names and ids, handles case and whitespace, and prioritises exact matches", () => {
  const nodes = [
    { id: "store", label: "Customer database" },
    { id: "profile", label: "Customer" },
    { id: "customer-service", label: "Profile service" },
  ];
  assert.deepEqual(searchNodes(nodes, "  CUSTOMER ").map((node) => node.id), ["profile", "store", "customer-service"]);
  assert.deepEqual(searchNodes(nodes, "customer-service").map((node) => node.id), ["customer-service"]);
  assert.deepEqual(searchNodes(nodes, ""), []);
  assert.deepEqual(searchNodes(nodes, "does not exist"), []);
});

test("details render supplied metadata, APIs, dependencies and cited factors safely", () => {
  const node = fixture.graph.nodes[0];
  const component = {
    apis: [{ id: "preference", method: "PATCH", path: "/customers/{id}/preferences", description: "Update preferences", external: true }],
    upstream: ["api-gateway"], downstream: ["customer-db"], description: "Preference service",
  };
  const html = renderToStaticMarkup(React.createElement(NodeDetailsPanel, {
    node, component, factors: [{ dimension: "security", label: "Customer <data>", points: 25 }], onClose() {},
  }));
  for (const text of [node.owner_team, `${node.criticality}`, "Personal data", "PATCH", "/customers/{id}/preferences", "api-gateway", "customer-db", "Customer &lt;data&gt;", "+25", "Security", "Close component details"]) assert.ok(html.includes(text), text);
  assert.equal(html.includes("API details are unavailable"), false);
});

test("details distinguish missing architecture metadata from empty recorded lists", () => {
  const props = { node: fixture.graph.nodes[0], factors: [], onClose() {} };
  const missing = renderToStaticMarkup(React.createElement(NodeDetailsPanel, props));
  assert.ok(missing.includes("API details are unavailable"));
  assert.ok(missing.includes("Dependency details are unavailable"));
  assert.ok(missing.includes("No risk factors cite this component"));
  const empty = renderToStaticMarkup(React.createElement(NodeDetailsPanel, { ...props, component: { apis: [], upstream: [], downstream: [] } }));
  assert.ok(empty.includes("No APIs recorded"));
  assert.equal(empty.includes("Dependency details are unavailable"), false);
});

test("all five fixture node types render accessible buttons and Lucide icons", () => {
  for (const type of ["channel", "core", "platform", "database", "analytics"]) {
    const node = fixture.graph.nodes.find((item) => item.type === type);
    assert.ok(node, `Fixture needs a ${type} node`);
    const html = renderToStaticMarkup(React.createElement(ReactFlowProvider, null,
      React.createElement(impactNodeTypes[type], { id: node.id, data: { node }, selected: true }),
    ));
    assert.ok(html.includes(`data-type="${type}"`));
    assert.ok(html.includes("aria-pressed=\"true\""));
    assert.ok(html.includes("View details"));
    assert.ok(html.includes("lucide"));
  }
});

test("preview metadata is an exact architecture snapshot for the matching fixture components", () => {
  const preview = JSON.parse(readFileSync(path.resolve(__dirname, "preview-components.json"), "utf8"));
  const architecture = JSON.parse(readFileSync(path.resolve(__dirname, "../../../data/architecture.json"), "utf8"));
  const expected = architecture.components.filter((component) => fixture.graph.nodes.some((node) => node.id === component.id));
  assert.deepEqual(preview, expected);
});
