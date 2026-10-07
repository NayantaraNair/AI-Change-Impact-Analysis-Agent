# Design spec

## Direction

**Simple first.** The audience is a manager planning a sprint. Every result opens with a short impact summary (one line per question: what changes, what it affects, teams, main risks, compliance, tests, release), then the dependency graph. Detail sits in tabs and folded sections. Copy is short and plain: one line per idea, no jargon ("steps away", not "hops"; "clash", not "conflict kind").


Dark graphite, modern and quiet, with one rule above all: **colour is evidence.**

- The risk scale (jade, saffron, coral) only ever means risk level.
- Violet only ever means "a language model wrote this, or is working on it now". It marks model provenance, live model activity and the copilot's citations, which puts the project's core idea ("the model reads; code scores") into the colour system.
- Chalk (near-white) marks everything you can act on: primary buttons, links, focus, selection. There is no blue anywhere.
- Everything else is graphite, so the chrome never competes with the evidence.

Avoid the generic AI-dashboard look. **Do not use:**
- a grid of identical rounded KPI cards with the same soft shadow (readouts are hairline-divided rows)
- gradient washes used as decoration
- ALL-CAPS tracked-out labels above headings
- monospace fonts for small data labels
- `→` appended to buttons or links
- fade-and-slide-up animation on every section
- hover animation on every card
- near-black `#0B0B0B` / `#111` backgrounds
- accenting a single word in a heading with a different colour or italics
- `01 / 02 / 03` numbering on content that isn't a sequence (pipeline steps are a sequence)

## The one memorable element: the dependency graph

**Current form (simple):** a left-to-right map. Changed components sit in the left column with a tinted fill and thick border; each column to the right is one step further away. Cards show the name and "type · criticality n/10", bordered by impact level. Straight links, a faint grid behind, and a three-item legend (changed, high/medium/low impact). Only affected components appear.

**Themes:** dark (default) and light, toggled in the header and remembered per browser. Both keep the same colour roles.

The notes below describe the earlier ring layout and are kept for reference.


- The services a story directly changes (hop 0) sit at the **centre**. Impacted nodes are arranged in **concentric rings by hop distance** (hop 1, hop 2, hop 3+). Unimpacted components sit in a faint outer ring at low opacity.
- Node fill and border colour encode **severity** (impact-low/med/high). Unimpacted nodes are `line`-coloured.
- **Edges on the impact path animate once**, a single flowing dash along the path for about 1.2 s when the analysis loads, then stay solid in severity colour. All other edges are thin, `line`-coloured and still.
- Node shape encodes **type**: channels are rounded pills, services rounded rectangles, databases cylinders (or a rectangle with a database icon), analytics hexagon-ish or with a chart icon. Each has a Lucide icon.
- Clicking a node opens the details panel (owner team, criticality, data classes, APIs, upstream and downstream, which risk factors cite it).
- Clicking a risk factor elsewhere on the page highlights its `node_ids` in the graph and dims everything else.

This is where the boldness goes. Everything else is quiet, dense and disciplined.

## Colour tokens (CSS variables in `frontend/app/globals.css`, wired into Tailwind and the shadcn theme)

| Token | Hex | Use |
|---|---|---|
| `canvas` | `#18171D` | page background (graphite) |
| `surface` | `#201F27` | panels, drawers, table headers |
| `surface-raised` | `#2A2933` | popovers, selected rows |
| `line` / `line-strong` | `#383645` / `#4A4859` | borders, unimpacted edges and nodes; hover borders |
| `text` | `#EEECF3` | primary text |
| `muted` | `#9E9AAD` | secondary text |
| `chalk` | `#F4F2F8` | interactive only: primary buttons, links (`link-ui`), focus ring, selection |
| `model` | `#B49BFF` | model provenance and live model activity only |
| `impact-low` | `#3CC4A3` | low risk / GO |
| `impact-med` | `#F2B544` | medium risk / GO_WITH_CONDITIONS (also `warn` for fallbacks) |
| `impact-high` | `#FF6A55` | high risk / NO_GO |

Check contrast of text on these backgrounds (WCAG AA).

## Type

- **One family: Mona Sans** (`next/font/google`, with its width axis), and `tabular-nums` on every number.
- **Width carries the personality:** scores and readouts use the `numeral` utility (75% width, bold), like instrument readouts; page titles are set at 112% width; body text is normal width.
- **Scale:** 12 (meta), 13 (table and dense UI), 15 (body), 18 (section titles), 24 (page titles), 48 (readout numerals).
- **Weights:** 400 for body, 500 for UI labels, 600 for titles, 700 for numerals.
- Sentence case everywhere. Labels sit next to their values, not as eyebrows above headings.
- **Scores are shown as large numerals,** coloured by level. Don't use gauges or donut charts for single scores.

