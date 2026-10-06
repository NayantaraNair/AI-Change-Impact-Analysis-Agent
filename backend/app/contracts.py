"""Shared data contracts. Read-only for every task except the orchestrator.

Mirrored in frontend/lib/types.ts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ServiceId = str
ComponentType = Literal["channel", "core", "platform", "database", "analytics"]
DataClass = Literal["pii", "card", "financial", "audit"]
Severity = Literal["low", "medium", "high"]
ChangeType = Literal[
    "new_feature",
    "enhancement",
    "bug_fix",
    "config_change",
    "business_rule_change",
    "refactor",
    "schema_change",
    "integration_change",
]


# ---------------------------------------------------------------- architecture


class ApiEndpoint(BaseModel):
    id: str
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str
    description: str
    external: bool = False


class Component(BaseModel):
    id: ServiceId
    name: str
    type: ComponentType
    description: str
    owner_team: str
    owner_contact: str
    criticality: int = Field(ge=1, le=10)
    data_classes: list[DataClass] = []
    apis: list[ApiEndpoint] = []
    upstream: list[ServiceId] = []  # things that call this component
    downstream: list[ServiceId] = []  # things this component calls or writes to
    deployment_group: str
    sla_tier: Literal["tier1", "tier2", "tier3"]


class Architecture(BaseModel):
    components: list[Component]


class CatalogTest(BaseModel):
    """One entry in data/test_catalog.json."""

    id: str
    title: str
    type: Literal["functional", "api", "integration", "regression", "security"]
    services: list[ServiceId]
    apis: list[str] = []
    automated: bool
    duration_min: int


# ---------------------------------------------------------------- story input


class StoryInput(BaseModel):
    id: str
    title: str
    description: str
    type: Literal["story", "epic", "change_request"] = "story"
    acceptance_criteria: list[str] = []


class DemoSprint(BaseModel):
    sprint_id: str
    name: str
    stories: list[StoryInput]


# ---------------------------------------------------------------- requirement


class RequirementFacts(BaseModel):
    business_summary: str
    technical_summary: str
    business_domain: str
    affected_capabilities: list[str]
    affected_services: list[ServiceId]  # only IDs from architecture.json
    change_type: ChangeType
    touches_customer_data: bool
    touches_card_data: bool
    touches_financial_data: bool
    changes_auth_flow: bool
    changes_external_api_contract: bool
    changes_db_schema: bool
    ambiguity: Literal["low", "medium", "high"]
    engineering_scope: str
    source: str  # provider label or "keyword-fallback"


# ---------------------------------------------------------------- graph


class GraphNode(BaseModel):
    id: ServiceId
    label: str
    type: ComponentType
    hop: int | None  # 0 = directly changed, None = not impacted
    severity: Severity | None
    x: float
    y: float
    criticality: int
    owner_team: str
    data_classes: list[DataClass]


class GraphEdge(BaseModel):
    id: str
    source: ServiceId
    target: ServiceId
    on_impact_path: bool
    conflict: bool = False  # set only on sprint conflict graphs


class ImpactGraph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    impacted_services: list[ServiceId]
    impacted_databases: list[ServiceId]
    impacted_apis: list[str]
    downstream_systems: list[ServiceId]
    deployment_groups: list[str]


# ---------------------------------------------------------------- risk


RiskDimensionName = Literal[
    "delivery", "technical", "security", "operational", "compliance", "performance"
]


class RiskFactor(BaseModel):
    label: str
    points: int
    node_ids: list[ServiceId]


class RiskDimension(BaseModel):
    name: RiskDimensionName
    score: int  # 0-100; equals the sum of factor points, clamped
    level: Severity  # low <40, medium 40-69, high >=70
    factors: list[RiskFactor]
    explanation: str


class RiskReport(BaseModel):
    dimensions: list[RiskDimension]
    overall: int
    highest: str  # name of the highest-scoring dimension


# ---------------------------------------------------------------- tests


class TestCase(BaseModel):
    __test__ = False  # not a pytest class

    id: str
    title: str
    type: Literal["functional", "api", "integration", "regression", "security"]
    priority: Literal["P1", "P2", "P3"]
    covers: list[ServiceId]
    steps: list[str]
    expected: str
    source: Literal["catalog", "generated"]
    automation_candidate: bool


class TestPlan(BaseModel):
    __test__ = False

    tests: list[TestCase]
    coverage_estimate: float  # 0-1
    effort_hours: float
    automation_candidates: int
    summary: str


# ---------------------------------------------------------------- compliance


class ComplianceFinding(BaseModel):
    text: str
    node_ids: list[ServiceId]


class FrameworkAssessment(BaseModel):
    framework: Literal["GDPR", "PCI DSS", "SOX", "Internal Governance"]
    applicable: bool
    reason: str
    risk_level: Severity | None
    score: int | None  # 0-100, higher = more compliant
    findings: list[ComplianceFinding]
    recommendations: list[str]


class ComplianceReport(BaseModel):
    frameworks: list[FrameworkAssessment]
    overall_score: int
    summary: str


# ---------------------------------------------------------------- release


class ReleaseAssessment(BaseModel):
    confidence: int  # 0-100
    decision: Literal["GO", "GO_WITH_CONDITIONS", "NO_GO"]
    triggered_rules: list[str]
    conditions: list[str]
    complexity: Literal["low", "medium", "high"]
    rollback_plan: list[str]
    deployment_notes: list[str]


# ---------------------------------------------------------------- story analysis


class StoryAnalysis(BaseModel):
    story: StoryInput
    requirement: RequirementFacts
    graph: ImpactGraph
    risk: RiskReport
    tests: TestPlan
    compliance: ComplianceReport
    release: ReleaseAssessment
    providers_used: dict[str, str]  # stage -> provider label
    duration_ms: int
    created_at: datetime


# ---------------------------------------------------------------- sprint


class Conflict(BaseModel):
    id: str
    story_a: str
    story_b: str
    shared_component: ServiceId
    kind: Literal[
        "deployment_collision",
        "schema_contention",
        "parallel_modification",
        "shared_api_change",
        "shared_database",
    ]
    risk: Severity
    risk_score: int
    recommendation: str


class SprintKpis(BaseModel):
    stories: int
    applications_impacted: int
    dependencies_impacted: int
    conflicts: int
    compliance_issues: int
    testing_effort_hours: float
    health_score: int
    release_confidence: int
    high_risk_stories: list[str]


class SprintAnalysis(BaseModel):
    sprint_id: str
    name: str
    stories: list[StoryAnalysis]
    conflicts: list[Conflict]
    kpis: SprintKpis
    conflict_graph: ImpactGraph  # union graph with conflict edges marked
    summary: str


class SprintRequest(BaseModel):
    sprint_id: str | None = None
    name: str | None = None
    stories: list[StoryInput] | None = None


# ---------------------------------------------------------------- chat


class ChatRequest(BaseModel):
    session_id: str
    message: str
    context_type: Literal["story", "sprint"]
    context_id: str


class ChatResponse(BaseModel):
    answer: str
    cited_nodes: list[ServiceId]
    cited_factors: list[str]
    provider: str
