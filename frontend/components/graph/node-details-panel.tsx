"use client";

import { useId } from "react";
import { X } from "lucide-react";
import type { Component, GraphNode } from "@/lib/types";
import { NodeIcon } from "./impact-nodes";
import styles from "./graph.module.css";
import { hopLabel } from "./graph-model";

export interface NodeDetailsPanelProps {
  node: GraphNode;
  component?: Component;
  factors: { dimension: string; label: string; points: number }[];
  onClose: () => void;
}

const dataLabels = { pii: "Personal data", card: "Card data", financial: "Financial data", audit: "Audit data" };

export function NodeDetailsPanel({ node, component, factors, onClose }: NodeDetailsPanelProps) {
  const titleId = useId();
  return (
    <aside className={styles.details} aria-labelledby={titleId}>
      <header className={styles.detailsHeader}>
        <NodeIcon node={node} size={20} aria-hidden="true" />
        <div><h2 id={titleId}>{node.label}</h2><p>{node.type.charAt(0).toUpperCase() + node.type.slice(1)} · {hopLabel(node.hop)}</p></div>
        <button type="button" className={styles.closeButton} onClick={onClose} aria-label="Close component details"><X size={18} /></button>
      </header>
      <div className={styles.detailsBody}>
        {component?.description && <p className={styles.description}>{component.description}</p>}
        <dl className={styles.metadata}>
          <div><dt>Owner</dt><dd>{node.owner_team || "Not recorded"}</dd></div>
          <div><dt>Criticality</dt><dd>{node.criticality}<span className={styles.muted}> / 10</span></dd></div>
          <div><dt>Impact</dt><dd className={styles.severityText} data-severity={node.hop === null ? "none" : node.severity}>{node.hop === null ? "None" : node.severity ? `${node.severity.charAt(0).toUpperCase()}${node.severity.slice(1)}` : "Not recorded"}</dd></div>
          <div><dt>Data classes</dt><dd>{node.data_classes.length ? node.data_classes.map((dataClass) => <span key={dataClass} className={styles.dataTag}>{dataLabels[dataClass]}</span>) : "None"}</dd></div>
        </dl>
        <section className={styles.detailsSection} aria-label="APIs">
          <h3>APIs <span>{component ? component.apis.length : ""}</span></h3>
          {!component ? <p className={styles.muted}>API details are unavailable for this component.</p> : !component.apis.length ? <p className={styles.muted}>No APIs recorded.</p> : (
            <ul className={styles.apiList}>{component.apis.map((api) => (
              <li key={api.id}><div className={styles.apiEndpoint}><span className={styles.method}>{api.method}</span><span>{api.path}</span></div><p>{api.description}</p><span className={styles.apiScope}>{api.external ? "External API" : "Internal API"}</span></li>
            ))}</ul>
          )}
        </section>
        <section className={styles.detailsSection} aria-label="Dependencies">
          <h3>Dependencies</h3>
          {!component ? <p className={styles.muted}>Dependency details are unavailable for this component.</p> : (
            <div className={styles.dependencies}>{(["upstream", "downstream"] as const).map((direction) => (
              <div key={direction}><h4>{direction === "upstream" ? "Upstream" : "Downstream"}<span>{component[direction].length}</span></h4>{component[direction].length ? <ul>{component[direction].map((id) => <li key={id}>{id}</li>)}</ul> : <p className={styles.muted}>None</p>}</div>
            ))}</div>
          )}
        </section>
        <section className={styles.detailsSection} aria-label="Risk factors citing this component">
          <h3>Risk factors <span>{factors.length}</span></h3>
          {factors.length ? <ul className={styles.factorList}>{factors.map((factor, index) => (
            <li key={`${factor.dimension}-${factor.label}-${index}`}><div><span>{factor.label}</span><span className={styles.points}>{factor.points >= 0 ? "+" : ""}{factor.points}</span></div><p>{factor.dimension.charAt(0).toUpperCase() + factor.dimension.slice(1)}</p></li>
          ))}</ul> : <p className={styles.muted}>No risk factors cite this component.</p>}
        </section>
      </div>
    </aside>
  );
}
