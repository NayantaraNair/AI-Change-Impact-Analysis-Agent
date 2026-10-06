# Design spec

## Direction

The team's brief asked for **"Microsoft Fabric + Azure inspired, dark mode"**, so keep that. Within it, avoid the generic AI-dashboard look. Specifically, **do not use:**
- a grid of identical rounded KPI cards with the same soft shadow
- gradient washes used as decoration
- ALL-CAPS tracked-out labels above headings
- monospace fonts for small data labels
- `→` appended to buttons or links
- fade-and-slide-up animation on every section
- hover animation on every card
- near-black `#0B0B0B` / `#111` backgrounds
- accenting a single word in a heading with a different colour or italics
- `01 / 02 / 03` numbering on content that isn't a sequence

## The one memorable element: the blast-radius graph

- The services a story directly changes (hop 0) sit at the **centre**. Impacted nodes are arranged in **concentric rings by hop distance** (hop 1, hop 2, hop 3+). Unimpacted components sit in a faint outer ring at low opacity.
- Node fill and border colour encode **severity** (impact-low/med/high). Unimpacted nodes are `line`-coloured.
- **Edges on the impact path animate once**, a single flowing dash along the path for about 1.2 s when the analysis loads, then stay solid in severity colour. All other edges are thin, `line`-coloured and still.
- Node shape encodes **type**: channels are rounded pills, services rounded rectangles, databases cylinders (or a rectangle with a database icon), analytics hexagon-ish or with a chart icon. Each has a Lucide icon.
- Clicking a node opens the details panel (owner team, criticality, data classes, APIs, upstream and downstream, which risk factors cite it).
- Clicking a risk factor elsewhere on the page highlights its `node_ids` in the graph and dims everything else.

This is where the boldness goes. Everything else is quiet, dense and disciplined.

## Colour tokens (define them as CSS variables and wire them into Tailwind and the shadcn theme)

| Token | Hex | Use |
|---|---|---|
| `canvas` | `#131A23` | page background (slate blue, not near-black) |
| `surface` | `#1A2330` | panels, drawer, table header |
| `surface-raised` | `#212C3B` | popovers, selected rows |
| `line` | `#2B3646` | borders, unimpacted edges and nodes |
| `text` | `#E4EAF2` | primary text |
| `muted` | `#8B97A9` | secondary text |
| `azure` | `#3A96DD` | interactive elements only: buttons, links, focus ring, selection |
| `impact-low` | `#4FB3A9` | low risk / GO |
| `impact-med` | `#E2A74B` | medium risk / GO_WITH_CONDITIONS |
| `impact-high` | `#E5654E` | high risk / NO_GO |

**The impact colours always mean risk level and are never used for decoration.** Azure always means "you can interact with this". Charts use the impact scale for risk and azure or muted for everything else. Check contrast of text on these backgrounds (WCAG AA).

## Type

- **One family: Instrument Sans** (`next/font/google`), with `font-variant-numeric: tabular-nums` on every number.
- **Scale:** 12 (meta), 13 (table and dense UI), 15 (body), 18 (section titles), 24 (page titles), 40 (hero numbers in the stat strip).
- **Weights:** 400 for body, 500 for UI labels, 600 for titles and numbers.
- Sentence case everywhere. Labels sit next to their values, not as eyebrows above headings.
- **Scores are shown as large numbers in type,** coloured by level. Don't use gauges or donut charts for single scores.

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
│a │           BLAST-RADIUS GRAPH (hero)            │  collapsible) │
│i │                                                │               │
│l ├────────────────────────────────────────────────┤               │
│  │ Tabs: Risk | Tests | Compliance | Release |    │               │
│  │       Summary                                  │               │
└──┴────────────────────────────────────────────────┴───────────────┘
```

- The **stat strip** is a single row of number+label pairs separated by thin vertical rules. It is **not** a grid of cards.
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
           recommendation) + conflict graph (reuses the blast-radius
           component; conflict edges drawn in impact-high, dashed)
```

**Copilot drawer:** a message list, an input, and 5 starter questions as chips (section 10, T13). Answers render markdown and show cited nodes as small chips. Clicking a chip highlights the node in the graph if one is visible.

## Motion and quality

- **Exactly one orchestrated moment:** the impact-path animation when the graph loads. Elsewhere, motion only responds to the user (drawer open, tab switch, row expand), at 150–200 ms.
- **Respect `prefers-reduced-motion`:** no edge animation, instant transitions.
- Visible keyboard focus everywhere (a 2 px azure ring). All controls reachable by keyboard.
- Designed for desktop at ≥ 1280 px and usable down to 1024 px. Below that, the details panel stacks under the graph.
- **Empty states give direction:** "Paste a story and select Analyze to see its blast radius." **Errors say what happened and what to do:** "Couldn't reach the analysis server at :8000. Start the backend or set NEXT_PUBLIC_MOCK=1."
- **Copy:** plain verbs, sentence case, buttons say what they do ("Analyze story", "Analyze sprint", "Export report"), and the vocabulary stays consistent ("blast radius", "impact path", "factor").
