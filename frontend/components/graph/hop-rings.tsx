"use client";

import { ViewportPortal } from "@xyflow/react";
import type { GraphNode } from "@/lib/types";
import { hopRings } from "./graph-model";
import styles from "./graph.module.css";

export function HopRings({ nodes, showUnimpacted }: { nodes: GraphNode[]; showUnimpacted: boolean }) {
  const rings = hopRings(nodes).filter(({ hop }) => showUnimpacted || hop !== null);
  const extent = Math.max(0, ...rings.map(({ radius }) => radius)) + 32;
  return (
    <ViewportPortal>
      <svg className={styles.rings} style={{ left: -extent, top: -extent }} width={extent * 2} height={extent * 2} viewBox={`${-extent} ${-extent} ${extent * 2} ${extent * 2}`} aria-hidden="true">
        {rings.map(({ hop, radius }) => (
          <circle key={hop ?? "unimpacted"} cx="0" cy="0" r={radius} />
        ))}
      </svg>
    </ViewportPortal>
  );
}
