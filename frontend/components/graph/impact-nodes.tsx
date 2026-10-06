"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { ChartLine, Database, KeyRound, Monitor, Server, Shield, Smartphone, type LucideProps } from "lucide-react";
import type { GraphNode } from "@/lib/types";
import type { ImpactFlowNode } from "./graph-model";
import styles from "./graph.module.css";

export function NodeIcon({ node, ...props }: { node: Pick<GraphNode, "type" | "id" | "label"> } & LucideProps) {
  switch (node.type) {
    case "channel": return /mobile|atm/i.test(`${node.id} ${node.label}`) ? <Smartphone {...props} /> : <Monitor {...props} />;
    case "core": return <Server {...props} />;
    case "platform": return /auth|identity/i.test(`${node.id} ${node.label}`) ? <KeyRound {...props} /> : <Shield {...props} />;
    case "database": return <Database {...props} />;
    case "analytics": return <ChartLine {...props} />;
  }
}

function NodeFrame({ data, selected }: NodeProps<ImpactFlowNode>) {
  const { node, onSelect } = data;
  return (
    <div className={styles.nodeFrame}>
      {[Position.Top, Position.Right, Position.Bottom, Position.Left].map((position) => (
        <span key={position}>
          <Handle type="source" id={`source-${position}`} position={position} isConnectable={false} className={styles.handle} />
          <Handle type="target" id={`target-${position}`} position={position} isConnectable={false} className={styles.handle} />
        </span>
      ))}
      <button
        type="button"
        className={`nodrag nopan ${styles.node}`}
        data-type={node.type}
        data-severity={node.hop === null ? "none" : node.severity ?? "none"}
        data-direct={node.hop === 0}
        data-selected={selected}
        aria-pressed={Boolean(selected)}
        aria-label={`${node.label}, ${node.type}, ${node.hop === null ? "unimpacted" : node.hop === 0 ? "direct change" : `hop ${node.hop}`}${node.severity ? `, ${node.severity} impact` : ""}. View details`}
        title={node.label}
        onClick={() => onSelect?.(node.id)}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.stopPropagation();
            onSelect?.(null);
          }
        }}
      >
        <NodeIcon node={node} size={18} strokeWidth={1.6} className={styles.nodeIcon} aria-hidden="true" />
        <span className={styles.nodeText}>
          <span className={styles.nodeLabel}>{node.label}</span>
          <span className={styles.nodeMeta}>{node.hop === null ? "Unimpacted" : node.hop === 0 ? "Direct change" : `Hop ${node.hop}`}</span>
        </span>
      </button>
    </div>
  );
}

export function ChannelNode(props: NodeProps<ImpactFlowNode>) { return <NodeFrame {...props} />; }
export function CoreNode(props: NodeProps<ImpactFlowNode>) { return <NodeFrame {...props} />; }
export function PlatformNode(props: NodeProps<ImpactFlowNode>) { return <NodeFrame {...props} />; }
export function DatabaseNode(props: NodeProps<ImpactFlowNode>) { return <NodeFrame {...props} />; }
export function AnalyticsNode(props: NodeProps<ImpactFlowNode>) { return <NodeFrame {...props} />; }

export const impactNodeTypes = {
  channel: ChannelNode,
  core: CoreNode,
  platform: PlatformNode,
  database: DatabaseNode,
  analytics: AnalyticsNode,
};
