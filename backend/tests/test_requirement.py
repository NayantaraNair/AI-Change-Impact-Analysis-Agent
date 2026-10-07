"""Requirement extraction tests use real demo data or mocked providers only."""

from typing import get_args

import pytest
from pydantic import ValidationError

from app import llm
from app.agents.requirement import analyze_requirement
from app.architecture import get_architecture, load_demo_sprint
from app.contracts import Architecture, ChangeType, RequirementFacts, StoryInput


@pytest.fixture
def arch():
    return get_architecture()


def story(text: str, *, description: str | None = None, criteria: list[str] | None = None):
    return StoryInput(
        id="TEST-1",
        title=text,
        description=description if description is not None else text,
        acceptance_criteria=criteria if criteria is not None else ["The requested behavior is verified."],
    )


@pytest.mark.parametrize(
    ("story_id", "primary_services"),
    [
        ("ST-101", {"payment-service"}),
        ("ST-104", {"customer-service", "customer-db"}),
        ("ST-107", {"card-service", "authentication-service"}),
        ("ST-110", {"fraud-engine"}),
        ("ST-112", {"authentication-service", "mobile-banking"}),
        ("ST-115", {"document-service"}),
    ],
)
async def test_real_demo_fallback_primary_services(arch, story_id, primary_services):
    demo_story = next(item for item in load_demo_sprint().stories if item.id == story_id)

    facts = await analyze_requirement(demo_story, arch)

    assert primary_services <= set(facts.affected_services)
    assert set(facts.affected_services) <= {component.id for component in arch.components}
    assert len(facts.affected_services) == len(set(facts.affected_services))
    assert facts.source == "keyword-fallback"
    assert facts.ambiguity == "low"
    assert facts.business_summary and facts.technical_summary and facts.engineering_scope


async def test_statement_footer_has_no_unrelated_services_or_data_flags(arch):
    footer = next(item for item in load_demo_sprint().stories if item.id == "ST-115")

    facts = await analyze_requirement(footer, arch)

    assert set(facts.affected_services) == {"document-service", "reporting-service"}
    assert not facts.touches_customer_data
    assert not facts.touches_card_data
    assert not facts.touches_financial_data
    assert not facts.changes_auth_flow
    assert not facts.changes_external_api_contract
    assert not facts.changes_db_schema
    assert facts.change_type == "enhancement"


@pytest.mark.parametrize(
    ("text", "services", "flag"),
    [
        ("Raise transfer limits", {"payment-service"}, "touches_financial_data"),
        ("FREEZE controls", {"card-service"}, "touches_card_data"),
        ("Change MFA verification", {"authentication-service"}, "changes_auth_flow"),
        ("Change STEP UP verification", {"authentication-service"}, "changes_auth_flow"),
        ("Change OTP verification", {"authentication-service"}, "changes_auth_flow"),
        ("Add an EMAIL to the profile", {"customer-service", "customer-db"}, "touches_customer_data"),
        ("Revise velocity checks", {"fraud-engine"}, "touches_card_data"),
        ("Add a preferred name field", {"customer-service", "customer-db"}, "changes_db_schema"),
    ],
)
async def test_case_insensitive_synonyms_and_flags(arch, text, services, flag):
    facts = await analyze_requirement(story(text), arch)

    assert services <= set(facts.affected_services)
    assert getattr(facts, flag)


async def test_keywords_use_word_boundaries(arch):
    facts = await analyze_requirement(story("Refresh discarded semifinal lim itinerary profiled panels"), arch)

    assert facts.affected_services == []
    assert not facts.touches_customer_data
    assert not facts.touches_card_data
    assert not facts.touches_financial_data
    assert not facts.changes_auth_flow


async def test_matches_names_and_ids_from_supplied_catalog(arch):
    custom = arch.components[0].model_copy(update={
        "id": "custom-service", "name": "Settlement Hub", "data_classes": ["financial"],
    })
    supplied_arch = Architecture(components=[custom])

    for text in ("Update Settlement Hub", "Update CUSTOM-SERVICE"):
        facts = await analyze_requirement(story(text), supplied_arch)
        assert facts.affected_services == ["custom-service"]
        assert facts.touches_financial_data

    facts = await analyze_requirement(story("Add payment controls"), supplied_arch)
    assert facts.affected_services == []


@pytest.mark.parametrize(
    ("service_id", "flag"),
    [
        ("customer-db", "touches_customer_data"),
        ("reporting-db", "touches_financial_data"),
        ("card-service", "touches_card_data"),
    ],
)
async def test_data_classes_from_directly_matched_services(arch, service_id, flag):
    component = next(item for item in arch.components if item.id == service_id)
    custom = component.model_copy(update={"id": "custom-store", "name": "Custom Store"})

    facts = await analyze_requirement(story("Update custom-store"), Architecture(components=[custom]))

    assert getattr(facts, flag)
    assert facts.affected_services == ["custom-store"]


