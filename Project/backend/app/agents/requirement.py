"""Extract categorical requirements, with a deterministic keyword fallback."""

from __future__ import annotations

import re
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict

from app import llm
from app.contracts import Architecture, ChangeType, RequirementFacts, StoryInput


class _ExtractedFacts(BaseModel):
    """Provider-authored facts; provenance is supplied by the caller."""

    model_config = ConfigDict(extra="forbid")

    business_summary: str
    technical_summary: str
    business_domain: str
    affected_capabilities: list[str]
    affected_services: list[str]
    change_type: ChangeType
    touches_customer_data: bool
    touches_card_data: bool
    touches_financial_data: bool
    changes_auth_flow: bool
    changes_external_api_contract: bool
    changes_db_schema: bool
    ambiguity: Literal["low", "medium", "high"]
    engineering_scope: str


_AUTH_KEYWORDS = (
    "login", "biometric", "biometrics", "MFA", "step-up", "authentication", "OTP",
)
_CUSTOMER_KEYWORDS = (
    "profile", "profiles", "email", "emails", "PII", "personal data",
    "customer data", "preferred name",
)
_CARD_KEYWORDS = ("card", "cards", "cardholder", "PAN", "PCI DSS")
_FINANCIAL_KEYWORDS = (
    "payment", "payments", "transfer", "transfers", "transaction", "transactions",
    "financial data", "balance", "balances", "ledger", "loan", "loans",
)
_SERVICE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "payment-service": ("payment", "payments", "limit", "limits", "transfer", "transfers"),
    "card-service": ("card", "cards", "cardholder", "freeze", "unfreeze"),
    "authentication-service": _AUTH_KEYWORDS,
    "customer-service": _CUSTOMER_KEYWORDS,
    "customer-db": _CUSTOMER_KEYWORDS,
    "fraud-engine": ("fraud", "velocity"),
    "document-service": ("statement", "statements", "PDF", "PDFs", "document", "documents"),
    "mobile-banking": ("mobile app", "mobile banking", "mobile-banking"),
    "web-banking": ("web app", "web banking", "internet banking", "online banking"),
    "atm": ("ATM", "ATMs", "cash withdrawal", "cash withdrawals"),
    "branch-portal": ("branch portal",),
    "account-service": ("account", "accounts", "balance", "balances"),
    "loan-service": ("loan", "loans", "lending"),
    "notification-service": ("notification", "notifications", "SMS", "push notification"),
    "api-gateway": ("API gateway",),
    "transaction-db": ("transaction ledger", "ledger database"),
    "audit-db": ("audit database", "audit store"),
    "reporting-db": ("reporting database", "reporting store"),
    "risk-engine": ("risk engine", "credit risk"),
    "reporting-service": ("reporting service",),
    "crm": ("CRM",),
}


def _matches(text: str, keywords: tuple[str, ...]) -> bool:
    """Match whole words or phrases, allowing spaces and hyphens in names."""
    for keyword in keywords:
        pattern = r"[\s-]+".join(re.escape(part) for part in re.split(r"[\s-]+", keyword))
        if re.search(rf"\b{pattern}\b", text, flags=re.IGNORECASE):
            return True
    return False


def _change_type(text: str) -> ChangeType:
    if _matches(text, ("rule", "rules")):
        return "business_rule_change"
    if _matches(text, ("fix", "bug", "bugs")):
        return "bug_fix"
    if _matches(text, ("update text", "footer", "copy")):
        return "enhancement"
    if _matches(text, ("add", "new")):
        return "new_feature"
    return "enhancement"


