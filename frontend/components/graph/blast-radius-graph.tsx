"use client";

import { useCallback, useEffect, useId, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { Controls, ReactFlow, ReactFlowProvider, useNodesInitialized, useReactFlow } from "@xyflow/react";
import { CircleDot, Search, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import type { GraphEdge, GraphNode, ImpactGraph } from "@/lib/types";
import { searchNodes, toFlowElements, type ImpactFlowEdge, type ImpactFlowNode } from "./graph-model";
import { impactNodeTypes } from "./impact-nodes";
import { impactEdgeTypes } from "./impact-edge";
import { HopRings } from "./hop-rings";
import "@xyflow/react/dist/style.css";
import styles from "./graph.module.css";

export interface BlastRadiusGraphProps {
  graph: ImpactGraph;
  highlight?: string[];
  selectedId?: string | null;
  onNodeSelect?: (id: string | null) => void;
  height?: number | string;
  conflictEdges?: GraphEdge[];
}

const motionQuery = "(prefers-reduced-motion: reduce)";
function subscribeMotion(callback: () => void) {
  const query = window.matchMedia(motionQuery);
  query.addEventListener("change", callback);
  return () => query.removeEventListener("change", callback);
}
const getMotion = () => window.matchMedia(motionQuery).matches;
const getServerMotion = () => true;
const defaultFitOptions = { padding: 0.08, minZoom: 0.2, maxZoom: 1.15 };

function GraphCanvas({ graph, highlight, selectedId, onNodeSelect, conflictEdges }: BlastRadiusGraphProps) {
  const [showUnimpacted, setShowUnimpacted] = useState(true);
  const [query, setQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchIndex, setSearchIndex] = useState(0);
  const [internalSelection, setInternalSelection] = useState<string | null>(null);
  const [animate, setAnimate] = useState(true);
  const reducedMotion = useSyncExternalStore(subscribeMotion, getMotion, getServerMotion);
  const { fitView, setCenter } = useReactFlow<ImpactFlowNode, ImpactFlowEdge>();
  const initialized = useNodesInitialized();
  const pendingCenter = useRef<GraphNode | null>(null);
  const searchId = useId();
  const selection = selectedId === undefined ? internalSelection : selectedId;
  const select = useCallback((id: string | null) => {
    setInternalSelection(id);
    onNodeSelect?.(id);
  }, [onNodeSelect]);
  const { nodes, edges } = useMemo(() => toFlowElements(graph, {
    highlight, selectedId: selection, showUnimpacted, animate: animate && !reducedMotion, onSelect: select, conflictEdges,
  }), [graph, highlight, selection, showUnimpacted, animate, reducedMotion, select, conflictEdges]);
  const matches = useMemo(() => searchNodes(graph.nodes, query), [graph.nodes, query]);
  const activeIndex = Math.min(searchIndex, Math.max(matches.length - 1, 0));
  const fitOptions = useMemo(() => ({
    ...defaultFitOptions,
    nodes: graph.nodes.filter((node) => showUnimpacted || node.hop !== null).map(({ id }) => ({ id })),
  }), [graph.nodes, showUnimpacted]);

  useEffect(() => {
    const timer = window.setTimeout(() => setAnimate(false), 1200);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!initialized) return;
    const frame = requestAnimationFrame(() => {
      const target = pendingCenter.current;
      if (target) {
        pendingCenter.current = null;
        void setCenter(target.x, target.y, { zoom: 1.15, duration: reducedMotion ? 0 : 180 });
      } else {
        void fitView(fitOptions);
      }
    });
    return () => cancelAnimationFrame(frame);
  }, [initialized, fitOptions, fitView, setCenter, reducedMotion]);

  function focusNode(node: GraphNode) {
    if (node.hop === null && !showUnimpacted) {
      pendingCenter.current = node;
      setShowUnimpacted(true);
    } else {
      void setCenter(node.x, node.y, { zoom: 1.15, duration: reducedMotion ? 0 : 180 });
    }
    select(node.id);
    setSearchOpen(false);
  }

  return (
    <>
      <div className={styles.toolbar}>
        <div className={styles.search} onBlur={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget)) setSearchOpen(false);
        }}>
          <Search size={16} className={styles.searchIcon} aria-hidden="true" />
          <Input
            id={searchId}
            className={styles.searchInput}
            placeholder="Find a component"
            aria-label="Find a component by name"
            role="combobox"
            aria-autocomplete="list"
            aria-expanded={searchOpen && Boolean(query.trim())}
            aria-controls={`${searchId}-results`}
            aria-activedescendant={searchOpen && matches.length ? `${searchId}-match-${activeIndex}` : undefined}
            value={query}
            onFocus={() => setSearchOpen(true)}
            onChange={(event) => { setQuery(event.target.value); setSearchIndex(0); setSearchOpen(true); }}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                if (matches[activeIndex]) focusNode(matches[activeIndex]);
              } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                event.preventDefault();
                setSearchOpen(true);
                setSearchIndex((index) => Math.max(0, Math.min(matches.length - 1, index + (event.key === "ArrowDown" ? 1 : -1))));
              } else if (event.key === "Escape") {
                setSearchOpen(false);
              }
            }}
          />
          {query && <button type="button" className={styles.clearSearch} aria-label="Clear component search" onClick={() => { setQuery(""); setSearchIndex(0); }}><X size={14} /></button>}
          {searchOpen && query.trim() && (
            <ul id={`${searchId}-results`} role="listbox" aria-label="Matching components" className={styles.searchResults}>
              {matches.length ? matches.map((node, index) => (
                <li
                  key={node.id}
                  id={`${searchId}-match-${index}`}
                  role="option"
                  aria-selected={index === activeIndex}
                  className={index === activeIndex ? styles.activeResult : undefined}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => focusNode(node)}
                >
                  <span>{node.label}</span><span className={styles.resultMeta}>{node.hop === null ? "Unimpacted" : `Hop ${node.hop}`}</span>
                </li>
              )) : <li role="presentation" className={styles.noResults}>No components match. Try another name.</li>}
            </ul>
          )}
        </div>
        <label className={styles.toggle}>
          <input type="checkbox" checked={showUnimpacted} onChange={(event) => {
            setShowUnimpacted(event.target.checked);
            if (!event.target.checked && graph.nodes.some((node) => node.id === selection && node.hop === null)) select(null);
          }} />
          Show unimpacted
        </label>
      </div>
      <div className={styles.flowArea}>
        {graph.nodes.length ? (
          <ReactFlow<ImpactFlowNode, ImpactFlowEdge>
            nodes={nodes}
            edges={edges}
            nodeTypes={impactNodeTypes}
            edgeTypes={impactEdgeTypes}
            nodeOrigin={[0.5, 0.5]}
            nodesDraggable={false}
            nodesConnectable={false}
            nodesFocusable={false}
            edgesFocusable={false}
            edgesReconnectable={false}
            elementsSelectable={false}
            deleteKeyCode={null}
            onPaneClick={() => select(null)}
            fitView
            fitViewOptions={fitOptions}
            minZoom={0.2}
            maxZoom={2}
            colorMode="dark"
            proOptions={{ hideAttribution: true }}
            aria-label="Blast radius dependency graph"
          >
            <HopRings nodes={graph.nodes} showUnimpacted={showUnimpacted} />
            <Controls showInteractive={false} position="bottom-left" fitViewOptions={fitOptions} />
          </ReactFlow>
        ) : <p className={styles.emptyState}>Paste a story and select Analyze to see its blast radius.</p>}
      </div>
      <div className={styles.legend} aria-label="Graph legend">
        <span>Severity</span>
        <span><i className={styles.lowSwatch} />Low</span>
        <span><i className={styles.mediumSwatch} />Medium</span>
        <span><i className={styles.highSwatch} />High</span>
        <span className={styles.ringLegend}><CircleDot size={14} aria-hidden="true" />Hop rings</span>
        <span className={styles.legendHint}>Select a component for details</span>
      </div>
    </>
  );
}

export function BlastRadiusGraph(props: BlastRadiusGraphProps) {
  // A new analysis restarts the single load animation and fits its supplied positions.
  // Selection, search, highlights and visibility do not remount the graph.
  const graphKey = JSON.stringify([props.graph.nodes, props.graph.edges, props.conflictEdges]);
  return (
    <section className={styles.graph} style={{ height: props.height ?? "clamp(560px, 68vh, 760px)" }} aria-label="Blast radius">
      <ReactFlowProvider key={graphKey}><GraphCanvas {...props} /></ReactFlowProvider>
    </section>
  );
}