## Layout

**App shell.** A 56 px **nav rail** on the left (Fluent style) with icons and tooltips: Story analysis, Sprint, and a Copilot toggle at the bottom. The main pane is left-aligned. The copilot is a 400 px right **drawer** that pushes or overlays the content.

**Story analysis page (`/story`):**

```
┌──┬────────────────────────────────────────────────┬───────────────┐
│  │ Story input (title, description, AC) [Analyze] │               │
│N │ ─────────────────────────────────────────────  │  Node or      │
│a │ Stat strip: Decision · Confidence · Highest    │  factor       │
│v │ risk · Impacted services · Coverage            │  details      │
│  ├────────────────────────────────────────────────┤  panel        │
│r │                                                │  (360 px,     │
│a │           DEPENDENCY GRAPH (hero)               │  collapsible) │
│i │                                                │               │
│l ├────────────────────────────────────────────────┤               │
│  │ Tabs: Risk | Tests | Compliance | Release |    │               │
│  │       Summary                                  │               │
└──┴────────────────────────────────────────────────┴───────────────┘
```

- The **stat strip** is a row of number+label readouts separated by hairline rules that wraps on narrow screens (the `readouts` utility). It is **not** a grid of cards.
- Every result shows **how it was produced** (model, code, cache, saved result or fallback) and every derived number has an info tooltip explaining the rule behind it.
- While an analysis runs, the **live progress** view replaces the results: each pipeline step, the model working on it against its timeout, and every fallback with its reason. A **debug slide-over** (nav rail and header) shows the full run.
- **Risk tab:** a Recharts radar chart of the 6 dimensions, plus, for each dimension, a horizontal **stacked factor-contribution bar** (each segment is one factor's points, labelled "+25 customer data"). Clicking a segment highlights its nodes in the graph. The explanation text sits under each bar.
- **Tests tab:** a dense table with columns priority badge, title, type, covers, source (catalog/generated), automation. Filter chips for P1/P2/P3 and for type. The coverage estimate and effort hours go at the top.
- **Compliance tab:** one row per framework, showing applicable or not, risk level, score, and expandable findings and recommendations.
- **Release tab:** the decision in large type, coloured by level; the triggered rules as a list; conditions; and the rollback plan and deployment notes as ordered lists (these really are sequences).
- **Summary tab:** business and technical summary, affected capabilities, and which provider produced each stage (small, muted).

**Sprint page (`/sprint`):**

```
Stat strip: Stories · Apps impacted · Dependencies · Conflicts ·
            Compliance issues · Test effort · Health score · Release confidence
──────────────────────────────────────────────────────────────────────
Left (60%): Story table (id, title, highest risk, decision badge,
            impacted count). Clicking a row opens that story's analysis.
Right (40%): Bar chart of risk by story (stacked by dimension or
             showing the highest)
──────────────────────────────────────────────────────────────────────
Conflicts: table (story A, story B, shared component, kind, risk,
           recommendation) + conflict graph (reuses the dependency
           component; conflict edges drawn in impact-high, dashed)
```

**Copilot drawer:** a message list, an input, and 5 starter questions as chips (section 10, T13). Answers render markdown and show cited nodes as small chips. Clicking a chip highlights the node in the graph if one is visible.

## Motion and quality

- **Exactly one orchestrated moment:** the impact-path animation when the graph loads. (Live progress indicators move because work is happening, not for decoration.) Elsewhere, motion only responds to the user (drawer open, tab switch, row expand), at 150–200 ms.
- **Respect `prefers-reduced-motion`:** no edge animation, instant transitions.
- Visible keyboard focus everywhere (a 2 px chalk ring). All controls reachable by keyboard.
- Designed for desktop at ≥ 1280 px and usable down to 1024 px. Below that, the details panel stacks under the graph.
- **Empty states give direction:** "Attach or paste a story, then select Analyze." **Errors say what happened and what to do:** "Couldn't reach the analysis server at :8000. Start the backend or set NEXT_PUBLIC_MOCK=1."
- **Copy:** plain verbs, sentence case, buttons say what they do ("Analyze story", "Analyze sprint", "Export report"), and the vocabulary stays consistent ("dependency graph", "impact summary", "clash").