def _fallback(story: StoryInput, arch: Architecture) -> RequirementFacts:
    text = "\n".join((story.title, story.description, *story.acceptance_criteria))
    def matching(source: str):
        return [
            component
            for component in arch.components
            if _matches(
                source,
                (component.id, component.name, *_SERVICE_KEYWORDS.get(component.id, ())),
            )
        ]

    # The title names what changes; the description also names what it merely
    # calls or reads. Use the full text only when the title names no service.
    matched = matching(story.title) or matching(text)
    service_ids = list(dict.fromkeys(component.id for component in matched))
    # Use only directly matched components, never their graph neighbours.
    data_classes = {data_class for component in matched for data_class in component.data_classes}
    domains = (
        ("fraud-engine", "Fraud prevention"),
        ("card-service", "Cards"),
        ("payment-service", "Payments"),
        ("customer-service", "Customer management"),
        ("authentication-service", "Identity and access"),
        ("document-service", "Statements and documents"),
        ("loan-service", "Lending"),
        ("account-service", "Accounts"),
    )
    domain = next((label for service_id, label in domains if service_id in service_ids), "Banking")
    capabilities = list(dict.fromkeys(component.name for component in matched if component.type != "database"))
    scope = ", ".join(service_ids) if service_ids else "services requiring clarification"
    change_type = _change_type(text)
    return RequirementFacts(
        business_summary=f"Requested banking change: {story.title}.",
        technical_summary=f"Apply the {change_type.replace('_', ' ')} to {scope} according to the supplied criteria.",
        business_domain=domain,
        affected_capabilities=capabilities,
        affected_services=service_ids,
        change_type=change_type,
        touches_customer_data="pii" in data_classes or _matches(text, _CUSTOMER_KEYWORDS),
        touches_card_data="card" in data_classes or _matches(text, _CARD_KEYWORDS),
        touches_financial_data="financial" in data_classes or _matches(text, _FINANCIAL_KEYWORDS),
        changes_auth_flow=_matches(text, _AUTH_KEYWORDS),
        changes_external_api_contract=(
            _matches(text, ("endpoint", "endpoints", "API", "APIs", "contract", "contracts"))
            or ("api-gateway" in service_ids and any(component.type == "channel" for component in matched))
        ),
        changes_db_schema=_matches(text, ("column", "columns", "field", "fields", "schema", "migration", "migrations")),
        ambiguity="high" if len(story.description.split()) < 20 or not story.acceptance_criteria else "low",
        engineering_scope=f"Implement {story.title} across {scope}; verify {len(story.acceptance_criteria)} acceptance criteria.",
        source="keyword-fallback",
    )


async def analyze_requirement(story: StoryInput, arch: Architecture) -> RequirementFacts:
    """Ask for facts only and restrict service IDs to the supplied architecture."""
    catalog = "\n".join(
        f"{component.id}: {component.name} — {component.description}"
        for component in arch.components
    )
    system = (
        "You are a banking solutions analyst. Extract facts only; never estimate risk.\n"
        "Return the requested categorical facts and human-readable summaries only. "
        "Do not produce scores or release decisions. "
        "affected_services must use only catalog IDs; do not invent IDs or infer downstream dependencies.\n"
        "Be practical and keep the scope as small as the story really is:\n"
        "- affected_services: only services whose code, configuration or schema must change. "
        "Leave out services the change merely calls, reads from or keeps using unchanged.\n"
        "- Set a data flag true only if the change alters how that data is stored, shown, shared "
        "or processed, not just because a listed service holds such data.\n"
        "- changes_auth_flow, changes_external_api_contract and changes_db_schema are true only "
        "when the story itself changes the login flow, a public API contract or a database schema.\n"
        "- A limit, threshold, rule, text or configuration change in one service is a small, "
        "contained change: say so in engineering_scope.\n"
        f"Allowed change_type values: {', '.join(get_args(ChangeType))}.\n"
        f"Component catalog (id: name — description):\n{catalog}"
    )
    criteria = "\n".join(f"- {criterion}" for criterion in story.acceptance_criteria) or "None supplied."
    user = f"Title: {story.title}\nDescription: {story.description}\nAcceptance criteria:\n{criteria}"
    try:
        extracted, provider = await llm.complete_structured(
            system, user, _ExtractedFacts, tier="fast", max_tokens=llm.MAX_TOKENS["requirement"],
        )
    except llm.NoLLM:
        return _fallback(story, arch)

    facts = _ExtractedFacts.model_validate(extracted.model_dump()).model_dump()
    catalog_ids = {component.id for component in arch.components}
    facts["affected_services"] = list(dict.fromkeys(
        service_id for service_id in facts["affected_services"] if service_id in catalog_ids
    ))
    return RequirementFacts(**facts, source=provider)
