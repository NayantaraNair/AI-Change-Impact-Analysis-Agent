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
    # How far the change reaches, decided in code (engine/scope.py).
    change_size: Literal["small", "medium", "large"] = "medium"
    change_size_reason: str = ""


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


# ---------------------------------------------------------------- codebase impact

TestCategory = Literal["functional", "api", "integration", "unit", "regression", "security"]


class CodeFile(BaseModel):
    """What the indexer found in one source file (regex extraction, no execution)."""

    path: str  # relative to the analysed root, forward slashes
    service: str
    language: str
    classes: list[str] = []
    functions: list[str] = []
    apis: list[str] = []  # "POST /auth/login"
    tables: list[str] = []  # tables defined or used


class CodeService(BaseModel):
    name: str
    path: str
    languages: list[str]
    files: int
    classes: int
    apis: int
    tables: list[str]


class RepoIndex(BaseModel):
    repo_url: str
    ref: str
    root: str  # subfolder analysed, "" for the whole repository
    tree: list[str]  # every file path in the analysed root (capped)
    files: list[CodeFile]  # indexed source files
    services: list[CodeService]
    truncated: bool = False


class ImpactedFile(BaseModel):
    path: str
    service: str
    reason: str
    classes: list[str]
    apis: list[str]
    tables: list[str]


class ServiceImpact(BaseModel):
    service: str
    reason: str
    files: list[str]
    classes: list[str]
    apis: list[str]
    tables: list[str]


class DevTest(BaseModel):
    id: str
    title: str
    category: TestCategory
    target: str  # the class, API or table it exercises
    steps: list[str]
    expected: str


class CodebaseRequest(BaseModel):
    repo_url: str
    story: StoryInput


class CodebaseAnalysis(BaseModel):
    story: StoryInput
    repo: RepoIndex
    summary: str
    services: list[ServiceImpact]
    files: list[ImpactedFile]
    tests: list[DevTest]
    providers_used: dict[str, str]
    duration_ms: int
    created_at: datetime


# ---------------------------------------------------------------- runs (live progress)

RunKind = Literal["story", "sprint", "chat", "codebase"]
RunStatus = Literal["running", "succeeded", "failed"]
StageStatus = Literal["pending", "running", "done", "failed"]
AttemptOutcome = Literal[
    "running",  # the call is still in flight
    "ok",
    "timeout",
    "rate_limited",  # 429 or 402: provider cools down for 60 s
    "http_error",
    "connection_error",
    "truncated",  # the model hit max_tokens before finishing its JSON
    "invalid_json",
    "schema_mismatch",
    "empty",
    "skipped",  # no key, or cooling down after a rate limit
]


class LlmAttempt(BaseModel):
    """One call to one provider; a stage may need several before one succeeds."""

    id: int
    story_id: str | None
    stage: str | None
    provider: str
    model: str
    tier: Literal["fast", "strong"]
    max_tokens: int
    timeout_s: float
    started_at: datetime
    elapsed_ms: int
    outcome: AttemptOutcome
    detail: str  # human-readable reason, e.g. "Timed out after 180 s"
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    reasoning_tokens: int | None = None


class StageProgress(BaseModel):
    story_id: str | None  # None for sprint-wide stages
    stage: str
    label: str
    status: StageStatus
    # "llm" (a model wrote it), "deterministic" (pure code), "cache", "fixture",
    # or "fallback" (template text because every model failed or none is configured)
    source: Literal["llm", "deterministic", "cache", "fixture", "fallback"] | None = None
    provider: str | None = None  # provider label when source is "llm"
    message: str = ""
    started_at: datetime | None = None
    elapsed_ms: int | None = None


class RunLogEntry(BaseModel):
    at: datetime
    level: Literal["info", "warning", "error"]
    story_id: str | None = None
    message: str


class Run(BaseModel):
    id: str
    kind: RunKind
    status: RunStatus
    title: str
    story_ids: list[str]
    started_at: datetime
    finished_at: datetime | None = None
    elapsed_ms: int
    stages: list[StageProgress]
    attempts: list[LlmAttempt]
    log: list[RunLogEntry]
    error: str | None = None
    story_result: StoryAnalysis | None = None
    sprint_result: SprintAnalysis | None = None
    codebase_result: CodebaseAnalysis | None = None


class RunStarted(BaseModel):
    run_id: str


class ProviderInfo(BaseModel):
    order: int
    name: str
    model: str
    host: str
    configured: bool
    tool_calling_only: bool
    cooling_down_s: int  # seconds left before a rate-limited provider is retried


class DebugInfo(BaseModel):
    llm_disabled: bool
    providers: list[ProviderInfo]
    strong_tier_model: str
    timeout_s: float
    max_concurrent_calls: int
    max_tokens: dict[str, int]  # stage -> output token cap
    cache_enabled: bool
    fixtures_available: list[str]
