"use client";

import { ViewportPortal } from "@xyflow/react";
import styles from "./graph.module.css";

export function HopRings({ showUnimpacted }: { showUnimpacted: boolean }) {
  return (
    <ViewportPortal>
      <svg className={styles.rings} width="1700" height="1700" viewBox="-850 -850 1700 1700" aria-hidden="true">
        {[1, 2, 3, ...(showUnimpacted ? [4] : [])].map((hop) => {
          const radius = 140 + hop * 170;
          return (
            <g key={hop}>
              <circle cx="0" cy="0" r={radius} />
              <text x="12" y={-radius + 20}>{hop === 4 ? "Unimpacted" : `Hop ${hop}${hop === 3 ? "+" : ""}`}</text>
            </g>
          );
        })}
      </svg>
    </ViewportPortal>
  );
}
