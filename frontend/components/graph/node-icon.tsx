import { ChartLine, Database, KeyRound, Monitor, Server, Shield, Smartphone, type LucideProps } from "lucide-react";
import type { GraphNode } from "@/lib/types";

export function NodeIcon({ node, ...props }: { node: Pick<GraphNode, "type" | "id" | "label"> } & LucideProps) {
  switch (node.type) {
    case "channel": return /mobile|atm/i.test(`${node.id} ${node.label}`) ? <Smartphone {...props} /> : <Monitor {...props} />;
    case "core": return <Server {...props} />;
    case "platform": return /auth|identity/i.test(`${node.id} ${node.label}`) ? <KeyRound {...props} /> : <Shield {...props} />;
    case "database": return <Database {...props} />;
    case "analytics": return <ChartLine {...props} />;
  }
}

/** Plain-language distance from the change. */
export function hopLabel(hop: number | null): string {
  if (hop === null) return "Not affected";
  if (hop === 0) return "Changed";
  return hop === 1 ? "1 step away" : `${hop} steps away`;
}

export const typeLabel: Record<GraphNode["type"], string> = {
  channel: "channel", core: "service", platform: "platform", database: "database", analytics: "analytics",
};
