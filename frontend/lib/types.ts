// Mirror of backend/app/contracts.py. Read-only: change only via the orchestrator.

export type ServiceId = string;
export type ComponentType = "channel" | "core" | "platform" | "database" | "analytics";
export type DataClass = "pii" | "card" | "financial" | "audit";
export type Severity = "low" | "medium" | "high";
export type ChangeType =
  | "new_feature"
  | "enhancement"
  | "bug_fix"
  | "config_change"
  | "business_rule_change"
  | "refactor"
  | "schema_change"
  | "integration_change";

// ---------------------------------------------------------------- architecture

export interface ApiEndpoint {
  id: string;
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  path: string;
  description: string;
  external: boolean;
}

export interface Component {
  id: ServiceId;
  name: string;
  type: ComponentType;
  description: string;
  owner_team: string;
  owner_contact: string;
  criticality: number;
  data_classes: DataClass[];
  apis: ApiEndpoint[];
  upstream: ServiceId[];
  downstream: ServiceId[];
  deployment_group: string;
  sla_tier: "tier1" | "tier2" | "tier3";
}

export interface Architecture {
  components: Component[];
}

// ---------------------------------------------------------------- story input

export interface StoryInput {
  id: string;
  title: string;
  description: string;
  type: "story" | "epic" | "change_request";
  acceptance_criteria: string[];
}

export interface DemoSprint {
  sprint_id: string;
  name: string;
  stories: StoryInput[];
}

// ---------------------------------------------------------------- requirement

export interface RequirementFacts {
  business_summary: string;
  technical_summary: string;
  business_domain: string;
  affected_capabilities: string[];
  affected_services: ServiceId[];
  change_type: ChangeType;
  touches_customer_data: boolean;
  touches_card_data: boolean;
  touches_financial_data: boolean;
  changes_auth_flow: boolean;
  changes_external_api_contract: boolean;
  changes_db_schema: boolean;
  ambiguity: "low" | "medium" | "high";
  engineering_scope: string;
  source: string;
}

// ---------------------------------------------------------------- graph

export interface GraphNode {
  id: ServiceId;
  label: string;
  type: ComponentType;
  hop: number | null;
  severity: Severity | null;
  x: number;
  y: number;
  criticality: number;
  owner_team: string;
  data_classes: DataClass[];
}

export interface GraphEdge {
  id: string;
  source: ServiceId;
  target: ServiceId;
  on_impact_path: boolean;
  conflict: boolean;
}

export interface ImpactGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  impacted_services: ServiceId[];
  impacted_databases: ServiceId[];
  impacted_apis: string[];
  downstream_systems: ServiceId[];
  deployment_groups: string[];
}

// ---------------------------------------------------------------- risk

export type RiskDimensionName =
  | "delivery"
  | "technical"
  | "security"
  | "operational"
  | "compliance"
  | "performance";

export interface RiskFactor {
  label: string;
  points: number;
  node_ids: ServiceId[];
}

export interface RiskDimension {
  name: RiskDimensionName;
  score: number;
  level: Severity;
  factors: RiskFactor[];
  explanation: string;
}

export interface RiskReport {
  dimensions: RiskDimension[];
  overall: number;
  highest: string;
}

// ---------------------------------------------------------------- tests

export interface TestCase {
  id: string;
  title: string;
  type: "functional" | "api" | "integration" | "regression" | "security";
  priority: "P1" | "P2" | "P3";
  covers: ServiceId[];
  steps: string[];
  expected: string;
  source: "catalog" | "generated";
  automation_candidate: boolean;
}

export interface TestPlan {
  tests: TestCase[];
  coverage_estimate: number;
  effort_hours: number;
  automation_candidates: number;
  summary: string;
}

// ---------------------------------------------------------------- compliance

export interface ComplianceFinding {
  text: string;
  node_ids: ServiceId[];
}

export interface FrameworkAssessment {
  framework: "GDPR" | "PCI DSS" | "SOX" | "Internal Governance";
  applicable: boolean;
  reason: string;
  risk_level: Severity | null;
  score: number | null;
  findings: ComplianceFinding[];
  recommendations: string[];
}

export interface ComplianceReport {
  frameworks: FrameworkAssessment[];
  overall_score: number;
  summary: string;
}

// ---------------------------------------------------------------- release

export type ReleaseDecision = "GO" | "GO_WITH_CONDITIONS" | "NO_GO";

export interface ReleaseAssessment {
  confidence: number;
  decision: ReleaseDecision;
  triggered_rules: string[];
  conditions: string[];
  complexity: "low" | "medium" | "high";
  rollback_plan: string[];
  deployment_notes: string[];
}

// ---------------------------------------------------------------- story analysis

export interface StoryAnalysis {
  story: StoryInput;
  requirement: RequirementFacts;
  graph: ImpactGraph;
  risk: RiskReport;
  tests: TestPlan;
  compliance: ComplianceReport;
  release: ReleaseAssessment;
  providers_used: Record<string, string>;
  duration_ms: number;
  created_at: string;
}

// ---------------------------------------------------------------- sprint

export interface Conflict {
  id: string;
  story_a: string;
  story_b: string;
  shared_component: ServiceId;
  kind:
    | "deployment_collision"
    | "schema_contention"
    | "parallel_modification"
    | "shared_api_change"
    | "shared_database";
  risk: Severity;
  risk_score: number;
  recommendation: string;
}

export interface SprintKpis {
  stories: number;
  applications_impacted: number;
  dependencies_impacted: number;
  conflicts: number;
  compliance_issues: number;
  testing_effort_hours: number;
  health_score: number;
  release_confidence: number;
  high_risk_stories: string[];
}

export interface SprintAnalysis {
  sprint_id: string;
  name: string;
  stories: StoryAnalysis[];
  conflicts: Conflict[];
  kpis: SprintKpis;
  conflict_graph: ImpactGraph;
  summary: string;
}

export interface SprintRequest {
  sprint_id?: string;
  name?: string;
  stories?: StoryInput[];
}

// ---------------------------------------------------------------- chat

export interface ChatRequest {
  session_id: string;
  message: string;
  context_type: "story" | "sprint";
  context_id: string;
}

export interface ChatResponse {
  answer: string;
  cited_nodes: ServiceId[];
  cited_factors: string[];
  provider: string;
}
