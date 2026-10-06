"use client";

import { BaseEdge, getBezierPath, type EdgeProps } from "@xyflow/react";
import type { ImpactFlowEdge } from "./graph-model";
import styles from "./graph.module.css";

export function ImpactEdge(props: EdgeProps<ImpactFlowEdge>) {
  const [path] = getBezierPath(props);
  const { data } = props;
  const className = data?.conflict ? styles.conflictEdge : data?.onImpactPath && data.animate ? styles.animatedEdge : undefined;
  return <BaseEdge id={props.id} path={path} markerEnd={props.markerEnd} style={props.style} className={className} interactionWidth={0} />;
}

export const impactEdgeTypes = { impact: ImpactEdge };