@pytest.mark.parametrize("text", ["Revise API", "Revise endpoint", "Revise contract", "Mobile app and gateway policies"])
async def test_external_contract_keywords_and_channel_gateway(arch, text):
    if text == "Mobile app and gateway policies":
        gateway = next(item for item in arch.components if item.id == "api-gateway")
        arch = Architecture(components=[
            gateway.model_copy(update={"name": "Gateway Policies"}),
            next(item for item in arch.components if item.id == "mobile-banking"),
        ])

    facts = await analyze_requirement(story(text), arch)

    assert facts.changes_external_api_contract


@pytest.mark.parametrize("text", ["Add a column", "Add a field", "Perform schema migration"])
async def test_database_schema_keywords(arch, text):
    assert (await analyze_requirement(story(text), arch)).changes_db_schema


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Add new fraud rule", "business_rule_change"),
        ("Add preferred name", "new_feature"),
        ("New mobile control", "new_feature"),
        ("Fix rendering bug", "bug_fix"),
        ("Update text", "enhancement"),
        ("Update footer for newly rendered documents", "enhancement"),
        ("Change copy", "enhancement"),
        ("Revise display", "enhancement"),
    ],
)
async def test_deterministic_change_type(arch, text, expected):
    assert (await analyze_requirement(story(text), arch)).change_type == expected


@pytest.mark.parametrize(
    ("word_count", "criteria", "expected"),
    [(19, ["Verified"], "high"), (20, [], "high"), (20, ["Verified"], "low")],
)
async def test_ambiguity_description_boundary_and_missing_criteria(arch, word_count, criteria, expected):
    item = story("Update display", description=" ".join(["word"] * word_count), criteria=criteria)

    assert (await analyze_requirement(item, arch)).ambiguity == expected


async def test_nollm_provider_failure_uses_fallback(monkeypatch, arch):
    async def unavailable(*args, **kwargs):
        raise llm.NoLLM("Mocked provider exhaustion")

    monkeypatch.setattr(llm, "complete_structured", unavailable)

    facts = await analyze_requirement(story("Freeze a card"), arch)

    assert facts.source == "keyword-fallback"
    assert "card-service" in facts.affected_services


def extracted_payload():
    return {
        "business_summary": "Increase payment allowance.",
        "technical_summary": "Update the existing payment rule.",
        "business_domain": "Payments",
        "affected_capabilities": ["Domestic payments"],
        "affected_services": ["payment-service", "unknown", "payment-service", "card-service"],
        "change_type": "business_rule_change",
        "touches_customer_data": False,
        "touches_card_data": False,
        "touches_financial_data": True,
        "changes_auth_flow": False,
        "changes_external_api_contract": False,
        "changes_db_schema": False,
        "ambiguity": "medium",
        "engineering_scope": "Update rule configuration.",
    }


async def test_mocked_llm_prompt_validation_filtering_and_provenance(monkeypatch, arch):
    item = story("Increase allowance", description="Apply an approved change.", criteria=["Check the allowance."])

    async def complete(system, user, schema, *, tier, max_tokens):
        assert system.startswith("You are a banking solutions analyst. Extract facts only; never estimate risk.")
        for component in arch.components:
            assert f"{component.id}: {component.name} — {component.description}" in system
        for value in get_args(ChangeType):
            assert value in system
        assert "affected_services must use only catalog IDs" in system
        assert item.title in user and item.description in user and item.acceptance_criteria[0] in user
        assert tier == "fast"
        assert set(schema.model_fields) == set(RequirementFacts.model_fields) - {"source"}
        return schema.model_validate(extracted_payload()), "mock-provider:model"

    monkeypatch.setattr(llm, "complete_structured", complete)

    facts = await analyze_requirement(item, arch)

    assert isinstance(facts, RequirementFacts)
    assert facts.affected_services == ["payment-service", "card-service"]
    assert facts.source == "mock-provider:model"
    assert facts.ambiguity == "medium"
    assert not facts.touches_card_data  # Preserve provider facts; no fallback keyword pass.


@pytest.mark.parametrize(
    "invalid",
    [{"change_type": "high_risk"}, {"ambiguity": "unknown"}, {"affected_services": "payment-service"}, {"risk_score": 99}],
)
async def test_llm_schema_rejects_invalid_categorical_output(monkeypatch, arch, invalid):
    async def complete(system, user, schema, **kwargs):
        return schema.model_validate(extracted_payload() | invalid), "mock-provider"

    monkeypatch.setattr(llm, "complete_structured", complete)

    with pytest.raises(ValidationError):
        await analyze_requirement(story("Update payment rule"), arch)
